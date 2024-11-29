from django.shortcuts import get_object_or_404
import os
import logging
from django.core.cache import cache
import time
from django.utils import timezone
from datetime import timedelta
from projects.services.view_analytics import ViewAnalyticsService
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from users.services.follow_services import FollowService

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
    def get_user_like_status(video, user):
        """Get the like status for a specific user and video"""
        if user.is_authenticated:
            return video.likes.filter(user=user).first()
        return None
    
    @staticmethod
    def get_video_context(video, get_recommendations_func):
        """Get common video context data"""
        from projects.models import Video
        
        cache_key = f'video_context_{video.id}'
        context = cache.get(cache_key)
        
        if not context:
            recommended = get_recommendations_func(video)
            if not recommended.exists():
                recommended = Video.objects.exclude(id=video.id).order_by('-created_at')[:5]
            
            # Add is_following status
            is_following = False
            if hasattr(video, 'request_user') and video.request_user.is_authenticated:
                follow_service = FollowService()
                is_following = follow_service.check_following_status(video.request_user, video.uploader)
            
            context = {
                'video': video,
                'reviews': video.reviews.all().order_by('-created_at'),
                'tags': video.tags.all(),
                'recommended_videos': recommended,
                'likes_count': video.likes.filter(is_like=True).count(),
                'dislikes_count': video.likes.filter(is_like=False).count(),
                'user_like': VideoService.get_user_like_status(video, video.request_user),
                'is_following': is_following
            }
        else:
            # Update user-specific data even if context is cached
            if hasattr(video, 'request_user') and video.request_user.is_authenticated:
                follow_service = FollowService()
                context['is_following'] = follow_service.check_following_status(video.request_user, video.uploader)
                context['user_like'] = VideoService.get_user_like_status(video, video.request_user)
        
        return context
    
    @staticmethod
    def invalidate_video_cache(video_id):
        """Invalidate all caches for a video"""
        cache.delete(f'video_context_{video_id}')
    
    @staticmethod
    def update_video(video_id, data):
        """Update video and invalidate cache"""
        from projects.models import Video
        video = Video.objects.get(id=video_id)
        video.title = data['title']
        video.save()
        
        # Invalidate all related caches
        VideoService.invalidate_video_cache(video_id)
        cache.delete(f'video_context_{video_id}')
        cache.delete(f'video_{video_id}')  # Add any other related cache keys
    
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
    
    @staticmethod
    def get_creator_studio_analytics(videos):
        """Get all analytics data for creator studio"""
        
        video_analytics = {}
        chart_labels = []
        chart_data = []
        daily_views_data = {}
        hourly_views_data = {}
        analytics_service = ViewAnalyticsService()

        for video in videos:
            if hasattr(video, 'analytics'):
                video_id = str(video.id)
                
                # Basic analytics data
                video_analytics[video_id] = {
                    'title': video.analytics.title,
                    'thumbnail_url': video.thumbnail.url if video.thumbnail else None,
                    'total_views': video.analytics.total_views,
                    'total_likes': video.analytics.total_likes,
                    'total_dislikes': video.analytics.total_dislikes,
                    'total_comments': video.reviews.count(),
                    'created_at': video.analytics.created_at,
                }
                
                # Total views chart data
                chart_labels.append(video.analytics.title)
                chart_data.append(video.analytics.total_views)
                
                # Daily views data
                daily_views = analytics_service.get_views_over_time(video)
                if daily_views:
                    daily_views_data[video_id] = VideoService._process_daily_views(daily_views)
                
                # Hourly views data
                hourly_views = analytics_service.get_views_by_hour(video)
                if hourly_views:
                    hourly_views_data[video_id] = {
                        'labels': [view['hour'].strftime('%H:00') for view in hourly_views],
                        'data': [view['count'] for view in hourly_views]
                    }

        return {
            'video_analytics': video_analytics,
            'chart_labels': chart_labels,
            'chart_data': chart_data,
            'daily_views_data': daily_views_data,
            'hourly_views_data': hourly_views_data
        }
    
    @staticmethod
    def _process_daily_views(daily_views):
        """Helper method to process daily views data"""
        from django.utils import timezone
        from datetime import timedelta
        
        date_range = [(timezone.now() - timedelta(days=x)).date() for x in range(30)]
        views_dict = {view['day'].date(): view['count'] for view in daily_views}
        
        daily_data = []
        daily_labels = []
        
        for date in reversed(date_range):
            daily_labels.append(date.strftime('%Y-%m-%d'))
            daily_data.append(views_dict.get(date, 0))
        
        return {
            'labels': daily_labels,
            'data': daily_data
        }
    
    @staticmethod
    def search_videos(search_query):
        """Handle video search across multiple fields"""
        from django.db.models import Q
        from projects.models import Video  # Import here to avoid circular import
        
        if not search_query:
            return Video.objects.all().order_by('-created_at')
            
        return Video.objects.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(tags__name__icontains=search_query) |
            Q(uploader__username__icontains=search_query)
        ).distinct().order_by('-created_at')
    
    @staticmethod
    def get_paginated_videos(videos, page, items_per_page=9):
        """Handle video pagination and page range calculation"""
        paginator = Paginator(videos, items_per_page)
        
        try:
            paged_videos = paginator.page(page)
            page_number = int(page)
        except PageNotAnInteger:
            paged_videos = paginator.page(1)
            page_number = 1
        except EmptyPage:
            paged_videos = paginator.page(paginator.num_pages)
            page_number = paginator.num_pages

        # Calculate custom page range
        left_index = (page_number - 4) if (page_number - 4) > 0 else 1
        right_index = (page_number + 5) if (page_number + 5) < paginator.num_pages else paginator.num_pages
        custom_range = range(left_index, right_index + 1)
        
        return paged_videos, custom_range
    
    @staticmethod
    def handle_like_action(video, user, is_like):
        """Handle like/dislike action"""
        from projects.models import Like
        
        try:
            # Clear any cached context for this video
            cache.delete(f'video_context_{video.id}')
            
            like = Like.objects.filter(video=video, user=user).first()
            
            if like:
                if like.is_like == is_like:
                    like.delete()
                    action = 'removed'
                else:
                    like.is_like = is_like
                    like.save()
                    action = 'switched'
            else:
                Like.objects.create(
                    video=video,
                    user=user,
                    is_like=is_like
                )
                action = 'added'
                
            # Get fresh counts directly from database
            likes_count = video.likes.filter(is_like=True).count()
            dislikes_count = video.likes.filter(is_like=False).count()
            
            return {
                'status': 'success',
                'action': action,
                'likes_count': likes_count,
                'dislikes_count': dislikes_count
            }
            
        except Exception as e:
            logger.error(f"Error handling like: {str(e)}")
            return {'status': 'error', 'message': str(e)}

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
