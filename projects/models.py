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
from PIL import Image
import io
from django.core.files.uploadedfile import InMemoryUploadedFile
from projects.utils import add_black_bars
from django.utils.text import slugify
from datetime import datetime
from django.templatetags.static import static
from .services.media_servies import ModelService

logger = logging.getLogger(__name__)

# Create your models here.

class Video(models.Model):
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

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def likes_count(self):
        return self.likes.filter(is_like=True).count()

    @property
    def dislikes_count(self):
        return self.likes.filter(is_like=False).count()

    def get_video_url(self, quality=None):
        return ModelService.get_video_url(self, quality)

    def save(self, *args, **kwargs):
        # Flag to track if this is a new upload
        is_new_upload = not self.pk or (
            self.pk and 
            not self.encoded_versions and 
            hasattr(self, '_file_changed') and 
            self._file_changed
        )
        
        # Clear thumbnail processing cache on new upload
        if is_new_upload:
            cache_key = f'thumbnail_processed_{self.pk}'
            cache.delete(cache_key)
        
        # First save to ensure file is written to disk
        super().save(*args, **kwargs)
        
        # Then handle encoding if needed
        if is_new_upload and self.file:
            # Store original file path
            original_file = self.file.path
            
            # Run encoding
            from .signals import handle_video_encoding
            handle_video_encoding(sender=self.__class__, instance=self)
            
            # Clean up original if encoding was successful
            if self.encoded_versions:
                ModelService.cleanup_original_file(original_file)
            
            # Save again to store encoded versions
            super().save(update_fields=['encoded_versions', 'file'])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_file = self.file if self.file else None
    
    def clean(self):
        super().clean()
        if self.file and self._original_file != self.file:
            self._file_changed = True

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
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='playlists',
        null=True
    )
    videos = models.ManyToManyField(
        Video,
        related_name='playlists'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} by {self.user.username}"

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

class ViewHistory(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4, 
        primary_key=True,
        unique=True, 
        editable=False
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
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

    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['video', 'viewed_at']),
            models.Index(fields=['user', 'viewed_at']),
        ]

    def __str__(self):
        viewer = self.user.username if self.user else f"Anonymous ({self.ip_address})"
        return f"{viewer} viewed {self.video.title}"