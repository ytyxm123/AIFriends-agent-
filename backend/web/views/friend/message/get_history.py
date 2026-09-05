from rest_framework.views import APIView

from rest_framework.response import Response

from rest_framework.permissions import IsAuthenticated

from web.models.friend import Message


class GetHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self,request):
        try:
            last_messages_id =int(request.query_params.get('last_messages_id'))
            friend_id = request.query_params.get('friend_id')
            queryset = Message.objects.filter(friend_id=friend_id,friend__me__user=request.user)
            if last_messages_id>0:
                queryset = queryset.filter(id__lt=last_messages_id)
            messages_row = queryset.order_by('-id')[:1]
            messages=[]
            for message in messages_row:
                messages.append({
                    'id':message.id,
                    'user_message':message.user_message,
                    'output':message.output
                })
            return Response({
                'messages':messages,
                'result':'success',
            })
        except:
            return Response({
                'result':'系统异常，请稍后重试'
            })