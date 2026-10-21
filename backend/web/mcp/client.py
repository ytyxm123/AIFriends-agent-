"""Runtime MCP client: discover servers, sync tools, and load LangChain tools.

Connection model (v1, request-scoped):
- Each chat request runs inside its own ``asyncio.run`` loop, so a long-lived
  MCP connection (bound to an event loop) cannot be shared across requests.
- On every graph build we connect to every enabled, non-tripped server, fetch
  its tools, and merge the enabled ones into the graph. ``MultiServerMCPClient``
  opens a fresh subprocess/session for each tool call and tears it down, so
  there is no persistent client to close.
- Per-server failures are isolated (``asyncio.gather`` + ``return_exceptions``
  semantics) and counted toward a circuit breaker; a tripped server is skipped
  until a health check resets it.

This is intentionally correct-first; a registry thread + dedicated loop
(connection pool) is the documented follow-up.
"""
import asyncio
import logging
import os

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils.timezone import now
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import create_session
from langchain_mcp_adapters.tools import load_mcp_tools

from web.models.mcp import McpServer, McpTool

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_COMMANDS = ['npx', 'uvx', 'python', 'python3']
DEFAULT_CONNECT_TIMEOUT = 8
DEFAULT_TOTAL_BUDGET = 15
DEFAULT_TOOL_TIMEOUT = 30


class MCPConfigError(Exception):
    """Raised when a server configuration is missing or unsafe."""


def connect_timeout():
    return int(getattr(settings, 'MCP_CONNECT_TIMEOUT', DEFAULT_CONNECT_TIMEOUT))


def total_budget():
    return int(getattr(settings, 'MCP_TOTAL_BUDGET', DEFAULT_TOTAL_BUDGET))


def tool_timeout():
    return int(getattr(settings, 'MCP_TOOL_TIMEOUT', DEFAULT_TOOL_TIMEOUT))


def allowed_commands():
    configured = getattr(settings, 'MCP_ALLOWED_COMMANDS', None)
    return [c for c in (configured or DEFAULT_ALLOWED_COMMANDS)]


def command_is_allowed(command):
    """Whitelist the stdio executable (basename, extension-insensitive).

    Windows ships ``npx.cmd`` / ``uvx.exe``; compare the file stem so both the
    bare name and platform-specific wrapper are accepted.
    """
    base = os.path.basename(command or '')
    stem = os.path.splitext(base)[0].lower()
    allowed = {os.path.splitext(os.path.basename(c))[0].lower()
               for c in allowed_commands()}
    return stem in allowed


def build_connection(server):
    """Translate a McpServer row into a langchain-mcp-adapters connection dict."""
    if server.transport == McpServer.Transport.STDIO:
        if not server.command:
            raise MCPConfigError('stdio 服务缺少 command')
        if not command_is_allowed(server.command):
            raise MCPConfigError(
                f'命令 {server.command!r} 不在允许列表中：{allowed_commands()}')
        connection = {
            'transport': 'stdio',
            'command': server.command,
            'args': list(server.args or []),
        }
        if server.env:
            connection['env'] = dict(server.env)
        return connection

    if server.transport in (McpServer.Transport.SSE,
                            McpServer.Transport.STREAMABLE_HTTP):
        if not server.url:
            raise MCPConfigError('远程服务缺少 URL')
        connection = {
            'transport': server.transport,
            'url': server.url,
            'timeout': connect_timeout(),
        }
        if server.headers:
            connection['headers'] = dict(server.headers)
        return connection

    raise MCPConfigError(f'不支持的传输方式：{server.transport}')


async def list_server_tools(server, timeout=None):
    """Connect once and return raw MCP ``Tool`` objects (name/schema)."""
    connection = build_connection(server)
    timeout = timeout if timeout is not None else connect_timeout()

    async def _connect():
        async with create_session(connection) as session:
            # create_session only opens the transport; the MCP initialize
            # handshake is required before any tools/list request.
            await session.initialize()
            result = await session.list_tools()
            return result.tools

    return await asyncio.wait_for(_connect(), timeout=timeout)


