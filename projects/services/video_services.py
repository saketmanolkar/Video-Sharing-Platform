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
from django.db.models import Count, Q
from django.db.models.functions import TruncDay, ExtractHour
import uuid


logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self):
        self.view_cache = ViewRecordingCache()
        self.context_cache = VideoContextCache()

    @staticmethod
    def get_video(video_id, model, select_related_fields=None, prefetch_related_fields=None):
        """
        Get a video by ID with optional select_related and prefetch_related fields to reduce queries
        """
        queryset = model.objects
        
        # If select_related fields are provided, use them to fetch related data in one query
        if select_related_fields:
            if isinstance(select_related_fields, (list, tuple)):
                queryset = queryset.select_related(*select_related_fields)
            else:
                queryset = queryset.select_related(select_related_fields)
        
        # Include analytics in the query
        queryset = queryset.select_related('analytics')
        
        # If prefetch_related fields are provided, use them to fetch related data in one query
        if prefetch_related_fields:
            if isinstance(prefetch_related_fields, (list, tuple)):
                queryset = queryset.prefetch_related(*prefetch_related_fields)
            else:
                queryset = queryset.prefetch_related(prefetch_related_fields)
        
        # Always prefetch tags to avoid duplicate queries
        queryset = queryset.prefetch_related('tags')
        
        return get_object_or_404(queryset, id=video_id)
    
    def record_view(self, video, user, ip_address, view_history_model):
        """Handle view recording with time-based cache tracking"""
        from django.db import transaction
        from projects.models import Video
        
        if not video.processed:
            print(f"⏳ Skipping view record creation - video {video.id} still processing")
            return None
        
        view_history = None
        
        if self.view_cache.can_record_view(
            video_id=video.id,
            user_id=user.id if user else None,
            ip_address=ip_address
        ):
            try:
                # Wrap all operations in a transaction
                with transaction.atomic():
                    # Get video with lock to prevent race conditions
                    video = Video.objects.select_for_update().get(id=video.id)
                    
                    # 1. Create view history record
                    view_history = view_history_model.objects.create(
                        video=video,
                        user=user,
                        ip_address=ip_address
                    )
                    
                    # 2. Update video views count
                    video.views += 1
                    video.save()
                    
                    # Note: Analytics update is now handled by the signal
                    
            except Exception as e:
                logger.error(f"❌ Error recording view: {str(e)}")
        
        return view_history

    def get_all_period_views_counts_optimized(self, video):
        """Get views for all time periods in a single query"""
        from django.db.models import Count, Q
        
        # Calculate time thresholds
        now = timezone.now()
        day_1 = now - timedelta(days=1)
        day_7 = now - timedelta(days=7)
        day_30 = now - timedelta(days=30)
        
        # Print debug info
        print(f"🔍 Running optimized query for video {video.id}")
        print(f"Time thresholds: 1d={day_1}, 7d={day_7}, 30d={day_30}")
        
        # Execute a single query with conditional counts
        result = video.views_history.aggregate(
            day_1=Count('id', filter=Q(viewed_at__gte=day_1)),
            day_7=Count('id', filter=Q(viewed_at__gte=day_7)),
            day_30=Count('id', filter=Q(viewed_at__gte=day_30)),
            total=Count('id')  # Add total count
        )
        
        print(f"📊 Query result: {result}")
        
        return result
    
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
                'tags': list(video.tags.all())  # Use list() to ensure we use the prefetched data
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
    def get_likes_count_optimized(video):
        """Get count of likes for video"""
        return video.analytics.total_likes

    @staticmethod
    def get_dislikes_count(video):
        """Get count of dislikes for video"""
        return video.likes.filter(is_like=False).count()
    
    @staticmethod
    def get_dislikes_count_optimized(video):
        """Get count of dislikes for video"""
        return video.analytics.total_dislikes
    
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
        
        # Get first video in one query instead of two
        first_video = videos.first()
        user = first_video.uploader if first_video else None
        user_videos = videos.filter(uploader=user).select_related('analytics')
        
        # Use AnalyticsService to get total views data
        views_data = analytics_service.get_total_views_data(user_videos)
        # Extract labels and data from the new format
        chart_labels = [item['video_title'] for item in views_data]
        chart_data = [item['total_views'] for item in views_data]
        
        video_analytics = {}
        videos_with_analytics = []
        daily_views_data = {}
        hourly_views_data = {}

        # First pass - collect basic info and build list of videos with analytics
        for video in user_videos:
            if video.analytics:
                video_id = str(video.id)
                videos_with_analytics.append(video)
                
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

                #daily_views_data[video_id] = VideoService.get_views_over_time(video)
                #hourly_views_data[video_id] = VideoService.get_views_by_hour(video)
        
        # Get views data in bulk for all videos at once
        daily_views_data = VideoService.get_bulk_views_over_time(videos_with_analytics)
        hourly_views_data = VideoService.get_bulk_views_by_hour(videos_with_analytics)  # You'll need to implement this too
        
        # Get likes and comments data for filtered videos
        likes_data = analytics_service.get_likes_dislikes_data(user_videos)
        comments_data = analytics_service.get_comments_data(user_videos)
        watch_time_data = analytics_service.get_watch_time_data(user_videos)
        completion_rate_data = analytics_service.get_completion_rate_data(user_videos)
        avg_watch_time_data = analytics_service.get_avg_watch_time_for_user_data(user_videos)
        avg_completion_rate_data = analytics_service.get_avg_completion_rate_for_user_data(user_videos)

        return {
            'video_analytics': video_analytics,
            'chart_labels': chart_labels,
            'chart_data': chart_data,
            'daily_views_data': daily_views_data,
            'hourly_views_data': hourly_views_data,
            'watch_time_data': watch_time_data,
            'completion_rate_data': completion_rate_data,
            'avg_watch_time_data': avg_watch_time_data,
            'avg_completion_rate_data': avg_completion_rate_data,
            'likes_data': likes_data,
            'comments_data': comments_data
        }
    @staticmethod
    def get_views_over_time(video, days=30):
        """Get views over time for a single video with robust error handling"""
        from django.db.models import Count
        from django.db.models.functions import TruncDay
        
        # Handle case where video is None
        if not video:
            # Return empty data structure with correct format
            return {
                'labels': [],
                'data': []
            }
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        date_range = [(end_date - timedelta(days=x)).date() for x in range(days)]
        
        try:
            # Check if video has views_history attribute
            if hasattr(video, 'views_history'):
                daily_views_rows = list(video.views_history.filter(
                    viewed_at__gte=start_date
                ).annotate(
                    day=TruncDay('viewed_at')
                ).values('day').annotate(
                    count=Count('id')
                ))
                
                # Create dictionary with date objects as keys (not datetime objects)
                daily_views_dict = {
                    row['day'].date(): row['count']  # Convert datetime to date for key matching
                    for row in daily_views_rows
                }
            else:
                # No views_history available
                daily_views_dict = {}
        except Exception as e:
            # Log the error but continue with empty data
            print(f"Error getting views for video {video.id}: {str(e)}")
            daily_views_dict = {}
        
        # Always return properly formatted response
        return {
            'labels': [d.strftime('%Y-%m-%d') for d in reversed(date_range)],
            'data': [daily_views_dict.get(d, 0) for d in reversed(date_range)]
        }
    
    @staticmethod
    def get_views_by_hour(video, days=30):
        """Get hourly view distribution"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Force single evaluation with list()
        hourly_views_list = list(video.views_history.filter(
            viewed_at__gte=start_date
        ).annotate(
            hour=ExtractHour('viewed_at')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour'))
        
        # Return formatted data directly
        return {
            'labels': [f"{str(row['hour']).zfill(2)}:00" for row in hourly_views_list],
            'data': [row['count'] for row in hourly_views_list]
        }
    
    @staticmethod
    def search_videos(search_query):
        """Handle video search across multiple fields with optimized queries"""
        from django.db.models import Q, Prefetch
        from projects.models import Video, Tag
        
        # Optimize tag prefetch to only get needed fields
        tags_prefetch = Prefetch(
            'tags',
            queryset=Tag.objects.only('name', 'id'),
        )
        
        base_query = Video.objects.select_related(
            'uploader',          # Get user data
            'uploader__profile'  # Get profile data
        ).prefetch_related(
            'tags'              # Get all tags in one query
        )
        
        if not search_query:
            return base_query.order_by('-created_at')
            
        return base_query.filter(
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

    @staticmethod
    def get_videos_with_reactions(videos):
        """Get likes and dislikes counts for multiple videos in bulk"""
        from django.db.models import Count, Q
        from projects.models import Video
        
        # Get all video IDs
        video_ids = [video.id for video in videos]
        
        # Get counts in a single query using conditional aggregation
        reactions = Video.objects.filter(id__in=video_ids).annotate(
            likes_count=Count('likes', filter=Q(likes__is_like=True)),
            dislikes_count=Count('likes', filter=Q(likes__is_like=False))
        ).values('id', 'likes_count', 'dislikes_count')
        
        # Create a lookup dictionary
        reaction_lookup = {
            str(r['id']): {
                'likes': r['likes_count'],
                'dislikes': r['dislikes_count']
            } for r in reactions
        }
        
        return reaction_lookup

    @staticmethod
    def get_bulk_views_over_time(videos, days=30):
        """Get views over time for multiple videos in a single query (truly optimized)"""
        from django.db.models import Count
        from django.db.models.functions import TruncDay
        from projects.models import ViewHistory
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        date_range = [(end_date - timedelta(days=x)).date() for x in range(days)]
        
        # If no videos, return empty dict
        if not videos:
            return {}
        
        # Get all video IDs
        video_ids = [video.id for video in videos]
        
        # Make a SINGLE query for ALL videos
        all_daily_views = list(ViewHistory.objects.filter(
            video_id__in=video_ids,
            viewed_at__gte=start_date
        ).annotate(
            day=TruncDay('viewed_at')
        ).values('day', 'video_id').annotate(
            count=Count('id')
        ))
        
        # Organize by video_id
        views_by_video = {}
        for row in all_daily_views:
            video_id = str(row['video_id'])
            if video_id not in views_by_video:
                views_by_video[video_id] = {}
            
            # Convert datetime to date for key matching
            day_date = row['day'].date()
            views_by_video[video_id][day_date] = row['count']
        
        # Format results for each video
        result_by_video = {}
        for video in videos:
            video_id = str(video.id)
            
            # Get this video's data (or empty dict if none)
            video_data = views_by_video.get(video_id, {})
            
            # Format exactly as in original function
            result_by_video[video_id] = {
                'labels': [d.strftime('%Y-%m-%d') for d in reversed(date_range)],
                'data': [video_data.get(d, 0) for d in reversed(date_range)]
            }
        
        return result_by_video

    @staticmethod
    def get_bulk_views_by_hour(videos, days=30):
        """Get hourly views for multiple videos in a single query (truly optimized)"""
        from django.db.models import Count
        from django.db.models.functions import ExtractHour
        from projects.models import ViewHistory
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # If no videos, return empty dict
        if not videos:
            return {}
        
        # Get all video IDs
        video_ids = [video.id for video in videos]
        
        # Make a SINGLE query for ALL videos
        all_hours_data = list(ViewHistory.objects.filter(
            video_id__in=video_ids,
            viewed_at__gte=start_date
        ).annotate(
            hour=ExtractHour('viewed_at')
        ).values('hour', 'video_id').annotate(
            count=Count('id')
        ).order_by('video_id', 'hour'))
        
        # Organize by video_id
        hours_by_video = {}
        for row in all_hours_data:
            video_id = str(row['video_id'])
            if video_id not in hours_by_video:
                hours_by_video[video_id] = []
            
            hours_by_video[video_id].append({
                'hour': row['hour'],
                'count': row['count']
            })
        
        # Format results for each video
        result_by_video = {}
        for video in videos:
            video_id = str(video.id)
            
            # Get this video's data (or empty list if none)
            video_data = hours_by_video.get(video_id, [])
            
            # Format in the same way as the original function
            result_by_video[video_id] = {
                'labels': [f"{str(item['hour']).zfill(2)}:00" for item in video_data],
                'data': [item['count'] for item in video_data]
            }
        
        return result_by_video

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
