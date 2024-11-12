from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.conf import settings
import uuid
from django.core.cache import cache
import os
from django.core.files import File
from projects.utils import cleanup_media_files
from .storage import VideoStorage
import json
import logging

logger = logging.getLogger(__name__)

# Create your models here.

class Video(models.Model):

    title = models.CharField(
        max_length=100,
        help_text="Video title"
    )
    description = models.TextField(
        blank=True,
        help_text="Video description"
    )
    file = models.FileField(
        upload_to='videos/',
        storage=VideoStorage(),
        validators=[FileExtensionValidator(['mp4', 'mov'])],
        help_text="Upload MP4 or MOV files only"
    )
    thumbnail = models.ImageField(
        upload_to='thumbnails/',
        blank=True,
        null=True,
        help_text="Video thumbnail"
    )
    # User Fields
    #uploader = models.ForeignKey(
        #User, 
        #on_delete=models.CASCADE,
        #related_name='videos'
    #)
    views = models.PositiveIntegerField(default=0)
    tags = models.ManyToManyField('Tag', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(
        default=uuid.uuid4, unique=True, 
        primary_key=True, editable=False
    )
    
    # Add new fields
    encoded_versions = models.JSONField(
        null=True,  # Make it nullable
        blank=True,
        default=dict  # Provide a default empty dict
    )
    current_quality = models.CharField(
        max_length=10,
        default='720p',
        choices=[
            ('1080p', 'Full HD'),
            ('720p', 'HD'),
            ('480p', 'SD'),
            ('360p', 'Low')
        ]
    )
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # If this is an update and the file has changed
        if not is_new:
            try:
                old_video = Video.objects.get(pk=self.pk)
                if old_video.file != self.file:
                    cleanup_media_files(os.path.basename(old_video.file.name))
            except Video.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # After saving, check for encoded versions
        if self.file:
            try:
                name_without_ext = os.path.splitext(os.path.basename(self.file.name))[0]
                versions_file = os.path.join(
                    settings.MEDIA_ROOT,
                    'videos',
                    f"{name_without_ext}_versions.json"
                )
                
                if os.path.exists(versions_file):
                    with open(versions_file, 'r') as f:
                        self.encoded_versions = json.load(f)
                        super().save(update_fields=['encoded_versions'])
                    os.remove(versions_file)  # Clean up the temporary file
                    print(f"Updated encoded versions: {self.encoded_versions}")  # Debug print
                    
            except Exception as e:
                print(f"Error loading encoded versions: {str(e)}")
    
    def __str__(self):
        return self.title
    
    @property
    def likes_count(self):
        cache_key = f'video_{self.id}_likes_count'
        count = cache.get(cache_key)
        if count is None:
            count = self.likes.filter(is_like=True).count()
            cache.set(cache_key, count, timeout=3600)  # Cache for 1 hour
        return count
    
    @property
    def dislikes_count(self):
        return self.likes.filter(is_like=False).count()

    def get_video_url(self, quality=None):
        if not quality and self.encoded_versions:
            # Get the highest quality available
            quality = list(self.encoded_versions.keys())[0]
            
        if self.encoded_versions and quality in self.encoded_versions:
            # Get the full path to the encoded video file
            video_filename = self.encoded_versions[quality]
            # Make sure we're using the correct path structure
            return f"{settings.MEDIA_URL}videos/{video_filename}"
        
        # Return original video URL if no encoded version exists
        return self.file.url

    def delete(self, *args, **kwargs):
        try:
            if self.file:
                cleanup_media_files(os.path.basename(self.file.name))
        except Exception as e:
            logger.error(f"Error deleting video files: {str(e)}")
        finally:
            super().delete(*args, **kwargs)

    def get_versions(self):
        """Get all available versions of the video"""
        try:
            if not self.file:
                return {}
                
            versions = {}
            base_path = os.path.dirname(self.file.path)
            name_without_ext, ext = os.path.splitext(os.path.basename(self.file.name))
            
            qualities = ['720p', '480p', '360p']
            for quality in qualities:
                version_name = f"{name_without_ext}_{quality}{ext}"
                version_path = os.path.join(base_path, version_name)
                if os.path.exists(version_path):
                    versions[quality] = f"videos/{version_name}"
                    
            return versions
            
        except Exception as e:
            logger.error(f"Error getting video versions: {str(e)}")
            return {}

class Review(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    comment = models.TextField(
        blank=True,
        help_text="Video description"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(
        default=uuid.uuid4, unique=True, 
        primary_key=True, editable=False
    )
    def __str__(self):
        return f"Review for {self.video.title}"

class Tag(models.Model):
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(
        default=uuid.uuid4, unique=True, 
        primary_key=True, editable=False
    )
    def __str__(self):
        return self.name

class Playlist(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True,
                          unique=True, editable=False)
    name = models.CharField(max_length=100)
    videos = models.ManyToManyField(Video)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name

class Like(models.Model):
    video = models.ForeignKey(
        Video, 
        on_delete=models.CASCADE,
        related_name='likes'
    )
    def __str__(self):
        return f"Like for {self.video.title}"
    #user = models.ForeignKey(
    #    User, 
    #    on_delete=models.CASCADE,
    #    related_name='video_likes'
    #)
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
        # Ensure user can only like/dislike once
        #unique_together = ['video', 'user']
        indexes = [
            models.Index(fields=['video', 'is_like']),
        ]
    
@property
def likes_count(self):
    cache_key = f'video_{self.id}_likes_count'
    count = cache.get(cache_key)
    if count is None:
        count = self.likes.filter(is_like=True).count()
        cache.set(cache_key, count, timeout=3600)  # Cache for 1 hour
    return count

@property
def dislikes_count(self):
    cache_key = f'video_{self.id}_dislikes_count'
    count = cache.get(cache_key)
    if count is None:
        count = self.likes.filter(is_like=False).count()
        cache.set(cache_key, count, timeout=3600)  # Cache for 1 hour
    return count