from django.urls import path
from . import views

urlpatterns = [
    path('profile/<str:pk>/', views.profile, name="profile"),
    path('profile/<str:pk>/videos/', views.user_videos, name="user-videos"),
    path('profile/<str:pk>/history/', views.user_history, name="user-history"),
]