def record_success(server):
    server.status = McpServer.Status.HEALTHY
    server.failure_count = 0
    server.last_connected_at = now()
    server.last_error = ''
    server.save()


def record_failure(server, error):
    server.status = McpServer.Status.UNHEALTHY
    server.failure_count = min(server.failure_count + 1, 9999)
    server.last_error = f'{type(error).__name__}: {error}'[:300]
    server.save()
    logger.warning('mcp_server_failure server=%s count=%s error=%s',
                   server.name, server.failure_count, type(error).__name__)


async def sync_server_tools(server):
    """Connect, then upsert every advertised tool into the database."""
    raw_tools = await list_server_tools(server)

    def _persist():
        seen_ids = set()
        added = 0
        updated = 0
        for raw in raw_tools:
            schema = getattr(raw, 'inputSchema', None) or {}
            tool, created = McpTool.objects.update_or_create(
                server=server,
                name=raw.name,
                defaults={
                    'description': raw.description or '',
                    'input_schema': schema,
                    'last_seen_at': now(),
                },
            )
            seen_ids.add(tool.pk)
            if created:
                added += 1
            else:
                updated += 1
        # Tools no longer advertised are turned off, not deleted, so a
        # transient blip does not destroy operator state.
        McpTool.objects.filter(server=server).exclude(pk__in=seen_ids).update(
            enabled=False)
        return {'total': len(raw_tools), 'added': added, 'updated': updated}

    summary = await sync_to_async(_persist)()
    await sync_to_async(record_success)(server)
    return summary


def _with_tool_timeout(base_tool, seconds):
    """Add a hard execution timeout while preserving the tool's own schema.

    Rebuilding a StructuredTool from ``get_input_schema()`` breaks the MCP
    adapter's generated model (its fields carry aliases), so we instead copy
    the original tool and only swap the async callable.
    """
    original_coro = base_tool.coroutine
    if original_coro is None:
        return base_tool

    async def _timed_coro(**kwargs):
        return await asyncio.wait_for(original_coro(**kwargs), timeout=seconds)

    return base_tool.model_copy(update={'coroutine': _timed_coro})


async def _fetch_one_server(server, enabled_names):
    connection = build_connection(server)
    client = MultiServerMCPClient({server.name: connection})
    tools = await client.get_tools(server_name=server.name)
    kept = [t for t in tools if t.name in enabled_names]
    return kept


async def load_runtime_tools():
    """Return LangChain tools for every enabled, non-tripped server.

    Failures are isolated per server and feed the circuit breaker; this never
    raises for a bad server so a chat request still works with the rest.
    """
    def _load_servers():
        return [s for s in McpServer.objects.filter(enabled=True)
                if not s.circuit_open]

    servers = await sync_to_async(_load_servers)()
    if not servers:
        return []

    async def per_server(server):
        def _enabled_names():
            return set(
                McpTool.objects.filter(server=server, enabled=True)
                .values_list('name', flat=True))

        enabled_names = await sync_to_async(_enabled_names)()
        try:
            tools = await asyncio.wait_for(
                _fetch_one_server(server, enabled_names),
                timeout=connect_timeout())
            return server, tools, None
        except Exception as exc:  # noqa: BLE001 - isolate per server
            await sync_to_async(record_failure)(server, exc)
            return server, [], exc

    async def gather_all():
        return await asyncio.gather(
            *[per_server(server) for server in servers])

    try:
        results = await asyncio.wait_for(gather_all(), timeout=total_budget())
    except asyncio.TimeoutError:
        logger.error('mcp_total_budget_exceeded budget=%ss', total_budget())
        return []

    async def _mark_success(server):
        await sync_to_async(record_success)(server)

    all_tools = []
    seen_names = set()
    for server, tools, error in results:
        if error is None:
            # A successful handshake clears the breaker.
            await _mark_success(server)
        for tool in tools:
            if tool.name in seen_names:
                logger.warning('mcp_duplicate_tool_skipped name=%s', tool.name)
                continue
            seen_names.add(tool.name)
            all_tools.append(_with_tool_timeout(tool, tool_timeout()))
    return all_tools
