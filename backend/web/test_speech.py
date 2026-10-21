"""Speech model compatibility and safe migration tests; no external API calls."""
import asyncio
import json
import os
from io import StringIO
from queue import Queue
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from web.models.character import Voice
from web.speech import SpeechServiceError, synthesis_model
from web.views.create.character.voice.custom.create_voice import create_voice
from web.views.friend.message.chat.chat import MessageChatView


class SpeechCompatibilityTests(SimpleTestCase):
    @patch.dict(os.environ, {'TTS_MODEL': 'cosyvoice-v3-flash'})
    def test_builtin_voices_follow_default(self):
        self.assertEqual(synthesis_model('longanyang'), 'cosyvoice-v3-flash')

    @patch.dict(os.environ, {'TTS_MODEL': 'cosyvoice-v3-flash'})
    def test_old_clone_does_not_silently_switch_models(self):
        self.assertEqual(synthesis_model('cosyvoice-v3-plus-test-123'), 'cosyvoice-v3-plus')

    def test_new_clone_uses_its_bound_model(self):
        self.assertEqual(synthesis_model('cosyvoice-v3-flash-test-123'), 'cosyvoice-v3-flash')
        self.assertEqual(synthesis_model('cosyvoice-v3.5-flash-test-123'), 'cosyvoice-v3.5-flash')

    def test_unknown_custom_voice_is_not_sent_to_an_arbitrary_model(self):
        with self.assertRaises(ValueError):
            synthesis_model('cosyvoice-unsupported-123')

    @patch.dict(os.environ, {'TTS_MODEL': 'cosyvoice-v3-flash'})
    def test_enrollment_uses_same_config_as_synthesis(self):
        with patch('web.views.create.character.voice.custom.create_voice.voice_request') as request:
            create_voice('https://example.com/sample.wav', 'test')
        request.assert_called_once_with('create_voice', target_model=synthesis_model('longanyang'),
                                        prefix='test', url='https://example.com/sample.wav')

    def test_quota_warning_does_not_claim_the_model_is_permanently_free(self):
        error = SpeechServiceError('AllocationQuota.FreeTierOnly')
        self.assertIn('免费额度', error.user_message)
        self.assertIn('文字回复不受影响', error.user_message)

    def test_receiver_preserves_quota_failure_for_trace_and_ui(self):
        class Socket:
            async def __aiter__(self):
                yield json.dumps({'header': {'event': 'task-failed',
                                            'error_code': 'AllocationQuota.FreeTierOnly'}})

        with self.assertRaises(SpeechServiceError) as error:
            asyncio.run(MessageChatView().tts_receiver(Queue(), Socket()))
        self.assertEqual(error.exception.code, 'AllocationQuota.FreeTierOnly')

    @patch.dict(os.environ, {'TTS_MODEL': 'cosyvoice-v3-flash', 'WSS_URL': 'wss://example.invalid'})
    def test_startup_sends_matching_model_and_keeps_service_error(self):
        sent = []

        class Socket:
            async def send(self, value):
                sent.append(json.loads(value))

            async def __aiter__(self):
                yield json.dumps({'header': {'event': 'task-failed',
                                            'error_code': 'AllocationQuota.FreeTierOnly'}})

        class Connection:
            async def __aenter__(self):
                return Socket()

            async def __aexit__(self, *args):
                pass

        with patch('web.views.friend.message.chat.chat.websockets.connect', return_value=Connection()):
            with self.assertRaises(SpeechServiceError):
                asyncio.run(MessageChatView()._run_tts_tasks(None, {}, Queue(),
                    'cosyvoice-v3-flash-test-123', None))
        self.assertEqual(sent[0]['payload']['model'], 'cosyvoice-v3-flash')


class VoiceMigrationTests(TestCase):
    def setUp(self):
        self.voice = Voice.objects.create(name='测试音色', voice_id='cosyvoice-v3-plus-test-123')

    def migrate(self, *extra):
        call_command('migrate_voice_model', target_model='cosyvoice-v3-flash',
                     voice_id=[self.voice.pk], apply=True, stdout=StringIO(), stderr=StringIO())

    def test_preview_does_not_call_api_or_write_ids(self):
        with patch('web.management.commands.migrate_voice_model.voice_request') as request:
            call_command('migrate_voice_model', target_model='cosyvoice-v3-flash', stdout=StringIO())
        request.assert_not_called()
        self.voice.refresh_from_db()
        self.assertEqual(self.voice.voice_id, 'cosyvoice-v3-plus-test-123')

    def test_success_keeps_local_row_and_character_references(self):
        with patch('web.management.commands.migrate_voice_model.voice_request', return_value={
                'output': {'status': 'OK', 'resource_link': 'https://example.com/sample.wav'}}), \
                patch('web.management.commands.migrate_voice_model.create_voice', return_value={
                    'output': {'voice_id': 'cosyvoice-v3-flash-test-new'}}), \
                patch('web.management.commands.migrate_voice_model.verify_voice', return_value=100):
            self.migrate()
        self.voice.refresh_from_db()
        self.assertEqual(self.voice.voice_id, 'cosyvoice-v3-flash-test-new')
        self.assertEqual(Voice.objects.count(), 1)

    def test_failed_audio_validation_preserves_original_voice(self):
        with patch('web.management.commands.migrate_voice_model.voice_request', return_value={
                'output': {'status': 'OK', 'resource_link': 'https://example.com/sample.wav'}}), \
                patch('web.management.commands.migrate_voice_model.create_voice', return_value={
                    'output': {'voice_id': 'cosyvoice-v3-flash-test-new'}}), \
                patch('web.management.commands.migrate_voice_model.verify_voice', side_effect=TimeoutError):
            with self.assertRaises(CommandError):
                self.migrate()
        self.voice.refresh_from_db()
        self.assertEqual(self.voice.voice_id, 'cosyvoice-v3-plus-test-123')
