from django.contrib.auth.models import User
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from web.models.user import UserProfile


class RegisterView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            username = request.data['username'].strip()
            password = request.data['password'].strip()
            if not username or not password:
                return Response({
                    'result': '用户或密码不能为空',
                })
            if User.objects.filter(username=username).exists():
                return Response({
                    'result','用户名已存在'
                })
            user = User.objects.create_user(username=username, password=password)
            user_profile = UserProfile.objects.create(user=user)
            refresh = RefreshToken.for_user(user)
            confirm_password = request.data.get('confirm_password').strip()

        except:
            return Response({
                'result':'系统异常，请稍后重试',
            })
