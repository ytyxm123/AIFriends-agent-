from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from rest_framework.response import Response

from web.models.character import Voice


class GetVoiceList(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            voice_raw = Voice.objects.order_by('id')
            voice_list = []
            for voice in voice_raw:
                voice_list.append({
                    'id': voice.id,
                    'name': voice.name,
                })
            return Response({
                'result': 'success',
                'voices': voice_list,
            })

        except:
            return Response({
                'result':"系统异常请，稍后重试"
            })