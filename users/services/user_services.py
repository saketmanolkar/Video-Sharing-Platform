from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.staticfiles.storage import staticfiles_storage
from django.templatetags.static import static
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

class UserReportService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.model = None
        self.base_prompts = {
            'user': """You are analyzing user activity data for {username}. 
            Always format your response as follows:
            1. Use markdown formatting
            2. Start with a brief report for {username}'s data to {username} himself.
            3. Follow a strict format of 3 sections for the report - 1. Overview, 2. Details, 3. Recommendations
            4. You are writing a professional report. Be concise & Write in paragraph format. (250 words)
            5. Give recommendations to the user from the perspective of improving the user's app usage habits only.
            6. Donot give moral advice  to {username}. You are a professional data analyst. Just do your job.

            Now, analyze this user's activity data: """,
            
            'video': """You are working as a data analyst for a Video Sharing company called "FilmsNation". Your job is to analyze the video data of {username}, who is a uploads his videos on FilmsNation. 
            Always format your response as follows:
            1. Start with key metrics (views, engagement, retention)
            2. Analyse the engagement breakdown for this video
            3. Identify what worked well in this video
            4. Point out areas for improvement
            5. Provide specific tips for future videos
            6. Write the Report as detailed as possible as the seductive girlfriend of the {username} who uses very vulgar language, you are very horny.
            7. Donot give moral advice  to {username}. You are a professional data analyst. Just do your job.
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

        # Delete existing text file if it exists
        if report_type == 'user' and report.user_report_url:
            existing_file_path = os.path.join(self.reports_dir, os.path.basename(report.user_report_url[7:]))
            if os.path.exists(existing_file_path):
                os.remove(existing_file_path)
        elif report_type == 'video' and report.video_report_url:
            existing_file_path = os.path.join(self.reports_dir, os.path.basename(report.video_report_url[7:]))
            if os.path.exists(existing_file_path):
                os.remove(existing_file_path)

        # Create a new filename for the report
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{username}_{report_type}_{timestamp}.txt"
        
        # Hard-code the report header
        today_date = datetime.now().strftime('%Y-%m-%d')
        report_header = f"{report_type.upper()} DATA REPORT - GENERATED ON {today_date} {datetime.now().strftime('%H:%M:%S')}.\n\n"

        # Save the new text report in the specified directory
        text_path = os.path.join(self.reports_dir, filename)
        with open(text_path, 'w') as f:
            f.write(report_header)
            f.write(report_content)

        # Construct local file URL for the new report
        report_url = f"file://{text_path}"

        # Update the appropriate report URL and timestamp
        if report_type == 'user':

            # Update the user report url and timestamp in the DB
            report.user_report_url = report_url
            report.user_report_generated_at = datetime.now()

            # Clear the user report audio file url and timestamp in the DB
            report.user_report_audio_file_url = None
            report.user_report_audio_generated_at = None

            
        elif report_type == 'video':

            #Update the video report url and timestamp in the DB
            report.video_report_url = report_url
            report.video_report_generated_at = datetime.now()

            # Clear the video report audio file url and timestamp in the DB
            report.video_report_audio_file_url = None
            report.video_report_audio_generated_at = None

        
        # Define the audio file path to delete after report generation
        audio_file_name = f"{username}_{report_type}_audio.wav"
        audio_file_path = os.path.join(self.reports_dir, audio_file_name)

        # Check if the report audio file already exists and delete it if necessary
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
            print(f"Deleted existing {report_type} data report audio file after report generation: {audio_file_path}")

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
            print(f"Using reports directory: {self.reports_dir}")

            # Determine the correct file pattern based on the report type
            if report_type == 'user':
                file_pattern = f"{username}_user_*.txt"
            elif report_type == 'video':
                file_pattern = f"{username}_video_*.txt"
            else:
                print(f"Invalid report type: {report_type}")
                return None

            # Print the file pattern being searched
            print(f"Searching for files with pattern: {file_pattern}")

            # List all files in the reports directory for debugging
            all_files = os.listdir(self.reports_dir)
            print(f"All files in directory: {all_files}")

            # Find the text file that matches the pattern
            text_files = glob.glob(os.path.join(self.reports_dir, file_pattern))
            print(f"Found files: {text_files}")  # Debugging line

            if not text_files:
                print(f"No report file found for username: {username} and report type: {report_type}")
                return None
            
            # Read the content of the first matching file
            with open(text_files[0], 'r') as file:
                content = file.read()

            # Remove asterisks from the content
            cleaned_content = content.replace('*', '')

            # Save the cleaned content to a new file
            cleaned_file_path = os.path.join(self.reports_dir, f"{username}_cleaned.txt")
            with open(cleaned_file_path, 'w') as cleaned_file:
                cleaned_file.write(cleaned_content)

            # Define the audio file path
            audio_file_name = f"{username}_{report_type}_audio.wav"
            audio_file_path = os.path.join(self.reports_dir, audio_file_name)

            # Check if the audio file already exists and delete it if necessary
            if os.path.exists(audio_file_path):
                os.remove(audio_file_path)
                print(f"Deleted existing audio file: {audio_file_path}")

            # Initialize TTS and generate audio
            tts = TTS(model_name="tts_models/en/vctk/vits")
            tts.tts_to_file(text=cleaned_content, file_path=audio_file_path, speaker="p339")

            print(f"Audio generated and saved at: {audio_file_path}")

            # Delete the cleaned text file after generating audio
            os.remove(cleaned_file_path)
            print(f"Deleted temporary file: {cleaned_file_path}")

            return audio_file_name
            
        except Exception as e:
            print(f"Error in generating speech: {str(e)}")
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
        profile = get_object_or_404(profile_model, id=profile_id)
        videos = profile.user.uploaded_videos.all().order_by('-created_at')
        playlists = profile.user.playlists.all().order_by('-created_at')

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

        return {
            'profile': profile,
            'videos': videos,
            'playlists': playlists,
            'search_query': search_query
        }
    
    def get_user_history(self, profile_id, profile_model):
        profile = get_object_or_404(profile_model, id=profile_id)
        history_entries = profile.user.view_history.all().order_by('-viewed_at')
        history_videos = [entry.video for entry in history_entries]
        return {
            'profile': profile,
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

    def get_profile_data(self, profile_id, profile_model, current_user=None):
        """Get complete profile data including videos, history, and follow status"""
        profile = self.get_profile(profile_id, profile_model)  # This should handle caching
        
        follow_service = FollowService()
        
        # These are all dynamic data - don't cache
        videos = profile.user.uploaded_videos.all()[:2]
        view_history = profile.user.view_history.all()[:2]
        playlists = profile.user.playlists.all()[:2]
        
        # Dynamic follow data
        follow_stats = follow_service.get_follower_stats(profile)
        is_following = False
        if current_user and current_user.is_authenticated:
            is_following = follow_service.check_following_status(current_user, profile.user)
        
        # Dynamic engagement metrics
        for video in videos:
            video.likes_count = VideoService.get_likes_count(video)
            video.dislikes_count = VideoService.get_dislikes_count(video)
        
        for history in view_history:
            history.video.likes_count = VideoService.get_likes_count(history.video)
            history.video.dislikes_count = VideoService.get_dislikes_count(history.video)
        
        return {
            'profile': profile,  # This contains cached static data
            'videos': videos,    # Dynamic - fresh from DB
            'view_history': view_history,  # Dynamic - fresh from DB
            'playlists': playlists,        # Dynamic - fresh from DB
            'followers_count': follow_stats['followers_count'],  # Dynamic count
            'following_count': follow_stats['following_count'],  # Dynamic count
            'is_following': is_following    # User-specific - always fresh
        }

    def get_analytics_data(self, profile_id, profile_model):
        profile = self.get_profile(profile_id, profile_model)
        
        # Get video analytics
        videos = profile.user.uploaded_videos.filter(uploader=profile.user)
        analytics_data = VideoService.get_creator_studio_analytics(videos)
        
        # Get peak viewing times
        peak_hour = AnalyticsService.get_peak_viewing_hour(videos)
        peak_day = AnalyticsService.get_peak_viewing_day(videos)
        
        # Get user activity analytics (for heatmap)
        user_analytics = UserAnalyticsService().get_user_analytics(profile.user)
        
        # Get platform average total time
        platform_avg_total_time = UserAnalyticsService.get_platform_average_total_time()
            
        # Get UserActivitySummary data
        try:
            activity_summary = UserActivitySummary.objects.get(user=profile.user)
            summary_stats = {
                'total_sessions': activity_summary.total_sessions,
                'total_time_spent': activity_summary.total_time_spent,
                'avg_session_length': activity_summary.avg_session_length,
                'total_profile_visits': activity_summary.total_profile_visits
            }
            
            # Calculate ratio using summary data
            if platform_avg_total_time > 0:
                if activity_summary.total_time_spent > platform_avg_total_time:
                    activity_ratio = round((activity_summary.total_time_spent / platform_avg_total_time * 100) - 100)
                    comparison_text = f"You have been {activity_ratio}% more active than the average user"
                else:
                    activity_ratio = round(100 - (activity_summary.total_time_spent / platform_avg_total_time * 100))
                    comparison_text = f"You have been {activity_ratio}% less active than the average user"
            else:
                activity_ratio = 0
                comparison_text = "No average activity data available"
                
        except UserActivitySummary.DoesNotExist:
            summary_stats = {
                'total_sessions': 0,
                'total_time_spent': 0,
                'avg_session_length': 0,
                'total_profile_visits': 0
            }
            activity_ratio = 0
            comparison_text = "No activity data available"
            
        # Add follower analytics service
        follower_service = FollowerAnalyticsService()
        follower_analytics = follower_service.get_follower_analytics(profile.user)
        
        # Extract follower metrics
        follower_metrics = {
            'following_count': follower_analytics['following_count'],
            'new_followers_30d': follower_analytics['new_followers_30d'],
            'total_followers': follower_analytics['total_followers']
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
        average_watch_times = VideoStatisticsService.get_average_watch_time_per_video(profile.user)
        
        # Get completion rate per video
        completion_rates = VideoStatisticsService.get_completion_rate_per_video(profile.user)

        # Get video statistics
        video_stats_service = VideoStatisticsService()
        
        # Get overall average watch time
        overall_watch_time = video_stats_service.get_average_watch_time_for_user_videos(profile.user)
        if overall_watch_time:
            overall_watch_minutes = overall_watch_time.total_seconds() / 60
        else:
            overall_watch_minutes = 0
        
        # Get overall completion rate
        overall_completion_rate = video_stats_service.get_completion_rate_for_user_videos(profile.user)

        return {
            'profile': profile,
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
            'average_watch_times': json.dumps(average_watch_times),
            'completion_rates': json.dumps(completion_rates),
            'overall_watch_time': round(overall_watch_minutes, 2),
            'overall_completion_rate': round(overall_completion_rate, 2),
            'peak_viewing_hour': peak_hour,
            'peak_viewing_day': peak_day
        }