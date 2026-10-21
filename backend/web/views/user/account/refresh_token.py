from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken

from rest_framework.response import Response

class RefreshToken(APIView):
    authentication_classes = []
    def post(self, request):
        try:
            refresh_token = request.COOKIES.get('refresh_token')

            if not refresh_token:
                return Response({
                    'result': 'refresh token不存在',
                },status=401)
            refresh = JWTRefreshToken(refresh_token)#自己检查是不是在有效期内，如果过期了会报异常
            if settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS']:
                refresh.set_jti()
                response = Response({
                    'result': 'success',
                    'access': str(refresh.access_token),
                })
                response.set_cookie(
                    key='refresh_token',
                    value=str(refresh),
                    httponly=True,
                    samesite='lax',
                    secure=not settings.DEBUG,
                    max_age=86400 * 7,
                )
                return response
            return Response({
                'result': 'success',
                'access': str(refresh.access_token),
            })
        except:
            return Response({
                'result': 'refresh token过期了',
            },status=401)#必须加401
