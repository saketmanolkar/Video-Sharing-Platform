from django.urls import path
from . import views
from api import views as api_views


urlpatterns = [
    path("",views.projects,name="projects"),
    path("project/<str:pk>/",views.project,name="project"),
    path("video/stream/<str:pk>/", views.stream_video, name="stream-video"),
    path("create-project/",views.create_project,name="create-project"),
    path("update-project/<str:pk>/",views.update_project,name="update-project"),
    path("delete-project/<str:pk>/",views.delete_project,name="delete-project"),
    path('debug-videos/', views.debug_videos, name='debug_videos'),
    path('fun-corner/', views.fun_corner, name='fun-corner'),
    path('profile/<uuid:pk>/create-playlist/', views.create_playlist, name='create-playlist'),
    path('update-playlist/<str:pk>/', views.update_playlist, name='update-playlist'),
    path('delete-playlist/<str:pk>/', views.delete_playlist, name='delete-playlist'),
    path('api/video-status/<uuid:video_id>/', views.video_status, name='video-status'),
    path('projects/', views.projects, name="projects-list"),
]
