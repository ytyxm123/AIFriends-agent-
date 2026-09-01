from django.utils.timezone import now
from rest_framework.views import APIView

from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from web.models.character import Character
from web.views.utils.photo import remove_old_photos


class UpdateCharacterView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self,request):
        try:
            character_id = request.data.get('character_id')
            character = Character.objects.get(id=character_id,author__user=request.user)
            name = request.data.get('name').strip()
            photo = request.FILES.get('photo',None)
            background_image = request.FILES.get('background_image',None)
            profile = request.data.get('profile').strip()[:100000]

            if not name:
                return Response({
                    'result':'名称不能为空'
                })

            if not profile:
                return Response({
                    'result':'角色介绍不能为空'
                })
            if photo:
                remove_old_photos(character.photo)
                character.photo = photo
            if background_image:
                remove_old_photos(character.background_image)
                character.background_image = background_image
            character.name = name
            character.profile = profile
            character.update_time = now()
            character.save()
            return Response({
                'result':'success'
            })
        except:
            return Response({
                'result':'系统异常，请稍后重试'
            })