from .models import Video

def get_video_recommendations(current_video, max_recommendations=5):
    """
    Get video recommendations based on various factors
    
    Args:
        current_video: The Video object for which to find recommendations
        max_recommendations: Maximum number of recommendations to return
    
    Returns:
        List of recommended Video objects
    """
    
    # Get all tags from current video
    tags = current_video.tags.all()
    
    # First try to get videos with matching tags
    recommended_videos = Video.objects.filter(
        tags__in=tags
    ).exclude(
        id=current_video.id
    ).distinct().order_by('-views', '-created_at')[:max_recommendations]
    
    # If not enough recommendations, add popular videos
    if recommended_videos.count() < max_recommendations:
        more_videos = Video.objects.exclude(
            id__in=[v.id for v in list(recommended_videos)] + [current_video.id]
        ).order_by('-views', '-created_at')[:max_recommendations-recommended_videos.count()]
        recommended_videos = list(recommended_videos) + list(more_videos)
    
    return recommended_videos

# You can add more recommendation functions here
def get_trending_videos(max_videos=5):
    """Get trending videos based on views"""
    return Video.objects.order_by('-views', '-created_at')[:max_videos]

def get_similar_by_tags(video, max_videos=5):
    """Get videos with similar tags"""
    tags = video.tags.all()
    return Video.objects.filter(
        tags__in=tags
    ).exclude(
        id=video.id
    ).distinct().order_by('-created_at')[:max_videos]

def get_latest_videos(max_videos=5):
    """Get latest uploaded videos"""
    return Video.objects.order_by('-created_at')[:max_videos] 