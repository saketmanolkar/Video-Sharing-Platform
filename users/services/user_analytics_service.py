from collections import defaultdict, OrderedDict
from django.utils import timezone
from datetime import timedelta, datetime
from users.models import UserSession, UserActivitySummary
import pytz
from django.contrib.auth import get_user_model
from users.services.follower_analytics_service import FollowerAnalyticsService
from django.db import models

User = get_user_model()

class UserAnalyticsService:
    @staticmethod
    def get_user_analytics(user):
        """Get complete user behavior analytics"""
        # Optimized Query:
        sessions = UserSession.objects.filter(
            user=user,
            start_time__gte=timezone.now() - timedelta(days=30)
        ).values(
            'start_time',    # Needed for day/hour
            'end_time',      # Needed for duration
            'user_id'        # Needed for filtering
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
        raw_data = defaultdict(lambda: defaultdict(float))
        
        for session in sessions:
            if session['end_time']:  # Dictionary access
                local_start = UserAnalyticsService.convert_utc_to_local(session['start_time'])
                local_end = UserAnalyticsService.convert_utc_to_local(session['end_time'])
                
                day = local_start.strftime('%A')
                hour_24 = int(local_start.strftime('%H'))
                
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
            if session['end_time']:  # Changed from session.end_time
                duration = (session['end_time'] - session['start_time']).total_seconds() / 60  # Changed access
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
    
    @staticmethod
    def get_platform_average_total_time_denormalized():
        """Calculate average total time spent per user across the platform using denormalized data"""
       
        # Calculate average directly from denormalized data
        avg_time = UserActivitySummary.objects.aggregate(
            avg_time=models.Avg('total_time_spent')
        )['avg_time']
        
        return round(avg_time or 0, 1)

    @staticmethod
    def format_user_data_for_prompt(user):
        """Formats all user data into a prompt for AI analysis"""
        try:
            # Get user's activity summary
            activity_summary = user.activity_summary
            
            # Get last 30 days of sessions for heatmap
            sessions = UserSession.objects.filter(
                user=user,
                start_time__gte=timezone.now() - timedelta(days=30)
            )
            
            # Get heatmap data
            analytics_service = UserAnalyticsService()
            heatmap_data = analytics_service._get_heatmap_data(sessions)
            
            # Get platform average
            platform_avg = analytics_service.get_platform_average_total_time()
            
            # Get follower analytics
            follower_service = FollowerAnalyticsService()
            follower_analytics = follower_service.get_follower_analytics(user)
            
            # Extract follower metrics
            follower_metrics = {
                'following_count': follower_analytics['following_count'],
                'new_followers_30d': follower_analytics['new_followers_30d'],
                'total_followers': follower_analytics['total_followers']
            }
            
            # Format the prompt
            prompt = f"""Here is the complete user activity data for analysis:

HEATMAP DATA of the last 30 days (Minutes spent per hour):
"""
            # Add heatmap data by day
            for day, hours in heatmap_data.items():
                prompt += f"\n{day}:\n"
                for hour, duration in hours.items():
                    prompt += f"{hour}: {duration} minutes\n"
            
            # Add summary stats from UserActivitySummary
            prompt += f"""
OVERALL STATISTICS:
Total Time Spent: {activity_summary.total_time_spent} minutes
Average Session Duration: {activity_summary.avg_session_length} minutes
Number of Sessions: {activity_summary.total_sessions}
Count of Visits to {user.username}'s profile by other users: {activity_summary.total_profile_visits}
Last Active: {activity_summary.last_session_date.strftime('%Y-%m-%d %H:%M')}
Platform Average Time: {platform_avg} minutes
Following Count: {follower_metrics['following_count']}
New Followers in the Last 30 Days: {follower_metrics['new_followers_30d']}
Total Followers: {follower_metrics['total_followers']}

In the report, give insights about the following metrics:

- Overall usage patterns
- Profile engagement
- Follower Count , Total Followers, New Followers in the Last 30 Days
- Visits to {user.username}'s profile by other users
- Peak usage times
- Session duration patterns ,Total Time Spent, Average Session Duration, Number of Sessions
- Unusual activity periods
- Daily and weekly patterns

Make sure to give insights in this order only, no exceptions.

Unusual activity periods, Daily and weekly patterns, Overall usage patterns should be half the report, 
and the rest of the report should be the other metrics.

"""
            
            return prompt
            
        except Exception as e:
            print(f"Error formatting user data: {str(e)}")
            return None
