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
        # First check if there are any videos
        if not user_videos.exists():
            return None
        
        hourly_totals = {i: 0 for i in range(24)}
        
        # Get hourly distribution for each video and aggregate
        for video in user_videos:
            hourly_views = AnalyticsService.get_views_by_hour(video, days)
            for view in hourly_views:
                hour = view['hour']
                count = view['count']
                hourly_totals[hour] += count
        
        # Check if we have any views at all
        if max(hourly_totals.values()) == 0:
            return None
        
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
        # First check if there are any videos
        if not user_videos.exists():
            return None
        
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
        
        # Check if we have any views at all
        if max(weekday_totals.values()) == 0:
            return None
        
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

class VideoReportService:
    @staticmethod
    def format_video_data_for_prompt(user, videos):
        from projects.services.video_services import VideoService
        from projects.services.video_stat_analytics_service import VideoStatisticsService
        from users.services.follower_analytics_service import FollowerAnalyticsService  # Import the follower analytics service
        """Formats all video data into a prompt for AI analysis"""
        try:
            # Filter for current user's videos only
            user_videos = videos.filter(uploader=user)

            # Get video analytics
            analytics_data = VideoService.get_creator_studio_analytics(user_videos)

            # Extract relevant data
            video_analytics = analytics_data['video_analytics']

            # Get engagement breakdown
            follower_analytics_service = FollowerAnalyticsService()
            engagement_breakdown = follower_analytics_service.get_engagement_breakdown(user)

            # Initialize the prompt
            prompt = "Here is the complete video activity data for analysis:\n\n"

            prompt += f"ENGAGEMENT BREAKDOWN FOR ALL OF {user.username}'S VIDEOS:\n"

            # Add engagement breakdown to the prompt
            for metric, data in engagement_breakdown['engagement_breakdown'].items():
                prompt += f"\n{metric.capitalize()}:\n"
                prompt += f"  Total: {data['total']}\n"
                prompt += f"  Follower Count: {data['follower_count']}\n"
                prompt += f"  Non-Follower Count: {data['non_follower_count']}\n"
                prompt += f"  Follower Percentage: {data['follower_percentage']:.2f}%\n"
                prompt += f"  Non-Follower Percentage: {data['non_follower_percentage']:.2f}%\n"

            # Get average watch time for each video
            avg_watch_times = VideoStatisticsService.get_average_watch_time_per_video(user)

            # Get completion rate for user videos
            completion_rate = VideoStatisticsService.get_completion_rate_for_user_videos(user)

            # Get average watch time for all user videos
            total_avg_watch_time = VideoStatisticsService.get_average_watch_time_for_user_videos(user)

            # Check if total_avg_watch_time is a timedelta and convert it to minutes if necessary
            if isinstance(total_avg_watch_time, timedelta):
                total_avg_watch_time_minutes = total_avg_watch_time.total_seconds() / 60  # Convert to minutes
            else:
                total_avg_watch_time_minutes = total_avg_watch_time  # Already in minutes

            prompt += "-----------------------------------------\n"
            prompt += "\n"
            prompt += f"PEAK ENGAGEMENT FOR ALL OF {user.username}'S VIDEOS:\n"
            # Get peak viewing day(s)
            peak_viewing_days = AnalyticsService.get_peak_viewing_day(user_videos)
            peak_viewing_hours = AnalyticsService.get_peak_viewing_hour(user_videos)

            # Add peak viewing day(s) to the prompt
            prompt += f"\nPeak Viewing Day for all of {user.username}'s videos: {peak_viewing_days}\n"
            prompt += f"\nPeak Viewing Hour for all of {user.username}'s videos: {peak_viewing_hours}\n"
            prompt += f"\nCompletion Rate for all of {user.username}'s videos: {completion_rate:.2f}%\n"
            prompt += f"\nAverage Watch Time for all of {user.username}'s videos: {total_avg_watch_time_minutes:.2f} minutes\n"

            prompt += "-----------------------------------------\n"
            prompt += "\n"

            prompt += f"OVERALL STATISTICS FOR ALL OF {user.username}'S VIDEOS:\n"

            for video in user_videos:  # Iterate over the actual video objects
                stats = video_analytics.get(str(video.id), {})  # Get stats for the current video
                if not stats:
                    continue  # Skip if no stats are found

                # Calculate individual video completion rate
                individual_completion_rate = VideoStatisticsService.get_completion_rate_for_video(video)

                # Add video statistics to the prompt
                prompt += f"""
                
Title: {stats['title']}
Total Views: {stats['total_views']}
Total Likes: {stats['total_likes']}
Total Dislikes: {stats['total_dislikes']}
Total Comments: {stats['total_comments']}
Average Watch Time: {next((item['avg_watch_time'] for item in avg_watch_times if item['video_title'] == stats['title']), 0)} minutes
Completion Rate: {individual_completion_rate:.2f}%
Created At: {stats['created_at']}

Views Over Days for '{stats['title']}':
"""
                # Get views data for the specific video
                views_data = AnalyticsService.get_views_over_time(video)  # Use the video object directly
                formatted_views = {str(view['day']): view['count'] for view in views_data}
                
                for date, count in formatted_views.items():
                    prompt += f"{date}: {count} views\n"

                # Add a new section for hourly views
                prompt += f"\nViews Distribution Over Hours for '{stats['title']}':\n"  # New section header

                # Get hourly views for the specific video
                hourly_views = AnalyticsService.get_views_by_hour(video)  # Call the function
                
                # Format hourly views to 12-hour format
                for view in hourly_views:
                    hour = view['hour']
                    count = view['count']
                    formatted_hour = VideoReportService.format_hour(hour)  # Use the existing format_hour function
                    prompt += f"{formatted_hour}: {count} views\n"

                # Add a new section for weekly views distribution
                prompt += f"\nView Distribution Over a Week for '{stats['title']}':\n"  # New section header

                # Get weekly views distribution for the specific video
                weekday_views = AnalyticsService.get_views_by_weekday(video)  # Call the function
                for entry in weekday_views:
                    prompt += f"{entry['day_name']}: {entry['count']} views\n"
                
                prompt += "\n"  # Add a newline for better separation between videos

            prompt += "-----------------------------------------\n"
            prompt += "\n"
            # End of the prompt
            prompt += "Please analyze the data above to derive additional insights and trends."

            return prompt
            
        except Exception as e:
            print(f"Error formatting video data: {str(e)}")
            return None

    @staticmethod
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