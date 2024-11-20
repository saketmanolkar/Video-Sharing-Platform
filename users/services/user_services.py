from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.staticfiles.storage import staticfiles_storage

class ProfileService:
    def get_profile(self, profile_id, profile_model):
        return get_object_or_404(profile_model, id=profile_id)
    
    def get_user_videos(self, profile_id, profile_model):
        profile = get_object_or_404(profile_model, id=profile_id)
        return {
            'profile': profile,
            'videos': profile.user.uploaded_videos.all().order_by('-created_at')
        }
    
    def get_user_history(self, profile_id, profile_model):
        profile = get_object_or_404(profile_model, id=profile_id)
        history_entries = profile.user.view_history.all().order_by('-viewed_at')
        history_videos = [entry.video for entry in history_entries]
        return {
            'profile': profile,
            'history_videos': history_videos
        }
    
    def get_total_views(self, user):
        from projects.models import Video
        return Video.objects.filter(uploader=user).aggregate(
            total_views=models.Sum('views')
        )['total_views'] or 0
    
    def get_profile_picture_url(self, profile):
        """Get profile picture URL with proper fallback"""
        if profile.profile_pics:
            return profile.profile_pics.url
        return staticfiles_storage.url('images/user-default.png')