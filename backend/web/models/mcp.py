"""MCP (Model Context Protocol) dynamic tool registration.

Servers are configured at runtime by staff; their tools are discovered by
connecting to the server and are enabled/disabled individually. The chat
graph loads enabled tools per request without code changes or restarts.
"""
from django.db import models
from django.utils.timezone import now


class McpServer(models.Model):
    class Transport(models.TextChoices):
        STDIO = 'stdio'
        SSE = 'sse'
        STREAMABLE_HTTP = 'streamable_http'

    class Status(models.TextChoices):
        UNKNOWN = 'unknown'
        HEALTHY = 'healthy'
        UNHEALTHY = 'unhealthy'

    name = models.CharField(max_length=100, unique=True)
    transport = models.CharField(max_length=20, choices=Transport.choices)
    # stdio
    command = models.CharField(max_length=255, default='', blank=True)
    args = models.JSONField(default=list, blank=True)
    # Secrets live here (tokens, api keys); never returned to the client.
    env = models.JSONField(default=dict, blank=True)
    # sse / streamable_http
    url = models.URLField(max_length=500, default='', blank=True)
    headers = models.JSONField(default=dict, blank=True)

    enabled = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.UNKNOWN)
    failure_count = models.PositiveIntegerField(default=0)
    failure_threshold = models.PositiveIntegerField(default=3)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, default='', blank=True)
    created_at = models.DateTimeField(default=now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    @property
    def circuit_open(self):
        """True when the server is tripped by the circuit breaker and skipped."""
        return self.failure_count >= self.failure_threshold

    def __str__(self):
        return f'{self.name} ({self.transport})'


class McpTool(models.Model):
    server = models.ForeignKey(McpServer, on_delete=models.CASCADE,
                               related_name='tools')
    name = models.CharField(max_length=150)
    description = models.TextField(default='', blank=True)
    input_schema = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(default=now)
    created_at = models.DateTimeField(default=now)

    class Meta:
        ordering = ['server__name', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['server', 'name'], name='mcp_tool_server_name_uniq'),
        ]

    def __str__(self):
        return f'{self.server.name}.{self.name}'
