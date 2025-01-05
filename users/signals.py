from django.db.models.signals import post_save, pre_delete, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.apps import apps
from django.core.mail import send_mail
from django.conf import settings
import os


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create Profile when User is created"""
    print('🟢 Creating Profile Signal: New user profile being created')
    if created:
        Profile = apps.get_model('users', 'Profile')
        Message = apps.get_model('users', 'Message')
        
        # Create profile first
        new_profile = Profile.objects.create(user=instance)
        print(f'✨ Profile created for user: {instance.username}')

        # Now that profile exists, create welcome message
        try:
            admin_user = User.objects.get(username='saketmanolkar')
            admin_profile = Profile.objects.get(user=admin_user)
            
            # Read welcome message template
            message_template_path = os.path.join(settings.BASE_DIR, 'templates', 'welcome_message.txt')
            with open(message_template_path, 'r') as file:
                message_body = file.read().format(username=instance.username)
            
            Message.objects.create(
                sender=admin_profile,
                recipient=new_profile,
                subject='Welcome to FilmsNation! 🎬',
                body=message_body,
                is_read=False
            )
            print(f'✨ Welcome message sent to: {instance.username}')
        except Exception as e:
            print(f'❌ Error sending welcome message: {str(e)}')

        # Send welcome email
        email_template_path = os.path.join(settings.BASE_DIR, 'templates', 'welcome_email.txt')
        with open(email_template_path, 'r') as file:
            email_body = file.read().format(username=instance.username)
        
        send_mail(
            subject='Welcome to FilmsNation',
            message=email_body,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[instance.email],
            fail_silently=False,
        )


@receiver(pre_save, sender='users.Profile')
def handle_profile_picture_update(sender, instance, **kwargs):
    """Handle profile picture replacement when updating"""
    print('🔄 Profile Update: Checking for profile picture changes')
    if instance.pk:  # Only for existing profiles
        try:
            old_profile = sender.objects.get(pk=instance.pk)
            if old_profile.profile_pics and old_profile.profile_pics != instance.profile_pics:
                old_profile.profile_pics.delete(save=False)
                print('🖼️ Old profile picture deleted')
        except sender.DoesNotExist:
            pass

@receiver(pre_delete, sender='users.Profile')
def cleanup_profile_files(sender, instance, **kwargs):
    """Clean up profile files before deletion"""
    print('🔴 Profile Deletion: Starting cleanup')
    try:
        if instance.profile_pics:
            instance.profile_pics.delete(save=False)
            print('📸 Profile picture deleted')
    except Exception as e:
        print(f'❌ Error cleaning up profile files: {str(e)}')

@receiver(post_delete, sender='users.Profile')
def delete_user(sender, instance, **kwargs):
    """Delete User after Profile is deleted"""
    print('🗑️ Profile Deleted: Cleaning up user')
    try:
        if instance.user:
            username = instance.user.username
            instance.user.delete()
            print(f'👤 User deleted: {username}')
    except Exception as e:
        print(f'❌ Error deleting user: {str(e)}')
