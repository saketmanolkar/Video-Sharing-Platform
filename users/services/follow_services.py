import logging
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from users.models import UserActivitySummary
logger = logging.getLogger(__name__)

class FollowService:
    @transaction.atomic
    @transaction.atomic
    def follow_user(self, user, user_to_follow):
        try:
            if not user_to_follow:
                raise ValidationError("User to follow does not exist.")
                
            if user == user_to_follow:
                raise ValidationError("You cannot follow yourself.")
            
            # Wrap all DB operations in transaction
            with transaction.atomic():
                # Create follow relationship
                _, created = user.following_set.get_or_create(following=user_to_follow)
                
                if created:  # Only update counts if new follow
                    # Use F() to prevent race conditions
                    UserActivitySummary.objects.filter(user=user_to_follow).update(
                        total_followers=F('total_followers') + 1
                    )
                    UserActivitySummary.objects.filter(user=user).update(
                        total_following=F('total_following') + 1
                    )

                    print(f"👥 User {user.username} followed {user_to_follow.username} and updated denormalized table")
            
            return True, "Successfully followed user."
            
        except Exception as e:
            logger.error(f"Follow error: {str(e)}")
            return False, str(e)

    @transaction.atomic
    def unfollow_user(self, user, user_to_unfollow):
        try:
            if not user_to_unfollow:
                raise ValidationError("User to unfollow does not exist.")
            
            with transaction.atomic():
                # Delete follow relationship
                deleted = user.following_set.filter(following=user_to_unfollow).delete()[0]
                
                if deleted:  # Only update counts if something was deleted
                    # Use F() to prevent race conditions
                    UserActivitySummary.objects.filter(user=user_to_unfollow).update(
                        total_followers=F('total_followers') - 1
                    )
                    UserActivitySummary.objects.filter(user=user).update(
                        total_following=F('total_following') - 1
                    )

                    print(f"👥 User {user.username} unfollowed {user_to_unfollow.username} and updated denormalized table")
            
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
        if hasattr(profile.user, 'activity_summary'):
            return {
                'followers_count': profile.user.activity_summary.total_followers,
                'following_count': profile.user.activity_summary.total_following
            }
        else:
            return {
                'followers_count': profile.user.followers_set.count(),
                'following_count': profile.user.following_set.count()
            }