"""Staff-only CRUD and actions for MCP servers."""
import asyncio
import logging

from django.db import IntegrityError
from django.utils.timezone import localtime
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from web.models.mcp import McpServer, McpTool
from web.mcp.client import (
    MCPConfigError,
    build_connection,
    list_server_tools,
    record_failure,
    sync_server_tools,
)

logger = logging.getLogger(__name__)

TRANSPORTS = dict(McpServer.Transport.choices)


def _fmt(value):
    return localtime(value).strftime('%Y-%m-%d %H:%M:%S') if value else ''


def serialize_server(server):
    # Secrets (env/headers) are never returned; the UI only sees whether they
    # are set, and sends new values only when replacing them.
    return {
        'id': server.id,
        'name': server.name,
        'transport': server.transport,
        'command': server.command,
        'args': server.args,
        'url': server.url,
        'has_env': bool(server.env),
        'has_headers': bool(server.headers),
        'enabled': server.enabled,
        'status': server.status,
        'failure_count': server.failure_count,
        'failure_threshold': server.failure_threshold,
        'circuit_open': server.circuit_open,
        'last_connected_at': _fmt(server.last_connected_at),
        'last_error': server.last_error,
        'tool_count': server.tools.count(),
        'created_at': _fmt(server.created_at),
        'updated_at': _fmt(server.updated_at),
    }


def validate_payload(data, partial=False):
    """Validate create/update payload. Returns (fields, error_message)."""
    fields = {}
    name = (data.get('name') or '').strip()
    if not partial or 'name' in data:
        if not name:
            return None, '名称不能为空'
        fields['name'] = name

    transport = data.get('transport')
    if transport is not None:
        if transport not in TRANSPORTS:
            return None, '不支持的传输方式'
        fields['transport'] = transport

    if 'command' in data:
        fields['command'] = (data.get('command') or '').strip()
    if 'url' in data:
        fields['url'] = (data.get('url') or '').strip()

    if 'args' in data:
        args = data.get('args') or []
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            return None, 'args 必须是字符串数组'
        fields['args'] = args

    if 'env' in data and isinstance(data.get('env'), dict):
        fields['env'] = {str(k): str(v) for k, v in data['env'].items()}
    if 'headers' in data and isinstance(data.get('headers'), dict):
        fields['headers'] = {str(k): str(v) for k, v in data['headers'].items()}

    if 'enabled' in data:
        fields['enabled'] = bool(data.get('enabled'))
    if 'failure_threshold' in data:
        try:
            fields['failure_threshold'] = max(1, int(data.get('failure_threshold')))
        except (TypeError, ValueError):
            return None, '熔断阈值必须是正整数'

    # Cross-field transport requirements, checked against merged values.
    return fields, None


def validate_connection_fields(server_or_transport, fields):
    """Validate command whitelist / url presence given merged configuration."""
    transport = fields.get('transport', getattr(server_or_transport, 'transport', None))
    if transport == McpServer.Transport.STDIO:
        command = fields.get('command', getattr(server_or_transport, 'command', ''))
        if not command:
            return 'stdio 服务需要填写 command'
        try:
            probe = type('S', (), {
                'transport': transport, 'command': command,
                'args': fields.get('args', getattr(server_or_transport, 'args', [])),
                'env': fields.get('env', getattr(server_or_transport, 'env', {})),
                'url': '', 'headers': {},
            })()
            build_connection(probe)
        except MCPConfigError as exc:
            return str(exc)
    elif transport in (McpServer.Transport.SSE,
                       McpServer.Transport.STREAMABLE_HTTP):
        url = fields.get('url', getattr(server_or_transport, 'url', ''))
        if not url:
            return '远程服务需要填写 URL'
    return None


class McpServerListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        servers = McpServer.objects.prefetch_related('tools').all()
        return Response({'result': 'success',
                         'servers': [serialize_server(s) for s in servers]})

    def post(self, request):
        fields, error = validate_payload(request.data)
        if error:
            return Response({'result': error}, status=400)
        transport = fields.get('transport')
        if transport not in TRANSPORTS:
            return Response({'result': '请选择传输方式'}, status=400)
        error = validate_connection_fields(transport, fields)
        if error:
            return Response({'result': error}, status=400)
        try:
            server = McpServer.objects.create(**fields)
        except IntegrityError:
            return Response({'result': '同名服务已存在'}, status=400)
        return Response({'result': 'success', 'server': serialize_server(server)})


class McpServerDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, server_id):
        server = McpServer.objects.filter(pk=server_id).first()
        if server is None:
            return Response({'result': '服务不存在'}, status=404)
        fields, error = validate_payload(request.data, partial=True)
        if error:
            return Response({'result': error}, status=400)
        error = validate_connection_fields(server, fields)
        if error:
            return Response({'result': error}, status=400)
        for key, value in fields.items():
            setattr(server, key, value)
        try:
            server.save()
        except IntegrityError:
            return Response({'result': '同名服务已存在'}, status=400)
        server.refresh_from_db()
        return Response({'result': 'success', 'server': serialize_server(server)})

    def delete(self, request, server_id):
        server = McpServer.objects.filter(pk=server_id).first()
        if server is None:
            return Response({'result': '服务不存在'}, status=404)
        server.delete()
        return Response({'result': 'success'})


class McpServerActionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, server_id, action):
        server = McpServer.objects.filter(pk=server_id).first()
        if server is None:
            return Response({'result': '服务不存在'}, status=404)

        if action == 'toggle':
            server.enabled = not server.enabled
            server.save(update_fields=['enabled'])
            server.refresh_from_db()
            return Response({'result': 'success',
                             'server': serialize_server(server)})

        if action == 'test_connection':
            try:
                tools = asyncio.run(list_server_tools(server))
            except Exception as exc:  # noqa: BLE001 - surface generic failure
                record_failure(server, exc)
                logger.warning('mcp_test_connection_failed server=%s error=%s',
                               server.name, type(exc).__name__)
                return Response(
                    {'result': '连接失败，请检查配置（服务地址、命令或网络）'},
                    status=502)
            return Response({
                'result': 'success',
                'tools': [{'name': t.name, 'description': t.description or ''}
                          for t in tools],
            })

        if action == 'refresh_tools':
            try:
                summary = asyncio.run(sync_server_tools(server))
            except Exception as exc:  # noqa: BLE001
                record_failure(server, exc)
                logger.warning('mcp_refresh_tools_failed server=%s error=%s',
                               server.name, type(exc).__name__)
                return Response(
                    {'result': '连接失败，无法同步工具'}, status=502)
            server.refresh_from_db()
            return Response({'result': 'success', 'summary': summary,
                             'server': serialize_server(server)})

        return Response({'result': '未知操作'}, status=400)
