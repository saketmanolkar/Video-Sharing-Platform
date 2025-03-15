import logging
import json
from django.utils import timezone
from ..models import UserSession
from projects.services.video_services import UtilityService
from ..tasks import create_user_session
from django_redis import get_redis_connection
from datetime import timedelta
from ..services.cache_service import SessionActivityCache, VideoStatsCache
import re
from urllib.parse import unquote
from django.core.cache import cache

logger = logging.getLogger(__name__)

class UserSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.redis = get_redis_connection("default")
        self.activity_cache = SessionActivityCache()
        self.video_stats_cache = VideoStatsCache()

    def __call__(self, request):
        # Skip for static, media, api files
        if any([
            request.path.startswith('/static/'),
            request.path.startswith('/media/'),
            request.path.startswith('/api/'),
            request.path == '/users/logout/'
        ]):
            return self.get_response(request)
        
        print("\n=== Session Middleware Check ===")
        print(f"Path: {request.path}")
        print(f"Method: {request.method}")
        print(f"User: {request.user}")
        
        # Skip session creation for exact logout path
        if request.path == '/users/logout/':
            print("⏩ Skipping session creation for logout")
            return self.get_response(request)
        
        if request.user.is_authenticated:
            try:
                # Find active session
                active_session = UserSession.objects.filter(
                    user=request.user,
                    end_time__isnull=True
                ).first()
                
                if active_session:
                    print(f"⏩ Using existing session: {active_session.id}")
                    # Use ONLY cache service
                    self.activity_cache.add_page_visit(
                        request.user.id,
                        active_session.id,
                        request.path
                    )
                else:
                    # Create new session only if none exists
                    session_data = {
                        'user_id': request.user.id,
                        'device_info': {
                            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                            'platform': request.META.get('HTTP_SEC_CH_UA_PLATFORM', '')
                        },
                        'browser_info': {
                            'browser': request.META.get('HTTP_SEC_CH_UA', ''),
                            'language': request.META.get('HTTP_ACCEPT_LANGUAGE', '')
                        },
                        'ip_location': request.META.get('REMOTE_ADDR')
                    }
                    
                    try:
                        print("🎯 Creating new session")
                        task = create_user_session.delay(**session_data)
                        print(f"✅ New session task queued: {task.id}")
                    except Exception as e:
                        print(f"❌ Failed to create session: {str(e)}")
                        
            except Exception as e:
                print(f"❌ Middleware error: {str(e)}")

        # Check for the videoWatchStats cookie
        video_watch_stats = request.COOKIES.get('videoWatchStats', None)

        if video_watch_stats:
            try:
                decoded_stats = json.loads(unquote(video_watch_stats))
                
                # Process the video stats data
                window_id = decoded_stats.get('window_id')
                video_id = decoded_stats.get('video_id')
                user_id = decoded_stats.get('user_id')
                total_watched = decoded_stats.get('total_watched')
                is_completed = decoded_stats.get('is_completed')

                # Use the VideoStatsCache
                try:
                    # Directly add video stats to the cache
                    self.video_stats_cache.set_video_stats(
                        user_id=user_id,
                        video_id=video_id,
                        window_id=window_id,
                        stats={
                            'total_watched': total_watched,
                            'is_completed': is_completed
                        }
                    )
                    print(f"✅ Cached video stats for user ID {user_id}, video ID {video_id}, window ID {window_id}.")
                except Exception as e:
                    print(f"❌ Failed to cache video stats: {str(e)}")

            except json.JSONDecodeError:
                print("❌ Failed to decode video watch stats cookie.")


            # Clear the cookie by setting it to an empty value and expiring it
            response = self.get_response(request)
            response.delete_cookie('videoWatchStats')
            return response
        

        return self.get_response(request)