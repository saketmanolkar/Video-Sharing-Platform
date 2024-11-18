from django.db import models
from django.contrib.auth.models import User
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.templatetags.static import static
from django.conf import settings
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4, 
        primary_key=True,
        unique=True, 
        editable=False
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Additional fields not in User model
    bio = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    profile_pics = models.ImageField(
        upload_to='profiles/', 
        blank=True, 
        null=True
    )
    github = models.CharField(max_length=200, blank=True, null=True)
    twitter = models.CharField(max_length=200, blank=True, null=True)
    linkedin = models.CharField(max_length=200, blank=True, null=True)
    youtube = models.CharField(max_length=200, blank=True, null=True)
    instagram = models.CharField(max_length=200, blank=True, null=True)
    
    # Timestamps
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']  # Newest profiles first

    def __str__(self):
        return f"{self.user.username}'s profile"
    
    # Properties to easily access User model fields
    @property
    def username(self):
        return self.user.username
        
    @property
    def email(self):
        return self.user.email
        
    @property
    def name(self):
        if self.user.first_name or self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        return self.user.username
    
    @property
    def followers_count(self):
        """Get total number of followers"""
        return self.user.followers_set.count()

    @property
    def following_count(self):
        """Get total number of users being followed"""
        return self.user.following_set.count()
    
    @property
    def total_views(self):
        """Get total views across all videos"""
        from projects.models import Video
        return Video.objects.filter(uploader=self.user).aggregate(
            total_views=models.Sum('views')
        )['total_views'] or 0

    def get_profile_pic_url(self):
        """Get profile picture URL with proper fallback"""
        if self.profile_pics:
            return self.profile_pics.url
        return static('images/user-default.jpg')

class Follow(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4, 
        primary_key=True,
        unique=True, 
        editable=False
    )
    follower = models.ForeignKey(
        User,
        related_name='following_set',
        on_delete=models.CASCADE
    )
    following = models.ForeignKey(
        User,
        related_name='followers_set',
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        indexes = [models.Index(fields=['follower', 'following'])]

    def clean(self):
        """Validate the follow relationship"""
        if self.follower == self.following:
            raise ValidationError("Users cannot follow themselves.")
        
        if Follow.objects.filter(
            follower=self.follower, 
            following=self.following
        ).exists():
            raise ValidationError("Already following this user.")

    def save(self, *args, **kwargs):
        self.clean()  # Run validation before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"

def follow(self, user_to_follow):
    """Follow another user with error handling"""
    try:
        if not user_to_follow:
            raise ValidationError("User to follow does not exist.")
            
        if self == user_to_follow:
            raise ValidationError("You cannot follow yourself.")
            
        _, created = Follow.objects.get_or_create(
            follower=self,
            following=user_to_follow
        )
        if not created:
            raise ValidationError("Already following this user.")
            
        return True, "Successfully followed user."
        
    except ValidationError as e:
        return False, str(e)
    except Exception as e:
        return False, f"An error occurred: {str(e)}"

def unfollow(self, user_to_unfollow):
    """Unfollow a user with error handling"""
    try:
        if not user_to_unfollow:
            raise ValidationError("User to unfollow does not exist.")
            
        follow = Follow.objects.filter(
            follower=self,
            following=user_to_unfollow
        )
        if not follow.exists():
            raise ValidationError("Not following this user.")
            
        follow.delete()
        return True, "Successfully unfollowed user."
        
    except ValidationError as e:
        return False, str(e)
    except Exception as e:
        return False, f"An error occurred: {str(e)}"

def is_following(self, user):
    """Check if following a user"""
    try:
        if not user:
            return False
        return self.following_set.filter(following=user).exists()
    except Exception:
        return False

# Add methods to User model
User.add_to_class('follow', follow)
User.add_to_class('unfollow', unfollow)
User.add_to_class('is_following', is_following)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create Profile when User is created"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save Profile when User is saved"""
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)
