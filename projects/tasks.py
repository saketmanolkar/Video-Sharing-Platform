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