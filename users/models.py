from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.staticfiles.storage import staticfiles_storage
import uuid
from django.contrib.auth import get_user_model
import time

User = get_user_model()

# Create a function to generate unique paths for profile pictures
def unique_profile_path(instance, filename):
    """
    Generate a unique path for profile pictures to prevent overwriting
    Format: profiles/username_timestamp_uuid.extension
    """
    # Get the file extension
    ext = filename.split('.')[-1] if '.' in filename else 'jpg'
    
    # Generate unique filename components
    username = instance.user.username if instance.user else 'unknown'
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]  # First 8 chars of UUID
    
    # Return the unique path
    return f'profiles/{username}_{timestamp}_{unique_id}.{ext}'

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
        upload_to=unique_profile_path,  # Use the custom function
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
    id = models.UUIDField(
        default=uuid.uuid4,
        primary_key=True,
        editable=False
    )
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

class Message(models.Model):
    sender = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)
    recipient = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True,related_name='messages')
    name = models.CharField(max_length=200,null=True,blank=True)
    email = models.EmailField(null=True,blank=True)
    subject = models.CharField(max_length=200,null=True,blank=True)
    body = models.TextField()
    is_read = models.BooleanField(default=False ,null=True)
    created = models.DateTimeField(auto_now_add=True)
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)

    def __str__(self):
        sender = self.sender.username if self.sender else self.name
        recipient = self.recipient.username if self.recipient else "Unknown"
        return f"From {sender} to {recipient} - {self.subject}"
    
    class Meta:
        ordering = ['is_read','-created']

class UserSession(models.Model):
    # Core info
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True)
    
    # Client info
    device_info = models.JSONField(default=dict)
    browser_info = models.JSONField(default=dict)
    ip_location = models.GenericIPAddressField(null=True)
    
    # Activity log - empty to start
    activity_log = models.JSONField(default=dict)

    class Meta:
        ordering = ['-start_time']  # Newest sessions first
        indexes = [
            models.Index(fields=['-start_time']),  # Index for faster sorting
        ]

    def __str__(self):
        return f"Session for {self.user.username} at {self.start_time}"

class UserActivitySummary(models.Model):

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='activity_summary'
    )

    # Session totals
    total_sessions = models.IntegerField(default=0)
    total_profile_visits = models.IntegerField(default=0)
    total_time_spent = models.FloatField(default=0)  # in minutes
    avg_session_length = models.FloatField(default=0)  # in minutes
    
    # Last activity tracking
    last_session_date = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Follower stats
    total_followers = models.IntegerField(default=0)
    total_following = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'user_activity_summary'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['last_session_date']),
            models.Index(fields=['total_followers']),  # Optional, if you need to query by these
            models.Index(fields=['total_following']),
            models.Index(fields=['total_time_spent'])  # Optional, if you need to query by these
        ]

    def __str__(self):
        return f"{self.user.username}'s Activity Summary"

class Report(models.Model):

    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # One-to-one relationship with User
    user_report_url = models.URLField(null=True, blank=True)  # URL for user report
    video_report_url = models.URLField(null=True, blank=True)  # URL for video report
    user_report_audio_file_url = models.URLField(null=True, blank=True)  # URL for generated audio file
    video_report_audio_file_url = models.URLField(null=True, blank=True)  # URL for generated audio file
    user_report_generated_at = models.DateTimeField(null=True, blank=True)  # Date for user report generation
    video_report_generated_at = models.DateTimeField(null=True, blank=True)  # Date for video report generation
    user_report_audio_generated_at = models.DateTimeField(null=True, blank=True)  # Date for audio generation
    video_report_audio_generated_at = models.DateTimeField(null=True, blank=True)  # Date for audio generation
    audio_is_generated = models.BooleanField(default=False)  # Checkbox for audio generation status

    def __str__(self):
        return f"Report for {self.user.username}"

# Create a function to generate paths for blog PDFs
def blog_pdf_path(instance, filename):
    """
    Generate a path for blog PDFs
    Format: blogs/uuid.pdf
    """
    # Get the file extension
    ext = filename.split('.')[-1] if '.' in filename else 'pdf'
    
    # Generate unique filename using the UUID
    unique_id = str(instance.id)
    
    # Return the path - this will create a 'blogs' folder in your DO Spaces
    return f'blogs/{unique_id}.{ext}'

class Blog(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    title = models.CharField(max_length=200)
    pdf_file = models.FileField(upload_to=blog_pdf_path)
    created = models.DateTimeField(auto_now_add=True)
    views = models.IntegerField(default=0)
    author = models.CharField(max_length=200, null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return self.title