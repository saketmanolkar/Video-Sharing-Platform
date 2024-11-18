from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from users.models import Profile
from projects.models import ViewHistory

# Create your views here.

def profile(request, pk):
    profile = get_object_or_404(Profile, id=pk)
    
    context = {
        'profile': profile,
        'uploaded_videos': profile.user.videos.all()[:2],  # For uploaded videos section
        'view_history': profile.user.view_history.all()[:2]  # For viewing history section
    }
    return render(request, "users/profile.html", context)

def user_videos(request, pk):
    profile = get_object_or_404(Profile, id=pk)
    videos = profile.user.videos.all().order_by('-created_at')
    
    context = {
        'profile': profile,
        'videos': videos
    }
    return render(request, "projects/user_video.html", context)

def user_history(request, pk):
    profile = get_object_or_404(Profile, id=pk)
    # Get the videos from view history
    history_entries = profile.user.view_history.all().order_by('-viewed_at')
    history_videos = [entry.video for entry in history_entries]
    
    context = {
        'profile': profile,
        'history_videos': history_videos
    }
    return render(request, "projects/view_history.html", context)
