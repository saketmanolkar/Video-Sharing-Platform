from collections import defaultdict, OrderedDict
from django.utils import timezone
from datetime import timedelta, datetime
from users.models import UserSession
import pytz
from django.contrib.auth import get_user_model

User = get_user_model()

class UserAnalyticsService:
    @staticmethod
    def get_user_analytics(user):
        """Get complete user behavior analytics"""
        sessions = UserSession.objects.filter(
            user=user,
            start_time__gte=timezone.now() - timedelta(days=30)
        )
        
        return {
            'heatmap_data': UserAnalyticsService._get_heatmap_data(sessions),
            'time_stats': UserAnalyticsService._get_time_stats(sessions)
        }
    
    @staticmethod
    def convert_to_12hr(hour):
        """Convert 24hr to 12hr format with AM/PM"""
        hour = int(hour)
        if hour == 0:
            return "12AM"
        elif hour < 12:
            return f"{hour}AM"
        elif hour == 12:
            return "12PM"
        else:
            return f"{hour-12}PM"
    
    @staticmethod
    def convert_utc_to_local(utc_dt):
        """Convert UTC datetime to local timezone (EST/EDT)"""
        local_tz = pytz.timezone('America/New_York')  # Or your timezone
        local_dt = utc_dt.astimezone(local_tz)
        return local_dt
    
    @staticmethod
    def time_to_24hr(time_str):
        """Convert '2PM' or '3AM' format to 24-hour integer for sorting"""
        hour = int(time_str[:-2])  # Get number part
        period = time_str[-2:]     # Get AM/PM part
        
        if period == 'PM' and hour != 12:
            hour += 12
        elif period == 'AM' and hour == 12:
            hour = 0
        
        return hour
    
    @staticmethod
    def _get_heatmap_data(sessions):
        """Transform sessions into day/hour heatmap using local time"""
        # Step 1: Collect raw data in 24-hour format
        raw_data = defaultdict(lambda: defaultdict(float))
        
        for session in sessions:
            if session.end_time:
                local_start = UserAnalyticsService.convert_utc_to_local(session.start_time)
                local_end = UserAnalyticsService.convert_utc_to_local(session.end_time)
                
                day = local_start.strftime('%A')
                hour_24 = int(local_start.strftime('%H'))  # Keep as 24-hour
                
                duration = (local_end - local_start).total_seconds() / 60
                raw_data[day][hour_24] += round(duration, 2)
        
        # Step 2: Create sorted result and convert to 12-hour only at the end
        result = {}
        for day, hours in raw_data.items():
            # Sort by hour (already in 24-hour format)
            sorted_hours = sorted(hours.items())
            
            # Convert to 12-hour format only once for final output
            result[day] = OrderedDict(
                (UserAnalyticsService.convert_to_12hr(hour), duration)
                for hour, duration in sorted_hours
            )
        
        return result
    
    @staticmethod
    def _get_time_stats(sessions):
        """Calculate time-based statistics"""
        total_time = 0
        session_count = 0
        
        for session in sessions:
            if session.end_time:
                duration = (session.end_time - session.start_time).total_seconds() / 60
                total_time += duration
                session_count += 1
        
        return {
            'total_time': round(total_time, 2),
            'avg_session': round(total_time / session_count if session_count else 0, 2),
            'session_count': session_count
        }
    
    @staticmethod
    def get_profile_visits_count(target_user):
        """Count visits to target_user's profile by other users"""
        profile_path = f'/users/profile/{target_user.profile.id}/'
        total_visits = 0
        
        other_sessions = UserSession.objects.exclude(
            user=target_user
        ).filter(
            activity_log__isnull=False
        )
        
        for session in other_sessions:
            log = session.activity_log
            if log and 'pages_visited' in log:
                for visit in log['pages_visited']:
                    if visit['path'] == profile_path:
                        total_visits += 1
        
        return total_visits

    @staticmethod
    def get_platform_average_total_time():
        """Calculate average total time spent per user across the platform"""
        # Get all sessions from last 30 days
        sessions = UserSession.objects.filter(
            start_time__gte=timezone.now() - timedelta(days=30),
            end_time__isnull=False
        )
        
        # Group by user to get per-user totals
        user_totals = defaultdict(float)
        
        for session in sessions:
            duration = (session.end_time - session.start_time).total_seconds() / 60
            user_totals[session.user_id] += duration
        
        # Calculate average across users
        active_totals = [total for total in user_totals.values() if total > 0]
        if active_totals:
            return round(sum(active_totals) / len(active_totals), 1)
        
        return 0
