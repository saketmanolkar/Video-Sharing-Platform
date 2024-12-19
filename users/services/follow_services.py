import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class FollowService:
    def follow_user(self, user, user_to_follow):
        try:
            if not user_to_follow:
                raise ValidationError("User to follow does not exist.")
                
            if user == user_to_follow:
                raise ValidationError("You cannot follow yourself.")
                
            _, created = user.following_set.get_or_create(following=user_to_follow)
            if not created:
                raise ValidationError("Already following this user.")
                
            return True, "Successfully followed user."
            
        except ValidationError as e:
            return False, str(e)
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
    
    def unfollow_user(self, user, user_to_unfollow):
        try:
            if not user_to_unfollow:
                raise ValidationError("User to unfollow does not exist.")
                
            follow = user.following_set.filter(following=user_to_unfollow)
            if not follow.exists():
                raise ValidationError("Not following this user.")
                
            follow.delete()
            return True, "Successfully unfollowed user."
            
        except ValidationError as e:
            return False, str(e)
        except Exception as e:
            return False, f"An error occurred: {str(e)}"
    
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