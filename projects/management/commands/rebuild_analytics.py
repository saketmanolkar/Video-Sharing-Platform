from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from projects.models import Video, VideoAnalytics, ViewHistory
from projects.services.video_services import VideoService
from projects.services.video_stat_analytics_service import VideoStatisticsService  # Import your stats service
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Rebuilds all video analytics data'

    def handle(self, *args, **options):
        self.stdout.write('🔄 Starting analytics rebuild...')
        
        # Delete all existing analytics
        VideoAnalytics.objects.all().delete()
        self.stdout.write('🗑️ Cleared existing analytics')
        
        # Rebuild for each video
        videos = Video.objects.all()
        total = videos.count()
        
        for index, video in enumerate(videos, 1):
            try:
                data = self.get_analytics_data(video)
                VideoAnalytics.objects.create(**data)
                self.stdout.write(f'✅ Rebuilt analytics for video {index}/{total}: {video.title}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error rebuilding analytics for {video.title}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS('✨ Analytics rebuild complete!'))

    @staticmethod
    def get_analytics_data(video):
        """Get all analytics data for a video"""
        now = timezone.now()

        # Get average watch time for this video
        avg_watch_times = VideoStatisticsService.get_average_watch_time_per_video(video.uploader)
        video_watch_time = 0.0
        for stat in avg_watch_times:
            if stat['video_title'] == video.title:
                video_watch_time = stat['avg_watch_time']
                break

        # Get completion rate for this video
        completion_rate = VideoStatisticsService.get_completion_rate_for_video(video)

        # NEW: get number of completed views directly from DB
        completed_views = ViewHistory.objects.filter(video=video, completed=True).count()

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
            'last_30d_views': VideoService.get_period_views_count(video, 30),

            # Watch Time and Completion Metrics
            'watch_time': round(video_watch_time, 2),  # Average watch time in minutes
            'completion_rate': round(completion_rate, 2),  # Completion rate as percentage

            # NEW FIELD in your "VideoAnalytics" model
            'completed_views': completed_views
        }
