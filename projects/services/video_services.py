from django.shortcuts import get_object_or_404
import os
import logging
from django.core.cache import cache
from projects.services.cache_service import ViewRecordingCache, VideoContextCache
import time
from django.utils import timezone
from datetime import timedelta
from projects.services.analytics_service import AnalyticsService
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from users.services.follow_services import FollowService
from django.db import connection
from django.utils.dateparse import parse_datetime


logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self):
        self.view_cache = ViewRecordingCache()
        self.context_cache = VideoContextCache()

    @staticmethod
    def get_video(video_id, model):
        return get_object_or_404(model, id=video_id)
    
    def record_view(self, video, user, ip_address, view_history_model):
        """Handle view recording with time-based cache tracking"""
        
        # Check if we can record the view in this time window
        if self.view_cache.can_record_view(
            video_id=video.id,
            user_id=user.id if user else None,
            ip_address=ip_address
        ):
            try:
                # 1. Create view history record
                view_history_model.objects.create(
                    video=video,
                    user=user,
                    ip_address=ip_address
                )
                
                # 2. Update video views count
                video.views += 1
                video.save()
                
                # 3. Update analytics
                try:
                    analytics = video.analytics
                    analytics.total_views = video.views
                    analytics.last_24h_views = self.get_period_views_count(video, 1)
                    analytics.last_7d_views = self.get_period_views_count(video, 7)
                    analytics.last_30d_views = self.get_period_views_count(video, 30)
                    analytics.save(update_fields=[
                        'total_views', 
                        'last_24h_views', 
                        'last_7d_views', 
                        'last_30d_views',
                        'updated_at'
                    ])
                    logger.info(f"✅ Updated view metrics for video: {video.title}")
                except Exception as e:
                    logger.error(f"❌ Error updating analytics: {str(e)}")
                    
            except Exception as e:
                logger.error(f"❌ Error recording view: {str(e)}")
    
    @staticmethod
    def get_user_like_status(video, user):
        """Get the like status for a specific user and video"""
        if user.is_authenticated:
            return video.likes.filter(user=user).first()
        return None
    
    def get_video_context(self, video, get_recommendations_func):
        """Get video context with caching for static data only"""
        from projects.models import ViewHistory
        cache_service = VideoContextCache()
        
        # Try to get static data from cache
        cached_data = cache_service.get_context(video.id)
        
        if cached_data:
            print("\n🔵 Using cached data for video:", video.id)
            # Use cached static data
            context = cached_data
            
            # Add fresh dynamic data
            context['recommended_videos'] = get_recommendations_func(video)
            context['views_count'] = ViewHistory.objects.filter(video=video).count()
            context['video'] = video  # Use full video object for template
            
        else:
            print("\n🟡 Cache miss - creating new context for video:", video.id)
            # Create new context with static data
            context = {
                'video': video,
                'tags': video.tags.all()
            }
            
            # Cache static data
            cache_service.set_context(video.id, context)
            print("✅ New data cached")
            
            # Add fresh dynamic data
            context['recommended_videos'] = get_recommendations_func(video)
            context['views_count'] = ViewHistory.objects.filter(video=video).count()
        
        return context
    
    @staticmethod
    def invalidate_video_cache(video_id):
        """Invalidate video context cache"""
        # Use the new cache service
        cache_service = VideoContextCache()
        cache_service.invalidate(video_id)
    
    
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
        if getattr(video, '_saving', False):
            return
        
        video._saving = True
        try:
            # Just save, and don't queue here
            super(video.__class__, video).save(*args, **kwargs)
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
            'created_at': parse_datetime(video.created_at) if isinstance(video.created_at, str) else video.created_at,
            
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
        analytics_service = AnalyticsService()
        
        # Filter for current user's videos only
        user = videos.first().uploader if videos.exists() else None
        user_videos = videos.filter(uploader=user)
        
        # Use AnalyticsService to get total views data
        views_data = analytics_service.get_total_views_data(user_videos)
        chart_labels = views_data['labels']
        chart_data = views_data['data']
        
        video_analytics = {}
        daily_views_data = {}
        hourly_views_data = {}

        for video in user_videos:
            if hasattr(video, 'analytics'):
                video_id = str(video.id)
                
                # Basic analytics data
                video_analytics[video_id] = {
                    'title': video.analytics.title,
                    'thumbnail_url': video.thumbnail.url if video.thumbnail else None,
                    'total_views': video.analytics.total_views,
                    'total_likes': video.analytics.total_likes,
                    'total_dislikes': video.analytics.total_dislikes,
                    'total_comments': video.analytics.total_comments,
                    'created_at': parse_datetime(video.created_at) if isinstance(video.created_at, str) else video.created_at,
                }
                
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

        # Get likes and comments data for filtered videos
        likes_data = analytics_service.get_likes_dislikes_data(user_videos)
        comments_data = analytics_service.get_comments_data(user_videos)

        return {
            'video_analytics': video_analytics,
            'chart_labels': chart_labels,
            'chart_data': chart_data,
            'daily_views_data': daily_views_data,
            'hourly_views_data': hourly_views_data,
            'likes_data': likes_data,
            'comments_data': comments_data
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
            # Debug log initial state
            initial_likes = video.likes.filter(is_like=True).count()
            initial_dislikes = video.likes.filter(is_like=False).count()
            logger.info(f"Initial state - Likes: {initial_likes}, Dislikes: {initial_dislikes}")
            
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
            
            # Debug log final state
            logger.info(f"""
                Like Action Debug:
                User: {user.username}
                Action: {action}
                Is Like: {is_like}
                Before - Likes: {initial_likes}, Dislikes: {initial_dislikes}
                After - Likes: {likes_count}, Dislikes: {dislikes_count}
            """)
            
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
