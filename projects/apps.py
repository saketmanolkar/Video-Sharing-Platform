from django.apps import AppConfig
import os
from django.conf import settings


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projects'

    def ready(self):
        # Import signals
        from . import signals
        
        # Create necessary directories
        media_root = settings.MEDIA_ROOT
        videos_dir = os.path.join(media_root, 'videos')
        thumbnails_dir = os.path.join(media_root, 'thumbnails')
        
        # Create directories if they don't exist
        os.makedirs(media_root, exist_ok=True)
        os.makedirs(videos_dir, exist_ok=True)
        os.makedirs(thumbnails_dir, exist_ok=True)
