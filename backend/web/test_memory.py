from datetime import timedelta
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch
from unittest import skipUnless

from django.contrib.auth.models import User
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils.timezone import now
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from web.models.character import Character, Voice
from web.models.friend import Friend, Message
from web.models.memory import MemoryFact, MemoryRevision, MemoryState
from web.models.user import UserProfile
from web.observability.recorder import TraceRecorder
from web.views.friend.message.chat.chat import MessageChatView, add_recent_messages, add_system_prompt
from web.views.friend.message.memory.retrieval import embed_texts, memory_context, retrieve_facts, token_count
from web.views.friend.message.memory.schema import MemoryExtraction, MemoryOperation
from web.views.friend.message.memory.service import (
    commit_extraction, pending_update, extract_memories, update_memory,
)


@override_settings(AGENT_MEMORY={'USE_EMBEDDINGS': False})
class AgentMemoryTests(TestCase):
    def setUp(self):
        owner = UserProfile.objects.create(user=User.objects.create(username='alice'))
        other_owner = UserProfile.objects.create(user=User.objects.create(username='bob'))
        character = Character.objects.create(author=owner, name='助手', profile='友善')
        other_character = Character.objects.create(author=owner, name='另一角色', profile='认真')
        self.friend = Friend.objects.create(me=owner, character=character, memory='旧摘要')
        self.other = Friend.objects.create(me=other_owner, character=character)
        self.other_role = Friend.objects.create(me=owner, character=other_character)

    def message(self, text='我喜欢喝茶', friend=None, output='好的'):
        return Message.objects.create(friend=friend or self.friend, user_message=text, input='', output=output)

    def batch(self, count=10):
        batch = [self.message() for _ in range(count)]
        state, _ = pending_update(self.friend.pk, force=True)
        return batch, state

    def result(self, message, *, content='用户喜欢喝茶', action='upsert', key='user.drink', evidence=None):
        return MemoryExtraction(summary='用户偏好已记录', operations=[MemoryOperation(
            action=action, key=key, category='preference', content=content,
            source_message_id=message.id, evidence=evidence or message.user_message,
        )])

    def fact(self, friend=None, **kwargs):
        defaults = dict(friend=friend or self.friend, key='user.drink', category='preference',
                        content='用户喜欢喝茶', evidence='我喜欢喝茶')
        defaults.update(kwargs)
        return MemoryFact.objects.create(**defaults)

    def test_update_requires_ten_unprocessed_turns(self):
        for _ in range(9):
            self.message()
        self.assertIsNone(pending_update(self.friend.pk))
        self.message()
        self.assertEqual(len(pending_update(self.friend.pk)[1]), 10)

    def test_stale_concurrent_result_cannot_overwrite_new_summary(self):
        batch, old = self.batch()
        current, _ = pending_update(self.friend.pk)
        self.assertTrue(commit_extraction(current, batch, MemoryExtraction(summary='新摘要'), {}))
        self.assertFalse(commit_extraction(old, batch, MemoryExtraction(summary='过期摘要'), {}))
        self.friend.refresh_from_db()
        self.assertEqual(self.friend.memory, '新摘要')

    def test_commit_is_idempotent_and_advances_cursor(self):
        batch, job = self.batch()
        extraction = self.result(batch[-1])
        self.assertTrue(commit_extraction(job, batch, extraction, {}))
        self.assertFalse(commit_extraction(job, batch, extraction, {}))
        self.assertEqual(MemoryFact.objects.count(), 1)
        self.assertEqual(MemoryRevision.objects.count(), 1)
        state = MemoryState.objects.get(pk=job.pk)
        self.assertEqual(state.last_message_id, batch[-1].id)
        self.assertIsNone(pending_update(self.friend.pk))

    def test_conflict_updates_same_key_and_preserves_revision(self):
        batch, job = self.batch()
        commit_extraction(job, batch, self.result(batch[-1]), {})
        corrected = self.message('我现在改喝咖啡了')
        job, _ = pending_update(self.friend.pk, force=True)
        commit_extraction(job, [corrected], self.result(corrected, content='用户现在喜欢喝咖啡'), {})
        fact = MemoryFact.objects.get(friend=self.friend)
        self.assertEqual(fact.version, 2)
        self.assertEqual(fact.content, '用户现在喜欢喝咖啡')
        revision = fact.revisions.last()
        self.assertEqual(revision.previous['content'], '用户喜欢喝茶')
        self.assertEqual(revision.action, 'update')

    def test_foreign_source_is_rejected_without_writes(self):
        batch, job = self.batch()
        foreign = self.message(friend=self.other)
        with self.assertRaises(ValueError):
            commit_extraction(job, batch, self.result(foreign), {})
        self.assertFalse(MemoryFact.objects.exists())
        self.assertEqual(MemoryState.objects.get(pk=job.pk).last_message_id, 0)

    def test_assistant_claim_is_not_valid_evidence(self):
        source = self.message('你好', output='你喜欢喝咖啡')
        job, _ = pending_update(self.friend.pk, force=True)
        with self.assertRaises(ValueError):
            commit_extraction(job, [source], self.result(source, evidence='你喜欢喝咖啡'), {})

    def test_failure_keeps_cursor_and_retries(self):
        batch, job = self.batch()
        with patch('web.views.friend.message.memory.service.extract_memories', side_effect=TimeoutError):
            self.assertFalse(update_memory((job, batch)))
        state = MemoryState.objects.get(pk=job.pk)
        self.assertEqual(state.last_message_id, 0)
        self.assertEqual(state.last_error, 'TimeoutError')
        self.friend.refresh_from_db()
        self.assertEqual(self.friend.memory, '旧摘要')
        with patch('web.views.friend.message.memory.service.extract_memories', return_value=self.result(batch[-1])):
            self.assertTrue(update_memory(pending_update(self.friend.pk)))
        self.assertEqual(MemoryState.objects.get(pk=job.pk).last_error, '')

    def test_backlog_is_processed_in_order_without_skipping(self):
        batch, job = self.batch(25)
        commit_extraction(job, batch[:10], MemoryExtraction(summary='第一批'), {})
        next_job, next_batch = pending_update(self.friend.pk)
        self.assertEqual([m.pk for m in next_batch], [m.pk for m in batch[10:20]])
        self.assertEqual(next_job.last_message_id, batch[9].id)
        commit_extraction(next_job, batch[10:20], MemoryExtraction(summary='第二批'), {})
        state = MemoryState.objects.get(pk=job.pk)
        self.assertEqual(state.last_message_id, batch[19].id)
        self.assertIsNone(pending_update(self.friend.pk))
        self.assertEqual(len(pending_update(self.friend.pk, force=True)[1]), 5)

    def test_retrieval_isolates_users_and_characters(self):
        self.fact()
        self.fact(friend=self.other, content='用户喜欢红茶')
        self.fact(friend=self.other_role, content='用户喜欢绿茶')
        results = retrieve_facts(self.friend.pk, '喜欢喝茶')
        self.assertEqual([fact.friend_id for fact in results], [self.friend.pk])

    def test_irrelevant_expired_and_forgotten_facts_are_excluded(self):
        self.fact(active=False)
        self.fact(key='expired', expires_at=now() - timedelta(days=1))
        self.fact(key='event', category='event', content='去年参观博物馆')
        self.assertEqual(retrieve_facts(self.friend.pk, '喜欢喝茶'), [])

    def test_forget_excludes_fact_but_keeps_audit(self):
        self.fact()
        source = self.message('忘记我喜欢喝茶这件事')
        job, _ = pending_update(self.friend.pk, force=True)
        commit_extraction(job, [source], self.result(source, action='forget'), {})
        self.assertEqual(retrieve_facts(self.friend.pk, '喜欢喝茶'), [])
        self.assertEqual(MemoryRevision.objects.get().action, 'forget')

    @override_settings(AGENT_MEMORY={'USE_EMBEDDINGS': False, 'CONTEXT_TOKEN_BUDGET': 100})
    def test_memory_context_respects_budget(self):
        self.fact(content='用户喜欢喝茶' * 50)
        self.friend.memory = '摘要内容' * 1000
        self.assertLessEqual(token_count(memory_context(self.friend, '喝茶')), 100)

    @override_settings(AGENT_MEMORY={'USE_EMBEDDINGS': False, 'RECENT_TOKEN_BUDGET': 100})
    def test_recent_context_keeps_complete_pairs_and_current_question(self):
        self.message('很长的用户消息' * 100, output='很长的助手回复' * 100)
        current = HumanMessage('当前问题')
        state = add_recent_messages({'messages': [SystemMessage('设定'), current]}, self.friend)
        self.assertIs(state['messages'][-1], current)
        recent = state['messages'][1:-1]
        self.assertEqual(len(recent), 2)
        self.assertIsInstance(recent[0], HumanMessage)
        self.assertIsInstance(recent[1], AIMessage)
        self.assertLessEqual(sum(token_count(m.content) for m in recent) + 8, 100)

    def test_model_json_is_validated(self):
        message = self.message()
        expected = self.result(message)
        graph = SimpleNamespace(invoke=lambda state: {'messages': [AIMessage(expected.model_dump_json())]})
        with patch('web.views.friend.message.memory.service.MemoryGraph.create_app', return_value=graph):
            self.assertEqual(extract_memories(self.friend, [message]), expected)

    def test_unrelated_summary_is_preserved_if_retrieval_fails(self):
        with patch('web.views.friend.message.chat.chat.memory_context', side_effect=TimeoutError):
            inputs = add_system_prompt({'messages': [HumanMessage('你好')]}, self.friend)
        self.assertIn('旧摘要', inputs['messages'][0].content)

    def test_completed_stream_persists_before_done_and_no_longer_truncates_at_500(self):
        view = MessageChatView()
        self.friend.character.voice = Voice(name='test', voice_id='test')
        text = '完整回复' * 200
        recorder = TraceRecorder(user=self.friend.me, friend=self.friend,
                                 message='长消息' * 200)

        def work(inputs, mq, voice_id, recorder):
            mq.put({'content': text})
            mq.put(None)

        with patch.object(view, 'work', side_effect=work):
            stream = view.event_stream(recorder, {'messages': [HumanMessage('长消息' * 200)]},
                                       self.friend, '长消息' * 200)
            self.assertIn('trace_id', next(stream))
            self.assertIn('content', next(stream))
            self.assertEqual(next(stream), 'data: [DONE]\n\n')
            self.assertEqual(Message.objects.get().output, text)
            self.assertEqual(Message.objects.get().user_message, '长消息' * 200)

    def test_empty_reply_does_not_create_fake_turn(self):
        view = MessageChatView()
        self.friend.character.voice = Voice(name='test', voice_id='test')
        recorder = TraceRecorder(user=self.friend.me, friend=self.friend, message='你好')
        with patch.object(view, 'work', side_effect=lambda inputs, mq, voice, recorder: mq.put(None)):
            list(view.event_stream(recorder, {'messages': []}, self.friend, '你好'))
        self.assertFalse(Message.objects.exists())

    def test_embedding_failure_falls_back_to_lexical_retrieval(self):
        self.fact(embedding=[1.0, 0.0], embedding_model='text-embedding-v4')
        with override_settings(AGENT_MEMORY={'USE_EMBEDDINGS': True, 'EMBEDDING_DIMENSIONS': 2}):
            with patch('web.views.friend.message.memory.retrieval.embed_texts', side_effect=TimeoutError):
                self.assertEqual(len(retrieve_facts(self.friend.pk, '喝茶')), 1)

    def test_semantic_retrieval_matches_paraphrase(self):
        self.fact(content='用户爱喝茗茶', embedding=[1.0, 0.0], embedding_model='text-embedding-v4')
        with override_settings(AGENT_MEMORY={'USE_EMBEDDINGS': True, 'EMBEDDING_DIMENSIONS': 2}):
            with patch('web.views.friend.message.memory.retrieval.embed_texts', return_value=[[1.0, 0.0]]):
                self.assertEqual(len(retrieve_facts(self.friend.pk, '饮品偏好')), 1)

    def test_pending_update_is_scoped_to_one_friend(self):
        self.message(friend=self.other)
        self.assertIsNotNone(pending_update(self.other.pk, force=True))
        self.assertIsNone(pending_update(self.friend.pk, force=True))

    def test_fact_write_error_rolls_back_summary_cursor_and_all_facts(self):
        batch, job = self.batch()
        with patch('web.views.friend.message.memory.service.MemoryRevision.objects.create', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                commit_extraction(job, batch, self.result(batch[-1]), {})
        self.assertFalse(MemoryFact.objects.exists())
        self.friend.refresh_from_db()
        self.assertEqual(self.friend.memory, '旧摘要')
        self.assertEqual(MemoryState.objects.get(pk=job.pk).last_message_id, 0)

    def test_network_calls_are_outside_commit_transaction(self):
        # TestCase wraps tests in a transaction, so check the service boundary
        # explicitly rather than connection.in_atomic_block here.
        batch, job = self.batch()
        with patch('web.views.friend.message.memory.service.transaction.atomic', wraps=transaction.atomic) as atomic, \
                patch('web.views.friend.message.memory.service.extract_memories') as extract:
            def model(*args):
                self.assertEqual(atomic.call_count, 0)
                return self.result(batch[-1])
            extract.side_effect = model
            self.assertTrue(update_memory((job, batch)))

    def test_status_is_sent_after_text_and_save_but_before_memory_call(self):
        self.batch(9)
        view = MessageChatView()
        recorder = TraceRecorder(user=self.friend.me, friend=self.friend, message='你好')

        def work(inputs, queue, voice_id, recorder):
            queue.put({'content': '完整回答'})
            queue.put(None)

        with patch.object(view, 'work', side_effect=work), \
                patch('web.views.friend.message.chat.chat.update_memory', return_value=True) as update:
            stream = view.event_stream(recorder, {'messages': [HumanMessage('你好')]}, self.friend, '你好')
            self.assertIn('trace_id', next(stream))
            self.assertIn('完整回答', next(stream))
            self.assertIn('正在优化对话', next(stream))
            self.assertEqual(Message.objects.count(), 10)
            update.assert_not_called()
            self.assertIn('ready', next(stream))
            update.assert_called_once()
            self.assertEqual(next(stream), 'data: [DONE]\n\n')

    def test_failed_memory_update_keeps_reply_and_finishes_stream(self):
        self.batch(9)
        view = MessageChatView()
        recorder = TraceRecorder(user=self.friend.me, friend=self.friend, message='你好')

        def work(inputs, queue, voice_id, recorder):
            queue.put({'content': '完整回答'})
            queue.put(None)

        with patch.object(view, 'work', side_effect=work), \
                patch('web.views.friend.message.memory.service.extract_memories', side_effect=TimeoutError):
            output = ''.join(view.event_stream(
                recorder, {'messages': [HumanMessage('你好')]}, self.friend, '你好'))
        self.assertIn('完整回答', output)
        self.assertIn('下次对话会重试', output)
        self.assertTrue(output.endswith('data: [DONE]\n\n'))
        self.assertEqual(Message.objects.order_by('id').last().output, '完整回答')
        self.assertEqual(MemoryState.objects.get(friend=self.friend).last_message_id, 0)

    def test_low_confidence_claim_is_not_persisted(self):
        batch, job = self.batch()
        result = self.result(batch[-1])
        result.operations[0].confidence = 0.4
        self.assertTrue(commit_extraction(job, batch, result, {}))
        self.assertFalse(MemoryFact.objects.exists())

    def test_values_can_swap_between_different_attributes(self):
        preferred = self.fact(key='user.preferred_drink', content='茶')
        avoided = self.fact(key='user.avoided_drink', content='咖啡')
        source = self.message('我现在喜欢咖啡，不喜欢茶')
        job, _ = pending_update(self.friend.pk, force=True)
        result = MemoryExtraction(summary='饮品偏好改变', operations=[
            self.result(source, key=preferred.key, content='咖啡').operations[0],
            self.result(source, key=avoided.key, content='茶').operations[0],
        ])
        commit_extraction(job, [source], result, {})
        preferred.refresh_from_db()
        avoided.refresh_from_db()
        self.assertEqual(preferred.content, '咖啡')
        self.assertEqual(avoided.content, '茶')
        self.assertEqual(preferred.version, 2)
        self.assertEqual(avoided.version, 2)

    def test_explicit_update_can_process_partial_tail(self):
        messages = [self.message() for _ in range(15)]
        with patch('web.views.friend.message.memory.service.extract_memories',
                   return_value=MemoryExtraction(summary='已处理')):
            self.assertTrue(update_memory(pending_update(self.friend.pk)))
            self.assertTrue(update_memory(pending_update(self.friend.pk, force=True)))
        state = MemoryState.objects.get(friend=self.friend)
        self.assertEqual(state.last_message_id, messages[-1].id)

    def test_embedding_outage_does_not_lose_facts(self):
        from web.views.friend.message.memory.service import prepare_vectors
        batch, job = self.batch()
        result = self.result(batch[-1])
        with patch('web.views.friend.message.memory.service.embed_texts', side_effect=TimeoutError):
            vectors = prepare_vectors(result)
        self.assertTrue(commit_extraction(job, batch, result, vectors))
        self.assertEqual(MemoryFact.objects.get().embedding, [])

    @skipUnless(os.getenv('AGENT_MEMORY_LIVE_TEST') == '1', 'Opt-in paid API smoke test')
    def test_live_model_extraction_conflict_and_embeddings(self):
        # Only synthetic fixtures in the test DB are sent to the API, never real conversation history.
        first = self.message('我叫小林。我平时喜欢喝茶，不喜欢咖啡。')
        result = extract_memories(self.friend, [first])
        self.assertTrue(result.operations, 'Model extracted no facts from explicit synthetic statements')
        state, _ = pending_update(self.friend.pk, force=True)
        self.assertTrue(commit_extraction(state, [first], result, {}))
        self.friend.refresh_from_db()
        second = self.message('我的饮品偏好变了，我现在喜欢喝咖啡，不喜欢喝茶了。')
        updated = extract_memories(self.friend, [second])
        state, _ = pending_update(self.friend.pk, force=True)
        self.assertTrue(commit_extraction(state, [second], updated, {}))
        self.assertTrue(MemoryFact.objects.filter(friend=self.friend, version__gte=2).exists(),
                        f'Model did not reuse a stable key: first={result.model_dump_json()}; second={updated.model_dump_json()}')
        with override_settings(AGENT_MEMORY={'USE_EMBEDDINGS': True}):
            vectors = embed_texts(['用户喜欢喝茶', '用户的饮品偏好'])
        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), 1024)
