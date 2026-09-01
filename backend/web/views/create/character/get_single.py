from rest_framework.views import APIView

from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from web.models.character import Character


class GetSingleView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            character_id = request.query_params.get('character_id')
            character = Character.objects.get(id=character_id,author__user=request.user)

            return Response({
                'result':'success',
                'character':{
                    'character_id':character.id,
                    'name':character.name,
                    'photo':character.photo.url,
                    'profile':character.profile,
                    'background_image':character.background_image.url
                },
            })
        except:
            return Response({'result':'系统异常，请稍后重试'})