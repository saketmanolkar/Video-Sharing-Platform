from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.staticfiles.storage import staticfiles_storage
import uuid


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
    def total_views(self):
        from users.services.user_services import ProfileService
        profile_service = ProfileService()
        return profile_service.get_total_views(self.user)

    @property
    def followers_count(self):
        from users.services.follow_services import FollowService
        follow_service = FollowService()
        stats = follow_service.get_follower_stats(self)
        return stats['followers_count']

    @property
    def following_count(self):
        from users.services.follow_services import FollowService
        follow_service = FollowService()
        stats = follow_service.get_follower_stats(self)
        return stats['following_count']

    def get_profile_pic_url(self):
        """Get profile picture URL with proper fallback"""
        from users.services.user_services import ProfileService
        profile_service = ProfileService()
        return profile_service.get_profile_picture_url(self)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

class Follow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_set')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers_set')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'following')
        ordering = ['-created']

    def __str__(self):
        return f"{self.user.username} follows {self.following.username}"

    def clean(self):
        if self.user == self.following:
            raise ValidationError("Users cannot follow themselves.")
