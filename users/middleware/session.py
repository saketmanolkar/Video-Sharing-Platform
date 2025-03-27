import logging
import json
from django.utils import timezone
from ..models import UserSession
from projects.services.video_services import UtilityService
from ..tasks import create_user_session
from django_redis import get_redis_connection
from datetime import timedelta
from ..services.cache_service import SessionActivityCache, VideoStatsCache, SessionLockCache
import re
from urllib.parse import unquote
from django.core.cache import cache
import time
from django.contrib.auth.models import User
from django.conf import settings

logger = logging.getLogger(__name__)

class UserSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.activity_cache = SessionActivityCache()
        self.video_stats_cache = VideoStatsCache()
        self.session_lock = SessionLockCache()

    def __call__(self, request):
        # Skip session creation entirely during tests
        if settings.TESTING:
            return self.get_response(request)
        
        # Skip for static, media, api files and debug toolbar
        if any([
            request.path.startswith('/health/'),
            request.path.startswith('/static/'),
            request.path.startswith('/media/'),
            request.path.startswith('/api/'),
            request.path.startswith('/__debug__/'),
            request.path == '/users/logout/'
        ]):
            return self.get_response(request)
        
        # *** MOVE PRINTS HERE - AFTER THE SKIP CHECK ***
        print("\n=== Session Middleware Check ===")
        print(f"Path: {request.path}")
        print(f"Method: {request.method}")
        print(f"User: {request.user}")
        
        # Safely prefetch user profile if authenticated
        # This reduces duplicate profile queries in templates
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                # Only prefetch if this is a real user object with an ID
                if hasattr(request.user, 'id') and request.user.id is not None:
                    # Replace the user on the request with one that has profile preloaded
                    prefetched_user = User.objects.select_related('profile').filter(id=request.user.id).first()
                    if prefetched_user:
                        # Store the original user's attributes that might be session-specific
                        session_attrs = {}
                        for attr in ['_wrapped', '_auth_user_backend', '_auth_user_hash']:
                            if hasattr(request.user, attr):
                                session_attrs[attr] = getattr(request.user, attr)
                        
                        # Replace with prefetched user
                        request.user = prefetched_user
                        
                        # Restore session attributes
                        for attr, value in session_attrs.items():
                            setattr(request.user, attr, value)
                        
                        # Add user-related flags directly to the request object
                        # These will be available in templates via the request object
                        request.is_authenticated = True
                        request.user_id = request.user.id
                        request.user_username = request.user.username
                    else:
                        # Handle case where user might not be found
                        request.is_authenticated = False
                        request.user_id = None
                        request.user_username = ""
            except Exception as e:
                # Log but don't break the request flow
                logger.error(f"❌ Profile prefetch error: {str(e)}")
                request.is_authenticated = False
                request.user_id = None
                request.user_username = ""
        else:
            # Set default values for unauthenticated users
            request.is_authenticated = False
            request.user_id = None
            request.user_username = ""
        
        # Add IP address logging
        ip_address = request.META.get('REMOTE_ADDR', 'unknown')
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        
        if forwarded_for:
            print(f"IP: {ip_address} (X-Forwarded-For: {forwarded_for})")
        else:
            print(f"IP: {ip_address}")
        
        # Skip session creation for exact logout path
        if request.path == '/users/logout/':
            print("⏩ Skipping session creation for logout")
            return self.get_response(request)
        
        if request.user.is_authenticated:
            try:
                active_session = UserSession.objects.filter(
                    user=request.user,
                    end_time__isnull=True
                ).first()
                
                if active_session:
                    print(f"⏩ Using existing session: {active_session.id}")
                    self.activity_cache.add_page_visit(
                        request.user.id,
                        active_session.id,
                        request.path
                    )
                else:
                    # Try to acquire lock using cache service
                    if self.session_lock.acquire_lock(request.user.id):
                        try:
                            # Double-check active session
                            active_session = UserSession.objects.filter(
                                user=request.user,
                                end_time__isnull=True
                            ).first()
                            
                            if not active_session:
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
                                
                                print("🎯 Creating new session")
                                task = create_user_session.delay(**session_data)
                                self.session_lock.store_task_id(request.user.id, task.id)
                                print(f"✅ New session task queued: {task.id}")
                                
                        finally:
                            pass  # Let lock expire naturally
                    else:
                        print("⏩ Session creation already in progress")
                        time.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ Middleware error: {str(e)}")

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