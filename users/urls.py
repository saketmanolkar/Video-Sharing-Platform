from django.urls import path
from . import views

urlpatterns = [
    path('profile/<str:pk>/', views.profile, name="profile"),
    path('profile/<str:pk>/videos/', views.user_videos, name="user-videos"),
    path('profile/<str:pk>/history/', views.user_history, name="user-history"),
    path('login-register/', views.login_user, name="login-page"),
    path('logout/', views.logout_user, name="logout-user"),
    path('register/', views.register_user, name="register-page"),
    path('profile/<str:pk>/edit/', views.update_profile, name="update-profile"),
    path('profile/<str:pk>/creator-studio/', views.creator_studio, name="creator-studio"),
    path('inbox/', views.inbox, name='inbox'),
    path('message/<str:pk>/', views.view_message, name='message'),
    path('create-message/<str:pk>/', views.create_message, name='create-message'),
    path('profile/<str:pk>/analytics/', views.analytics, name="analytics"),
    path('settings/', views.settings, name='settings'),
    path('report/<str:pk>/', views.report, name='report'),
   
]
