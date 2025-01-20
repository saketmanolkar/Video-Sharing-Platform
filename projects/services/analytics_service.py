from django.db.models.functions import TruncDay, TruncHour, ExtractHour, ExtractIsoWeekDay
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
    def get_views_by_hour(video, days=30):
        """Get hourly view distribution"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        hourly_views = video.views_history.filter(
            viewed_at__gte=start_date
        ).annotate(
            hour=ExtractHour('viewed_at')
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

    @staticmethod
    def get_peak_viewing_hour(user_videos, days=30):
        """Get peak viewing hour across all user videos by comparing hourly distributions"""
        hourly_totals = {i: 0 for i in range(24)}
        
        # Get hourly distribution for each video and aggregate
        for video in user_videos:
            hourly_views = AnalyticsService.get_views_by_hour(video, days)
            for view in hourly_views:
                hour = view['hour']
                count = view['count']
                hourly_totals[hour] += count
        
        
        
        # Find all hours with maximum views
        max_views = max(hourly_totals.values())
        peak_hours = [hour for hour, views in hourly_totals.items() if views == max_views]
        
        
        def format_hour(hour):
            """Helper function to correctly format hour in 12-hour format"""
            if hour == 0:
                return "12 AM"
            elif hour == 12:
                return "12 PM"
            elif hour < 12:
                return f"{hour} AM"
            else:
                return f"{hour - 12} PM"
        
        # If there are ties, take up to 2 earliest hours
        if len(peak_hours) == 1:
            return format_hour(peak_hours[0])
        else:
            # Sort and take first two peak hours
            peak_hours = sorted(peak_hours)[:2]
            return f"{format_hour(peak_hours[0])} & {format_hour(peak_hours[1])}"

    @staticmethod
    def get_views_by_weekday(video, days=30):
        """Get weekly view distribution"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        weekday_views = video.views_history.filter(
            viewed_at__gte=start_date
        ).annotate(
            weekday=ExtractIsoWeekDay('viewed_at')  # 1=Monday, 7=Sunday
        ).values('weekday').annotate(
            count=Count('id')
        ).order_by('weekday')
        
        # Convert ISO weekdays (1-7) to more common format (0-6, Sunday=0)
        weekday_mapping = {
            1: 'Monday',
            2: 'Tuesday',
            3: 'Wednesday',
            4: 'Thursday',
            5: 'Friday',
            6: 'Saturday',
            7: 'Sunday'
        }
        
        # Add weekday names to the queryset result
        for entry in weekday_views:
            entry['day_name'] = weekday_mapping[entry['weekday']]
        
        return weekday_views

    @staticmethod
    def get_peak_viewing_day(user_videos, days=30):
        """Get peak viewing day(s) across all user videos"""
        weekday_totals = {
            1: 0,  # Monday
            2: 0,  # Tuesday
            3: 0,  # Wednesday
            4: 0,  # Thursday
            5: 0,  # Friday
            6: 0,  # Saturday
            7: 0   # Sunday
        }
        
        # Get weekly distribution for each video and aggregate
        for video in user_videos:
            weekday_views = AnalyticsService.get_views_by_weekday(video, days)
            for view in weekday_views:
                weekday = view['weekday']
                count = view['count']
                weekday_totals[weekday] += count
        
      
        
        # Find all days with maximum views
        max_views = max(weekday_totals.values())
        peak_days = [day for day, views in weekday_totals.items() if views == max_views]
   
        # Day name mapping
        day_mapping = {
            1: 'Monday',
            2: 'Tuesday',
            3: 'Wednesday',
            4: 'Thursday',
            5: 'Friday',
            6: 'Saturday',
            7: 'Sunday'
        }
        
        # Return up to 2 peak days
        if len(peak_days) == 1:
            return day_mapping[peak_days[0]]
        else:
            # Sort and take first two peak days
            peak_days = sorted(peak_days)[:2]
            return f"{day_mapping[peak_days[0]]} & {day_mapping[peak_days[1]]}"