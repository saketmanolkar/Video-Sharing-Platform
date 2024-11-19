from django.shortcuts import get_object_or_404
from django.conf import settings
import os
import logging
from django.core.cache import cache
from projects.models import Video
import time

logger = logging.getLogger(__name__)

class VideoService:
    @staticmethod
    def get_video(video_id, model):
        return get_object_or_404(model, id=video_id)
    
    @staticmethod
    def record_view(video, user, ip_address, view_history_model):
        """Handle view recording with session-based tracking"""
        # Create cache key that expires with browser session
        cache_key = f'view_{video.id}_{user.id if user else ip_address}_{int(time.time() / 300)}'
        
        # Check if view was recorded in current 5-minute window
        if not cache.get(cache_key):
            # Record view
            view_history_model.objects.create(
                video=video,
                user=user,
                ip_address=ip_address
            )
            video.views += 1
            video.save()
            
            # Cache for current 5-minute window only
            cache.set(cache_key, True, timeout=300)
    
    @staticmethod
    def get_video_context(video, get_recommendations_func):
        """Get common video context data"""
        cache_key = f'video_context_{video.id}'
        context = cache.get(cache_key)
        if not context:
            # Get recommendations using multiple methods
            recommended = get_recommendations_func(video)
            if not recommended.exists():
                # Fallback to recent videos if no recommendations
                recommended = Video.objects.exclude(id=video.id).order_by('-created_at')[:5]
            
            context = {
                'video': video,
                'reviews': video.reviews.all().order_by('-created_at'),
                'tags': video.tags.all(),
                'recommended_videos': recommended,
            }
            cache.set(cache_key, context, timeout=3600)  # Cache for 1 hour
        return context
    
    @staticmethod
    def invalidate_video_cache(video_id):
        """Invalidate all caches for a video"""
        cache.delete(f'video_context_{video_id}')
    
    @staticmethod
    def update_video(video_id, data):
        """Update video and invalidate cache"""
        video = Video.objects.get(id=video_id)
        video.title = data['title']
        video.save()
        
        VideoService.invalidate_video_cache(video_id)

class UtilityService:
    @staticmethod
    def get_client_ip(request):
        """Get client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
