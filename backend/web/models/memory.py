"""Conversation-scoped facts, summary cursor and revision history."""
from django.db import models
from django.utils.timezone import now


class MemoryState(models.Model):
    friend = models.OneToOneField('web.Friend', on_delete=models.CASCADE, related_name='memory_state')
    last_message_id = models.PositiveBigIntegerField(default=0)
    last_error = models.CharField(max_length=100, default='', blank=True)
    updated_at = models.DateTimeField(default=now)

    def __str__(self):
        return f'friend={self.friend_id} cursor={self.last_message_id}'


class MemoryFact(models.Model):
    friend = models.ForeignKey('web.Friend', on_delete=models.CASCADE, related_name='memory_facts')
    key = models.CharField(max_length=100)
    category = models.CharField(max_length=16, choices=[(s, s) for s in
                                ('profile', 'preference', 'event', 'relationship')])
    content = models.TextField(max_length=500)
    importance = models.FloatField(default=0.5)
    confidence = models.FloatField(default=1.0)
    source_message = models.ForeignKey('web.Message', null=True, on_delete=models.SET_NULL)
    evidence = models.TextField(max_length=500)
    embedding = models.JSONField(default=list, blank=True)
    embedding_model = models.CharField(max_length=100, default='', blank=True)
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=now)
    updated_at = models.DateTimeField(default=now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['friend', 'key'], name='unique_friend_memory_key')]
        indexes = [models.Index(fields=['friend', 'active'], name='memory_friend_active_idx')]

    def __str__(self):
        return f'{self.friend_id}/{self.key}: {self.content[:60]}'


class MemoryRevision(models.Model):
    fact = models.ForeignKey(MemoryFact, on_delete=models.CASCADE, related_name='revisions')
    action = models.CharField(max_length=12)
    previous = models.JSONField(default=dict)
    current = models.JSONField(default=dict)
    source_message = models.ForeignKey('web.Message', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=now)

    class Meta:
        ordering = ['id']
