from django.shortcuts import get_object_or_404
from django.conf import settings
import os
import logging
from django.core.cache import cache
import time
from django.utils import timezone
from datetime import timedelta


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
            # Create view history record
            view_history_model.objects.create(
                video=video,
                user=user,
                ip_address=ip_address
            )
            
            # Update video views count
            video.views += 1
            video.save()
            
            # Update analytics immediately
            try:
                analytics = video.analytics
                analytics.total_views = video.views
                analytics.last_24h_views = VideoService.get_period_views_count(video, 1)
                analytics.last_7d_views = VideoService.get_period_views_count(video, 7)
                analytics.last_30d_views = VideoService.get_period_views_count(video, 30)
                analytics.save(update_fields=[
                    'total_views', 
                    'last_24h_views', 
                    'last_7d_views', 
                    'last_30d_views', 
                    'updated_at'
                ])
                logger.info(f"✅ Updated view metrics immediately for video: {video.title}")
            except Exception as e:
                logger.error(f"❌ Error updating analytics on view: {str(e)}")
            
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
    
    @staticmethod
    def get_views_count(video):
        """Get total views for video"""
        return video.views
    
    @staticmethod
    def get_comments_count(video):
        """Get count of comments/reviews for video"""
        return video.reviews.count()
    
    @staticmethod
    def get_period_views_count(video, days):
        """Get views for a specific time period"""
        now = timezone.now()
        return video.views_history.filter(
            viewed_at__gte=now - timedelta(days=days)
        ).count()
    
    @staticmethod
    def get_analytics_data(video):
        """Get all analytics data for a video"""
        now = timezone.now()
        return {
            # Basic Info
            'video': video,
            'uploader': video.uploader,
            'title': video.title,
            'created_at': video.created_at,
            
            # Engagement Metrics
            'total_views': VideoService.get_views_count(video),
            'total_comments': VideoService.get_comments_count(video),
            'total_likes': VideoService.get_likes_count(video),
            'total_dislikes': VideoService.get_dislikes_count(video),
            
            # Time-based Metrics
            'last_24h_views': VideoService.get_period_views_count(video, 1),
            'last_7d_views': VideoService.get_period_views_count(video, 7),
            'last_30d_views': VideoService.get_period_views_count(video, 30)
        }

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
