"""Staff-only listing and enable/disable for MCP tools."""
from django.utils.timezone import localtime
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from web.models.mcp import McpTool


def _fmt(value):
    return localtime(value).strftime('%Y-%m-%d %H:%M:%S') if value else ''


def serialize_tool(tool):
    return {
        'id': tool.id,
        'server_id': tool.server_id,
        'server_name': tool.server.name,
        'name': tool.name,
        'description': tool.description,
        'input_schema': tool.input_schema,
        'enabled': tool.enabled,
        'last_seen_at': _fmt(tool.last_seen_at),
    }


class McpToolListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        tools = McpTool.objects.select_related('server').all()
        server_id = request.GET.get('server_id')
        if server_id:
            tools = tools.filter(server_id=server_id)
        return Response({'result': 'success',
                         'tools': [serialize_tool(t) for t in tools]})


class McpToolToggleView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, tool_id):
        tool = McpTool.objects.select_related('server').filter(pk=tool_id).first()
        if tool is None:
            return Response({'result': '工具不存在'}, status=404)
        tool.enabled = not tool.enabled
        tool.save(update_fields=['enabled'])
        tool.refresh_from_db()
        return Response({'result': 'success', 'tool': serialize_tool(tool)})
