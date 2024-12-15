from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.staticfiles.storage import staticfiles_storage
from django.templatetags.static import static
import json
from projects.services.video_services import VideoService
from users.services.follow_services import FollowService
from users.models import Profile

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
    
    def clear_profile_picture(self, profile):
        """Clear the profile picture and return the updated profile"""
        try:
            if profile.profile_pics:
                # Delete the physical file
                profile.profile_pics.delete(save=False)
                # Set the field to None
                profile.profile_pics = None
                profile.save()
            return True, "Profile picture cleared successfully"
        except Exception as e:
            return False, f"Error clearing profile picture: {str(e)}"
    
    def update_profile(self, profile, user_data, profile_form, should_clear_pic=False):
        """Update profile and user data"""
        try:
            # Update User model fields
            user = profile.user
            user.first_name = user_data.get('first_name')
            user.last_name = user_data.get('last_name')
            user.username = user_data.get('username').lower()
            user.save()

            # Handle profile picture clearing if requested
            if should_clear_pic:
                success, message = self.clear_profile_picture(profile)
                if not success:
                    return False, message

            # Save profile form
            if profile_form.is_valid():
                profile_form.save()
                return True, "Profile updated successfully"
            return False, "Invalid form data"

        except Exception as e:
            return False, f"Error updating profile: {str(e)}"
    
    def get_creator_studio_data(self, profile_id, profile_model):
        """Get creator studio data for a profile"""
        profile = self.get_profile(profile_id, profile_model)
        videos = profile.user.uploaded_videos.all()
        analytics_data = VideoService.get_creator_studio_analytics(videos)
        
        # Add default thumbnail URL to the context
        default_thumbnail = static('images/default.jpg')
        
        # Get followers and following profiles
        followers = Profile.objects.filter(user__in=profile.user.followers_set.values('user'))
        following = Profile.objects.filter(user__in=profile.user.following_set.values('following'))
        
        return {
            'profile': profile,
            'default_thumbnail': default_thumbnail,
            'video_analytics': analytics_data['video_analytics'],
            'followers': followers,  # Now contains Profile objects
            'following': following,  # Now contains Profile objects
        }

    def get_profile_data(self, profile_id, profile_model, current_user=None):
        """Get complete profile data including videos, history, and follow status"""
        profile = self.get_profile(profile_id, profile_model)
        follow_service = FollowService()
        
        # Get existing data
        videos = profile.user.uploaded_videos.all()[:2]
        view_history = profile.user.view_history.all()[:2]
        
        # Add follow-related data
        follow_stats = follow_service.get_follower_stats(profile)
        is_following = False
        if current_user and current_user.is_authenticated:
            is_following = follow_service.check_following_status(current_user, profile.user)
        
        # Add engagement metrics
        for video in videos:
            video.likes_count = VideoService.get_likes_count(video)
            video.dislikes_count = VideoService.get_dislikes_count(video)
        
        for history in view_history:
            history.video.likes_count = VideoService.get_likes_count(history.video)
            history.video.dislikes_count = VideoService.get_dislikes_count(history.video)
        
        return {
            'profile': profile,
            'videos': videos,
            'view_history': view_history,
            'followers_count': follow_stats['followers_count'],
            'following_count': follow_stats['following_count'],
            'is_following': is_following
        }

    def get_analytics_data(self, profile_id, profile_model):
        """Get analytics data for a profile"""
        profile = self.get_profile(profile_id, profile_model)
        videos = profile.user.uploaded_videos.all()
        analytics_data = VideoService.get_creator_studio_analytics(videos)
        
        return {
            'profile': profile,
            'video_analytics': analytics_data['video_analytics'],
            'chart_labels': json.dumps(analytics_data['chart_labels']),
            'chart_data': json.dumps(analytics_data['chart_data']),
            'daily_views_data': json.dumps(analytics_data['daily_views_data']),
            'hourly_views_data': json.dumps(analytics_data['hourly_views_data']),
        }