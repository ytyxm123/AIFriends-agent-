import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('web', '0008_voice_character_voice')]

    operations = [
        migrations.CreateModel(
            name='MemoryState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_message_id', models.PositiveBigIntegerField(default=0)),
                ('status', models.CharField(choices=[(s, s) for s in ('idle', 'pending', 'running', 'failed')], db_index=True, default='idle', max_length=12)),
                ('attempts', models.PositiveIntegerField(default=0)),
                ('available_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('lease_id', models.CharField(blank=True, default='', max_length=32)),
                ('lease_until', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.CharField(blank=True, default='', max_length=100)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('friend', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='memory_state', to='web.friend')),
            ],
        ),
        migrations.CreateModel(
            name='MemoryFact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100)),
                ('category', models.CharField(choices=[(s, s) for s in ('profile', 'preference', 'event', 'relationship')], max_length=16)),
                ('content', models.TextField(max_length=500)),
                ('importance', models.FloatField(default=0.5)),
                ('confidence', models.FloatField(default=1.0)),
                ('evidence', models.TextField(max_length=500)),
                ('embedding', models.JSONField(blank=True, default=list)),
                ('embedding_model', models.CharField(blank=True, default='', max_length=100)),
                ('active', models.BooleanField(default=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('friend', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memory_facts', to='web.friend')),
                ('source_message', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='web.message')),
            ],
            options={
                'indexes': [models.Index(fields=['friend', 'active'], name='memory_friend_active_idx')],
                'constraints': [models.UniqueConstraint(fields=('friend', 'key'), name='unique_friend_memory_key')],
            },
        ),
        migrations.CreateModel(
            name='MemoryRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=12)),
                ('previous', models.JSONField(default=dict)),
                ('current', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('fact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='web.memoryfact')),
                ('source_message', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='web.message')),
            ],
            options={'ordering': ['id']},
        ),
    ]
