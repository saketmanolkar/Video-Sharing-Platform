from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from users.models import Profile
from projects.models import ViewHistory

# Create your views here.

def profile(request, pk):
    profile = get_object_or_404(Profile, id=pk)
    
    context = {
        'profile': profile,
        'videos': profile.user.uploaded_videos.all()[:2],
        'view_history': profile.user.view_history.all()[:2]
    }
    return render(request, "users/profile.html", context)

def user_videos(request, pk):
    profile = get_object_or_404(Profile, id=pk)
    videos = profile.user.uploaded_videos.all().order_by('-created_at')
    
    context = {
        'profile': profile,
        'videos': videos
    }
    return render(request, "projects/user_video.html", context)

def user_history(request, pk):
    profile = get_object_or_404(Profile, id=pk)
    history_entries = profile.user.view_history.all().order_by('-viewed_at')
    history_videos = [entry.video for entry in history_entries]
    
    context = {
        'profile': profile,
        'history_videos': history_videos
    }
    return render(request, "projects/view_history.html", context)
