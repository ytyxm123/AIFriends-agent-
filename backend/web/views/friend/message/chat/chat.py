#把聊天消息交给大模型，再把大模型的回复加入聊天记录
import asyncio
import base64
import json
import os
import threading
from queue import Queue
import socket
import uuid
import logging

import websockets
from django.http import StreamingHttpResponse
from django.db import transaction
from langchain_core.messages import HumanMessage, BaseMessageChunk, SystemMessage, AIMessage
from rest_framework.renderers import BaseRenderer
from rest_framework.renderers import JSONRenderer
from rest_framework import serializers

from rest_framework.views import APIView

from rest_framework.response import Response

from rest_framework.permissions import IsAuthenticated
from web.models.friend import Friend, Message, SystemPrompt
from web.models.observability import Span, Trace
from web.observability.callbacks import TraceCallbackHandler
from web.observability.recorder import TraceRecorder
from web.speech import SpeechServiceError, synthesis_model
from web.views.friend.message.chat.graph import ChatGraph, DEFAULT_CHAT_MODEL
from web.views.friend.message.memory.service import pending_update, update_memory
from web.views.friend.message.memory.config import setting
from web.views.friend.message.memory.retrieval import memory_context, trim_tokens, token_count

logger = logging.getLogger(__name__)


class SSERenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'txt'
    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


def add_system_prompt(state,friend):
        msgs = state['messages']
        system_prompt = SystemPrompt.objects.filter(title='回复').order_by('order_number')
        prompt=''
        for p in system_prompt:
            prompt+=p.prompt
        prompt+=f'\n【角色性格】\n{friend.character.profile}\n'
        query = msgs[-1].content if msgs else ''
        try:
            context = memory_context(friend, query)
        except Exception as exc:
            logger.warning('memory_context_fallback friend=%s error=%s', friend.pk, type(exc).__name__)
            context = trim_tokens(friend.memory or '', setting('SUMMARY_TOKEN_BUDGET'))
        prompt+=f'【长期记忆数据】\n{context}\n'
        return {'messages':[SystemMessage(prompt)]+msgs}


