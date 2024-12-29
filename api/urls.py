from django.urls import path
from . import views

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('users/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('users/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/token-from-session/', views.get_token_for_user, name='token-from-session'),

    path('', views.getRoutes, name='getRoutes'),
    path('projects/', views.getProjects),
    path('projects/<str:pk>/', views.getProject),
    path('projects/<str:pk>/like/', views.ProjectLike, name='project-like'),
    
    # Reviews - Put stream URL first and separate from review_actions
    path('projects/<str:pk>/reviews/stream/', views.stream_reviews),
    path('projects/<str:pk>/reviews/', views.review_actions),
    path('projects/<str:pk>/reviews/<str:review_id>/', views.review_actions),
]
