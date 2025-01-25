from django.db.models import Count, Avg, F
from django.utils import timezone
from datetime import timedelta
from projects.models import Video, ViewHistory

class VideoStatisticsService:
    @staticmethod
    def get_average_watch_time_for_user_videos(user):
        """Get average watch time for all videos uploaded by the user"""
        user_videos = Video.objects.filter(uploader=user)  # Assuming 'uploader' is the field for the user
        avg_watch_time = ViewHistory.objects.filter(video__in=user_videos).aggregate(
            avg_duration=Avg('duration_watched')
        )
        return avg_watch_time['avg_duration']

    @staticmethod
    def get_average_watch_time_per_video(user):
        """Get average watch time for each individual video uploaded by the user"""
        avg_watch_times = []
        videos = Video.objects.filter(uploader=user)
        
        for video in videos:
            avg_time = ViewHistory.objects.filter(video=video).aggregate(
                avg_watch_time=Avg('duration_watched')
            )['avg_watch_time']
            
            if avg_time:
                # Convert timedelta to minutes
                minutes = avg_time.total_seconds() / 60
                
                avg_watch_times.append({
                    'video_title': video.title,
                    'avg_watch_time': round(minutes, 2)  # Round to 2 decimal places
                })
        
        return avg_watch_times

    @staticmethod
    def get_completion_rate_for_user_videos(user):
        """Get overall completion rate for all videos uploaded by the user"""
        user_videos = Video.objects.filter(uploader=user)
        total_views = ViewHistory.objects.filter(video__in=user_videos).count()
        completed_views = ViewHistory.objects.filter(video__in=user_videos, completed=True).count()
        
        completion_rate = (completed_views / total_views) * 100 if total_views > 0 else 0
        return completion_rate

    @staticmethod
    def get_completion_rate_per_video(user):
        """Get completion rate for each individual video uploaded by the user"""
        user_videos = Video.objects.filter(uploader=user)
        completion_rates = []

        for video in user_videos:
            total_views = ViewHistory.objects.filter(video=video).count()
            completed_views = ViewHistory.objects.filter(video=video, completed=True).count()
            completion_rate = (completed_views / total_views) * 100 if total_views > 0 else 0
            
            completion_rates.append({
                'video_title': video.title,
                'completion_rate': completion_rate
            })

        return completion_rates

    @staticmethod
    def get_completion_rate_for_video(video):
        """Calculate the completion rate for a specific video."""
        total_views = ViewHistory.objects.filter(video=video).count()
        completed_views = ViewHistory.objects.filter(video=video, completed=True).count()
        
        completion_rate = (completed_views / total_views) * 100 if total_views > 0 else 0
        return completion_rate

