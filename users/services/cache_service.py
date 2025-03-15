from django.core.cache import cache
from django_redis import get_redis_connection
from logging import getLogger
from django.utils import timezone
from django.contrib.auth.models import User
import json

logger = getLogger(__name__)

class ProfileCache:
    FOLDER = "profile"
    PROFILE_CACHE_TTL = 600  # 10 minutes
    
    @staticmethod
    def get_cache_key(profile_id):
        return f"{ProfileCache.FOLDER}:{profile_id}"
    
    def get_static_profile_data(self, profile):
        """Cache only static profile data"""
        cached_data = {
            'id': str(profile.id),
            'name': profile.name,
            'username': profile.username,
            'bio': profile.bio,
            'profile_pic_url': profile.get_profile_pic_url(),
            'social': {
                'github': profile.github,
                'twitter': profile.twitter,
                'linkedin': profile.linkedin,
                'youtube': profile.youtube,
                'instagram': profile.instagram,
            }
        }
        print(f"\n📝 Caching data with key: {self.get_cache_key(profile.id)}")
        return cached_data
    
    def set_profile_cache(self, profile_id, profile):
        """Set cache for static profile data"""
        static_data = self.get_static_profile_data(profile)
        cache.set(self.get_cache_key(profile_id), static_data, timeout=self.PROFILE_CACHE_TTL)
    
    def get_profile_cache(self, profile_id):
        """Get cached profile data"""
        return cache.get(self.get_cache_key(profile_id))
        
    def invalidate(self, profile_id):
        """Invalidate profile cache"""
        cache.delete(self.get_cache_key(profile_id))

class SessionActivityCache:
    FOLDER = ":1:session_activity"
    TTL = 60 * 60 * 24  # 24 hours
    MAX_ENTRIES = 1000  # Example limit
    
    def __init__(self):
        self.redis = get_redis_connection("default")
    
    @staticmethod
    def get_cache_key(user_id, session_id):
        return f"{SessionActivityCache.FOLDER}:user_{user_id}_session_{session_id}"
    
    def add_page_visit(self, user_id, session_id, path):
        """Add a page visit to the session activity cache"""
        from users.tasks import save_activity_overflow  # New task
        
        if not path.startswith(('/api/', '/media/','/static/')):
            cache_key = self.get_cache_key(user_id, session_id)
            current_time = timezone.now().strftime('%H:%M:%S.%f')
            
            try:
                # Add new entry first
                pipeline = self.redis.pipeline()
                pipeline.hset(cache_key, current_time, path)
                pipeline.expire(cache_key, self.TTL)
                pipeline.execute()
                
                # Check size after adding
                current_size = self.redis.hlen(cache_key)
                logger.info(f"📊 Current cache size: {current_size}")
                
                if current_size >= self.MAX_ENTRIES:
                    # Queue overflow task
                    task = save_activity_overflow.delay(
                        session_id=str(session_id),
                        user_id=user_id
                    )
                    logger.info(f"✅ Queued overflow task: {task.id}")
            except Exception as e:
                logger.error(f"Failed to cache activity: {str(e)}")
    
    def get_activity_log(self, user_id, session_id):
        """Get all activity for a session"""
        cache_key = self.get_cache_key(user_id, session_id)
        activities = self.redis.hgetall(cache_key)
        
        pages_visited = []
        for timestamp, path in sorted(activities.items()):
            pages_visited.append({
                "timestamp": timestamp.decode(),
                "path": path.decode()
            })
            
        return {
            "pages_visited": pages_visited,
            "session_stats": {
                "total_pages": len(pages_visited),
                "start_time": pages_visited[0]["timestamp"] if pages_visited else None,
                "last_activity": pages_visited[-1]["timestamp"] if pages_visited else None
            }
        }
    
    def clear_activity_cache(self, user_id, session_id):
        """Clear the activity cache for a session"""
        cache_key = self.get_cache_key(user_id, session_id)
        self.redis.delete(cache_key)

class VideoStatsCache:
    FOLDER = ":1:video_stats"  # Single folder for user stats
    TTL = 60 * 60 * 24  # 24 hours
    
    def __init__(self):
        self.redis = get_redis_connection("default")
    
    @staticmethod
    def get_cache_key(user_id):
        return f"{VideoStatsCache.FOLDER}:{user_id}"  # Single key for user stats
    
    def set_video_stats(self, user_id, video_id, window_id, stats):
        """Add video stats to cache under a single user key as a hash"""
        cache_key = self.get_cache_key(user_id)
        
        # Create a unique field for the hash using window_id and video_id
        field_key = f"{video_id}:{window_id}"

        # Store the stats in a hash
        self.redis.hset(cache_key, field_key, json.dumps({
            'total_watched': str(stats['total_watched']),
            'is_completed': str(stats['is_completed'])
        }))
        self.redis.expire(cache_key, self.TTL)  # Set TTL for the hash

        logger.info(f"📊 Added video stats for user ID {user_id}: {field_key}.")

    def get_video_stats(self, user_id):
        """Get all video stats for a user"""
        cache_key = self.get_cache_key(user_id)
        try:
            stats = self.redis.hgetall(cache_key)  # Get all entries in the hash
            return {key.decode(): json.loads(value) for key, value in stats.items()}  # Decode each entry
        except Exception as e:
            logger.error(f"Failed to get video stats: {str(e)}")
        return None
    
    def invalidate(self, user_id):
        """Invalidate all video stats for a user"""
        cache_key = self.get_cache_key(user_id)
        self.redis.delete(cache_key)