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
from .models import Video, Review, Like, VideoAnalytics, ViewHistory, Playlist
from .services.video_services import VideoService
from django.db import transaction
from django.db.transaction import on_commit
from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Video)
def handle_video_encoding(sender, instance, created, **kwargs):
    """Queue video encoding for new uploads AND updates"""
    
    # Add this check to prevent re-encoding already encoded videos
    if instance.encoded_versions and '720p' in instance.encoded_versions:
        print("⏩ Skipping - video already has encoded versions")
        return
    
    # Process if new video OR file changed
    if not (created or getattr(instance, '_file_changed', False)):
        print("⏩ Skipping - no video changes")
        return
        
    print("✅ Video changes detected - proceeding")
    
    if not instance.file:
        print("❌ No video file to process")
        return
        
    def queue_video_task():
        from .tasks import process_video_task
        task = process_video_task.delay(str(instance.pk))
        print(f"🎯 Queued video task: {task.id}")
    
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
        
        try:
            from django.core.files.storage import default_storage
            
            # Clean up encoded versions
            if instance.encoded_versions:
                print('\n📼 Encoded Versions to delete:')
                for quality, filename in instance.encoded_versions.items():
                    print(f"   • {quality}: {filename}")
                    if default_storage.exists(filename):
                        default_storage.delete(filename)
                        print(f"   ✅ Removed from storage: {filename}")
                    else:
                        print(f"   ❌ File not found in storage: {filename}")
            
            # Clean up thumbnail
            if instance.thumbnail:
                thumb_path = str(instance.thumbnail)
                print(f"\n🖼️ Thumbnail to delete: {thumb_path}")
                if default_storage.exists(thumb_path):
                    default_storage.delete(thumb_path)
                    print(f"   ✅ Removed from storage: {thumb_path}")
                else:
                    print(f"   ❌ File not found in storage: {thumb_path}")
            
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
        # Check if the video still exists (may be None during deletion cascade)
        if not hasattr(instance, 'video') or not instance.video:
            print("⏩ Skipping review analytics update - video is being deleted")
            return
            
        with transaction.atomic():
            # Check if analytics exists before trying to update it
            try:
                analytics = VideoAnalytics.objects.select_for_update().get(video=instance.video)
                analytics.total_comments = VideoService.get_comments_count(instance.video)
                analytics.save(update_fields=['total_comments', 'updated_at'])
                logger.info(f"✅ Updated comment count for video: {instance.video.title}")
            except VideoAnalytics.DoesNotExist:
                logger.warning(f"⚠️ Analytics doesn't exist for video {instance.video.id} - skipping comment update")
                return
    except Exception as e:
        logger.error(f"❌ Error updating review analytics: {str(e)}")

@receiver([post_save, post_delete], sender=Like)
def handle_like_analytics_update(sender, instance, **kwargs):
    """UPDATE signal - Updates analytics when likes/dislikes change"""
    try:
        # Check if the video still exists (may be None during deletion cascade)
        if not hasattr(instance, 'video') or not instance.video:
            print("⏩ Skipping like analytics update - video is being deleted")
            return
            
        with transaction.atomic():
            # Check if analytics exists before trying to update it
            try:
                analytics = VideoAnalytics.objects.select_for_update().get(video=instance.video)
                # Use VideoService for accurate counts
                analytics.total_likes = VideoService.get_likes_count(instance.video)
                analytics.total_dislikes = VideoService.get_dislikes_count(instance.video)
                analytics.save(update_fields=['total_likes', 'total_dislikes', 'updated_at'])
                logger.info(f"✅ Updated like counts for video: {instance.video.title}")
            except VideoAnalytics.DoesNotExist:
                logger.warning(f"⚠️ Analytics doesn't exist for video {instance.video.id} - skipping like update")
                return
    except Exception as e:
        logger.error(f"❌ Error updating like analytics: {str(e)}")

