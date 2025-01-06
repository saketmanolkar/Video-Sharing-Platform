from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.staticfiles.storage import staticfiles_storage
from django.templatetags.static import static
import json
from projects.services.video_services import VideoService
from users.services.follow_services import FollowService
from users.models import Profile
from projects.services.analytics_service import AnalyticsService
from .cache_service import ProfileCache
from django.db.models import Q

class ProfileService:
    def __init__(self):
        self.profile_cache = ProfileCache()  # Initialize here
    
    def get_profile(self, profile_id, profile_model):
        """Get profile with cache"""
        # Try to get from cache first
        cached_data = self.profile_cache.get_profile_cache(profile_id)
        
        if cached_data:
            print("\n🎯 CACHE HIT: Found in cache")
            return profile_model.objects.get(id=profile_id)
        
        # If not in cache, get from DB
        print("\n💾 CACHE MISS: Getting from DB")
        profile = get_object_or_404(profile_model, id=profile_id)
        
        # Save to cache
        self.profile_cache.set_profile_cache(profile_id, profile)
        print(f"📝 Saved to cache: {profile_id}")
        
        return profile
    
    def get_user_videos(self, profile_id, profile_model, search_query=None):
        profile = get_object_or_404(profile_model, id=profile_id)
        videos = profile.user.uploaded_videos.all().order_by('-created_at')
        playlists = profile.user.playlists.all().order_by('-created_at')

        # Apply search if query exists
        if search_query:
            videos = videos.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()

            playlists = playlists.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            ).distinct()

        return {
            'profile': profile,
            'videos': videos,
            'playlists': playlists,
            'search_query': search_query
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
        
        # Get videos with their privacy status
        videos_with_privacy = videos.values('id', 'title', 'views', 'created_at', 'privacy_status', 'thumbnail')
        
        # Merge privacy status into analytics data
        for video in videos_with_privacy:
            video_id = str(video['id'])
            if video_id in analytics_data['video_analytics']:
                analytics_data['video_analytics'][video_id]['privacy_status'] = video['privacy_status']
        
        return {
            'profile': profile,
            'default_thumbnail': default_thumbnail,
            'video_analytics': analytics_data['video_analytics'],
            'followers': followers,
            'following': following,
        }

    def get_profile_data(self, profile_id, profile_model, current_user=None):
        """Get complete profile data including videos, history, and follow status"""
        profile = self.get_profile(profile_id, profile_model)  # This should handle caching
        
        follow_service = FollowService()
        
        # These are all dynamic data - don't cache
        videos = profile.user.uploaded_videos.all()[:2]
        view_history = profile.user.view_history.all()[:2]
        playlists = profile.user.playlists.all()[:2]
        
        # Dynamic follow data
        follow_stats = follow_service.get_follower_stats(profile)
        is_following = False
        if current_user and current_user.is_authenticated:
            is_following = follow_service.check_following_status(current_user, profile.user)
        
        # Dynamic engagement metrics
        for video in videos:
            video.likes_count = VideoService.get_likes_count(video)
            video.dislikes_count = VideoService.get_dislikes_count(video)
        
        for history in view_history:
            history.video.likes_count = VideoService.get_likes_count(history.video)
            history.video.dislikes_count = VideoService.get_dislikes_count(history.video)
        
        return {
            'profile': profile,  # This contains cached static data
            'videos': videos,    # Dynamic - fresh from DB
            'view_history': view_history,  # Dynamic - fresh from DB
            'playlists': playlists,        # Dynamic - fresh from DB
            'followers_count': follow_stats['followers_count'],  # Dynamic count
            'following_count': follow_stats['following_count'],  # Dynamic count
            'is_following': is_following    # User-specific - always fresh
        }

    def get_analytics_data(self, profile_id, profile_model):
        profile = self.get_profile(profile_id, profile_model)
        # Filter videos to only get the current user's videos
        videos = profile.user.uploaded_videos.filter(uploader=profile.user)
        analytics_data = VideoService.get_creator_studio_analytics(videos)
        
        return {
            'profile': profile,
            'video_analytics': analytics_data['video_analytics'],
            'chart_labels': json.dumps(analytics_data['chart_labels']),
            'chart_data': json.dumps(analytics_data['chart_data']),
            'daily_views_data': json.dumps(analytics_data['daily_views_data']),
            'hourly_views_data': json.dumps(analytics_data['hourly_views_data']),
            'likes_data': json.dumps(analytics_data['likes_data']),
            'comments_data': json.dumps(analytics_data['comments_data'])
        }