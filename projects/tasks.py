# Create a simple test task in projects/tasks.py
from celery import shared_task
from django.core.cache import cache
from logging import getLogger
from django.core.files import File
import os
from django.core.files.storage import default_storage
import logging
from redis import Redis
from redis.lock import Lock
import tempfile
import requests
from django.conf import settings

logger = getLogger(__name__)

# Get Redis host from environment or use 'redis' for Docker
redis_host = os.environ.get('REDIS_HOST', 'redis')
redis_client = Redis(host=redis_host, port=6379, db=0)


@shared_task(bind=True)
def process_thumbnail_task(self, video_id):
    """Process video thumbnail in background"""
    from .models import Video
    from .utils import add_black_bars
    
    lock = redis_client.lock(
        f'thumbnail_lock_{video_id}',
        timeout=60,
        blocking_timeout=5
    )
    
    print(f"\n{'='*50}")
    print(f"🎯 Starting Thumbnail Task {self.request.id}")
    print(f"📌 Processing video: {video_id}")
    
    try:
        # Try to acquire lock
        if not lock.acquire(blocking=False):
            print(f"🔒 Task already running for video {video_id}")
            return False
            
        try:
            video = Video.objects.get(pk=video_id)
            
            if not video.thumbnail:
                print("❌ No thumbnail found")
                return False
                
            print(f"🖼️ Processing thumbnail: {video.thumbnail.name}")
            
            with video.thumbnail.open('rb') as img_file:
                processed_thumbnail = add_black_bars(img_file)
                
                if processed_thumbnail:
                    old_path = video.thumbnail.name
                    print(f"🗑️ Removing: {old_path}")
                    video.thumbnail.delete(save=False)
                    
                    final_path = f'thumbnails/{os.path.basename(old_path)}'
                    print(f"💾 Saving to: {final_path}")
                    default_storage.save(final_path, processed_thumbnail)
                    
                    Video.objects.filter(pk=video_id).update(
                        thumbnail=final_path
                    )
                    
                    print("✅ Thumbnail processing complete")
                    print(f"{'='*50}\n")
                    return True
                    
            print("❌ Failed to process thumbnail")
            return False
                
        finally:
            # Always release the lock
            lock.release()
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        # Try to release lock in case of error
        try:
            lock.release()
        except:
            pass
        return False


@shared_task(bind=True)
def process_video_task(self, video_id):
    """Process video encoding in background - Cloud Storage Compatible"""
    from .models import Video
    from django.conf import settings
    import os
    import tempfile
    import requests
    from datetime import datetime
    from django.utils.text import slugify
    from .utils import encode_video
    from custom_storage import upload_file_to_spaces, delete_file_from_spaces
    
    lock_key = f'encoding_lock_{video_id}'
    lock = redis_client.lock(
        lock_key,
        timeout=3600,
        blocking_timeout=5
    )
    
    print(f"\n{'='*50}")
    print(f"🔍 Starting Video Task {self.request.id}")
    print(f"🔒 Attempting to acquire lock: {lock_key}")
    
    try:
        if not lock.acquire(blocking=False):
            print(f"❌ Lock exists, task already running for video {video_id}")
            return False
            
        print(f"✅ Lock acquired: {lock_key}")
        
        try:
            video = Video.objects.get(id=video_id)
            
            # IMPORTANT: Store original file path before changing it
            original_file_path = video.file.name
            print(f"💾 Original file path: {original_file_path}")
            
            # Get file from cloud storage
            video_url = video.file.url
            print(f"☁️ Downloading video from: {video_url}")
            
            # Create temp file for processing
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                input_path = temp_file.name
                
            # Download file to temp location
            response = requests.get(video_url, stream=True)
            if response.status_code != 200:
                print(f"❌ Failed to download video: {response.status_code}")
                return False
                
            with open(input_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            print(f"✅ Downloaded video to temp file: {input_path}")
            
            # Generate base output name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = slugify(os.path.splitext(os.path.basename(video.file.name))[0])
            
            encoded_versions = {}
            
            # Encode versions
            for quality in [('720p', '720'), ('360p', '360')]:
                version, size = quality
                print(f"🎬 Encoding {version}...")
                
                # Create temp output file
                with tempfile.NamedTemporaryFile(suffix=f'_{version}.mp4', delete=False) as out_temp:
                    output_path = out_temp.name
                
                if encode_video(input_path, output_path, size):
                    # Define cloud path
                    cloud_filename = f"videos/{base_name}_{timestamp}_{version}.mp4"
                    
                    # Upload encoded file to cloud
                    with open(output_path, 'rb') as f:
                        video_data = f.read()
                    
                    video_url = upload_file_to_spaces(video_data, cloud_filename)
                    if video_url:
                        encoded_versions[version] = cloud_filename
                        print(f"☁️ Uploaded to cloud: {cloud_filename}")
                    
                    # Clean up temp output file
                    os.unlink(output_path)
            
            # Clean up temp input file
            os.unlink(input_path)
            
            if encoded_versions:
                # Update video model
                video.encoded_versions = encoded_versions
                video.file.name = encoded_versions['720p']  # Use the HD version as the primary
                video.processed = True
                video.save()
                print("✨ Video processing complete")
                
                # Now delete the original file from cloud storage
                if original_file_path and original_file_path != encoded_versions['720p']:
                    print(f"🗑️ Attempting to delete original file: {original_file_path}")
                    delete_success = delete_file_from_spaces(original_file_path)
                    if delete_success:
                        print(f"✅ Original file deleted from cloud storage")
                    else:
                        print(f"⚠️ Failed to delete original file from cloud storage")
                return True
                
            return False
                
        finally:
            print(f"🔓 Releasing lock: {lock_key}")
            lock.release()
            print(f"🔍 Lock released successfully")
            
    except Exception as e:
        print(f"❌ Error in task: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            # Clean up temp files if they exist
            if 'input_path' in locals() and os.path.exists(input_path):
                os.unlink(input_path)
            if 'output_path' in locals() and os.path.exists(output_path):
                os.unlink(output_path)
            
            lock.release()
            print(f"🔓 Lock released after error")
        except Exception as cleanup_err:
            print(f"⚠️ Cleanup error: {str(cleanup_err)}")
        return False