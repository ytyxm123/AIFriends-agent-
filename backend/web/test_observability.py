"""Tests for trace recording, pricing and the staff-only APIs."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from rest_framework.test import APIClient

from web.models.character import Character
from web.models.friend import Friend
from web.models.observability import Span, Trace
from web.models.user import UserProfile
from web.observability.callbacks import TraceCallbackHandler
from web.observability.pricing import calculate_cost, get_price
from web.observability.recorder import TraceRecorder


class _FakeChatModel(FakeMessagesListChatModel):
    """Fake model that keeps the full callback chain and accepts tool binding."""

    def bind_tools(self, tools, **kwargs):
        return self


class PricingTests(SimpleTestCase):
    def test_known_model_exact_match(self):
        self.assertEqual(get_price('qwen-plus'), {'input': 0.8, 'output': 2.0})

    def test_unknown_model_is_free(self):
        self.assertEqual(get_price('some-new-model'), {'input': 0.0, 'output': 0.0})

    def test_prefix_match_and_cost(self):
        # deepseek-v4-flash matches the deepseek prefix.
        cost = calculate_cost('deepseek-v4-flash', 1_000_000, 1_000_000)
        self.assertEqual(cost, round(2.0 + 8.0, 6))

    def test_zero_tokens(self):
        self.assertEqual(calculate_cost('deepseek', 0, 0), 0.0)


class TraceRecorderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('trace-owner')
        self.owner = UserProfile.objects.create(user=self.user)
        self.character = Character.objects.create(
            author=self.owner, name='助手', profile='友善')
        self.friend = Friend.objects.create(
            me=self.owner, character=self.character)

    def test_success_persists_trace_with_spans_and_cost(self):
        recorder = TraceRecorder(
            user=self.owner, friend=self.friend,
            message='你好', model='deepseek-v4-flash')
        with recorder.span(Span.SpanType.LLM, 'model_call', {'q': '你好'}):
            pass
        recorder.finish(
            output='回答', input_tokens=1_000_000, output_tokens=1_000_000)
        trace = Trace.objects.get(pk=recorder.trace.pk)
        self.assertEqual(trace.status, Trace.Status.SUCCESS)
        self.assertEqual(trace.output, '回答')
        self.assertEqual(trace.total_tokens, 2_000_000)
        self.assertEqual(trace.cost, 10.0)
        self.assertEqual(trace.spans.count(), 1)
        span = trace.spans.first()
        self.assertEqual(span.span_type, Span.SpanType.LLM)
        self.assertEqual(span.status, Span.Status.SUCCESS)
        self.assertGreaterEqual(span.duration_ms, 0)

    def test_failure_marks_trace_and_open_span_failed(self):
        recorder = TraceRecorder(
            user=self.owner, friend=self.friend, message='出错', model='m')
        record = recorder.start_span(Span.SpanType.TTS, 'tts')
        self.assertIsNone(record.ended_at)
        recorder.finish(status=Trace.Status.FAILED, error='boom')
        trace = Trace.objects.get(pk=recorder.trace.pk)
        self.assertEqual(trace.status, Trace.Status.FAILED)
        self.assertEqual(trace.cost, 0.0)
        self.assertEqual(trace.error, 'boom')
        self.assertEqual(trace.spans.first().status, Span.Status.FAILED)

    def test_double_finish_is_idempotent(self):
        recorder = TraceRecorder(
            user=self.owner, friend=self.friend, message='x', model='m')
        recorder.finish(output='a')
        recorder.finish(output='b')
        self.assertEqual(Span.objects.filter(trace=recorder.trace).count(), 0)
        self.assertEqual(Trace.objects.get(pk=recorder.trace.pk).output, 'a')


class CallbackIntegrationTests(SimpleTestCase):
    """Run the real graph through astream and verify callbacks fire.

    Uses FakeListChatModel (a real BaseChatModel subclass) so the full
    LangChain callback chain runs; a plain Mock's ainvoke would bypass
    run managers and never emit on_chat_model_start.
    """

    def _build_app(self, responses):
        import asyncio  # noqa: F401 (kept for callers running streams)
        from unittest.mock import patch
        from web.views.friend.message.chat.graph import ChatGraph

        fake = _FakeChatModel(responses=responses)
        with patch('web.views.friend.message.chat.graph.ChatOpenAI',
                   return_value=fake):
            app = ChatGraph.create_app()
        return app

    @staticmethod
    def _consume(app, handler, text):
        import asyncio
        from langchain_core.messages import HumanMessage

        async def run():
            async for _ in app.astream(
                {'messages': [HumanMessage(text)]},
                stream_mode='messages',
                config={'callbacks': [handler]},
            ):
                pass

        asyncio.run(run())

    def test_astream_records_llm_span_through_graph(self):
        from langchain_core.messages import AIMessage

        app = self._build_app([AIMessage(
            content='回答',
            usage_metadata={'input_tokens': 10, 'output_tokens': 5,
                            'total_tokens': 15})])
        recorder = Mock()
        recorder.trace = Mock(model='')
        recorder.start_span.return_value = Mock()
        handler = TraceCallbackHandler(recorder)

        self._consume(app, handler, '你好')

        types = [call.kwargs.get('span_type') or call.args[0]
                 for call in recorder.start_span.call_args_list]
        self.assertIn(Span.SpanType.LLM, types)
        recorder.end_span.assert_called_once()
        kwargs = recorder.end_span.call_args.kwargs
        self.assertEqual(kwargs['input_tokens'], 10)
        self.assertEqual(kwargs['output_tokens'], 5)
        self.assertEqual(kwargs['output'], '回答')

    def test_tool_call_records_tool_span_through_graph(self):
        from langchain_core.messages import AIMessage

        app = self._build_app([
            AIMessage(content='', tool_calls=[{
                'id': 't1', 'name': 'get_time', 'args': {}}]),
            AIMessage(content='现在是三点'),
        ])
        recorder = Mock()
        recorder.trace = Mock(model='')
        recorder.start_span.return_value = Mock()
        handler = TraceCallbackHandler(recorder)

        self._consume(app, handler, '几点了')

        names = [call.args[1] if len(call.args) > 1 else call.kwargs.get('name')
                 for call in recorder.start_span.call_args_list]
        self.assertIn('get_time', names)


class CallbackHandlerTests(SimpleTestCase):
    def test_llm_end_extracts_usage_and_output(self):
        recorder = Mock()
        recorder.start_span.return_value = Mock()
        handler = TraceCallbackHandler(recorder)
        run_id = uuid.uuid4()
        import asyncio
        asyncio.run(handler.on_chat_model_start(
            {'name': 'ChatOpenAI'},
            [[SimpleNamespace(content='你好')]],
            run_id=run_id,
            invocation_params={'model': 'deepseek-v4-flash'},
        ))
        message = SimpleNamespace(
            content='答案',
            usage_metadata={'input_tokens': 11, 'output_tokens': 7,
                            'total_tokens': 18})
        response = SimpleNamespace(
            generations=[[SimpleNamespace(message=message)]])
        asyncio.run(handler.on_llm_end(response, run_id=run_id))
        recorder.end_span.assert_called_once()
        kwargs = recorder.end_span.call_args.kwargs
        self.assertEqual(kwargs['input_tokens'], 11)
        self.assertEqual(kwargs['output_tokens'], 7)
        self.assertEqual(kwargs['output'], '答案')


class StaffObservabilityEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('plain')
        owner = UserProfile.objects.create(user=self.user)
        character = Character.objects.create(
            author=owner, name='助手', profile='友善')
        friend = Friend.objects.create(me=owner, character=character)
        recorder = TraceRecorder(
            user=owner, friend=friend, message='你好', model='deepseek')
        with recorder.span(Span.SpanType.LLM, 'model_call'):
            pass
        recorder.finish(output='回答', input_tokens=10, output_tokens=5)

    def test_staff_can_view_stats_and_detail(self):
        staff = User.objects.create_user('boss', is_staff=True)
        client = APIClient()
        client.force_authenticate(staff)
        stats = client.get('/api/observability/stats/?days=7')
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()['total'], 1)
        self.assertTrue({'likes', 'dislikes', 'satisfaction'}.isdisjoint(stats.json()))
        listing = client.get('/api/observability/traces/')
        self.assertEqual(listing.status_code, 200)
        trace_id = listing.json()['traces'][0]['trace_id']
        detail = client.get(f'/api/observability/traces/{trace_id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()['spans']), 1)
        self.assertNotIn('feedback', listing.json()['traces'][0])
        self.assertNotIn('feedback', detail.json()['trace'])

    def test_feedback_endpoint_is_removed(self):
        # Removed APIs must not fall through to the frontend HTML response.
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post('/api/observability/feedback/', {'feedback': 'like'}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('feedback', {field.name for field in Trace._meta.fields})

    def test_plain_user_forbidden(self):
        client = APIClient()
        client.force_authenticate(self.user)
        self.assertEqual(client.get('/api/observability/stats/').status_code, 403)
        self.assertEqual(client.get('/api/observability/traces/').status_code, 403)
