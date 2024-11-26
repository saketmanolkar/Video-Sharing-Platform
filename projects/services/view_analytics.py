from django.db.models.functions import TruncDay, TruncHour
from django.db.models import Count, F
from django.utils import timezone
from datetime import timedelta

class ViewAnalyticsService:
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