"""Probe every enabled MCP server and update health/circuit-breaker state.

Schedule periodically (cron / task scheduler) to reset the breaker for servers
that have recovered and to keep status current without waiting for a chat.
"""
import asyncio

from django.core.management.base import BaseCommand

from web.models.mcp import McpServer
from web.mcp.client import list_server_tools, record_failure, record_success


class Command(BaseCommand):
    help = 'Probe enabled MCP servers and update health / circuit-breaker state.'

    async def check_one(self, server):
        try:
            await list_server_tools(server)
            record_success(server)
            return server.name, True, ''
        except Exception as exc:  # noqa: BLE001
            record_failure(server, exc)
            return server.name, False, f'{type(exc).__name__}: {exc}'

    async def run_all(self, servers):
        return await asyncio.gather(*[self.check_one(s) for s in servers])

    def handle(self, *args, **options):
        servers = list(McpServer.objects.filter(enabled=True))
        if not servers:
            self.stdout.write('No enabled MCP servers.')
            return
        for name, ok, error in asyncio.run(self.run_all(servers)):
            if ok:
                self.stdout.write(self.style.SUCCESS(f'[healthy]   {name}'))
            else:
                self.stdout.write(self.style.ERROR(f'[unhealthy] {name}: {error}'))