def add_recent_messages(state,friend):
        msgs = state['messages']
        message_raw = list(Message.objects.filter(friend=friend).order_by('-id')[:setting('RECENT_TURNS')])
        turns = []
        remaining = setting('RECENT_TOKEN_BUDGET')
        for m in message_raw:
            size = token_count(m.user_message) + token_count(m.output) + 8
            if size > remaining:
                if not turns and remaining > 8:
                    # Keep a bounded slice of the latest complete user/assistant pair.
                    user = trim_tokens(m.user_message, (remaining - 8) // 2)
                    output = trim_tokens(m.output, remaining - 8 - token_count(user))
                    turns.append([HumanMessage(user), AIMessage(output)])
                break
            turns.append([HumanMessage(m.user_message), AIMessage(m.output)])
            remaining -= size
        messages = [message for turn in reversed(turns) for message in turn]
        return {'messages':msgs[:1]+messages+msgs[-1:]}

class MessageChatView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer, SSERenderer]
    def post(self,request):
        class ChatInput(serializers.Serializer):
            friend_id = serializers.IntegerField(min_value=1)
            message = serializers.CharField(max_length=5000, trim_whitespace=True)
            enable_tts = serializers.BooleanField(default=True)

        data = ChatInput(data=request.data)
        data.is_valid(raise_exception=True)
        friend_id = data.validated_data['friend_id']
        message = data.validated_data['message']
        friend = Friend.objects.select_related('character__voice', 'me').filter(
            pk=friend_id, me__user=request.user).first()
        if friend is None:
            return Response({
                'result':'好友不存在'
            }, status=404)
        recorder = TraceRecorder(
            user=friend.me,
            friend=friend,
            message=message,
            model=os.getenv('CHAT_MODEL', DEFAULT_CHAT_MODEL),
        )
        inputs = {
            'messages':[HumanMessage(message)],
        }
        inputs = add_system_prompt(inputs,friend)
        inputs = add_recent_messages(inputs,friend)

        response = StreamingHttpResponse(
            self.event_stream(recorder, inputs,friend,message, enable_tts=data.validated_data['enable_tts']),
            content_type="text/event-stream")
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


    async def tts_sender(self, app, inputs, mq, ws, task_id, handler):
        speech_failed = False
        async for msg, metadata in app.astream(
            inputs, stream_mode="messages", config={"callbacks": [handler]}):
            if not isinstance(msg, AIMessage):
                continue
            if msg.content:
                if not speech_failed:
                    try:
                        await ws.send(json.dumps({
                            'header': {
                                'action': 'continue-task',
                                'task_id': task_id,
                                'streaming': 'duplex',
                            },
                            'payload': {'input': {'text': msg.content}},
                        }))
                    except Exception:
                        speech_failed = True
                        mq.put_nowait({'warning': '语音暂时不可用，已继续文字回复。'})
        if speech_failed:
            return
        try:
            await ws.send(json.dumps({
                'header': {
                    'action': 'finish-task',
                    'task_id': task_id,
                    'streaming': 'duplex',
                },
                'payload': {'input': {}},
            }))
        except Exception:
            mq.put_nowait({'warning': '语音暂时不可用，文字回复已完成。'})

    async def tts_receiver(self,mq,ws):
        async for msg in ws:
            if isinstance(msg, bytes):
                audio = base64.b64encode(msg).decode('UTF-8')
                mq.put_nowait({'audio': audio})
            else:
                data =  json.loads(msg)
                event = data['header']['event']
                if event == 'task-failed':
                    raise SpeechServiceError(data['header'].get('error_code'))
                if event == 'task-finished':
                    break

    async  def run_tts_tasks(self,app,inputs,mq,voice_id,recorder):
        handler = TraceCallbackHandler(recorder)
        tts_span = recorder.start_span(
            Span.SpanType.TTS, 'cosyvoice-tts', {'voice': voice_id}, model=synthesis_model(voice_id))
        try:
            await self._run_tts_tasks(
                app, inputs, mq, voice_id, handler)
        except Exception as exc:
            recorder.end_span(
                tts_span, status=Span.Status.FAILED,
                error=f'{type(exc).__name__}: {exc}')
            raise
        else:
            recorder.end_span(tts_span)

    async def _run_tts_tasks(self, app, inputs, mq, voice_id, handler):
        task_id = uuid.uuid4().hex
        api_key = os.getenv('API_KEY')
        wss_url = os.getenv('WSS_URL')
        headers = {
            "Authorization": f"Bearer {api_key}",
        }
        async with websockets.connect(wss_url, additional_headers=headers, family=socket.AF_INET,open_timeout=5,) as ws:
            await ws.send(json.dumps({
                "header": {
                    "action": "run-task",
                    "task_id": task_id,  # 随机uuid
                    "streaming": "duplex"
                },
                "payload": {
                    "task_group": "audio",
                    "task": "tts",
                    "function": "SpeechSynthesizer",
                    "model": synthesis_model(voice_id),
                    "parameters": {
                        "text_type": "PlainText",
                        "voice": voice_id,  # 音色
                        "format": "mp3",  # 音频格式
                        "sample_rate": 22050,  # 采样率
                        "volume": 50,  # 音量
                        "rate": 1.25,  # 语速
                        "pitch": 1  # 音调
                    },
                    "input": {  # input不能省去，不然会报错
                    }
                }
            }))
            async with asyncio.timeout(5):
                async for msg in ws:
                    header = json.loads(msg)['header']
                    event = header['event']
                    if event == 'task-started':
                        break
                    if event == 'task-failed':
                        raise SpeechServiceError(header.get('error_code'))
                else:
                    raise RuntimeError('Speech connection closed before task started')
            receiver = asyncio.create_task(self.tts_receiver(mq, ws))
            try:
                await self.tts_sender(app, inputs, mq, ws, task_id, handler)
                try:
                    await asyncio.wait_for(receiver, timeout=15)
                except SpeechServiceError:
                    raise
                except Exception:
                    mq.put_nowait({'warning': '语音连接已结束，文字回复已完成。'})
            finally:
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)

    async def run_chat_tasks(self, app, inputs, mq, handler, speech_queue=None):
        """Stream text when the optional speech service is disabled."""
        async for msg, metadata in app.astream(
            inputs, stream_mode="messages", config={"callbacks": [handler]}):
            if not isinstance(msg, AIMessage):
                continue
            if msg.content:
                mq.put_nowait({'content': msg.content})
                if speech_queue is not None:
                    speech_queue.put_nowait(msg)
            if getattr(msg, 'usage_metadata', None):
                mq.put_nowait({'usage': msg.usage_metadata})




    async def run_with_app(self, inputs, mq, voice_id, recorder, enable_tts):
        # Build the graph inside the request loop so MCP servers (whose
        # connections are bound to this loop) can be discovered dynamically.
        app = await ChatGraph.create_app_async()
        if not enable_tts:
            await self.run_chat_tasks(app, inputs, mq, TraceCallbackHandler(recorder))
            return

        # Generate text once, immediately. Speech connects independently and
        # consumes buffered text; a broken voice service never restarts the LLM.
        speech_queue = asyncio.Queue()

        class SpeechStream:
            async def astream(self, *args, **kwargs):
                while True:
                    chunk = await speech_queue.get()
                    if chunk is None:
                        return
                    yield chunk, {}

        async def speak():
            try:
                await self.run_tts_tasks(SpeechStream(), inputs, mq, voice_id, recorder)
            except Exception as exc:
                logger.warning('speech_unavailable error=%s code=%s; text continues',
                               type(exc).__name__, getattr(exc, 'code', ''))
                warning = exc.user_message if isinstance(exc, SpeechServiceError) else '语音暂时不可用，已继续文字回复。'
                mq.put_nowait({'warning': warning})

        speech_task = asyncio.create_task(speak())
        try:
            try:
                await self.run_chat_tasks(app, inputs, mq, TraceCallbackHandler(recorder), speech_queue)
            finally:
                speech_queue.put_nowait(None)
            await speech_task
        finally:
            speech_task.cancel()
            await asyncio.gather(speech_task, return_exceptions=True)

    def work(self,inputs,mq,voice_id,recorder):
        try:
            enable_tts = (
                os.getenv('ENABLE_TTS', 'true').lower() == 'true'
                and bool(os.getenv('WSS_URL'))
                and bool(voice_id)
            )
            asyncio.run(self.run_with_app(
                inputs, mq, voice_id, recorder, enable_tts))
        except Exception as exc:
            logger.exception('chat_stream_failed error=%s', type(exc).__name__)
            mq.put_nowait({
                'error': 'AI 服务暂时不可用，请稍后重试。',
            })
        finally:
            mq.put_nowait(None)

    def event_stream(self,recorder,inputs,friend,message, enable_tts=True):  # 流式输出
        mq = Queue()
        voice = friend.character.voice
        voice_id = voice.voice_id if voice and enable_tts else None
        # Keep the request identifier in the stream for diagnostics.
        yield f"data: {json.dumps({'trace_id': str(recorder.trace_id)}, ensure_ascii=False)}\n\n"
        thread = threading.Thread(target=self.work,args=(inputs,mq,voice_id,recorder), daemon=True)
        thread.start()
        final_output = ''
        final_usage = {}
        failed = False
        while True:
            msg = mq.get()
            if not msg:
                break
            if msg.get('content',None):
                final_output += msg['content']
                yield f"data: {json.dumps({'content': msg['content']}, ensure_ascii=False)}\n\n"
            if msg.get('audio',None):
                yield f"data: {json.dumps({'audio': msg['audio']}, ensure_ascii=False)}\n\n"
            if msg.get('usage',None):
                final_usage = msg.get('usage')
            if msg.get('error',None):
                failed = True
                yield f"data: {json.dumps({'error': msg['error']}, ensure_ascii=False)}\n\n"
            if msg.get('warning'):
                yield f"data: {json.dumps({'warning': msg['warning']}, ensure_ascii=False)}\n\n"

        input_tokens = final_usage.get('input_tokens', 0)
        output_tokens = final_usage.get('output_tokens', 0)
        total_tokens = final_usage.get('total_tokens', 0)
        # Persist before DONE: a client may close the stream as soon as it receives DONE.
        # Failed TTS/model requests with no reply must not become fake memory sources.
        if final_output.strip() and not failed:
            with transaction.atomic():
                Message.objects.create(
                    friend=friend,
                    user_message=message[:5000],
                    input=json.dumps(
                        [m.model_dump() for m in inputs['messages']], ensure_ascii=False
                    )[:10000],
                    output=final_output[:5000],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
            # Reply is already visible and saved before we invoke the memory model.
            # A failed update must not turn a successful answer into a failed chat.
            try:
                update = pending_update(friend.pk)
                if update is not None:
                    yield 'data: {"status":"optimizing","message":"正在优化对话"}\n\n'
                    if not update_memory(update):
                        yield 'data: {"warning":"本次对话整理未完成，回答已保存，下次对话会重试。"}\n\n'
                    yield 'data: {"status":"ready"}\n\n'
            except Exception as exc:
                logger.warning('memory_update_unavailable friend=%s error=%s', friend.pk, type(exc).__name__)
                yield 'data: {"warning":"对话整理暂时不可用，回答已保存。"}\n\n'
        if failed:
            recorder.finish(
                output=final_output,
                status=Trace.Status.FAILED,
                error='chat_stream_failed',
            )
        else:
            recorder.finish(
                output=final_output,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
        yield "data: [DONE]\n\n"


