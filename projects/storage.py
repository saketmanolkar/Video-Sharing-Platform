from django.core.files.storage import FileSystemStorage
from django.core.files import File
from django.conf import settings
from .utils import compress_video
import os

class VideoStorage(FileSystemStorage):
    def _save(self, name, content):
        # Create temporary file
        temp_path = super()._save(name, content)
        full_temp_path = os.path.join(self.location, temp_path)
        
        try:
            # Compress video and get relative path
            compressed_relative_path = compress_video(full_temp_path)
            
            # Delete original after successful compression
            if os.path.exists(full_temp_path):
                os.remove(full_temp_path)
                print(f"Deleted original file: {full_temp_path}")
            
            # Important: Return the path relative to MEDIA_ROOT that includes 'videos/'
            return f'videos/{os.path.basename(compressed_relative_path)}'
                
        except Exception as e:
            print(f"Error processing video: {str(e)}")
            return temp_path