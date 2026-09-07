#把聊天消息交给大模型，再把大模型的回复加入聊天记录
import json

from django.http import StreamingHttpResponse
from langchain_core.messages import HumanMessage, BaseMessageChunk, SystemMessage, AIMessage
from rest_framework.renderers import BaseRenderer

from rest_framework.views import APIView

from rest_framework.response import Response

from rest_framework.permissions import IsAuthenticated

from web.models.character import Character
from web.models.friend import Friend, Message, SystemPrompt
from web.views.friend.message.chat.graph import ChatGraph
from web.views.friend.message.memory.update import update_memory


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
        prompt+=f'【长期记忆】\n{friend.memory}\n'
        return {'messages':[SystemMessage(prompt)]+msgs}


def add_recent_messages(state,friend):
        msgs = state['messages']
        message_raw = list(Message.objects.filter(friend=friend).order_by('-id')[:10])
        message_raw.reverse()
        messages = []
        for m in message_raw:
            messages.append(HumanMessage(m.user_message))
            messages.append(AIMessage(m.output))
        return {'messages':msgs[:1]+messages+msgs[-1:]}

class MessageChatView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [SSERenderer]
    def post(self,request):
        friend_id = request.data['friend_id']
        message = request.data['message'].strip()
        if not message:
            return Response({
                'result':'消息不能为空',
            })
        friends = Friend.objects.filter(pk = friend_id,me__user = request.user)
        if not friends.exists():
            return Response({
                'result':'好友不存在'
            })
        friend = friends.first()
        app = ChatGraph.create_app()
        inputs = {
            'messages':[HumanMessage(message)],
        }
        inputs = add_system_prompt(inputs,friend)
        inputs = add_recent_messages(inputs,friend)
        def event_stream():#流式输出
            final_output = ''
            final_usage = {}
            for msg, metadata in app.stream(inputs, stream_mode="messages"):
                if isinstance(msg, BaseMessageChunk):
                    if msg.content:
                        final_output += msg.content
                        yield f"data: {json.dumps({'content': msg.content}, ensure_ascii=False)}\n\n"
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        final_usage = msg.usage_metadata
            yield "data: [DONE]\n\n"
            input_tokens = final_usage.get('input_tokens',0)
            output_tokens = final_usage.get('output_tokens',0)
            total_tokens = final_usage.get('total_tokens',0)
            Message.objects.create(
                friend=friend,
                user_message=message[:500],
                input = json.dumps(
                    [m.model_dump() for m in inputs['messages']],
                    ensure_ascii=False
                )[:10000],
                output = final_output[:500],
                input_tokens = input_tokens,
                output_tokens = output_tokens,
                total_tokens = total_tokens,
            )
            message_count = Message.objects.filter(friend=friend).count()

            if message_count%10==0:
                update_memory(friend)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response['Cache-Control'] = 'no-cache'
        return response