@receiver([post_save, post_delete], sender=ViewHistory)
def handle_view_analytics_update(sender, instance, **kwargs):
    """UPDATE signal - Updates analytics when views change"""
    try:
        # Check if the video still exists (may be None during deletion cascade)
        if not instance.video:
            print("⏩ Skipping view analytics update - video is being deleted")
            return
            
        with transaction.atomic():
            # Check if analytics exists before trying to update it
            try:
                analytics = VideoAnalytics.objects.select_for_update().get(video=instance.video)
            except VideoAnalytics.DoesNotExist:
                print(f"⚠️ Analytics doesn't exist for video {instance.video.id if instance.video else 'None'} - skipping update")
                return
                
            # Use the optimized method to get all period counts in a single query
            video_service = VideoService()
            
            # Make sure we're using the correct method
            period_counts = video_service.get_all_period_views_counts_optimized(instance.video)
            
            # Debug output to verify we're getting the right data
            print(f"🔍 Period counts from optimized query: {period_counts}")
            
            # Update analytics with the counts - now including total views
            analytics.total_views = period_counts['total']
            analytics.last_24h_views = period_counts['day_1']
            analytics.last_7d_views = period_counts['day_7']
            analytics.last_30d_views = period_counts['day_30']
            
            analytics.save(update_fields=[
                'total_views', 
                'last_24h_views', 
                'last_7d_views', 
                'last_30d_views', 
                'updated_at'
            ])
            print(f"✅ Updated view metrics for video: {instance.video.title}")
    except Exception as e:
        print(f"❌ Error updating view analytics: {str(e)}")
        # Print the full stack trace for debugging
        import traceback
        print(traceback.format_exc())

@receiver(pre_delete, sender=Video)
def handle_video_cleanup(sender, instance, **kwargs):
    """DELETE signal - Only deletes analytics when video is deleted"""
    if hasattr(instance, '_cleanup_processed'):
        print("⏩ Skipping duplicate video cleanup")
        return
        
    try:
        instance._cleanup_processed = True
        
        # Only delete analytics, keep everything else (likes, reviews, views)
        try:
            if hasattr(instance, 'analytics'):
                instance.analytics.delete()
                print("✅ Deleted video analytics")
        except VideoAnalytics.DoesNotExist:
            print("⚠️ Analytics already deleted")
            
        logger.info(f"✅ Preserved engagement data and cleaned up analytics for video: {instance.title}")
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {str(e)}")

@receiver(post_save, sender=Video)
def handle_video_update(sender, instance, created, **kwargs):
    """UPDATE signal - Updates analytics when video details change"""
    if created:  # Skip if this is a new video (handled by handle_analytics_create)
        return
        
    try:
        with transaction.atomic():
            # Get analytics with a lock to prevent concurrent modifications
            analytics = VideoAnalytics.objects.select_for_update().get(video=instance)
            
            # Update title if it changed
            if analytics.title != instance.title:
                analytics.title = instance.title
                analytics.save(update_fields=['title', 'updated_at'])
                logger.info(f"✅ Updated analytics title for video: {instance.title}")
    except Exception as e:
        logger.error(f"❌ Error updating video analytics: {str(e)}")

@receiver(pre_delete, sender=Video)
def cleanup_empty_playlists(sender, instance, **kwargs):
    """
    When a video is about to be deleted:
    1. Get playlist IDs BEFORE cascade happens
    2. Delete playlists that will become empty
    """
    try:
        # Get playlists that only contain this video
        playlist_ids = list(instance.playlist_items.values_list('playlist_id', flat=True))
        print(f"🎯 Found playlists before delete: {playlist_ids}")
        
        if playlist_ids:
            # Find playlists that only have this one video
            playlists_to_delete = Playlist.objects.filter(
                id__in=playlist_ids
            ).annotate(
                video_count=models.Count('items')
            ).filter(video_count=1)
            
            count = playlists_to_delete.count()
            if count > 0:
                print(f"🗑️ Deleting {count} playlists that will be empty")
                playlists_to_delete.delete()
                
    except Exception as e:
        print(f"❌ Error in cleanup: {str(e)}")

