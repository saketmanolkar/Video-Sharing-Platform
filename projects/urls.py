from django.urls import path
from . import views
from api import views as api_views


urlpatterns = [
    path("",views.projects,name="projects"),
    path("project/<uuid:pk>/",views.project,name="project"),
    path("create-project/",views.create_project,name="create-project"),
    path("update-project/<uuid:pk>/",views.update_project,name="update-project"),
    path("delete-project/<uuid:pk>/",views.delete_project,name="delete-project"),
    path('fun-corner/', views.fun_corner, name='fun-corner'),
    path('create-playlist/', views.create_playlist, name='create-playlist'),
    path('update-playlist/<uuid:pk>/', views.update_playlist, name='update-playlist'),
    path('delete-playlist/<uuid:pk>/', views.delete_playlist, name='delete-playlist'),
    path('api/video-status/<uuid:video_id>/', views.video_status, name='video-status'),
    path('projects/', views.projects, name="projects-list"),
]
