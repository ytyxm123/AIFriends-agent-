"""Re-create custom voices for a new model without deleting original voices."""
import asyncio
from queue import Queue

from django.core.management.base import BaseCommand, CommandError
from langchain_core.messages import AIMessage

from web.models.character import Voice
from web.speech import CLONING_MODELS, synthesis_model, voice_request
from web.views.create.character.voice.custom.create_voice import create_voice
from web.views.friend.message.chat.chat import MessageChatView


async def verify_voice(voice_id):
    class Sample:
        async def astream(self, *args, **kwargs):
            yield AIMessage(content='你好。'), {}

    queue = Queue()
    await MessageChatView()._run_tts_tasks(Sample(), {}, queue, voice_id, None)
    audio_bytes = 0
    while not queue.empty():
        item = queue.get_nowait()
        if item.get('warning'):
            raise RuntimeError('Speech verification returned a warning')
        audio_bytes += len(item.get('audio', ''))
    if not audio_bytes:
        raise RuntimeError('Speech verification returned no audio')
    return audio_bytes


class Command(BaseCommand):
    help = 'Preview, or re-create selected custom voices on another model. Uses speech APIs.'

    def add_arguments(self, parser):
        parser.add_argument('--target-model', required=True, choices=CLONING_MODELS)
        parser.add_argument('--voice-id', type=int, action='append', help='Local Voice row ID; repeatable')
        parser.add_argument('--apply', action='store_true', help='Create remote voices and update local IDs')

    def handle(self, *args, **options):
        target = options['target_model']
        voices = Voice.objects.filter(voice_id__startswith='cosyvoice-').order_by('id')
        if options['voice_id']:
            voices = voices.filter(pk__in=options['voice_id'])
        changed = 0
        failed = 0
        for voice in voices:
            if synthesis_model(voice.voice_id) == target:
                continue
            if not options['apply']:
                self.stdout.write(f'Voice {voice.pk}: {synthesis_model(voice.voice_id)} -> {target}')
                continue
            old_id = voice.voice_id
            try:
                details = voice_request('query_voice', voice_id=old_id).get('output', {})
                source = details.get('resource_link')
                if details.get('status') != 'OK' or not source:
                    raise ValueError('Original recording unavailable')
                result = create_voice(source, f'af{voice.pk}', target_model=target)
                new_id = (result.get('output') or {}).get('voice_id', '')
                if not new_id or synthesis_model(new_id) != target:
                    raise ValueError('Enrollment returned an incompatible voice')
                asyncio.run(verify_voice(new_id))
                # Never hold a transaction during network calls or overwrite a
                # concurrent edit. Original remote voices remain recoverable.
                updated = Voice.objects.filter(pk=voice.pk, voice_id=old_id).update(voice_id=new_id)
                if not updated:
                    raise RuntimeError('Voice changed concurrently; new remote voice was retained')
                changed += 1
                self.stdout.write(f'Voice {voice.pk}: migrated and audio verified')
            except Exception as exc:
                failed += 1
                self.stderr.write(f'Voice {voice.pk}: {type(exc).__name__}; original local ID preserved')
        self.stdout.write(f'Migrated={changed}, failed={failed}. Original remote voices were not deleted.')
        if failed:
            raise CommandError('Some voices were not migrated; check API access and source recordings.')
