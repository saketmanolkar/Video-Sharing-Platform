from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.staticfiles.storage import staticfiles_storage
from django.templatetags.static import static
from django.utils.dateparse import parse_datetime
import json
from projects.services.video_services import VideoService
from users.services.follow_services import FollowService
from users.models import Profile
from projects.services.analytics_service import AnalyticsService
from .cache_service import ProfileCache
from django.db.models import Q
from users.services.user_analytics_service import UserAnalyticsService
from users.models import UserActivitySummary
from users.services.follower_analytics_service import FollowerAnalyticsService
from projects.services.video_stat_analytics_service import VideoStatisticsService
import google.generativeai as genai
import os
from django.conf import settings
from datetime import datetime
from TTS.api import TTS
import psutil
import time
import glob
from users.models import User  # Import User model
from users.models import Report  # Import your Report model
from django.db.utils import IntegrityError
from django.db.models import Count, Prefetch
from projects.models import Playlist, Video, Tag
from projects.models import ViewHistory
from projects.models import PlaylistItem
from custom_storage import upload_content_to_spaces

class UserReportService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.model = None
        self.base_prompts = {
            'user': """You are analyzing user activity data for {username} for a video sharing platform called "FilmsNation". You job is to analyze the user data of {username} , who is a user of FilmsNation.
            Always format your response as follows:
            1. Use markdown formatting
            2. Start with a headline that says "User Data Analytics Report for {username}"
            3. Follow a strict format of 3 sections for the report - 1. Overview, 2. Details, 3. Recommendations
            4. While writing the Details section, give a detailed analysis of the user's activity data in 5 concise bullet points that capture all the provided metrics.
            5. You are writing a professional report. Be concise & Write in paragraph format.
            6. Give recommendations to the user from the perspective of improving the user's app usage habits only.
            7. The Word limit of this report stictly should'nt exceed 250 words.
            8. Donot give moral advice  to {username}. You are a professional data analyst. Just do your job.

            Now, analyze this user's activity data: """,
            
            'video': """You are working as a data analyst for a Video Sharing company called "FilmsNation". Your job is to analyze the video data of {username}, who is a uploads his videos on FilmsNation. 
            Always format your response as follows:
            1. Use markdown formatting
            2. Start with a headline that says "Video Data Analytics Report for {username}"
            3. Follow a strict format of 3 sections for the report - 1. Overview, 2. Details, 3. Recommendations
            4. While writing the Details section, give a detailed analysis of the video's performance data in 5 concise bullet points that capture all the provided metrics.
            5. In the Recommendations section, in 3 concise bullet points, identify what worked well for {username} , Point out areas for improvement and provide user specific tips for future videos based no the provided metrics.
            6. You are writing a professional report. Be concise & Write in paragraph format.
            7. The Word limit of this report stictly should'nt exceed 250 words.
            8. Donot give moral advice  to {username}. You are a professional data analyst. Just do your job.

            Now, analyze this video performance data: """
        }
        self.configure_api()
        self.reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        os.makedirs(self.reports_dir, exist_ok=True)

    def configure_api(self):
        """Configure the Gemini API with the provided API key."""
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate_report_content(self, prompt, report_type='user', username=None):
        """Generate content using the Gemini API based on the provided prompt and type."""
        base_prompt = self.base_prompts.get(report_type, self.base_prompts['user'])
        if username and report_type == 'user':
            base_prompt = base_prompt.format(username=username)
        full_prompt = f"{base_prompt}\n{prompt}"
        response = self.model.generate_content(full_prompt)
        report_content = response.text
        
        # Save report and update the database
        self.save_report_and_update_db(username, report_content, report_type)
        
        return {
            'text': report_content,
        }

    def save_report_and_update_db(self, username, report_content, report_type):
        """Save report text and update the database."""
        try:
            # Get the user instance
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            print(f"User '{username}' not found.")
            return None

        # Get or create a report for the user
        report, created = Report.objects.get_or_create(user=user)
        
        # Create a new filename for the report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{username}_{report_type}_{timestamp}.txt"
        
        # Hard-code the report header
        today_date = datetime.now().strftime('%Y-%m-%d')
        report_header = f"{report_type.upper()} DATA REPORT - GENERATED ON {datetime.now().strftime('%d %b %I:%M %p')}.\n\n"
        
        # Combine header and content
        full_content = report_header + report_content
        
        # Handle storage differently based on environment
        if settings.TESTING:
            # Testing mode: Save locally
            self.reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
            os.makedirs(self.reports_dir, exist_ok=True)
            
            # Delete existing report files
            try:
                report_pattern = f"{username}_{report_type}_*.txt"
                existing_reports = [f for f in os.listdir(self.reports_dir) 
                                  if f.startswith(f"{username}_{report_type}_") and f.endswith('.txt')]
                
                for report_file in existing_reports:
                    try:
                        report_path = os.path.join(self.reports_dir, report_file)
                        os.remove(report_path)
                        print(f"Successfully deleted existing {report_type} report: {report_file}")
                    except OSError as e:
                        print(f"Error deleting {report_type} report {report_file}: {str(e)}")
            except Exception as e:
                print(f"Error handling report deletion: {str(e)}")
            
            # Save local file
            text_path = os.path.join(self.reports_dir, filename)
            with open(text_path, 'w') as f:
                f.write(full_content)
            
            # Use file:// URL for local testing
            report_url = f"file://{text_path}"
        else:
            # Production mode: Upload directly to DO Spaces
            
            # Delete ALL existing reports for this user and type in DO Spaces
            try:
                # Import boto3
                import boto3
                
                print(f"🔍 DEBUG: Starting cleanup of reports for user: {username}, type: {report_type}")
                print(f"🔍 DEBUG: AWS settings - Bucket: {settings.AWS_STORAGE_BUCKET_NAME}, Endpoint: {settings.AWS_S3_ENDPOINT_URL}")
                
                # Create a boto3 client using settings
                s3 = boto3.client('s3',
                    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME)
                
                # List all objects in the reports directory
                print(f"🔍 DEBUG: Listing objects with prefix 'reports/'")
                response = s3.list_objects_v2(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Prefix='reports/'
                )
                
                # Count and log found objects
                found_files = []
                if 'Contents' in response:
                    print(f"🔍 DEBUG: Found {len(response['Contents'])} total objects in bucket")
                    for obj in response['Contents']:
                        found_files.append(obj['Key'])
                    print(f"🔍 DEBUG: All files in reports/: {', '.join(found_files)}")
                else:
                    print("🔍 DEBUG: No objects found in reports/")
                
                # Track deleted files
                deleted_files = []
                
                # Delete matching report files using exact start pattern
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        
                        # Check if file matches our pattern (username_type_)
                        search_pattern = f"{username}_{report_type}_"
                        
                        # We need to check if the filename (not full path) starts with our pattern
                        # Extract just the filename part from the full key
                        filename_part = key.split('/')[-1]
                        
                        if filename_part.startswith(search_pattern) and filename_part.endswith('.txt'):
                            print(f"🔍 DEBUG: MATCH FOUND - will delete: {key}")
                            
                            try:
                                # Delete the object
                                s3.delete_object(
                                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                                    Key=key
                                )
                                deleted_files.append(key)
                                print(f"✅ DELETED: Report {key}")
                            except Exception as e:
                                print(f"❌ ERROR: Failed to delete {key}: {str(e)}")
                
                
            except Exception as e:
                print(f"❌ ERROR: Failed to clean up old reports: {str(e)}")
                import traceback
                traceback.print_exc()
            
            report_url = upload_content_to_spaces(full_content, filename)
        
        # Update the appropriate report URL and timestamp
        if report_type == 'user':
            report.user_report_url = report_url
            report.user_report_generated_at = datetime.now()
            report.user_report_audio_file_url = None
            report.user_report_audio_generated_at = None
        elif report_type == 'video':
            report.video_report_url = report_url
            report.video_report_generated_at = datetime.now()
            report.video_report_audio_file_url = None
            report.video_report_audio_generated_at = None
        
        # Handle audio file cleanup in both environments
        if settings.TESTING:
            # Define the audio file path to delete after report generation
            audio_file_name = f"{username}_{report_type}_audio.wav"
            audio_file_path = os.path.join(self.reports_dir, audio_file_name)
            
            # Check if the report audio file already exists and delete it if necessary
            if os.path.exists(audio_file_path):
                os.remove(audio_file_path)
                print(f"Deleted existing {report_type} data report audio file after report generation: {audio_file_path}")
        else:
            # Delete associated audio files in DO Spaces too
            try:
                # Use the same s3 client from above
                # List objects again to find audio files
                response = s3.list_objects_v2(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Prefix='reports/'
                )
                
                # Filter for this user's audio files of the specified type
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        # Check if this is an audio file for this user and type
                        if key.endswith('.wav') and f"/{username}_{report_type}_audio" in key:
                            try:
                                # Delete the object
                                s3.delete_object(
                                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                                    Key=key
                                )
                                print(f"Deleted old audio file from DO Spaces: {key}")
                            except Exception as e:
                                print(f"Error deleting audio file {key}: {str(e)}")
            except Exception as e:
                print(f"Error cleaning up old audio files in DO Spaces: {str(e)}")
        
        report.save()

        return {
            'text_file': filename
        }

