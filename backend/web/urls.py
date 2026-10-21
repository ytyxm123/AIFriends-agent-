
from django.urls import path, re_path

from web.views.create.character.create import CreateCharacterView
from web.views.create.character.get_list import GetListCharacterView
from web.views.create.character.get_single import GetSingleView
from web.views.create.character.remove import RemoveCharacterView
from web.views.create.character.update import UpdateCharacterView
from web.views.create.character.voice.getlist import GetVoiceList
from web.views.friend.get_list import GetListFriendView
from web.views.friend.get_or_create import GetOrCreateFriendView
from web.views.friend.message.asr.asr import ASRView
from web.views.friend.message.chat.chat import MessageChatView
from web.views.friend.message.get_history import GetHistoryView
from web.views.friend.remove import RemoveFriendView
from web.views.homepage.index import HomepageIndexView
from web.views.index import index
from web.views.mcp.servers import (
    McpServerDetailView,
    McpServerListCreateView,
    McpServerActionView,
)
from web.views.mcp.tools import McpToolListView, McpToolToggleView
from web.views.observability.traces import (
    TraceDetailView,
    TraceListView,
    TraceStatsView,
)
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

    path('api/homePage/index/',HomepageIndexView.as_view()),

    path('api/remove/friends/', RemoveFriendView.as_view()),

    path('api/get_list/friends/', GetListFriendView.as_view()),

    path('api/get_or_create/friends/', GetOrCreateFriendView.as_view()),

    path('api/friend/message/chat/', MessageChatView.as_view()),

    path('api/friend/message/get_history/', GetHistoryView.as_view()),

    path('api/friend/message/asr/asr/', ASRView.as_view()),

    path('api/observability/stats/', TraceStatsView.as_view()),
    path('api/observability/traces/', TraceListView.as_view()),
    path('api/observability/traces/<uuid:trace_id>/', TraceDetailView.as_view()),

    path('api/mcp/servers/', McpServerListCreateView.as_view()),
    path('api/mcp/servers/<int:server_id>/', McpServerDetailView.as_view()),
    path('api/mcp/servers/<int:server_id>/<str:action>/', McpServerActionView.as_view()),
    path('api/mcp/tools/', McpToolListView.as_view()),
    path('api/mcp/tools/<int:tool_id>/toggle/', McpToolToggleView.as_view()),

    path('api/create/character/voice/get_list/', GetVoiceList.as_view()),
    path('',index),
    re_path(r'^(?!api/|media/|static/|assets/).*$', index)
]
