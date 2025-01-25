from django.urls import path
from . import views # Adjust the import based on your structure

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    # Auth
    path('users/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('users/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/token-from-session/', views.get_token_for_user, name='token-from-session'),

    # Routes
    path('', views.getRoutes, name='getRoutes'),

    # Projects
    path('projects/', views.getProjects),
    path('projects/<str:pk>/', views.getProject),

    # Likes
    path('projects/<str:pk>/like/', views.api_handle_like, name='api-handle-like'),
    
    # Reviews
    path('projects/<str:pk>/reviews/', views.review_actions),
    path('projects/<str:pk>/reviews/<str:review_id>/', views.review_actions),
    path('projects/<str:pk>/reviews/stream/', views.stream_reviews),

    # Follow
    path('users/<str:pk>/follow/', views.api_handle_follow, name='api-handle-follow'),

    # Stream Video
    path('projects/<str:pk>/stream/', views.stream_video_api, name='api-stream-video'),

    # Debug
    path('debug-videos/', views.api_debug_videos, name='api-debug-videos'),

    # Video Stats
    path('video-stats/', views.update_video_stats, name='api-video-stats'),

    # Generate Report
    path('generate-report/', views.generate_report, name='generate_report'),

    # Generate Speech
    path('generate-speech/', views.generate_speech, name='generate_speech'),

    # Serve Audio
    path('audio/<str:profile_id>/<str:report_type>/', views.serve_audio, name='serve_audio'),

    # Check TTS Status
    path('check-tts-status/<str:username>/', views.check_tts_status, name='check_tts_status'),

]
