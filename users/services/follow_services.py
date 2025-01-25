import logging
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

class FollowService:
    @transaction.atomic
    def follow_user(self, user, user_to_follow):
        try:
            if not user_to_follow:
                raise ValidationError("User to follow does not exist.")
                
            if user == user_to_follow:
                raise ValidationError("You cannot follow yourself.")
            
            # Immediate database update with transaction
            _, created = user.following_set.get_or_create(following=user_to_follow)
            
            # Clear any cached data
            cache.delete(f'follow_{user.id}_{user_to_follow.id}')
            cache.delete(f'followers_count_{user_to_follow.id}')
            cache.delete(f'following_count_{user.id}')
            
            return True, "Successfully followed user."
            
        except Exception as e:
            logger.error(f"Follow error: {str(e)}")
            return False, str(e)
    
    @transaction.atomic
    def unfollow_user(self, user, user_to_unfollow):
        try:
            if not user_to_unfollow:
                raise ValidationError("User to unfollow does not exist.")
            
            # Immediate database update with transaction
            user.following_set.filter(following=user_to_unfollow).delete()
            
            # Clear any cached data
            cache.delete(f'follow_{user.id}_{user_to_unfollow.id}')
            cache.delete(f'followers_count_{user_to_unfollow.id}')
            cache.delete(f'following_count_{user.id}')
            
            return True, "Successfully unfollowed user."
            
        except Exception as e:
            logger.error(f"Unfollow error: {str(e)}")
            return False, str(e)
    
    def check_following_status(self, user, target_user):
        try:
            if not target_user:
                return False
            return user.following_set.filter(following=target_user).exists()
        except Exception:
            logger.error(f"Error checking following status for {user} -> {target_user}")
            return False
    
    def get_follower_stats(self, profile):
        return {
            'followers_count': profile.user.followers_set.count(),
            'following_count': profile.user.following_set.count()
        }