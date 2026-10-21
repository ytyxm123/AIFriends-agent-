from django.contrib.auth import authenticate
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from web.models.user import UserProfile


class LoginView(APIView):
    authentication_classes = []
    def post(self, request, *args, **kwargs):
        try:
            username = request.data['username'].strip()
            password = request.data['password'].strip()
            if not username or not password:
                return Response(
                    {'result': '用户名或密码不能为空'})
            user = authenticate(username=username, password=password)#验证用户名和密码
            if user:
                user_profile = UserProfile.objects.get(user=user)
                refresh = RefreshToken.for_user(user)#生成jwt_token
                response = Response({
                    'result': 'success',
                    'access': str(refresh.access_token),
                    'user_id': user.id,
                    'is_staff': user.is_staff,
                    'username': user.username,
                    'photo': user_profile.photo.url,
                    'profile': user_profile.profile,
                })
                response.set_cookie(
                    key='refresh_token',
                    value=str(refresh),
                    httponly=True,
                    samesite='lax',
                    secure=not settings.DEBUG,
                    max_age=86400*7,
                )
                return response
            return Response({'result': '用户名或密码错误'})
        except:
            import traceback
            print(traceback.format_exc())
            return Response({
                'result': '系统异常，请稍后重试',
            })
