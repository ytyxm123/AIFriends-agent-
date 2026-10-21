"""Deterministic regression tests; no paid model or speech calls."""
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from unittest import skipUnless

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from rest_framework.test import APIClient

from web.models.character import Character
from web.models.friend import Friend, Message
from web.models.user import UserProfile
from web.observability.recorder import TraceRecorder
from web.views.friend.message.chat.chat import MessageChatView
from web.views.friend.message.chat.graph import ChatGraph


class AgentLoopTests(SimpleTestCase):
    def test_text_is_generated_before_speech_connection_is_ready(self):
        import asyncio
        from queue import Queue

        async def scenario():
            queue = Queue()
            view = MessageChatView()
            text_ready = asyncio.Event()
            calls = []

            class Stream:
                async def astream(self, *args, **kwargs):
                    calls.append('model')
                    yield AIMessageChunk(content='立即显示的文字'), {}

            async def speech(app, inputs, target, voice, recorder):
                # Simulates a speech handshake that cannot complete until text
                # has already been produced. Sequential startup would time out.
                await asyncio.wait_for(text_ready.wait(), timeout=0.5)
                self.assertEqual(queue.get_nowait()['content'], '立即显示的文字')
                chunks = [chunk.content async for chunk, _ in app.astream()]
                self.assertEqual(chunks, ['立即显示的文字'])

            original = view.run_chat_tasks

            async def generate(*args):
                await original(*args)
                text_ready.set()

            with patch.object(view, 'run_tts_tasks', side_effect=speech), \
                    patch.object(view, 'run_chat_tasks', side_effect=generate), \
                    patch('web.views.friend.message.chat.chat.ChatGraph.create_app_async',
                          new=AsyncMock(return_value=Stream())):
                await view.run_with_app({}, queue, 'voice', Mock(), True)
            self.assertEqual(calls, ['model'])
            self.assertTrue(queue.empty(), 'No speech error or duplicated text is expected')

        asyncio.run(scenario())

    def app(self, replies):
        model = Mock()
        model.bind_tools.return_value = model
        model.invoke.side_effect = replies
        with patch('web.views.friend.message.chat.graph.ChatOpenAI', return_value=model):
            app = ChatGraph.create_app()
        return app, model

    def call(self, name='get_time', args=None, identifier='one'):
        return AIMessage(content='', tool_calls=[{
            'id': identifier, 'name': name, 'args': args or {},
        }])

    def test_tool_result_returns_to_model(self):
        app, model = self.app([self.call(), AIMessage(content='完成')])
        state = app.invoke({'messages': [HumanMessage('现在几点')]})
        self.assertEqual(state['messages'][-1].content, '完成')
        self.assertEqual(model.invoke.call_count, 2)
        self.assertTrue(any(isinstance(m, ToolMessage) for m in state['messages']))

    def test_duplicate_arguments_stop_even_with_different_call_ids(self):
        app, model = self.app([self.call(identifier='a'), self.call(identifier='b')])
        state = app.invoke({'messages': [HumanMessage('现在几点')]})
        self.assertIn('未能收敛', state['messages'][-1].content)
        self.assertEqual(sum(isinstance(m, ToolMessage) for m in state['messages']), 1)

    @patch.dict(os.environ, {'AGENT_MAX_TOOL_ROUNDS': '2', 'AGENT_MAX_REPEAT_CALLS': '99'})
    def test_max_rounds_allows_exactly_two_tool_executions(self):
        app, model = self.app([self.call(identifier=str(i)) for i in range(3)])
        state = app.invoke({'messages': [HumanMessage('现在几点')]})
        self.assertIn('未能收敛', state['messages'][-1].content)
        self.assertEqual(sum(isinstance(m, ToolMessage) for m in state['messages']), 2)

    def test_invalid_knowledge_arguments_become_tool_error(self):
        app, model = self.app([
            self.call('search_knowledge_base', {'query': ''}), AIMessage(content='请补充问题'),
        ])
        state = app.invoke({'messages': [HumanMessage('查询')]})
        errors = [m for m in state['messages'] if isinstance(m, ToolMessage)]
        self.assertEqual(errors[0].status, 'error')

    def test_text_stream_does_not_expose_tool_payload(self):
        class Stream:
            async def astream(self, *args, **kwargs):
                yield ToolMessage(content='private tool payload', tool_call_id='x'), {}
                yield AIMessageChunk(content='回答'), {}
                yield AIMessage(content='已终止'), {}

        from queue import Queue
        import asyncio
        queue = Queue()
        asyncio.run(MessageChatView().run_chat_tasks(Stream(), {}, queue, Mock()))
        self.assertEqual([queue.get()['content'] for _ in range(queue.qsize())], ['回答', '已终止'])

    @patch.dict(os.environ, {'ENABLE_TTS': 'true', 'WSS_URL': 'wss://example.invalid'})
    def test_speech_setup_failure_falls_back_to_text_once(self):
        from queue import Queue
        view = MessageChatView()
        queue = Queue()

        async def text(app, inputs, target, handler, speech_queue=None):
            target.put({'content': '文字回答'})

        with patch.object(view, 'run_tts_tasks', side_effect=ConnectionError), \
                patch.object(view, 'run_chat_tasks', side_effect=text) as fallback, \
                patch('web.views.friend.message.chat.chat.ChatGraph.create_app_async',
                      new=AsyncMock(return_value=object())):
            view.work({}, queue, 'voice', Mock())
        items = [queue.get() for _ in range(queue.qsize())]
        self.assertEqual(fallback.call_count, 1)
        self.assertTrue(any(item and item.get('content') == '文字回答' for item in items))
        self.assertFalse(any(item and item.get('error') for item in items))


