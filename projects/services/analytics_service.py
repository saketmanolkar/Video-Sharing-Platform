from django.db.models.functions import TruncDay, TruncHour
from django.db.models import Count, F
from django.utils import timezone
from datetime import timedelta

class AnalyticsService:
    # Existing view methods
    @staticmethod
    def get_views_over_time(video, days=30):
        """Get daily view counts for the specified period"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        daily_views = video.views_history.filter(
            viewed_at__gte=start_date
        ).annotate(
            day=TruncDay('viewed_at')
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        return daily_views

    @staticmethod
    def get_total_views(video):
        """Get total views count"""
        return video.views_history.count()

    @staticmethod
    def get_views_by_hour(video, days=7):
        """Get hourly view distribution"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        hourly_views = video.views_history.filter(
            viewed_at__gte=start_date
        ).annotate(
            hour=TruncHour('viewed_at')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        
        return hourly_views

    @staticmethod
    def get_viewer_growth(video):
        """Get cumulative viewer growth over time"""
        views = video.views_history.all().order_by('viewed_at')
        cumulative_views = []
        total = 0
        
        for view in views:
            total += 1
            cumulative_views.append({
                'date': view.viewed_at,
                'total_views': total
            })
        
        return cumulative_views

    # Moving existing likes/comments chart functionality here
    @staticmethod
    def get_likes_dislikes_data(videos):
        """Get likes and dislikes data for chart"""
        return {
            'labels': [video.title for video in videos],
            'data': {
                'likes': [video.analytics.total_likes if hasattr(video, 'analytics') else 0 for video in videos],
                'dislikes': [video.analytics.total_dislikes if hasattr(video, 'analytics') else 0 for video in videos]
            }
        }

    @staticmethod
    def get_comments_data(videos):
        """Get comments data for chart"""
        return {
            'labels': [video.title for video in videos],
            'data': [video.analytics.total_comments if hasattr(video, 'analytics') else 0 for video in videos]
        }

    @staticmethod
    def get_total_views_data(videos):
        """Get total views data for chart"""
        return {
            'labels': [video.title for video in videos],
            'data': [video.analytics.total_views if hasattr(video, 'analytics') else 0 for video in videos]
        }