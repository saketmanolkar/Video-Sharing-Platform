from django.core.cache import cache
import time
import logging
import os
import pandas as pd

logger = logging.getLogger(__name__)

# Cache time to live - 15 minutes
CACHE_TTL = 900  # 15 * 60 seconds = 900 seconds

# Cache time to live - 60 seconds for form submissions
FORM_TTL = 60

class ProjectsCacheService:
    # Cache keys
    STUDIO_DATA_KEY = 'fun_corner:studio_data'
    CURRENT_MOVIES_KEY = 'fun_corner:current_movies'
    MOVIE_RECS_MODEL_KEY = 'fun_corner:movie_recs_model'
    
    # TTL for static data (24 hours)
    STATIC_DATA_TTL = 24 * 60 * 60  # 86400 seconds

    @staticmethod
    def get_studio_data():
        """Specific method for studio data caching"""
        start_time = time.time()
        logger.info(f"Checking cache key: {ProjectsCacheService.STUDIO_DATA_KEY}")
        value = cache.get(ProjectsCacheService.STUDIO_DATA_KEY)
        
        if value is None:
            print("\n🔴 Cache MISS - Loading from CSV...")
            from ..fun_corner.hollywood_analytics import get_major_studios_data
            value = get_major_studios_data()
            cache.set(
                ProjectsCacheService.STUDIO_DATA_KEY, 
                value,
                timeout=ProjectsCacheService.STATIC_DATA_TTL
            )
            load_time = time.time() - start_time
            print(f"⏱️ CSV Load Time: {load_time:.2f} seconds\n")
        else:
            load_time = time.time() - start_time
            print(f"\n🟢 Cache HIT for studio data! Load Time: {load_time:.2f} seconds\n")
            
        return value

    @staticmethod
    def clear_studio_data():
        """Clear studio data cache"""
        print(f"Clearing cache key: {ProjectsCacheService.STUDIO_DATA_KEY}")
        cache.delete(ProjectsCacheService.STUDIO_DATA_KEY)

    @staticmethod
    def refresh_studio_data():
        """Force refresh studio data cache"""
        ProjectsCacheService.clear_studio_data()
        return ProjectsCacheService.get_studio_data()

    @staticmethod
    def get_current_movies():
        """Cache layer for current movies data"""
        start_time = time.time()
        logger.info(f"Checking cache key: {ProjectsCacheService.CURRENT_MOVIES_KEY}")
        value = cache.get(ProjectsCacheService.CURRENT_MOVIES_KEY)
        
        if value is None:
            print("\n🔴 Cache MISS - Loading current movies...")
            from ..fun_corner.hollywood_analytics import get_current_movies_data
            value = get_current_movies_data()
            cache.set(
                ProjectsCacheService.CURRENT_MOVIES_KEY, 
                value,
                timeout=ProjectsCacheService.STATIC_DATA_TTL
            )
            load_time = time.time() - start_time
            print(f"⏱️ CSV Load Time: {load_time:.2f} seconds\n")
        else:
            load_time = time.time() - start_time
            print(f"\n🟢 Cache HIT for current movies! Load Time: {load_time:.2f} seconds\n")
            
        return value

    @staticmethod
    def clear_current_movies():
        """Clear current movies cache"""
        print(f"Clearing cache key: {ProjectsCacheService.CURRENT_MOVIES_KEY}")
        cache.delete(ProjectsCacheService.CURRENT_MOVIES_KEY)

    @staticmethod
    def refresh_current_movies():
        """Force refresh current movies cache"""
        ProjectsCacheService.clear_current_movies()
        return ProjectsCacheService.get_current_movies()

    @staticmethod
    def get_movie_recs_model():
        """Cache the movie recommendation model and clusters"""
        try:
            from ..fun_corner.movie_recs import create_optimized_clusters
            value = cache.get(ProjectsCacheService.MOVIE_RECS_MODEL_KEY)
            
            if value is None:
                print("\n🔴 Cache MISS - Creating recommendation model...")
                csv_path = os.path.join('projects', 'fun_corner', 'data', 'tmdb_all_media.csv')
                df = pd.read_csv(csv_path)
                
                # Convert genres right after loading
                df['genres'] = df['genres'].fillna('Unknown')
                df['genres'] = df['genres'].apply(
                    lambda x: ', '.join(eval(x)) if isinstance(x, str) and x.startswith('[') else x
                )
                
                df_clustered, X, kmeans = create_optimized_clusters(df)
                
                if df_clustered is None or X is None or kmeans is None:
                    raise Exception("Failed to create clusters")
                
                value = {
                    'df_clustered': df_clustered,
                    'X': X,
                    'kmeans': kmeans
                }
                
                cache.set(
                    ProjectsCacheService.MOVIE_RECS_MODEL_KEY,
                    value,
                    timeout=ProjectsCacheService.STATIC_DATA_TTL
                )
                print("✅ Recommendation model cached!")
            else:
                print("🟢 Cache HIT for recommendation model!")
                
            return value
            
        except Exception as e:
            print(f"Error in get_movie_recs_model: {str(e)}")
            return None

    @staticmethod
    def clear_movie_recs_model():
        """Clear movie recommendations model cache"""
        print(f"Clearing cache key: {ProjectsCacheService.MOVIE_RECS_MODEL_KEY}")
        cache.delete(ProjectsCacheService.MOVIE_RECS_MODEL_KEY)

    @staticmethod
    def refresh_movie_recs_model():
        """Force refresh movie recommendations model cache"""
        ProjectsCacheService.clear_movie_recs_model()
        return ProjectsCacheService.get_movie_recs_model()

