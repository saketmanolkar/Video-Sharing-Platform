from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
import uuid
from django.core.cache import cache

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
    ORIENTATION_CHOICES = [
        ('horizontal', 'Horizontal'),
        ('vertical', 'Vertical'),
    ]
    orientation = models.CharField(
        max_length=10,
        choices=ORIENTATION_CHOICES,
        default='horizontal'
    )
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