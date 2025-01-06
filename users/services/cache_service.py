from django.core.cache import cache
from logging import getLogger

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