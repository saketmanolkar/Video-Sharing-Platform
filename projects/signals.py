from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from .models import Video
from django.utils.text import slugify
from datetime import datetime
from .utils import add_black_bars, encode_video
import os
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Video)
def handle_video_encoding(sender, instance, **kwargs):
    """Handle video encoding for new uploads"""
    cache_key = f'encoding_{instance.pk}'
    
    # Skip if already processing
    if cache.get(cache_key):
        return
        
    if not instance.encoded_versions and instance.file:
        try:
            cache.set(cache_key, True, timeout=300)
            
            if not hasattr(instance.file, 'path') or not os.path.exists(instance.file.path):
                print("⚠️ File not accessible yet")
                cache.delete(cache_key)
                return
                
            print('🎥 Starting video encoding...')
            
            input_path = instance.file.path
            print(f"📁 Input path: {input_path}")
            
            # Generate base output name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = slugify(os.path.splitext(os.path.basename(instance.file.name))[0])
            
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
                instance.encoded_versions = encoded_versions
                # Update main file to point to 720p version
                instance.file.name = f"videos/{encoded_versions['720p']}"
                print(f"✨ Video processing complete")
                
            instance._encoding_done = True
            
        except Exception as e:
            logger.error(f'❌ Error encoding video: {str(e)}')
            cache.delete(cache_key)

@receiver(pre_save, sender=Video)
def handle_thumbnail_processing(sender, instance, **kwargs):
    """Handle thumbnail processing separately"""
    cache_key = f'thumbnail_processed_{instance.pk}'
    
    # Skip if already processed (check both cache and instance flag)
    if cache.get(cache_key) or getattr(instance, '_thumbnail_processed', False):
        return
        
    # Only process if thumbnail exists and has changed
    if instance.pk:
        try:
            old_instance = Video.objects.get(pk=instance.pk)
            if old_instance.thumbnail == instance.thumbnail:
                return  # Skip if thumbnail hasn't changed
        except Video.DoesNotExist:
            pass  # New instance, continue processing
            
    try:
        if instance.thumbnail:
            print('🖼️ Processing thumbnail...')
            processed_thumbnail = add_black_bars(instance.thumbnail)
            if processed_thumbnail and processed_thumbnail != instance.thumbnail:
                instance.thumbnail = processed_thumbnail
                instance._thumbnail_processed = True
                cache.set(cache_key, True, timeout=3600)  # Cache for 1 hour
                print('✨ Thumbnail processing complete')
                
    except Exception as e:
        logger.error(f'❌ Error processing thumbnail: {str(e)}')

@receiver(pre_delete, sender=Video)
def cleanup_files(sender, instance, **kwargs):
    """Clean up all files before deletion"""
    if not hasattr(instance, '_cleanup_done'):
        print('\n🗑️ Starting file cleanup')
        print(f'📁 MEDIA_ROOT: {settings.MEDIA_ROOT}')
        
        try:
            # Clean up encoded versions
            if instance.encoded_versions:
                print('\n📼 Encoded Versions to delete:')
                for quality, filename in instance.encoded_versions.items():
                    file_path = os.path.join(settings.MEDIA_ROOT, 'videos', filename)
                    print(f"   • {quality}: {file_path}")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"   ✅ Removed: {file_path}")
                    else:
                        print(f"   ❌ File not found: {file_path}")
            
            # Clean up thumbnail
            if instance.thumbnail:
                print('\n🖼️ Thumbnail to delete:')
                thumb_path = os.path.join(settings.MEDIA_ROOT, str(instance.thumbnail))
                print(f"   • {thumb_path}")
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
                    print(f"   ✅ Removed: {thumb_path}")
                else:
                    print(f"   ❌ File not found: {thumb_path}")
            
            instance._cleanup_done = True
            print('\n✨ Cleanup complete')
            
        except Exception as e:
            logger.error(f'❌ Error cleaning up files: {str(e)}')
