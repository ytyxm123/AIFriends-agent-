from django.contrib import admin
from web.models.character import Character,Voice
from web.models.friend import Friend, Message, SystemPrompt
from web.models.user import UserProfile
from web.models.memory import MemoryFact, MemoryRevision, MemoryState
from web.models.mcp import McpServer, McpTool
from web.models.observability import Span, Trace

# Register your models here.

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    raw_id_fields = ('user',)


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    raw_id_fields = ('author','voice')

@admin.register(Friend)
class FriendAdmin(admin.ModelAdmin):
    raw_id_fields = ('me','character',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    raw_id_fields = ('friend',)

admin.site.register(SystemPrompt)

admin.site.register(Voice)


@admin.register(MemoryFact)
class MemoryFactAdmin(admin.ModelAdmin):
    list_display = ('id', 'friend', 'key', 'category', 'active', 'version', 'updated_at')
    list_filter = ('category', 'active')
    search_fields = ('key', 'content')
    raw_id_fields = ('friend', 'source_message')
    readonly_fields = tuple(field.name for field in MemoryFact._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MemoryState)
class MemoryStateAdmin(admin.ModelAdmin):
    list_display = ('friend', 'last_message_id', 'last_error', 'updated_at')
    readonly_fields = tuple(field.name for field in MemoryState._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MemoryRevision)
class MemoryRevisionAdmin(admin.ModelAdmin):
    list_display = ('fact', 'action', 'source_message', 'created_at')
    readonly_fields = tuple(field.name for field in MemoryRevision._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Trace)
class TraceAdmin(admin.ModelAdmin):
    list_display = ('id', 'trace_id', 'user', 'friend', 'status', 'model',
                    'duration_ms', 'total_tokens', 'cost', 'started_at')
    list_filter = ('status', 'model')
    search_fields = ('trace_id', 'input', 'output', 'user__user__username')
    raw_id_fields = ('user', 'friend')
    readonly_fields = tuple(field.name for field in Trace._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(Span)
class SpanAdmin(admin.ModelAdmin):
    list_display = ('id', 'trace', 'span_type', 'name', 'status',
                    'duration_ms', 'order')
    list_filter = ('span_type', 'status')
    search_fields = ('name', 'output', 'error')
    raw_id_fields = ('trace',)
    readonly_fields = tuple(field.name for field in Span._meta.fields)

    def has_add_permission(self, request):
        return False


@admin.register(McpServer)
class McpServerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'transport', 'enabled', 'status',
                    'failure_count', 'last_connected_at')
    list_filter = ('transport', 'enabled', 'status')
    search_fields = ('name', 'url', 'command')


@admin.register(McpTool)
class McpToolAdmin(admin.ModelAdmin):
    list_display = ('id', 'server', 'name', 'enabled', 'last_seen_at')
    list_filter = ('enabled', 'server')
    search_fields = ('name', 'description')
    raw_id_fields = ('server',)