class SpeechService:
    def __init__(self, reports_dir):
        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)  # Create the directory if it doesn't exist

    def generate_speech(self, username, report_type):
        """Generate speech from a text file associated with the username and report type."""
        try:
            print(f"🔊 Starting speech generation for {username}, report type: {report_type}")
            
            # Get report content from the correct URL
            content = None
            remote_url = None
            
            try:
                from users.models import Report, User
                from django.conf import settings
                
                # Check if we're in testing mode
                is_testing = getattr(settings, 'TESTING', False)
                print(f"🔊 Environment mode: {'TESTING' if is_testing else 'PRODUCTION'}")
                
                user = User.objects.get(username=username)
                report = Report.objects.get(user=user)
                
                # Get the appropriate report URL based on type
                if report_type == 'user':
                    remote_url = report.user_report_url
                elif report_type == 'video':
                    remote_url = report.video_report_url
                else:
                    print(f"❌ Invalid report type: {report_type}")
                    return None
                    
                if not remote_url:
                    print(f"❌ No report URL found for {username} and {report_type}")
                    return None
                    
                print(f"📄 Found report URL: {remote_url}")
                
                # Fetch content from remote URL
                import requests
                try:
                    response = requests.get(remote_url)
                    if response.status_code == 200:
                        content = response.text
                        print(f"✅ Successfully fetched content: {len(content)} characters")
                    else:
                        print(f"❌ Error fetching content: HTTP {response.status_code}")
                        return None
                except Exception as req_err:
                    print(f"❌ Request error: {str(req_err)}")
                    return None
                    
            except Exception as db_err:
                print(f"❌ Database error: {str(db_err)}")
                return None
            
            if not content:
                print("❌ No content found for TTS generation")
                return None

            # Remove asterisks from the content
            cleaned_content = content.replace('*', '')

            # Create temp files for processing
            import tempfile
            audio_file_name = f"{username}_{report_type}_audio.wav"
            temp_audio_path = os.path.join(tempfile.gettempdir(), audio_file_name)
            
            # Initialize TTS and generate audio
            print(f"🔊 Generating audio with TTS engine...")
            tts = TTS(model_name="tts_models/en/vctk/vits")
            tts.tts_to_file(text=cleaned_content, file_path=temp_audio_path, speaker="p339")
            print(f"✅ Audio file generated at: {temp_audio_path}")
            
            # Upload to appropriate storage
            from django.conf import settings
            audio_url = None
            
            if not getattr(settings, 'TESTING', False):
                # Production: Upload to DigitalOcean Spaces
                print(f"📤 Uploading to DigitalOcean Spaces...")
                
                try:
                    # Make sure file exists before reading
                    if not os.path.exists(temp_audio_path):
                        print(f"❌ Temp audio file not found at: {temp_audio_path}")
                        return None
                    
                    # Read the generated audio file
                    with open(temp_audio_path, 'rb') as audio_file:
                        audio_content = audio_file.read()
                        print(f"✅ Read {len(audio_content)} bytes from temp audio file")
                    
                    # Upload to DO Spaces
                    from custom_storage import upload_file_to_spaces
                    spaces_path = f"reports/{audio_file_name}"
                    audio_url = upload_file_to_spaces(audio_content, spaces_path)
                    
                    if audio_url:
                        print(f"✅ Successfully uploaded to: {audio_url}")
                    else:
                        print("❌ upload_file_to_spaces returned None")
                        
                except Exception as upload_err:
                    print(f"❌ Upload error: {str(upload_err)}")
                    import traceback
                    traceback.print_exc()
                    # Fall back to local file
                    audio_url = f"/media/reports/{audio_file_name}"
                    # Copy to local reports directory
                    import shutil
                    shutil.copy(temp_audio_path, os.path.join(self.reports_dir, audio_file_name))
                    print(f"⚠️ Fallback to local file: {audio_url}")
            else:
                # Testing: Save locally
                local_audio_path = os.path.join(self.reports_dir, audio_file_name)
                import shutil
                shutil.copy(temp_audio_path, local_audio_path)
                audio_url = f"/media/reports/{audio_file_name}"
                print(f"✅ Saved to local path: {local_audio_path}")
            
            # Clean up temp files
            try:
                os.unlink(temp_audio_path)
                print(f"✅ Deleted temp audio file")
            except Exception as cleanup_err:
                print(f"⚠️ Error cleaning up temp file: {str(cleanup_err)}")
            
            return audio_url
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR in speech generation: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

