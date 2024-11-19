from django.shortcuts import render, get_object_or_404
from users.models import Profile
from .services.user_services import ProfileService
from .services.follow_services import FollowService

def profile(request, pk):

    profile_service = ProfileService()
    profile = profile_service.get_profile(pk, Profile)

    context = {
        'profile': profile,
        'videos': profile.user.uploaded_videos.all()[:2],
        'view_history': profile.user.view_history.all()[:2],
    }
    return render(request, "users/profile.html", context)

def user_videos(request, pk):
    profile_service = ProfileService()
    context = profile_service.get_user_videos(pk)
    return render(request, "projects/user_video.html", context)

def user_history(request, pk):
    profile_service = ProfileService()
    context = profile_service.get_user_history(pk)
    return render(request, "projects/view_history.html", context)

def login_register(request):
    return render(request, "users/login_register.html")