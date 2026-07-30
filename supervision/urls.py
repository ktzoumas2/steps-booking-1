from django.urls import path

from supervision import views

urlpatterns = [
    path("", views.home, name="home"),
    path("sign-in/", views.signin_view, name="signin"),
    path("sign-in/sent/", views.signin_sent, name="signin_sent"),
    path("sign-in/<str:raw_token>/", views.signin_redeem, name="signin_redeem"),
    path("sign-out/", views.signout, name="signout"),
    path("language/", views.set_language, name="set_language"),
    path("sessions/", views.participant_home, name="participant_home"),
    path("sessions/mine/", views.participant_my_sessions, name="participant_my_sessions"),
    path(
        "sessions/participation/",
        views.participant_participation,
        name="participant_participation",
    ),
    path("my-sessions/", views.supervisor_home, name="supervisor_home"),
    path("all-sessions/", views.admin_home, name="admin_home"),
    path("sessions/new/", views.session_new, name="session_new"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("sessions/<int:pk>/edit/", views.session_edit, name="session_edit"),
    path("sessions/<int:pk>/cancel/", views.session_cancel, name="session_cancel"),
]
