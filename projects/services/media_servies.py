from django.shortcuts import get_object_or_404
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)

class ModelService:
    @staticmethod
    def get_video_url(video, quality=None):
        """Get URL for video file at specified quality"""
        try:
            # Default to 720p if available
            if video.encoded_versions and '720p' in video.encoded_versions:
                return f"{settings.MEDIA_URL}videos/{video.encoded_versions['720p']}"
            
            # Fallback to original file
            return video.file.url if video.file else None
        except Exception as e:
            logger.error(f"Error getting video URL: {str(e)}")
            return None

    @staticmethod
    def cleanup_original_file(file_path):
        """Clean up original video file after encoding"""
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"🗑️ Cleaned up original file: {file_path}")
                return True
            except Exception as e:
                print(f"⚠️ Failed to clean up original: {str(e)}")
                return False
        return False
