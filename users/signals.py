from django.db.models.signals import post_save, pre_delete, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.apps import apps
from django.core.mail import send_mail
from django.conf import settings
import os
from users.models import UserSession, UserActivitySummary
from users.services.user_analytics_service import UserAnalyticsService
import traceback
from django.utils import timezone


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create Profile when User is created"""
    # Only proceed if this is a new user creation
    if created:
        print('🟢 Creating Profile Signal: New user profile being created')
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
        print(f'✨ Welcome email sent to: {instance.username}')
    else:
        print(f'⏩ Skipping profile creation for existing user: {instance.username}')


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


@receiver(post_save, sender=UserSession)
def update_user_activity_summary(sender, instance, **kwargs):
    """
    Updates UserActivitySummary using current session data
    """
    try:
        if instance.activity_log and 'pages_visited' in instance.activity_log:
            print(f"\n📊 Processing session for {instance.user.username}")
            
            # Get current session stats
            session_duration = 0
            if instance.end_time and instance.start_time:
                session_duration = (instance.end_time - instance.start_time).total_seconds() / 60
            
            # Update session owner's summary first
            owner_summary, created = UserActivitySummary.objects.get_or_create(
                user=instance.user,
                defaults={
                    'total_sessions': 1,
                    'total_time_spent': session_duration,
                    'avg_session_length': session_duration,
                    'last_session_date': timezone.now()
                }
            )
            
            if not created:
                owner_summary.total_sessions += 1
                owner_summary.total_time_spent += session_duration
                owner_summary.avg_session_length = owner_summary.total_time_spent / owner_summary.total_sessions
                owner_summary.last_session_date = timezone.now()
                owner_summary.save()
            
            print("🔍 Checking profile visits...")
            # Now update profile visit counts for OTHER users this person visited
            for page in instance.activity_log.get('pages_visited', []):
                path = page['path']
                
                # Use exact path matching like in get_profile_visits_count
                if '/users/profile/' in path:
                    try:
                        profile_id = path.split('/users/profile/')[1].strip('/')
                        exact_profile_path = f'/users/profile/{profile_id}/'
                        
                        # Only process if it's an exact profile path match
                        if path == exact_profile_path and profile_id != str(instance.user.profile.id):
                            from django.contrib.auth import get_user_model
                            User = get_user_model()
                            
                            visited_user = User.objects.filter(profile__id=profile_id).first()
                            if visited_user:
                                print(f"👤 Found visited user: {visited_user.username}")
                                
                                visited_summary, created = UserActivitySummary.objects.get_or_create(
                                    user=visited_user,
                                    defaults={
                                        'total_sessions': 0,
                                        'total_time_spent': 0,
                                        'avg_session_length': 0,
                                        'total_profile_visits': 1,
                                        'last_session_date': timezone.now()
                                    }
                                )
                                if not created:
                                    visited_summary.total_profile_visits += 1
                                    visited_summary.save(update_fields=['total_profile_visits'])
                                print(f"👀 Added visit to {visited_user.username}'s profile (total: {visited_summary.total_profile_visits})")
                            else:
                                print(f"⚠️ Could not find user with profile ID: {profile_id}")
                    except Exception as e:
                        print(f"⚠️ Error processing profile visit: {str(e)}")
            
            print(f"""
            ✅ Summary Updated for {instance.user.username}:
            - Session Length: {session_duration:.1f} mins
            - Total Sessions: {owner_summary.total_sessions}
            - Total Time: {owner_summary.total_time_spent:.1f} mins
            - Avg Session: {owner_summary.avg_session_length:.1f} mins
            """)
            
    except Exception as e:
        print(f"❌ Error updating summary: {str(e)}")
