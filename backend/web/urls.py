
from django.urls import path


from web.views.index import index
from web.views.user.account.login import LoginView
from web.views.user.account.logout import LogoutView
from web.views.user.account.refresh_token import RefreshToken
from web.views.user.account.register import RegisterView

urlpatterns = [

    path('api/user/login/', LoginView.as_view()),
    path('api/user/logout/', LogoutView.as_view()),
    path('api/user/register/', RegisterView.as_view()),
    path('api/user/refresh/', RefreshToken.as_view()),
    path('',index),
]
