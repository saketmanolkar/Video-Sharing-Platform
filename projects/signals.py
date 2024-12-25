from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver
from .models import Video
from django.utils.text import slugify
from datetime import datetime
from .utils import add_black_bars, encode_video
import os
import logging
from django.conf import settings
from django.core.cache import cache
from django.dispatch import receiver
from .models import Video, Review, Like, VideoAnalytics, ViewHistory
from .services.video_services import VideoService
from django.db import transaction
from django.db.transaction import on_commit

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Video)
def handle_video_encoding(sender, instance, created, **kwargs):
    """Queue video encoding for new uploads AND updates"""
    
    print("\n🔍 DEBUG: Video Signal Triggered")
    print(f"Created: {created}")
    print(f"File changed: {getattr(instance, '_file_changed', False)}")
    
    # Process if new video OR file changed
    if not (created or getattr(instance, '_file_changed', False)):
        print("⏩ Skipping - no video changes")
        return
        
    print("✅ Video changes detected - proceeding")
    
    if not instance.file:
        print("❌ No video file to process")
        return
        
    def queue_video_task():
        cache_key = f'encoding_{instance.pk}'
        if cache.get(cache_key):
            print(f"⏩ Already processing video {instance.pk}")
            return
            
        try:
            cache.set(cache_key, True, timeout=300)
            from .tasks import process_video_task
            task = process_video_task.delay(str(instance.pk))
            print(f"🎯 Queued video task: {task.id}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            cache.delete(cache_key)
    
    print("🔄 Waiting for transaction...")
    transaction.on_commit(queue_video_task)

@receiver(post_save, sender=Video)
def handle_thumbnail_processing(sender, instance, created, **kwargs):
    """Queue thumbnail processing for new and updated thumbnails"""
    
    print("\n🔍 DEBUG: Signal Triggered")
    print(f"Created: {created}")
    print(f"Has thumbnail: {bool(instance.thumbnail)}")
    print(f"Thumbnail changed: {getattr(instance, '_thumbnail_changed', False)}")
    
    # Process if new video OR thumbnail changed
    if not (created or getattr(instance, '_thumbnail_changed', False)):
        print("⏩ Skipping - no changes")
        return
        
    print("✅ Changes detected - proceeding")
    
    if not instance.thumbnail:
        print("❌ No thumbnail to process")
        return
        
    try:
        def queue_task():
            from projects.tasks import process_thumbnail_task
            print("🎯 About to queue task...")
            task = process_thumbnail_task.delay(str(instance.pk))
            print(f"✨ Task queued! ID: {task.id}")
            
        print("🔄 Committing transaction...")
        transaction.on_commit(queue_task)
            
    except Exception as e:
        print(f"❌ Error in signal: {str(e)}")

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

@receiver(post_save, sender=Video)
def handle_analytics_create(sender, instance, created, **kwargs):
    """CREATE signal - Creates analytics record when video is created"""
    if not created:
        return
        
    try:
        with transaction.atomic():
            # Check if analytics already exists
            if not hasattr(instance, 'analytics'):
                data = VideoService.get_analytics_data(instance)
                VideoAnalytics.objects.create(**data)
    except Exception as e:
        logger.error(f"Failed to create analytics: {str(e)}")
        # Attempt recovery
        VideoService.repair_analytics(instance)

@receiver([post_save, post_delete], sender=Review)
def handle_review_analytics_update(sender, instance, **kwargs):
    """UPDATE signal - Updates analytics when reviews change"""
    try:
        analytics = instance.video.analytics
        analytics.total_comments = VideoService.get_comments_count(instance.video)
        analytics.save(update_fields=['total_comments', 'updated_at'])
        logger.info(f"✅ Updated comment count for video: {instance.video.title}")
    except Exception as e:
        logger.error(f"❌ Error updating review analytics: {str(e)}")

@receiver([post_save, post_delete], sender=Like)
def handle_like_analytics_update(sender, instance, **kwargs):
    """UPDATE signal - Updates analytics when likes/dislikes change"""
    try:
        analytics = instance.video.analytics
        # Use VideoService for accurate counts
        analytics.total_likes = VideoService.get_likes_count(instance.video)
        analytics.total_dislikes = VideoService.get_dislikes_count(instance.video)
        analytics.save(update_fields=['total_likes', 'total_dislikes', 'updated_at'])
        logger.info(f"✅ Updated like counts for video: {instance.video.title}")
    except Exception as e:
        logger.error(f"❌ Error updating like analytics: {str(e)}")

@receiver([post_save, post_delete], sender=ViewHistory)
def handle_view_analytics_update(sender, instance, **kwargs):
    """UPDATE signal - Updates analytics when views change"""
    try:
        analytics = instance.video.analytics
        # Use VideoService for accurate view counts
        analytics.total_views = VideoService.get_views_count(instance.video)
        analytics.last_24h_views = VideoService.get_period_views_count(instance.video, 1)
        analytics.last_7d_views = VideoService.get_period_views_count(instance.video, 7)
        analytics.last_30d_views = VideoService.get_period_views_count(instance.video, 30)
        analytics.save(update_fields=[
            'total_views', 
            'last_24h_views', 
            'last_7d_views', 
            'last_30d_views', 
            'updated_at'
        ])
        logger.info(f"✅ Updated view metrics for video: {instance.video.title}")
    except Exception as e:
        logger.error(f"❌ Error updating view analytics: {str(e)}")

@receiver(pre_delete, sender=Video)
def handle_video_cleanup(sender, instance, **kwargs):
    """DELETE signal - Handles complete cleanup when video is deleted"""
    try:
        with transaction.atomic():
            # Delete related records in transaction
            instance.likes.all().delete()
            instance.reviews.all().delete()
            instance.views_history.all().delete()
            instance.analytics.delete()
        
        logger.info(f"✅ Successfully cleaned up all related data for video: {instance.title}")
    except Exception as e:
        logger.error(f"❌ Error during video cleanup: {str(e)}")
        raise  # Re-raise to prevent incomplete deletion

@receiver(post_save, sender=Video)
def handle_video_update(sender, instance, created, **kwargs):
    """UPDATE signal - Updates analytics when video details change"""
    if created:  # Skip if this is a new video (handled by handle_analytics_create)
        return
        
    try:
        analytics = instance.analytics
        # Update title if it changed
        if analytics.title != instance.title:
            analytics.title = instance.title
            analytics.save(update_fields=['title', 'updated_at'])
            logger.info(f"✅ Updated analytics title for video: {instance.title}")
    except Exception as e:
        logger.error(f"❌ Error updating video analytics: {str(e)}")

