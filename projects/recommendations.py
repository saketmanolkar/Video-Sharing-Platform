from projects.models import Video
import logging

logger = logging.getLogger(__name__)

def get_video_recommendations(video):
    """
    Get video recommendations using multiple strategies:
    1. Similar tags
    2. Recent videos from same uploader
    3. Most viewed videos
    4. Recent videos
    Returns up to 5 videos.
    """
    try:
        # Start with an empty queryset
        recommended = Video.objects.none()
        
        # Combine without orderings
        if video.tags.exists():
            tag_based = Video.objects.filter(
                tags__in=video.tags.all()
            ).exclude(id=video.id)
            recommended = recommended | tag_based
        
        uploader_videos = Video.objects.filter(
            uploader=video.uploader
        ).exclude(id=video.id)
        recommended = recommended | uploader_videos
        
        popular_videos = Video.objects.exclude(id=video.id)
        recommended = recommended | popular_videos
        
        # Apply final ordering after combining
        return recommended.distinct().order_by('-views', '-created_at')[:5]
        
    except Exception as e:
        logger.error(f"Error getting video recommendations: {str(e)}")
        # Fallback to recent videos
        return Video.objects.exclude(id=video.id).order_by('-created_at')[:5]

def get_trending_videos(max_videos=5):
    """Get trending videos based on views"""
    try:
        return Video.objects.order_by('-views', '-created_at')[:max_videos]
    except Exception as e:
        logger.error(f"Error getting trending videos: {str(e)}")
        return Video.objects.none()

def get_similar_by_tags(video, max_videos=5):
    """Get videos with similar tags"""
    try:
        return Video.objects.filter(
            tags__in=video.tags.all()
        ).exclude(
            id=video.id
        ).distinct().order_by('-created_at')[:max_videos]
    except Exception as e:
        logger.error(f"Error getting similar videos by tags: {str(e)}")
        return Video.objects.none()

def get_latest_videos(max_videos=5):
    """Get latest uploaded videos"""
    try:
        return Video.objects.order_by('-created_at')[:max_videos]
    except Exception as e:
        logger.error(f"Error getting latest videos: {str(e)}")
        return Video.objects.none() 