class ProfileService:
    def __init__(self):
        self.profile_cache = ProfileCache()  # Initialize here
    
    def get_profile(self, profile_id, profile_model):
        """Get profile with cache"""
        # Try to get from cache first
        cached_data = self.profile_cache.get_profile_cache(profile_id)
        
        if cached_data:
            print("\n🎯 CACHE HIT: Found in cache")
            return profile_model.objects.get(id=profile_id)
        
        # If not in cache, get from DB
        print("\n💾 CACHE MISS: Getting from DB")
        profile = get_object_or_404(profile_model, id=profile_id)
        
        # Save to cache
        self.profile_cache.set_profile_cache(profile_id, profile)
        print(f"📝 Saved to cache: {profile_id}")
        
        return profile
    
    def get_user_videos(self, profile_id, profile_model, search_query=None):
        # Use select_related to fetch the user in the same query as the profile
        profile = get_object_or_404(profile_model.objects.select_related('user'), id=profile_id)
        
        # Store user reference to avoid repeated lookups
        user = profile.user
        
        # Fetch videos with prefetch_related to optimize queries
        videos = user.uploaded_videos.all().order_by('-created_at').prefetch_related('tags')
        
        # Prefetch playlist items and their related videos
        playlist_items_prefetch = Prefetch(
            'items',
            queryset=PlaylistItem.objects.select_related('video', 'video__uploader')
        )
        
        # Annotate playlists with item count and prefetch related items
        playlists = user.playlists.annotate(
            items_count=Count('items')
        ).prefetch_related(
            playlist_items_prefetch
        ).order_by('-created_at')

        # Apply search if query exists
        if search_query:
            videos = videos.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(tags__name__icontains=search_query)
            ).distinct()

            playlists = playlists.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            ).distinct()

        # Use the existing method to get reactions in bulk
        reaction_lookup = VideoService.get_videos_with_reactions(videos)
        
        # Attach counts to videos
        for video in videos:
            video_id = str(video.id)
            if video_id in reaction_lookup:
                video.likes_count = reaction_lookup[video_id]['likes']
                video.dislikes_count = reaction_lookup[video_id]['dislikes']
            else:
                video.likes_count = 0
                video.dislikes_count = 0

        return {
            'profile': profile,
            'videos': videos,
            'playlists': playlists,
            'search_query': search_query
        }
    
    def get_user_history(self, profile):
        """Get user viewing history with optimized queries"""
        # Use select_related to fetch video, uploader, and uploader's profile in a single query
        # Also prefetch tags to avoid N+1 queries when displaying video tags
        history_entries = profile.user.view_history.select_related(
            'video', 
            'video__uploader',
            'video__uploader__profile'  # Prefetch the uploader's profile
        ).prefetch_related(
            'video__tags'  # Prefetch tags to avoid N+1 queries
        ).order_by('-viewed_at')
        
        # Extract videos from history entries
        history_videos = []
        for entry in history_entries:
            video = entry.video
            history_videos.append(video)
        
        return {
            'history_videos': history_videos
        }
    
    def get_total_views(self, user):
        from projects.models import Video
        return Video.objects.filter(uploader=user).aggregate(
            total_views=models.Sum('views')
        )['total_views'] or 0
    
    def get_profile_picture_url(self, profile):
        """Get profile picture URL with proper fallback"""
        if profile.profile_pics:
            return profile.profile_pics.url
        return staticfiles_storage.url('images/user-default.png')
    
    def clear_profile_picture(self, profile):
        """Clear the profile picture and return the updated profile"""
        try:
            if profile.profile_pics:
                # Delete the physical file
                profile.profile_pics.delete(save=False)
                # Set the field to None
                profile.profile_pics = None
                profile.save()
            return True, "Profile picture cleared successfully"
        except Exception as e:
            return False, f"Error clearing profile picture: {str(e)}"
    
    def update_profile(self, profile, user_data, profile_form, should_clear_pic=False):
        """Update profile and user data"""
        try:
            # Update User model fields
            user = profile.user
            user.first_name = user_data.get('first_name')
            user.last_name = user_data.get('last_name')
            user.username = user_data.get('username').lower()
            user.save()

            # Handle profile picture clearing if requested
            if should_clear_pic:
                success, message = self.clear_profile_picture(profile)
                if not success:
                    return False, message

            # Save profile form
            if profile_form.is_valid():
                profile_form.save()
                return True, "Profile updated successfully"
            return False, "Invalid form data"

        except Exception as e:
            return False, f"Error updating profile: {str(e)}"
    
    def get_creator_studio_data(self, profile_id, profile_model):
        """Get creator studio data for a profile"""
        profile = self.get_profile(profile_id, profile_model)
        videos = profile.user.uploaded_videos.all()
        analytics_data = VideoService.get_creator_studio_analytics(videos)
        
        # Add default thumbnail URL to the context
        default_thumbnail = static('images/default.jpg')
        
        # Get followers and following profiles
        followers = Profile.objects.filter(user__in=profile.user.followers_set.values('user'))
        following = Profile.objects.filter(user__in=profile.user.following_set.values('following'))
        
        # Get videos with their privacy status
        videos_with_privacy = videos.values('id', 'title', 'views', 'created_at', 'privacy_status', 'thumbnail')
        
        # Merge privacy status into analytics data
        for video in videos_with_privacy:
            video_id = str(video['id'])
            if video_id in analytics_data['video_analytics']:
                analytics_data['video_analytics'][video_id]['privacy_status'] = video['privacy_status']
        
        return {
            'profile': profile,
            'default_thumbnail': default_thumbnail,
            'video_analytics': analytics_data['video_analytics'],
            'followers': followers,
            'following': following,
        }

    def get_creator_studio_data_optimized(self, profile_id, profile_model):
        """Get only the essential data needed for creator studio display"""
        # Get profile with caching - only call this once
        cached_profile = self.profile_cache.get_profile_cache(profile_id)
        
        if cached_profile:
            # Check if cached_profile is a dictionary or an object
            if isinstance(cached_profile, dict):
                # If it's a dict, get the actual profile object from the database
                # Also fetch the activity_summary in the same query
                print("\n🎯 CACHE HIT: But need to fetch profile object")
                profile = profile_model.objects.select_related(
                    'user', 
                    'user__activity_summary'  # This fetches UserActivitySummary in the same query
                ).get(id=profile_id)
            else:
                profile = cached_profile
                print("\n🎯 CACHE HIT: Using cached profile object")
        else:
            # Get profile with select_related to avoid separate user query
            # Also fetch the activity_summary in the same query
            profile = profile_model.objects.select_related(
                'user', 
                'user__activity_summary'  # This fetches UserActivitySummary in the same query
            ).get(id=profile_id)
            # Cache it for future use
            self.profile_cache.set_profile_cache(profile_id, profile)
            print("\n💾 CACHE MISS: Fetched and cached profile")
        
        # Add default thumbnail URL
        default_thumbnail = static('images/default.jpg')
        
        # Store user reference to avoid repeated lookups
        user = profile.user
        
        # Check if activity_summary was fetched with select_related
        if hasattr(user, 'activity_summary') and user.activity_summary:
            # Use the already fetched activity_summary (no additional query)
            followers_count = user.activity_summary.total_followers
            following_count = user.activity_summary.total_following
        else:
            # Fall back to counting followers/following
            followers_count = user.followers_set.count()
            following_count = user.following_set.count()
        
        # Get followers and following with efficient queries
        followers = (Profile.objects
            .filter(user__in=user.followers_set.values('user'))
            .select_related('user'))
            
        following = (Profile.objects
            .filter(user__in=user.following_set.values('following'))
            .select_related('user'))
        
        # Get videos with necessary related data in a single query
        videos = (user.uploaded_videos
            .select_related('uploader', 'analytics'))
        
        # Build video analytics dictionary directly
        video_analytics = {}
        for video in videos:
            video_id = str(video.id)
            video_analytics[video_id] = {
                'title': video.title,
                'thumbnail_url': video.thumbnail.url if video.thumbnail else None,
                'total_views': video.views,  # Direct from video model
                'total_likes': video.analytics.total_likes if hasattr(video, 'analytics') and video.analytics else 0,
                'total_dislikes': video.analytics.total_dislikes if hasattr(video, 'analytics') and video.analytics else 0,
                'total_comments': video.analytics.total_comments if hasattr(video, 'analytics') and video.analytics else 0,
                'created_at': parse_datetime(video.created_at) if isinstance(video.created_at, str) else video.created_at,
                'privacy_status': video.privacy_status
            }
        
        return {
            'profile': profile,
            'default_thumbnail': default_thumbnail,
            'video_analytics': video_analytics,
            'followers': followers,
            'following': following,
            'followers_count': followers_count,
            'following_count': following_count,
        }

    def get_profile_data(self, profile_id, profile_model, current_user=None):
        """Get complete profile data including videos, history, and follow status"""
        
        # Get cached profile data
        profile = self.get_profile(profile_id, profile_model)
        
        # Get dynamic data with optimized queries
        videos = (profile.user.uploaded_videos
                 .select_related('uploader', 'uploader__profile')
                 .order_by('-created_at')[:2])
        
        # Optimize playlist query with prefetch_related
        playlists = (profile.user.playlists
                    .select_related('user')
                    .prefetch_related(
                        Prefetch(
                            'items',
                            queryset=PlaylistItem.objects.select_related(
                                'video',
                                'video__uploader'
                            )
                        )
                    )
                    .only(
                        'id', 'name', 'description', 'thumbnail',
                        'created_at', 'is_private', 'user_id'
                    )
                    .order_by('-created_at')[:2])
        
        # Get follow data
        follow_service = FollowService()
        follow_stats = follow_service.get_follower_stats(profile)
        is_following = False
        if current_user and current_user.is_authenticated:
            is_following = follow_service.check_following_status(current_user, profile.user)
        
        # Get video reactions in bulk - now just for uploaded videos
        videos_list = list(videos)
        reaction_counts = VideoService.get_videos_with_reactions(videos_list)
        
        # Attach counts to videos
        for video in videos_list:
            counts = reaction_counts.get(str(video.id), {'likes': 0, 'dislikes': 0})
            video.likes_count = counts['likes']
            video.dislikes_count = counts['dislikes']
        
        return {
            'profile': profile,
            'videos': videos_list,
            'playlists': playlists,
            'followers_count': follow_stats['followers_count'],
            'following_count': follow_stats['following_count'],
            'is_following': is_following
        }

    def get_analytics_data(self, profile):
        """Get analytics data using provided profile"""
        # Get video analytics
        videos = profile.user.uploaded_videos.filter(uploader=profile.user)
        analytics_data = VideoService.get_creator_studio_analytics(videos)
        
        # Get count from video_analytics instead of separate query
        videos_count = len(analytics_data['video_analytics'])
        
        # Get peak viewing times
        peak_hour = AnalyticsService.get_peak_viewing_hour(videos)
        peak_day = AnalyticsService.get_peak_viewing_day(videos)
        
        # Get user activity analytics (for heatmap)
        user_analytics = UserAnalyticsService().get_user_analytics(profile.user)
        
        # Get platform average total time
        platform_avg_total_time = UserAnalyticsService.get_platform_average_total_time_denormalized()
            
        # Get UserActivitySummary data
        try:
            activity_summary = UserActivitySummary.objects.values(
                'total_time_spent',
                'avg_session_length',
                'total_profile_visits',
                'total_followers',
                'total_following'
            ).get(user=profile.user)
            
            # Create summary_stats from values() result
            summary_stats = {
                'total_time_spent': activity_summary['total_time_spent'],
                'avg_session_length': activity_summary['avg_session_length'],
                'total_profile_visits': activity_summary['total_profile_visits'],
                'total_followers': activity_summary['total_followers'],
                'total_following': activity_summary['total_following']
            }
            
            # Calculate ratio using summary data
            if platform_avg_total_time > 0:
                if activity_summary['total_time_spent'] > platform_avg_total_time:
                    activity_ratio = round((activity_summary['total_time_spent'] / platform_avg_total_time * 100) - 100)
                    comparison_text = f"You have been {activity_ratio}% more active than the average user"
                else:
                    activity_ratio = round(100 - (activity_summary['total_time_spent'] / platform_avg_total_time * 100))
                    comparison_text = f"You have been {activity_ratio}% less active than the average user"
            else:
                activity_ratio = 0
                comparison_text = "No average activity data available"
                
        except UserActivitySummary.DoesNotExist:
            summary_stats = {
                'total_sessions': 0,
                'total_time_spent': 0,
                'avg_session_length': 0,
                'total_profile_visits': 0,
            }
            activity_ratio = 0
            comparison_text = "No activity data available"
            
        # Add follower analytics service
        follower_service = FollowerAnalyticsService()
        follower_analytics = follower_service.get_follower_analytics(profile.user)
        
        # Extract follower metrics
        follower_metrics = {
            'following_count': summary_stats.get('total_following', 0),
            'new_followers_30d': follower_analytics['new_followers_30d'],
            'total_followers': summary_stats.get('total_followers', 0)
        }
        
        # Extract just the engagement breakdown for pie charts
        pie_charts_data = {
            'engagement_breakdown': follower_analytics['engagement_breakdown']
        }
        
        # Format growth data for mini chart
        growth_mini_data = {
            'dates': [entry['created__date'].strftime('%b %d') for entry in follower_analytics['growth_data']],
            'values': [entry['new_followers'] for entry in follower_analytics['growth_data']]
        }
        
        # Get average watch time per video
        #average_watch_times = VideoStatisticsService.get_average_watch_time_per_video_denormalized(profile.user)
        
        # Get completion rate per video
        #completion_rates = VideoStatisticsService.get_completion_rate_per_video_denormalized(profile.user)

        # Get video statistics
        #video_stats_service = VideoStatisticsService()
        
        # Get overall average watch time
        #overall_watch_time = video_stats_service.get_average_watch_time_for_user_videos_denormalized(profile.user)
        #if overall_watch_time:
        #    overall_watch_minutes = overall_watch_time
        #else:
        #    overall_watch_minutes = 0
        
        # Get overall completion rate
        #overall_completion_rate = video_stats_service.get_completion_rate_for_user_videos_denormalized(profile.user)

        return {
            'profile': profile,
            'videos_count': videos_count,
            'video_analytics': analytics_data['video_analytics'],
            'chart_labels': json.dumps(analytics_data['chart_labels']),
            'chart_data': json.dumps(analytics_data['chart_data']),
            'daily_views_data': json.dumps(analytics_data['daily_views_data']),
            'hourly_views_data': json.dumps(analytics_data['hourly_views_data']),
            'likes_data': json.dumps(analytics_data['likes_data']),
            'comments_data': json.dumps(analytics_data['comments_data']),
            'activity_heatmap': json.dumps(user_analytics['heatmap_data']),
            'platform_avg_total_time': platform_avg_total_time,
            'activity_ratio': activity_ratio,
            'activity_comparison': comparison_text,
            'summary_stats': summary_stats,
            'pie_charts_data': json.dumps(pie_charts_data),
            'follower_metrics': follower_metrics,
            'growth_mini_data': json.dumps(growth_mini_data),
            'average_watch_times': json.dumps(analytics_data['watch_time_data']),
            #'average_watch_times': json.dumps(average_watch_times),
            'completion_rates': json.dumps(analytics_data['completion_rate_data']),
            #'completion_rates': json.dumps(completion_rates),
            'overall_watch_time': analytics_data['avg_watch_time_data'],
            #'overall_watch_time': round(overall_watch_minutes, 2),
            'overall_completion_rate': analytics_data['avg_completion_rate_data'],
            #'overall_completion_rate': round(overall_completion_rate, 2),
            'peak_viewing_hour': peak_hour or "N/A",
            'peak_viewing_day': peak_day or "N/A"
        }
