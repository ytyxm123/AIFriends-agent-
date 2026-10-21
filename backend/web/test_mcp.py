"""Tests for MCP server configuration, tool syncing, circuit breaker and APIs."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from rest_framework.test import APIClient

from web.models.mcp import McpServer, McpTool
from web.mcp.client import (
    MCPConfigError,
    build_connection,
    command_is_allowed,
    load_runtime_tools,
    record_failure,
    record_success,
    sync_server_tools,
)


class ConnectionConfigTests(SimpleTestCase):
    def test_command_whitelist_accepts_platform_wrappers(self):
        self.assertTrue(command_is_allowed('npx'))
        self.assertTrue(command_is_allowed('npx.cmd'))
        self.assertTrue(command_is_allowed('uvx.exe'))
        self.assertTrue(command_is_allowed('python'))
        self.assertFalse(command_is_allowed('rm'))
        self.assertFalse(command_is_allowed('/bin/bash'))
        self.assertFalse(command_is_allowed(''))

    def test_stdio_connection(self):
        server = SimpleNamespace(
            transport=McpServer.Transport.STDIO, command='npx',
            args=['-y', 'x'], env={'TOKEN': 't'}, url='', headers={})
        conn = build_connection(server)
        self.assertEqual(conn['transport'], 'stdio')
        self.assertEqual(conn['command'], 'npx')
        self.assertEqual(conn['args'], ['-y', 'x'])
        self.assertEqual(conn['env'], {'TOKEN': 't'})

    def test_stdio_rejects_non_whitelisted_command(self):
        server = SimpleNamespace(
            transport=McpServer.Transport.STDIO, command='rm',
            args=[], env={}, url='', headers={})
        with self.assertRaises(MCPConfigError):
            build_connection(server)

    def test_http_connection_requires_url(self):
        missing = SimpleNamespace(
            transport=McpServer.Transport.STREAMABLE_HTTP, command='',
            args=[], env={}, url='', headers={})
        with self.assertRaises(MCPConfigError):
            build_connection(missing)
        ok = SimpleNamespace(
            transport=McpServer.Transport.SSE, command='', args=[],
            env={}, url='http://127.0.0.1:9000/sse', headers={})
        self.assertEqual(build_connection(ok)['url'],
                         'http://127.0.0.1:9000/sse')


class CircuitBreakerTests(TestCase):
    def setUp(self):
        self.server = McpServer.objects.create(
            name='cb', transport=McpServer.Transport.STREAMABLE_HTTP,
            url='http://127.0.0.1:9000/mcp', failure_threshold=3)

    def test_breaker_opens_after_threshold(self):
        self.assertFalse(self.server.circuit_open)
        for _ in range(3):
            record_failure(self.server, RuntimeError('boom'))
            self.server.refresh_from_db()
        self.assertTrue(self.server.circuit_open)
        self.assertEqual(self.server.status, McpServer.Status.UNHEALTHY)
        self.assertIn('RuntimeError', self.server.last_error)

    def test_success_resets_counter(self):
        record_failure(self.server, RuntimeError('boom'))
        record_failure(self.server, RuntimeError('boom'))
        record_success(self.server)
        self.server.refresh_from_db()
        self.assertEqual(self.server.failure_count, 0)
        self.assertEqual(self.server.status, McpServer.Status.HEALTHY)
        self.assertIsNotNone(self.server.last_connected_at)


class SyncToolsTests(TransactionTestCase):
    def setUp(self):
        self.server = McpServer.objects.create(
            name='sync', transport=McpServer.Transport.STDIO,
            command='python', args=['server.py'])

    def test_sync_upserts_and_disables_missing(self):
        McpTool.objects.create(server=self.server, name='gone', enabled=True)
        raw = [
            SimpleNamespace(name='add', description='adds',
                            inputSchema={'type': 'object'}),
            SimpleNamespace(name='sub', description='subtracts',
                            inputSchema={'type': 'object'}),
        ]
        with patch('web.mcp.client.list_server_tools',
                   AsyncMock(return_value=raw)):
            summary = asyncio.run(sync_server_tools(self.server))
        self.assertEqual(summary['total'], 2)
        names = set(McpTool.objects.filter(server=self.server)
                    .values_list('name', flat=True))
        self.assertEqual(names, {'gone', 'add', 'sub'})
        # Tools that vanished from the server are disabled, not deleted.
        self.assertFalse(McpTool.objects.get(name='gone').enabled)
        add = McpTool.objects.get(name='add')
        self.assertEqual(add.description, 'adds')
        self.assertTrue(add.enabled)
        self.server.refresh_from_db()
        self.assertEqual(self.server.status, McpServer.Status.HEALTHY)


def _fake_tool(name, result='ok'):
    tool = SimpleNamespace(
        name=name,
        description=f'tool {name}',
        coroutine=AsyncMock(return_value=result),
    )

    def _model_copy(update=None):
        data = vars(tool).copy()
        if update:
            data.update(update)
        return SimpleNamespace(**data)

    tool.model_copy = _model_copy
    return tool


class RuntimeLoadTests(TransactionTestCase):
    def test_no_servers_returns_empty(self):
        self.assertEqual(asyncio.run(load_runtime_tools()), [])

    def test_loads_enabled_tools_and_skips_tripped(self):
        healthy = McpServer.objects.create(
            name='healthy', transport=McpServer.Transport.STDIO,
            command='python', args=['s.py'])
        McpTool.objects.create(server=healthy, name='on', enabled=True)
        McpTool.objects.create(server=healthy, name='off', enabled=False)
        tripped = McpServer.objects.create(
            name='tripped', transport=McpServer.Transport.STDIO,
            command='python', args=['s2.py'], failure_count=3)
        McpTool.objects.create(server=tripped, name='skipped', enabled=True)

        async def fake_fetch(server, enabled_names):
            return [_fake_tool(n) for n in enabled_names]

        with patch('web.mcp.client._fetch_one_server',
                   AsyncMock(side_effect=fake_fetch)):
            tools = asyncio.run(load_runtime_tools())
        self.assertEqual([t.name for t in tools], ['on'])

    def test_one_server_failure_is_isolated(self):
        good = McpServer.objects.create(
            name='good', transport=McpServer.Transport.STDIO,
            command='python', args=['g.py'])
        bad = McpServer.objects.create(
            name='bad', transport=McpServer.Transport.STDIO,
            command='python', args=['b.py'])
        McpTool.objects.create(server=good, name='good_tool')
        McpTool.objects.create(server=bad, name='bad_tool')

        async def fake_fetch(server, enabled_names):
            if server.name == 'bad':
                raise RuntimeError('connection refused')
            return [_fake_tool(n) for n in enabled_names]

        with patch('web.mcp.client._fetch_one_server',
                   AsyncMock(side_effect=fake_fetch)):
            tools = asyncio.run(load_runtime_tools())
        self.assertEqual([t.name for t in tools], ['good_tool'])
        bad.refresh_from_db()
        self.assertEqual(bad.failure_count, 1)
        good.refresh_from_db()
        self.assertEqual(good.status, McpServer.Status.HEALTHY)

    def test_duplicate_tool_names_are_deduplicated(self):
        a = McpServer.objects.create(
            name='dup-a', transport=McpServer.Transport.STDIO,
            command='python', args=['a.py'])
        b = McpServer.objects.create(
            name='dup-b', transport=McpServer.Transport.STDIO,
            command='python', args=['b.py'])
        McpTool.objects.create(server=a, name='same')
        McpTool.objects.create(server=b, name='same')

        async def fake_fetch(server, enabled_names):
            return [_fake_tool(n) for n in enabled_names]

        with patch('web.mcp.client._fetch_one_server',
                   AsyncMock(side_effect=fake_fetch)):
            tools = asyncio.run(load_runtime_tools())
        self.assertEqual([t.name for t in tools], ['same'])


class McpServerApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('mcp-boss', is_staff=True)
        self.staff_client = APIClient()
        self.staff_client.force_authenticate(self.staff)
        self.plain = User.objects.create_user('mcp-plain')
        self.plain_client = APIClient()
        self.plain_client.force_authenticate(self.plain)

    def test_permissions(self):
        self.assertEqual(self.plain_client.get('/api/mcp/servers/').status_code,
                         403)
        self.assertEqual(APIClient().get('/api/mcp/servers/').status_code, 401)

    def test_create_stdio_server(self):
        resp = self.staff_client.post('/api/mcp/servers/', {
            'name': 'math', 'transport': 'stdio',
            'command': 'uvx', 'args': ['math-mcp'],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        server = McpServer.objects.get(name='math')
        self.assertEqual(server.command, 'uvx')
        self.assertTrue(resp.json()['server']['has_env'] is False)

    def test_create_rejects_illegal_command(self):
        resp = self.staff_client.post('/api/mcp/servers/', {
            'name': 'evil', 'transport': 'stdio',
            'command': 'rm', 'args': ['-rf'],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(McpServer.objects.filter(name='evil').exists())

    def test_create_http_requires_url(self):
        resp = self.staff_client.post('/api/mcp/servers/', {
            'name': 'web', 'transport': 'streamable_http',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_name_rejected(self):
        McpServer.objects.create(
            name='dup', transport=McpServer.Transport.STDIO,
            command='python', args=['s.py'])
        resp = self.staff_client.post('/api/mcp/servers/', {
            'name': 'dup', 'transport': 'stdio',
            'command': 'python', 'args': ['s2.py'],
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_toggle_patch_delete(self):
        server = McpServer.objects.create(
            name='crud', transport=McpServer.Transport.STDIO,
            command='python', args=['s.py'])
        toggled = self.staff_client.post(
            f'/api/mcp/servers/{server.id}/toggle/')
        self.assertEqual(toggled.status_code, 200)
        server.refresh_from_db()
        self.assertFalse(server.enabled)

        patched = self.staff_client.patch(
            f'/api/mcp/servers/{server.id}/',
            {'failure_threshold': 5}, format='json')
        self.assertEqual(patched.status_code, 200)
        server.refresh_from_db()
        self.assertEqual(server.failure_threshold, 5)

        deleted = self.staff_client.delete(f'/api/mcp/servers/{server.id}/')
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(McpServer.objects.filter(id=server.id).exists())

    def test_refresh_tools_populates_db(self):
        server = McpServer.objects.create(
            name='refresh', transport=McpServer.Transport.STDIO,
            command='python', args=['s.py'])
        raw = [SimpleNamespace(name='ping', description='pings',
                               inputSchema={})]
        with patch('web.views.mcp.servers.sync_server_tools',
                   AsyncMock(return_value={'total': 1, 'added': 1,
                                           'updated': 0})):
            resp = self.staff_client.post(
                f'/api/mcp/servers/{server.id}/refresh_tools/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['summary']['total'], 1)

    def test_test_connection_failure_returns_generic_message(self):
        server = McpServer.objects.create(
            name='broke', transport=McpServer.Transport.STREAMABLE_HTTP,
            url='http://127.0.0.1:9/mcp')
        with patch('web.views.mcp.servers.list_server_tools',
                   AsyncMock(side_effect=ConnectionError('internal-host:9'))):
            resp = self.staff_client.post(
                f'/api/mcp/servers/{server.id}/test_connection/')
        self.assertEqual(resp.status_code, 502)
        self.assertNotIn('internal-host', resp.content.decode())
        server.refresh_from_db()
        self.assertEqual(server.failure_count, 1)


class McpToolApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('tool-boss', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.server = McpServer.objects.create(
            name='tool-srv', transport=McpServer.Transport.STDIO,
            command='python', args=['s.py'])
        self.tool = McpTool.objects.create(
            server=self.server, name='echo', description='echoes')

    def test_list_and_filter(self):
        resp = self.client.get('/api/mcp/tools/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['tools']), 1)
        filtered = self.client.get(f'/api/mcp/tools/?server_id={self.server.id}')
        self.assertEqual(len(filtered.json()['tools']), 1)

    def test_toggle(self):
        resp = self.client.post(f'/api/mcp/tools/{self.tool.id}/toggle/')
        self.assertEqual(resp.status_code, 200)
        self.tool.refresh_from_db()
        self.assertFalse(self.tool.enabled)

    def test_non_staff_forbidden(self):
        plain = User.objects.create_user('tool-plain')
        c = APIClient()
        c.force_authenticate(plain)
        self.assertEqual(c.get('/api/mcp/tools/').status_code, 403)
