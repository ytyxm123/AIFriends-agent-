"""Full-chain observability: one Trace per chat request and Spans per step."""
import uuid

from django.db import models
from django.utils.timezone import now

from web.models.friend import Friend
from web.models.user import UserProfile


class Trace(models.Model):
    class Status(models.TextChoices):
        RUNNING = 'running'
        SUCCESS = 'success'
        FAILED = 'failed'

    trace_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='traces')
    friend = models.ForeignKey(Friend, on_delete=models.CASCADE, related_name='traces')
    input = models.TextField(max_length=5000)
    output = models.TextField(default='', blank=True)
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.RUNNING, db_index=True)
    model = models.CharField(max_length=100, default='', blank=True)
    started_at = models.DateTimeField(default=now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    cost = models.FloatField(default=0.0)
    error = models.CharField(max_length=200, default='', blank=True)

    class Meta:
        ordering = ['-id']
        indexes = [
            models.Index(fields=['user', '-id'], name='trace_user_idx'),
            models.Index(fields=['friend', '-id'], name='trace_friend_idx'),
        ]

    def __str__(self):
        return f'{self.trace_id}-{self.status}'


class Span(models.Model):
    class SpanType(models.TextChoices):
        LLM = 'llm'
        TOOL = 'tool'
        RETRIEVAL = 'retrieval'
        TTS = 'tts'
        ASR = 'asr'

    class Status(models.TextChoices):
        RUNNING = 'running'
        SUCCESS = 'success'
        FAILED = 'failed'

    trace = models.ForeignKey(Trace, on_delete=models.CASCADE, related_name='spans')
    span_type = models.CharField(max_length=10, choices=SpanType.choices)
    name = models.CharField(max_length=150)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(default=now)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    input = models.JSONField(default=dict, blank=True)
    output = models.TextField(default='', blank=True)
    model = models.CharField(max_length=100, default='', blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    error = models.TextField(default='', blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.span_type}-{self.name}-{self.status}'
