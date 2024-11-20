from django.urls import path
from . import views


urlpatterns = [
    path("",views.projects,name="projects"),
    path("project/<str:pk>/",views.project,name="project"),
    path("create-project/",views.create_project,name="create-project"),
    path("update-project/<str:pk>/",views.update_project,name="update-project"),
    path("delete-project/<str:pk>/",views.delete_project,name="delete-project"),
    path("project/<str:pk>/add-review/", views.add_review, name="add-review"),
    path("review/<uuid:pk>/update/", views.update_review, name="update-review"),
    path("review/<str:pk>/delete/", views.delete_review, name="delete-review"),
    path('debug-videos/', views.debug_videos, name='debug_videos'),
    path('comments-stream/<uuid:video_id>/', views.comments_stream, name='comments-stream'),
]
