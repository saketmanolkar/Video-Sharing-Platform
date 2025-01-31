from celery import shared_task
from .models import UserSession
from projects.models import ViewHistory
from .services.cache_service import SessionActivityCache, VideoStatsCache
from datetime import timedelta
import logging
from django.utils import timezone
import os
from django.conf import settings
from .services.user_services import SpeechService
from .models import Report

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    name='users.tasks.create_user_session',
    queue='celery'
)
def create_user_session(self, user_id, device_info, browser_info, ip_location):
    """
    Async task to create user session
    Args:
        user_id: ID of the user
        device_info: Dictionary containing device information
        browser_info: Dictionary containing browser information
        ip_location: IP address of the user
    Returns:
        str: Session ID
    """
    try:
        # Create session record
        session = UserSession.objects.create(
            user_id=user_id,
            device_info=device_info,
            browser_info=browser_info,
            ip_location=ip_location
        )
        
        logger.warning(f"✅ Async session created: {session.id}")
        return str(session.id)
        
    except Exception as e:
        logger.error(f"❌ Session creation failed: {str(e)}")
        # Retry with exponential backoff
        retry_countdown = 2 ** self.request.retries
        self.retry(countdown=retry_countdown, exc=e)

def merge_activity_logs(existing_log, new_log):
    """Helper function to merge activity logs"""
    # Debug prints
    print("\n=== MERGING LOGS ===")
    print("Existing log:", existing_log)
    print("New log:", new_log)
    
    # Initialize if empty
    existing_log = existing_log or {
        "pages_visited": [],
        "session_stats": {
            "total_pages": 0,
            "start_time": None,
            "last_activity": None
        }
    }
    
    # IMPORTANT: Extend the list, don't replace
    all_pages = existing_log.get("pages_visited", []) + new_log.get("pages_visited", [])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_pages = []
    for page in all_pages:
        page_key = f"{page['timestamp']}_{page['path']}"
        if page_key not in seen:
            seen.add(page_key)
            unique_pages.append(page)
    
    merged = {
        "pages_visited": unique_pages,
        "session_stats": {
            "total_pages": len(unique_pages),
            "start_time": existing_log["session_stats"]["start_time"] or new_log["session_stats"]["start_time"],
            "last_activity": new_log["session_stats"]["last_activity"]
        }
    }
    
    # Debug print
    print("Merged result:", merged)
    return merged

@shared_task(
    bind=True,
    max_retries=3,
    name='users.tasks.save_session_activity',
    queue='celery'
)
def save_session_activity(self, session_id, user_id):
    from .services.cache_service import SessionActivityCache
    """
    Async task to save session activity and cleanup
    """
    try:
        # Get the current session
        session = UserSession.objects.get(id=session_id)
        activity_cache = SessionActivityCache()
        
        # Get new activity from cache
        new_activity = activity_cache.get_activity_log(user_id, session_id)
        
        # Merge with existing activity log
        merged_activity = merge_activity_logs(session.activity_log, new_activity)
        
        # Save merged data and end the current session
        session.activity_log = merged_activity
        session.end_time = timezone.now()
        session.save()
        
        # Clear cache for the current session
        activity_cache.clear_activity_cache(user_id, session_id)

        # Close any other active sessions for the user
        other_sessions = UserSession.objects.filter(user_id=user_id, end_time__isnull=True).exclude(id=session_id)
        stray_count = 0
        for other_session in other_sessions:
            other_session.end_time = timezone.now()  # Just close them
            other_session.save()
            stray_count += 1

        logger.warning(f"✅ Session activity saved: {session_id}")
        logger.warning(f"✅ {stray_count} stray sessions closed for user {user_id}")
        return str(session_id)
        
    except Exception as e:
        logger.error(f"❌ Session activity save failed: {str(e)}")
        retry_countdown = 2 ** self.request.retries
        self.retry(countdown=retry_countdown, exc=e)

