
from django.urls import path, re_path

from web.views.create.character.create import CreateCharacterView
from web.views.create.character.get_list import GetListCharacterView
from web.views.create.character.get_single import GetSingleView
from web.views.create.character.remove import RemoveCharacterView
from web.views.create.character.update import UpdateCharacterView
from web.views.index import index
from web.views.user.account.get_user_info import GetUserInfoView
from web.views.user.account.login import LoginView
from web.views.user.account.logout import LogoutView
from web.views.user.account.refresh_token import RefreshToken
from web.views.user.account.register import RegisterView
from web.views.user.profile.update import UpdateProfileView

urlpatterns = [

    path('api/user/login/', LoginView.as_view()),
    path('api/user/logout/', LogoutView.as_view()),
    path('api/user/register/', RegisterView.as_view()),
    path('api/user/refresh/', RefreshToken.as_view()),
    path('api/user/getInfo/', GetUserInfoView.as_view()),

    path('api/user/profile/update', UpdateProfileView.as_view()),

    path('api/create/character/', CreateCharacterView.as_view()),

    path('api/update/character/', UpdateCharacterView.as_view()),

    path('api/remove/character/', RemoveCharacterView.as_view()),

    path('api/get_single/character/',GetSingleView.as_view()),

    path('api/get_list/character/',GetListCharacterView.as_view()),
    path('',index),
    re_path(r'^(?!media/|static/|assets/).*$', index)
]