@receiver(pre_delete, sender=User)
def modify_username_in_view_history_on_delete(sender, instance, **kwargs):
    """Store both IP and deleted username in ip_address field in ViewHistory upon user deletion"""
    views = ViewHistory.objects.filter(user=instance)
    
    for view in views:
        original_ip = view.ip_address or "No IP"
        view.user = None
        view.ip_address = f"IP:{original_ip} | User:{instance.username}*DELETED*"
        view.save()

@receiver(post_save, sender=ViewHistory)
def update_video_analytics_watch_stats(sender, instance, created, **kwargs):
    """
    Debug signal to check when ViewHistory updates happen during logout
    """
    print("\n=== ViewHistory Signal Debug ===")
    print(f"• Event Type: {'Creation' if created else 'Update'}")
    print(f"• Video: {instance.video.title}")
    
    try:
        with transaction.atomic():
            # Check if analytics exists before trying to update it
            try:
                analytics = VideoAnalytics.objects.select_for_update().get(video=instance.video)
            except VideoAnalytics.DoesNotExist:
                print(f"⚠️ Analytics doesn't exist for video {instance.video.id} - skipping watch stats update")
                print("=== End Signal Debug ===\n")
                return
                
            total_views = instance.video.views 
                
            if not created:  # Remove duration_watched check
                old_avg_watch_time = analytics.watch_time
                new_minutes = (instance.duration_watched.total_seconds() if instance.duration_watched else 0) / 60
                new_avg = ((analytics.watch_time * (total_views - 1)) + new_minutes) / total_views
                
                old_completion_rate = analytics.completion_rate
                old_completed = analytics.completed_views
                if instance.completed is True:
                    analytics.completed_views += 1
                    print(f"🔑 Logged in user - completed video")
                else:
                    analytics.completed_views += 0
                    print(f"🔑 Logged in user - did not complete video")
                    
                new_rate = (analytics.completed_views / total_views) * 100
                
                analytics.watch_time = new_avg       
                analytics.completion_rate = new_rate
                
                print(f"""
    📊 Watch Update (Logged in user):
    • Total Views: {total_views}
    • Duration: {instance.duration_watched or '0:00:00'}
    • Old watch time: {old_avg_watch_time}
    • New watch time: {analytics.watch_time}
    • Old completed count: {old_completed}
    • New completed count: {analytics.completed_views}
    • Old completion rate: {old_completion_rate}
    • New completion rate: {analytics.completion_rate}
    """)
            
            analytics.save(update_fields=[
                'watch_time',
                'completion_rate',
                'completed_views'
            ])
            
            # Verify save
            analytics.refresh_from_db()
            print(f"✅ Verified save - completed views: {analytics.completed_views}")
    except Exception as e:
        print(f"❌ Error in watch stats update: {str(e)}")
    
    print("=== End Signal Debug ===\n")

@receiver(pre_delete, sender=Video)
def preserve_video_info(sender, instance, **kwargs):
    """Save video info to related models before deletion"""
    try:
        # Store video info in reviews
        for review in instance.reviews.all():
            review.deleted_video_title = instance.title
            review.deleted_video_id = instance.id  # UUID field
            review.save(update_fields=['deleted_video_title', 'deleted_video_id'])
        
        # Store video info in likes
        for like in instance.likes.all():
            like.deleted_video_title = instance.title
            like.deleted_video_id = instance.id  # UUID field
            like.save(update_fields=['deleted_video_title', 'deleted_video_id'])
        
        # Store video info in view history
        for view in instance.views_history.all():
            view.deleted_video_title = instance.title
            view.deleted_video_id = instance.id  # UUID field
            view.save(update_fields=['deleted_video_title', 'deleted_video_id'])
            
        print(f"✅ Preserved video info in {instance.reviews.count()} reviews, {instance.likes.count()} likes, and {instance.views_history.count()} views")
        
    except Exception as e:
        print(f"❌ Error preserving video info: {str(e)}")
        logger.error(f"Failed to preserve video info: {str(e)}")
