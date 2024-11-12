from django.core.management.base import BaseCommand
from django.conf import settings
import os
from projects.models import Video
from projects.utils import cleanup_media_files

class Command(BaseCommand):
    help = 'Clean up orphaned media files'

    def handle(self, *args, **options):
        # Get all video files in media directory
        media_dir = os.path.join(settings.MEDIA_ROOT, 'videos')
        all_files = set()
        for root, dirs, files in os.walk(media_dir):
            for file in files:
                all_files.add(file)

        # Get all files referenced in database
        db_files = set()
        for video in Video.objects.all():
            base_name = os.path.basename(video.file.name)
            db_files.add(base_name)

        # Clean up orphaned files
        for file in all_files:
            base_name = os.path.splitext(file)[0].split('_')[0]
            if not any(db_file.startswith(base_name) for db_file in db_files):
                cleanup_media_files(file)
                self.stdout.write(self.style.SUCCESS(f'Cleaned up orphaned file: {file}')) 