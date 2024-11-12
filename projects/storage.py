from django.core.files.storage import FileSystemStorage
import os
import json
from .utils import encode_video, cleanup_media_files

class VideoStorage(FileSystemStorage):
    def _save(self, name, content):
        # Save original file temporarily
        original_path = super()._save(name, content)
        full_path = self.path(original_path)
        
        try:
            directory = os.path.dirname(full_path)
            filename = os.path.basename(full_path)
            name_without_ext, ext = os.path.splitext(filename)
            
            # Create encoded versions
            versions = {
                '720p': '1280x720',
                '360p': '640x360'
            }
            
            encoded_versions = {}
            success = True
            
            for quality, size in versions.items():
                output_name = f"{name_without_ext}_{quality}{ext}"
                output_path = os.path.join(directory, output_name)
                
                if encode_video(full_path, output_path, size):
                    encoded_versions[quality] = output_name
                else:
                    success = False
                    break
            
            if success:
                # Save versions info
                versions_file = os.path.join(directory, f"{name_without_ext}_versions.json")
                with open(versions_file, 'w') as f:
                    json.dump(encoded_versions, f)
                    
                # Delete the original file after successful encoding
                if os.path.exists(full_path):
                    os.remove(full_path)
                    print(f"Deleted original file: {full_path}")
                
                # Return path to 720p version as the default
                return f"videos/{name_without_ext}_720p{ext}"
            else:
                cleanup_media_files(filename)
                raise Exception("Video encoding failed")
            
        except Exception as e:
            print(f"Storage error: {str(e)}")
            cleanup_media_files(filename)
            raise

    def post_process_video(self, video_instance, path):
        """Called after the video instance is saved"""
        try:
            # Check for temporary JSON file with encoded versions
            temp_json_path = os.path.join(
                self.location,
                f"{os.path.splitext(path)[0]}_versions.json"
            )
            
            if os.path.exists(temp_json_path):
                with open(temp_json_path, 'r') as f:
                    encoded_versions = json.load(f)
                
                # Update the video instance
                video_instance.encoded_versions = encoded_versions
                video_instance.save()
                
                # Clean up temp file
                os.remove(temp_json_path)
                
                return True
        except Exception as e:
            print(f"Error in post processing: {str(e)}")
            return False