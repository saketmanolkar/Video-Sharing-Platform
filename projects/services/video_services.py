from django.shortcuts import get_object_or_404
from django.conf import settings
import os
import logging
from django.core.cache import cache
import time


logger = logging.getLogger(__name__)

class VideoService:
    @staticmethod
    def get_video(video_id, model):
        return get_object_or_404(model, id=video_id)
    
    @staticmethod
    def record_view(video, user, ip_address, view_history_model):
        """Handle view recording with session-based tracking"""
        cache_key = f'view_{video.id}_{user.id if user else ip_address}_{int(time.time() / 300)}'
        
        if not cache.get(cache_key):
            view_history_model.objects.create(
                video=video,
                user=user,
                ip_address=ip_address
            )
            video.views += 1
            video.save()
            
            cache.set(cache_key, True, timeout=300)
    
    @staticmethod
    def get_video_context(video, get_recommendations_func):
        """Get common video context data"""
        from projects.models import Video  # Import here to avoid circular import
        
        cache_key = f'video_context_{video.id}'
        context = cache.get(cache_key)
        if not context:
            recommended = get_recommendations_func(video)
            if not recommended.exists():
                recommended = Video.objects.exclude(id=video.id).order_by('-created_at')[:5]
            
            context = {
                'video': video,
                'reviews': video.reviews.all().order_by('-created_at'),
                'tags': video.tags.all(),
                'recommended_videos': recommended,
            }
            cache.set(cache_key, context, timeout=3600)
        return context
    
    @staticmethod
    def invalidate_video_cache(video_id):
        """Invalidate all caches for a video"""
        cache.delete(f'video_context_{video_id}')
    
    @staticmethod
    def update_video(video_id, data):
        """Update video and invalidate cache"""
        from projects.models import Video  # Move import here to avoid circular import
        video = Video.objects.get(id=video_id)
        video.title = data['title']
        video.save()
        
        VideoService.invalidate_video_cache(video_id)
    
    @staticmethod
    def get_likes_count(video):
        """Get count of likes for video"""
        return video.likes.filter(is_like=True).count()
    
    @staticmethod
    def get_dislikes_count(video):
        """Get count of dislikes for video"""
        return video.likes.filter(is_like=False).count()
    
    @staticmethod
    def handle_video_save(video, *args, **kwargs):
        """Handle video save operations including encoding"""
        # Skip if we're already in a save operation
        if getattr(video, '_saving', False):
            return
        
        video._saving = True
        try:
            is_new_upload = not video.pk or (
                video.pk and 
                not video.encoded_versions and 
                hasattr(video, '_file_changed') and 
                video._file_changed
            )
            
            if is_new_upload:
                cache_key = f'thumbnail_processed_{video.pk}'
                cache.delete(cache_key)
            
            super(video.__class__, video).save(*args, **kwargs)  # Call the actual model save
            
            if is_new_upload and video.file:
                original_file = video.file.path
                from projects.signals import handle_video_encoding
                handle_video_encoding(sender=video.__class__, instance=video)
                
                if video.encoded_versions:
                    VideoService.cleanup_original_file(original_file)
                
                super(video.__class__, video).save(update_fields=['encoded_versions', 'file'])
        finally:
            video._saving = False
    
    @staticmethod
    def cleanup_original_file(file_path):
        """Delete original video file after encoding"""
        if os.path.exists(file_path):
            os.remove(file_path)

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
