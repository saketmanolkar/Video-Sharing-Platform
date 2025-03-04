from django.urls import path
from . import views

urlpatterns = [
    path('profile/<uuid:pk>/', views.profile, name="profile"),
    path('profile/<uuid:pk>/videos/', views.user_videos, name="user-videos"),
    path('history/', views.user_history, name="user-history"),
    path('login-register/', views.login_user, name="login-page"),
    path('logout/', views.logout_user, name="logout-user"),
    path('register/', views.register_user, name="register-page"),
    path('update-profile/', views.update_profile, name="update-profile"),
    path('creator-studio/', views.creator_studio, name="creator-studio"),
    path('inbox/', views.inbox, name='inbox'),
    path('message/<uuid:pk>/', views.view_message, name='message'),
    path('create-message/<uuid:pk>/', views.create_message, name='create-message'),
    path('analytics/', views.analytics, name="analytics"),
    path('settings/', views.settings, name='settings'),
    path('report/<uuid:pk>/', views.report, name='report'),
    path('delete-message/<uuid:pk>/', views.delete_message, name="delete-message"),
]
