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
    
    # Get stats using the class's own method to generate the key
    video_stats = video_stats_cache.get_video_stats(user_id)

    if video_stats:
        print("📊 Retrieved video stats from cache:")
        for key, value in video_stats.items():
            print(f"Key: {key}, Value: {value}")
            video_id, window_id = key.split(':')
            
            view_history_entry = ViewHistory.objects.filter(
                video_id=video_id, 
                window_id=window_id, 
                user_id=user_id
            ).first()

            if view_history_entry:
                # Refresh from DB to ensure we have latest state
                view_history_entry.refresh_from_db()
                
                # Update the fields
                view_history_entry.duration_watched = timedelta(seconds=float(value['total_watched']))
                view_history_entry.completed = value['is_completed'] == 'True'
                
                # Force update to trigger signal
                view_history_entry.save(
                    force_update=True, 
                    update_fields=['duration_watched', 'completed']
                )
                print(f"🔄 Updated ViewHistory entry for Video ID: {video_id}, Window ID: {window_id} : {view_history_entry.duration_watched} : {view_history_entry.completed}")
            else:
                print(f"No ViewHistory entry found for Video ID: {video_id}, Window ID: {window_id}")

    # Use the same pattern for invalidation as for retrieval
    video_stats_cache.invalidate(user_id)
    print(f"🗑️ Invalidated cached video stats for user ID: {user_id}")

@shared_task
def generate_speech_task(username, report_type):
    """Generate speech and store EVERYTHING in DigitalOcean Spaces only - no local files"""
    try:
        # Get report
        report = Report.objects.get(user__username=username)
        
        # Get report content from DO Spaces
        import requests
        from io import BytesIO
        
        if report_type == "user":
            report_url = report.user_report_url
        else:
            report_url = report.video_report_url
            
        print(f"🔍 Getting report from DO Spaces: {report_url}")
        response = requests.get(report_url)
        if response.status_code != 200:
            print(f"❌ ERROR: Failed to fetch report: {response.status_code}")
            return None
            
        # Process content in memory
        content = response.text
        cleaned_content = content.replace('*', '')
        
        # UPLOAD CLEANED TEXT TO DO SPACES
        from custom_storage import upload_file_to_spaces
        cleaned_filename = f"reports/{username}_{report_type}_cleaned.txt"
        cleaned_url = upload_file_to_spaces(cleaned_content.encode('utf-8'), cleaned_filename)
        
        if not cleaned_url:
            print("❌ ERROR: Failed to upload cleaned text to DO Spaces")
            return None
        
        print(f"✅ SUCCESS: Uploaded cleaned text to {cleaned_url}")
        
        # TTS requires a file path output, so we must use a temporary file
        # This is the only place we need local file access
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name
            
        # Run TTS
        from TTS.api import TTS
        tts = TTS(model_name="tts_models/en/vctk/vits")
        tts.tts_to_file(text=cleaned_content, file_path=temp_path, speaker="p339")
        
        # IMMEDIATELY read file to memory and delete
        try:
            with open(temp_path, 'rb') as f:
                audio_data = f.read()
            os.unlink(temp_path)  # Delete immediately
            print(f"✅ Generated audio ({len(audio_data)} bytes) and deleted temp file")
        except Exception as file_err:
            print(f"❌ ERROR reading temp file: {str(file_err)}")
            try:
                os.unlink(temp_path)  # Try to clean up
            except:
                pass
            return None
            
        # UPLOAD AUDIO TO DO SPACES
        audio_filename = f"reports/{username}_{report_type}_audio.wav"
        audio_url = upload_file_to_spaces(audio_data, audio_filename)
        
        if not audio_url:
            print("❌ ERROR: Failed to upload audio to DO Spaces")
            return None
            
        print(f"✅ SUCCESS: Uploaded audio to {audio_url}")
        
        # Update report
        now = timezone.now()
        if report_type == "user":
            report.user_report_audio_file_url = audio_url
            report.user_report_audio_generated_at = now
        else:
            report.video_report_audio_file_url = audio_url
            report.video_report_audio_generated_at = now
            
        report.audio_is_generated = True
        report.save()
        
        print(f"✅ SUCCESS: Updated report with audio URL: {audio_url}")
        
        # DELETE TEMP FILE FROM DO SPACES
        from custom_storage import delete_file_from_spaces
        deleted = delete_file_from_spaces(cleaned_filename)
        if deleted:
            print(f"🗑️ SUCCESS: Deleted temporary cleaned text file from DO Spaces: {cleaned_filename}")
        else:
            print(f"⚠️ WARNING: Failed to delete temporary cleaned text file: {cleaned_filename}")
        
        # Everything is now ONLY in DO Spaces!
        return audio_url
            
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