class ViewRecordingCache:
    """Caching layer for view recording using time-based policy"""
    
    # Cache key format: video_views:user_<id>:video_<id>:window_<timestamp>
    # Or: video_views:ip_<address>:video_<id>:window_<timestamp>
    CACHE_PREFIX = 'video_views'
    WINDOW_DURATION = 300  # 5 minutes in seconds
    
    @staticmethod
    def generate_cache_key(video_id, user_id=None, ip_address=None):
        """Generate unique cache key for the current time window"""
        # Determine viewer identifier type and value
        viewer_type = 'user' if user_id else 'ip'
        viewer_id = user_id if user_id else ip_address
        
        # Calculate current time window
        time_window = int(time.time() / ViewRecordingCache.WINDOW_DURATION)
        
        # Build cache key with clear sections
        return f"{ViewRecordingCache.CACHE_PREFIX}:{viewer_type}_{viewer_id}:video_{video_id}:window_{time_window}"
    
    @staticmethod
    def can_record_view(video_id, user_id=None, ip_address=None):
        """Check if a view can be recorded in the current time window"""
        try:
            cache_key = ViewRecordingCache.generate_cache_key(video_id, user_id, ip_address)
            
            # Check if view exists in current time window
            if cache.get(cache_key):
                print(f"🔵 View already recorded: {cache_key}")
                return False
                
            # Set cache for this time window
            cache.set(cache_key, True, timeout=ViewRecordingCache.WINDOW_DURATION)
            print(f"🟢 New view recorded: {cache_key}")
            return True
            
        except Exception as e:
            print(f"❌ Error in view recording cache: {str(e)}")
            return True  # Allow view on error
    
    @staticmethod
    def clear_view_record(video_id, user_id=None, ip_address=None):
        """Clear view record (for testing)"""
        cache_key = ViewRecordingCache.generate_cache_key(video_id, user_id, ip_address)
        cache.delete(cache_key)

class VideoContextCache:
    FOLDER = "video_context"  # The folder name in Redis
    
    @staticmethod
    def get_cache_key(video_id):
        """Get key inside the video_context folder"""
        return f"{VideoContextCache.FOLDER}:{video_id}"
    
    def get_context(self, video_id):
        """Get cached context for video"""
        return cache.get(self.get_cache_key(video_id))
        
    def set_context(self, video_id, context):
        """Cache only essential static data"""
        cached_data = {
            'video': {
                'id': context['video'].id,
                'title': context['video'].title,
                'description': context['video'].description,
                'created_at': context['video'].created_at,
                'uploader': {
                    'id': context['video'].uploader.id,
                    'username': context['video'].uploader.username
                }
            },
            'tags': [{'id': tag.id, 'name': tag.name} for tag in context['tags']]
        }
        
        cache.set(self.get_cache_key(video_id), cached_data, CACHE_TTL)
    
    def invalidate(self, video_id):
        """Invalidate video context cache"""
        cache.delete(self.get_cache_key(video_id))
        print(f"\n🗑️ Cache invalidated for video: {video_id}")

class FormSubmissionCache:
    FOLDER = "form_submission"  # The folder name in Redis
    
    @staticmethod
    def get_cache_key(submission_hash):
        """Get key inside the form_submission folder"""
        return f"{FormSubmissionCache.FOLDER}:{submission_hash}"
    
    def check_submission(self, submission_hash):
        """Check if form was recently submitted"""
        return cache.get(self.get_cache_key(submission_hash))
        
    def set_submission(self, submission_hash):
        """Mark form as submitted"""
        cache.set(self.get_cache_key(submission_hash), True, FORM_TTL)
    
    def clear_submission(self, submission_hash):
        """Clear submission cache if needed"""
        cache.delete(self.get_cache_key(submission_hash))