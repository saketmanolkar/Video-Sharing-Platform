from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.conf import settings
import uuid
from django.core.cache import cache
import os
from django.core.files import File
import json
import logging
from django.utils import timezone
from .services.video_services import VideoService
from django.core.exceptions import ValidationError
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)

# Create your models here.

class Video(models.Model):

    PRIVACY_PUBLIC = 'public'
    PRIVACY_PRIVATE = 'private'
    PRIVACY_UNLISTED = 'unlisted'
    PRIVACY_FOLLOWERS = 'followers'
    
    PRIVACY_CHOICES = [
        (PRIVACY_PUBLIC, 'Public - Anyone can view'),
        (PRIVACY_PRIVATE, 'Private - Only you can view'),
        (PRIVACY_UNLISTED, 'Unlisted - Only people with the link can view'),
        (PRIVACY_FOLLOWERS, 'Followers - Only your followers can view'),
    ]

    # Add the privacy field
    privacy_status = models.CharField(
        max_length=10,
        choices=PRIVACY_CHOICES,
        default=PRIVACY_PUBLIC, 
    )

    id = models.UUIDField(
        default=uuid.uuid4,
        primary_key=True,
        unique=True,
        editable=False
    )
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    file = models.FileField(
        upload_to='videos/',
        validators=[FileExtensionValidator(['mp4', 'mov'])]
    )
    thumbnail = models.ImageField(
        upload_to='thumbnails/',
        null=True,
        blank=True
    )
    tags = models.ManyToManyField(
        'Tag',
        related_name='videos',
        blank=True
    )
    uploader = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='uploaded_videos',
        null=True
    )
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    encoded_versions = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['description']),
            models.Index(fields=['uploader']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Check if thumbnail changed
        if self.thumbnail and self.thumbnail != self._original_thumbnail:
            self._thumbnail_changed = True
        else:
            self._thumbnail_changed = False
        
        VideoService.handle_video_save(self, *args, **kwargs)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_file = self.file if self.file else None
        self._original_thumbnail = self.thumbnail if self.thumbnail else None
    
    def clean(self):
        super().clean()
        if self.file and self._original_file != self.file:
            self._file_changed = True

    @property
    def processing_status(self):
        """Get video processing status"""
        # Force refresh from DB to get latest encoded_versions
        self.refresh_from_db()
        
        # If we have encoded versions, it's definitely ready
        if self.encoded_versions:
            return 'ready'
        
        # Check Redis lock
        from django_redis import get_redis_connection
        redis_client = get_redis_connection("default")
        lock_key = f'encoding_lock_{self.id}'
        is_processing = redis_client.exists(lock_key)
        
        if is_processing:
            return 'processing'
        
        # No encoded versions and no lock means error
        return 'error'

class Review(models.Model):
    video = models.ForeignKey(
        Video, 
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews',
        null=True
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(
        default=uuid.uuid4,
        primary_key=True,
        unique=True,
        editable=False
    )
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review by {self.user.username if self.user else 'Anonymous'} on {self.video.title}"

class Tag(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(default=timezone.now)
    id = models.UUIDField(
        default=uuid.uuid4, unique=True, 
        primary_key=True, editable=False
    )
    def __str__(self):
        return self.name

class Playlist(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4, 
        primary_key=True,
        unique=True, 
        editable=False
    )
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='playlists',
        null=True
    )
    is_private = models.BooleanField(default=False)
    thumbnail = models.ImageField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.thumbnail:
            # Get first video in playlist if any items exist
            first_item = self.items.first()
            if first_item and first_item.video.thumbnail:
                self.thumbnail = first_item.video.thumbnail
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} by {self.user.username if self.user else 'Unknown'}"

class PlaylistItem(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4, 
        primary_key=True,
        unique=True, 
        editable=False
    )
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name='items'
    )
    video = models.ForeignKey(
        'Video',
        on_delete=models.CASCADE,
        related_name='playlist_items'
    )
    position = models.PositiveIntegerField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position']
        unique_together = ['playlist', 'position']

    def __str__(self):
        return f"{self.video.title} in {self.playlist.name}"

class Like(models.Model):
    video = models.ForeignKey(
        Video, 
        on_delete=models.CASCADE,
        related_name='likes'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='video_likes',
        null=True
    )
    is_like = models.BooleanField(
        help_text="True for like, False for dislike"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(
        default=uuid.uuid4, 
        primary_key=True, 
        unique=True, 
        editable=False
    )

    class Meta:
        # Prevent multiple likes from same user on same video
        unique_together = ['user', 'video']
        indexes = [
            models.Index(fields=['video', 'is_like']),
        ]

    def __str__(self):
        action = "likes" if self.is_like else "dislikes"
        return f"{self.user.username} {action} {self.video.title}"

    def clean(self):
        # Prevent self-likes
        if self.user == self.video.uploader:
            raise ValidationError("Cannot like your own video")
            
        # Check for existing opposite reaction
        if Like.objects.filter(
            user=self.user,
            video=self.video,
            is_like=not self.is_like
        ).exists():
            raise ValidationError("Cannot like and dislike simultaneously")

class ViewHistory(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4, 
        primary_key=True,
        unique=True, 
        editable=False
    )
    window_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='view_history',
        null=True,  # Allow null for anonymous users
        blank=True
    )
    video = models.ForeignKey(
        Video,
        on_delete=models.CASCADE,
        related_name='views_history'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    duration_watched = models.DurationField(null=True, blank=True)  
    completed = models.BooleanField(default=False)             

    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['video', 'viewed_at']),
            models.Index(fields=['user', 'viewed_at']),
            models.Index(fields=['window_id']),
        ]

    def __str__(self):
        viewer = self.user.username if self.user else f"Anonymous ({self.ip_address})"
        return f"{viewer} viewed {self.video.title}"

class VideoAnalytics(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    video = models.OneToOneField('Video', on_delete=models.CASCADE, related_name='analytics')
    uploader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='video_analytics')
    
    # Basic Video Info
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField()  # Video creation date
    
    # Engagement Metrics
    total_views = models.IntegerField(default=0)
    total_comments = models.IntegerField(default=0)
    total_likes = models.IntegerField(default=0)
    total_dislikes = models.IntegerField(default=0)
    
    # Time-based Metrics
    last_24h_views = models.IntegerField(default=0)
    last_7d_views = models.IntegerField(default=0)
    last_30d_views = models.IntegerField(default=0)

    # New Metrics
    watch_time = models.FloatField(default=0)  # Total watch time in minutes
    completion_rate = models.FloatField(default=0)  # Completion rate as a percentage

    # Meta Information
    updated_at = models.DateTimeField(auto_now=True)

    completed_views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.uploader.username} - {self.title}"

    class Meta:
        indexes = [
            models.Index(fields=['uploader', '-total_views']),
            models.Index(fields=['-updated_at']),
        ]
        verbose_name = "Video Analytics"
        verbose_name_plural = "Video Analytics"