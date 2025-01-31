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

logger = getLogger(__name__)

redis_client = Redis(host='localhost', port=6379, db=0)


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
    """Process video encoding in background"""
    from .models import Video
    from django.conf import settings
    import os
    from datetime import datetime
    from django.utils.text import slugify
    from .utils import encode_video
    
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
            input_path = video.file.path
            print(f"📁 Input path: {input_path}")
            
            # Generate base output name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = slugify(os.path.splitext(os.path.basename(video.file.name))[0])
            
            # Ensure videos directory exists
            videos_dir = os.path.join(settings.MEDIA_ROOT, 'videos')
            os.makedirs(videos_dir, exist_ok=True)
            
            encoded_versions = {}
            
            # Encode versions
            for quality in [('720p', '720'), ('360p', '360')]:
                version, size = quality
                print(f"🎬 Encoding {version}...")
                output_name = f"{base_name}_{timestamp}_{version}.mp4"
                output_path = os.path.join(videos_dir, output_name)
                
                if encode_video(input_path, output_path, size):
                    encoded_versions[version] = output_name
                    print(f"✨ Encoded successfully: {output_name}")
            
            if encoded_versions:
                video.encoded_versions = encoded_versions
                video.file.name = f"videos/{encoded_versions['720p']}"
                video.processed = True
                video.save()
                print("✨ Video processing complete")
                
                # Only delete original after successful encoding
                if os.path.exists(input_path):
                    os.remove(input_path)
                    print(f"🗑️ Cleaned up original file")
                return True
                
            return False
                
        finally:
            print(f"🔓 Releasing lock: {lock_key}")
            lock.release()
            print(f"🔍 Lock released successfully")
            
    except Exception as e:
        print(f"❌ Error in task: {str(e)}")
        try:
            lock.release()
            print(f"🔓 Lock released after error")
        except:
            pass
        return False