@override_settings(AGENT_MEMORY={'USE_EMBEDDINGS': False})
class ChatEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('chat-test')
        owner = UserProfile.objects.create(user=self.user)
        character = Character.objects.create(author=owner, name='助手', profile='友善')
        self.friend = Friend.objects.create(me=owner, character=character)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_invalid_input_returns_json_400(self):
        response = self.client.post('/api/friend/message/chat/', {'message': ''}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('friend_id', response.json())

    def test_foreign_conversation_is_rejected(self):
        other = User.objects.create_user('other-chat-user')
        self.client.force_authenticate(other)
        response = self.client.post('/api/friend/message/chat/', {
            'friend_id': self.friend.pk, 'message': 'hello',
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_no_voice_still_streams_and_saves_text(self):
        def work(inputs, queue, voice_id, recorder):
            self.assertIsNone(voice_id)
            queue.put({'content': '你好'})
            queue.put(None)

        with patch.object(MessageChatView, 'work', side_effect=work):
            response = self.client.post('/api/friend/message/chat/', {
                'friend_id': self.friend.pk, 'message': 'hello', 'enable_tts': False,
            }, format='json', HTTP_ACCEPT='text/event-stream, application/json')
            body = b''.join(response.streaming_content).decode()
        self.assertIn('[DONE]', body)
        self.assertEqual(Message.objects.get().output, '你好')

    def test_partial_failure_is_not_saved_as_successful_memory_source(self):
        def work(inputs, queue, voice_id, recorder):
            queue.put({'content': '未完成'})
            queue.put({'error': '服务中断'})
            queue.put(None)

        recorder = TraceRecorder(user=self.friend.me, friend=self.friend,
                                 message='hello')
        with patch.object(MessageChatView, 'work', side_effect=work):
            body = ''.join(MessageChatView().event_stream(
                recorder, {'messages': []}, self.friend, 'hello'))
        self.assertIn('error', body)
        self.assertFalse(Message.objects.exists())

    def test_refresh_ignores_expired_access_header_and_sets_local_cookie(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        client = APIClient()
        client.cookies['refresh_token'] = str(RefreshToken.for_user(self.user))
        response = client.post('/api/user/refresh/', {}, format='json',
                               HTTP_AUTHORIZATION='Bearer expired.invalid.token')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['access'])

    @skipUnless(os.getenv('AIFRIENDS_LIVE_TEST') == '1', 'Opt-in paid model smoke test')
    def test_live_text_chat_endpoint_with_synthetic_conversation(self):
        response = self.client.post('/api/friend/message/chat/', {
            'friend_id': self.friend.pk,
            'message': '请调用时间工具告诉我现在的时间。简短回复即可。',
            'enable_tts': False,
        }, format='json', HTTP_ACCEPT='text/event-stream, application/json')
        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content).decode()
        self.assertNotIn('"error"', body)
        self.assertIn('[DONE]', body)
        self.assertTrue(Message.objects.get().output.strip())
