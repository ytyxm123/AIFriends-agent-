from rest_framework.views import APIView

from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from web.models.character import Character, Voice
from web.models.user import UserProfile


class CreateCharacterView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            user = request.user
            user_profile = UserProfile.objects.get(user=user)
            voice_id = request.data.get('voice_id')
            name = (request.data.get('name') or '').strip()
            profile = (request.data.get('profile') or '').strip()[:100000]
            photo = request.FILES.get('photo',None)
            background_image = request.FILES.get('background_image',None)

            if not name:
                return Response({
                    'result':'名称不能为空',
                })
            if not profile:
                return Response({
                    'result':'角色介绍不能为空'
                })
            if not background_image:
                return Response({
                    'result':'聊天背景图不能为空'
                })
            if not photo:
                return Response({
                    'result':'角色头像不能为空'
                })

            voice = Voice.objects.get(id=voice_id) if voice_id else None
            Character.objects.create(
                author=user_profile,
                name=name,
                profile=profile,
                background_image=background_image,
                photo=photo,
                voice=voice,
            )
            return Response({
                'result':'success'
            })
        except:
            return Response({
                'result': '系统异常请稍后再试'
            })