@shared_task(bind=True, max_retries=3)
def save_activity_overflow(self, session_id, user_id):
    from .services.cache_service import SessionActivityCache
    try:
        session = UserSession.objects.get(id=session_id)
        activity_cache = SessionActivityCache()
        
        # Get existing activity from session
        existing_activity = session.activity_log or {
            "pages_visited": [],
            "session_stats": {
                "total_pages": 0,
                "start_time": None,
                "last_activity": None
            }
        }
        
        # Get new activity from cache
        new_activity = activity_cache.get_activity_log(user_id, session_id)
        
        # Debug logging
        logger.info(f"📊 Existing pages: {len(existing_activity.get('pages_visited', []))}")
        logger.info(f"📊 New pages: {len(new_activity.get('pages_visited', []))}")
        
        # Merge activities
        merged_activity = {
            "pages_visited": existing_activity.get('pages_visited', []) + new_activity.get('pages_visited', []),
            "session_stats": {
                "total_pages": len(existing_activity.get('pages_visited', [])) + len(new_activity.get('pages_visited', [])),
                "start_time": existing_activity['session_stats']['start_time'] or new_activity['session_stats']['start_time'],
                "last_activity": new_activity['session_stats']['last_activity']
            }
        }
        
        # Save merged data
        session.activity_log = merged_activity
        session.save()
        
        # Clear cache after successful save
        activity_cache.clear_activity_cache(user_id, session_id)
        
        logger.warning(f"✅ Activity overflow appended: {session_id}")
        return str(session_id)
        
    except Exception as e:
        logger.error(f"❌ Activity overflow append failed: {str(e)}")
        retry_countdown = 2 ** self.request.retries
        self.retry(countdown=retry_countdown, exc=e)

@shared_task
def process_video_stats(user_id):
    video_stats_cache = VideoStatsCache()
    user_cache_key = f"user_{user_id}"  # Ensure consistent format

    # Retrieve video stats from cache
    video_stats = video_stats_cache.get_video_stats(user_cache_key)

    if video_stats:
        print("📊 Retrieved video stats from cache:")
        for key, value in video_stats.items():
            print(f"Key: {key}, Value: {value}")  # Log each retrieved stat
            video_id, window_id = key.split(':')  # Assuming key format is "video_id:window_id"
            
            # Retrieve the existing ViewHistory entry
            view_history_entry = ViewHistory.objects.filter(video_id=video_id, window_id=window_id, user_id=user_id).first()

            if view_history_entry:
                # Update the fields directly
                view_history_entry.duration_watched = timedelta(seconds=float(value['total_watched']))  # Convert to timedelta
                view_history_entry.completed = value['is_completed'] == 'True'  # Convert to boolean
                view_history_entry.save()  # Save the updated entry
                print(f"🔄 Updated ViewHistory entry for Video ID: {video_id}, Window ID: {window_id}")
            else:
                print(f"No ViewHistory entry found for Video ID: {video_id}, Window ID: {window_id}")

    # Invalidate the cached stats
    video_stats_cache.invalidate(user_cache_key)
    print(f"🗑️ Invalidated cached video stats for user ID: {user_id}")

@shared_task
def generate_speech_task(username, report_type):
    try:
        # Get report first
        report = Report.objects.get(user__username=username)
        
        # Initialize speech service
        reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        speech_service = SpeechService(reports_dir=reports_dir)
        
        # Generate the audio file
        audio_file_name = speech_service.generate_speech(username, report_type)
        
        if audio_file_name:
            # Construct the audio file URL
            audio_file_url = f"/media/reports/{audio_file_name}"
            now = timezone.now()

            # Simple direct updates with timestamps
            if report_type == "user":
                report.user_report_audio_file_url = audio_file_url
                report.user_report_audio_generated_at = now
            else:
                report.video_report_audio_file_url = audio_file_url
                report.video_report_audio_generated_at = now
            
            report.audio_is_generated = True
            report.save()
            
            print(f"Updated report for {username} - {report_type}")
            print(f"Audio URL: {audio_file_url}")
            print(f"Generated at: {now}")
            
            return audio_file_name
            
    except Exception as e:
        print(f"Error in speech generation task: {str(e)}")
        return None
