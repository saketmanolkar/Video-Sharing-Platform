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
import time
from celery.schedules import crontab
from django_redis import get_redis_connection

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
def save_session_activity(self, session_id, user_id, inactive=False):
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
        
        # If the inactive flag is True, use the last activity timestamp
        if inactive and merged_activity and merged_activity["session_stats"]["last_activity"]:
            # Extract the time from the last activity timestamp (format: HH:MM:SS.fff)
            last_activity = merged_activity["session_stats"]["last_activity"]
            time_parts = last_activity.split(':')
            
            # Create a datetime with today's date and the exact last activity time
            now = timezone.now()
            hour, minute, seconds = time_parts
            second = float(seconds)
            
            # Build the end time from the parts
            end_time = now.replace(
                hour=int(hour),
                minute=int(minute),
                second=int(second),
                microsecond=int((second - int(second)) * 1000000)
            )
            
            # If this time appears to be in the future, it must be from yesterday
            if end_time > now:
                end_time = end_time - timedelta(days=1)
                
            session.end_time = end_time
            logger.warning(f"⏰ Session marked as inactive - set end_time to last activity: {end_time}")
        else:
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

@shared_task(bind=True, max_retries=3)
def generate_speech_task(self, username, report_type):
    """Generate speech and store EVERYTHING in DigitalOcean Spaces only - no local files"""
    print(f"🔊 STARTING SPEECH GENERATION: User={username}, Type={report_type}")
    try:
        # Debug numpy
        import sys
        print(f"Python path: {sys.path}")
        
        try:
            import numpy as np
            print(f"NumPy version: {np.__version__}")
            print(f"NumPy location: {np.__file__}")
            # Create a small array to confirm NumPy works
            test_arr = np.array([1, 2, 3])
            print(f"NumPy test array: {test_arr}")
        except Exception as np_err:
            print(f"⚠️ NumPy error: {str(np_err)}")
        
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
        cleaned_content = content.replace('*', '').replace('#', '').replace('/', ' or ')
        
        # UPLOAD CLEANED TEXT TO DO SPACES
        from custom_storage import upload_file_to_spaces
        cleaned_filename = f"reports/{username}_{report_type}_cleaned.txt"
        cleaned_url = upload_file_to_spaces(cleaned_content.encode('utf-8'), cleaned_filename)
        
        if not cleaned_url:
            print("❌ ERROR: Failed to upload cleaned text to DO Spaces")
            return None
        
        print(f"✅ SUCCESS: Uploaded cleaned text to {cleaned_url}")
        
        # NEW: Function to split text into manageable chunks
        def split_into_chunks(text, max_chunk_size=350):
            import re
            # Split on sentences (more intelligently than just '.')
            sentence_endings = r'(?<=[.!?])\s+'
            sentences = re.split(sentence_endings, text)
            
            chunks = []
            current_chunk = ""
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                    
                # Make sure sentence ends with proper punctuation
                if not sentence.rstrip().endswith(('.', '!', '?')):
                    sentence = sentence.rstrip() + '.'
                
                # If adding this sentence would make chunk too large, start a new chunk
                if len(current_chunk) + len(sentence) + 1 > max_chunk_size:
                    if current_chunk:  # Don't add empty chunks
                        chunks.append(current_chunk)
                    current_chunk = sentence + " "
                else:
                    current_chunk += sentence + " "
            
            # Add the last chunk if it has content
            if current_chunk.strip():
                chunks.append(current_chunk)
                
            print(f"📚 Split content into {len(chunks)} chunks (avg size: {sum(len(c) for c in chunks)/max(len(chunks), 1):.1f} chars)")
            return chunks
        
        # Split the content into chunks
        chunks = split_into_chunks(cleaned_content)
        
        # Import TTS once outside the loop
        from TTS.api import TTS
        import os
        import tempfile
        import wave
        from pydub import AudioSegment
        
        # Create a temporary directory for all chunk files
        with tempfile.TemporaryDirectory() as temp_dir:
            chunk_files = []
            
            # Initialize TTS only once
            try:
                # Replace Tacotron2 with glow-tts as primary model
                tts = TTS(model_name="tts_models/en/ljspeech/glow-tts")
                
                # Process each chunk (same chunking logic, better model)
                for i, chunk in enumerate(chunks):
                    chunk_path = os.path.join(temp_dir, f"chunk_{i}.wav")
                    print(f"🔊 Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                    
                    # Generate TTS for this chunk
                    tts.tts_to_file(text=chunk, file_path=chunk_path)
                    chunk_files.append(chunk_path)
                
                # Combine audio files
                if not chunk_files:
                    raise Exception("No audio chunks were generated")
                
                # Combine using pydub (much lower memory usage than raw numpy concatenation)
                combined = AudioSegment.empty()
                for chunk_file in chunk_files:
                    audio_segment = AudioSegment.from_wav(chunk_file)
                    combined += audio_segment
                
                # Export combined audio to a temporary file
                final_temp_path = os.path.join(temp_dir, "final_audio.wav")
                combined.export(final_temp_path, format="wav")
                
                # Read the final combined file
                with open(final_temp_path, 'rb') as f:
                    audio_data = f.read()
                    
                print(f"✅ Generated combined audio ({len(audio_data)} bytes) from {len(chunks)} chunks")
                    
            except Exception as tts_err:
                print(f"⚠️ TTS with chunking failed: {str(tts_err)}")
                try:
                    # Fallback to a different model if glow-tts chunking fails
                    final_temp_path = os.path.join(temp_dir, "fallback_audio.wav")
                    tts = TTS(model_name="tts_models/en/ljspeech/vits")  # Try VITS as fallback
                    tts.tts_to_file(text=cleaned_content[:1000], file_path=final_temp_path)
                    
                    with open(final_temp_path, 'rb') as f:
                        audio_data = f.read()
                        
                    print(f"⚠️ Used fallback approach with limited text: {len(audio_data)} bytes")
                except Exception as tts_err2:
                    print(f"❌ Both TTS approaches failed: {str(tts_err2)}")
                    raise Exception(f"TTS generation failed with both approaches: {str(tts_err2)}")
        
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
        
        # Wait 1 second for transaction to complete
        time.sleep(1)
        
        # DELETE TEMP FILE FROM DO SPACES
        from custom_storage import delete_file_from_spaces
        deleted = delete_file_from_spaces(cleaned_filename)
        if deleted:
            print(f"🗑️ SUCCESS: Deleted temporary cleaned text file from DO Spaces: {cleaned_filename}")
        else:
            print(f"⚠️ WARNING: Failed to delete temporary cleaned text file: {cleaned_filename}")
        
        # Everything is now ONLY in DO Spaces!
        print(f"✅ COMPLETED SPEECH GENERATION: User={username}, Type={report_type}")
        return audio_url
            
    except Exception as e:
        print(f"❌ SPEECH GENERATION FAILED: User={username}, Type={report_type}, Error={str(e)}")
        import traceback
        traceback.print_exc()
        
        # Retry the task
        retry_count = self.request.retries
        print(f"🔄 Retrying task (attempt {retry_count+1}/3)")
        self.retry(exc=e, countdown=5 * (retry_count + 1))
        
        return None
    finally:
        # Always release the lock when task completes or fails
        try:
            from users.services.cache_service import TTSLockCache
            tts_lock = TTSLockCache()
            tts_lock.release_global_lock()
            print(f"🔓 RELEASED TTS LOCK: User={username}, Type={report_type}")
        except Exception as lock_err:
            print(f"⚠️ WARNING: Failed to release TTS lock: {str(lock_err)}")

@shared_task(name='users.tasks.check_expired_keys')
def check_expired_keys():
    """Check for keys with last activity older than one hour"""
    redis = get_redis_connection("default")
    
    # Get all session keys
    session_pattern = f"{SessionActivityCache.FOLDER}:user_*_session_*"
    session_keys = redis.keys(session_pattern)
    
    now = timezone.now()
    one_hour_ago = now - timedelta(hours=1)
    
    for key in session_keys:
        key_str = key.decode('utf-8')
        
        # Extract user_id and session_id
        parts = key_str.split(':')
        if len(parts) >= 3:
            user_session = parts[-1]
            user_id = user_session.split('_')[1]
            session_id = user_session.split('_')[3]
            
            # Get all activities for this session
            activities = redis.hgetall(key)
            if not activities:
                continue
                
            # Find the timestamp of the most recent activity
            latest_timestamp = max(activities.keys()).decode()
            
            # Parse the timestamp (HH:MM:SS.fff)
            # If timestamp is more than an hour old, process it
            hour, minute, seconds = latest_timestamp.split(':')
            
            # Create today's date with this time
            latest_time = now.replace(
                hour=int(hour),
                minute=int(minute),
                second=int(float(seconds)),
                microsecond=0
            )
            
            # If timestamp appears to be in the future, it's from yesterday
            if latest_time > now:
                latest_time = latest_time - timedelta(days=1)
            
            # Check if inactive for more than an hour
            if latest_time < one_hour_ago:
                # Queue tasks to process this inactive session
                save_session_activity.delay(session_id, user_id, inactive=True)
                process_video_stats.delay(user_id)
                
                # Log what we're processing
                inactive_minutes = (now - latest_time).total_seconds() / 60
                print(f"Processing inactive session: user_id={user_id}, session_id={session_id}, inactive for {inactive_minutes:.1f} minutes")
