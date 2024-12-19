from django.core.management.base import BaseCommand
from projects.models import Video, VideoAnalytics
from projects.services.video_services import VideoService
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
                data = VideoService.get_analytics_data(video)
                VideoAnalytics.objects.create(**data)
                self.stdout.write(f'✅ Rebuilt analytics for video {index}/{total}: {video.title}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error rebuilding analytics for {video.title}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS('✨ Analytics rebuild complete!'))
