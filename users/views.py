from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.models import User
from users.models import Profile, Message, Report, Blog
from .services.user_services import ProfileService
from .services.follow_services import FollowService
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required
from .forms import ProfileForm, MessageForm
from django.http import JsonResponse, Http404
from django.contrib.auth.forms import PasswordChangeForm
from rest_framework_simplejwt.tokens import RefreshToken
from django.middleware.csrf import get_token
from django.views.decorators.http import require_POST
from .services.cache_service import ProfileCache
from projects.services.cache_service import VideoContextCache,FormSubmissionCache
import hashlib
from projects.services.video_services import VideoService
from .models import UserSession
from django.contrib.auth.models import User
from django.contrib.auth import logout
from .tasks import save_session_activity
from users.tasks import save_session_activity , process_video_stats
import logging
from django.conf import settings as django_settings
import os
from django.views.decorators.cache import cache_control
from django.urls import reverse

logger = logging.getLogger(__name__)

@login_required(login_url="login-page")
def creator_studio(request):
    profile = request.user.profile
    profile_service = ProfileService()
    
    # Use the optimized function
    context = profile_service.get_creator_studio_data_optimized(profile.id, Profile)
    return render(request, "users/creator_studio.html", context)

@login_required(login_url="login-page")
def analytics(request):
    # Use current user's profile directly
    profile = request.user.profile
    profile_service = ProfileService()
    
    # Get analytics data for user's own profile
    context = profile_service.get_analytics_data(profile)
    
    return render(request, 'users/analytics.html', context)

def profile(request, pk):
    profile_service = ProfileService()
    follow_service = FollowService()
    
    # Get profile data
    context = profile_service.get_profile_data(pk, Profile)

    # Get unread messages count to the context
    context['unread_messages_count'] = context['profile'].messages.filter(is_read=False).count()
    
    # Add follow status to context if user is authenticated
    if request.user.is_authenticated and request.user != context['profile'].user:
        context['is_following'] = follow_service.check_following_status(
            request.user, 
            context['profile'].user
        )
    
    return render(request, "users/profile.html", context)

@login_required(login_url="login-page")
def update_profile(request):
    # Use the logged-in user's profile directly
    profile = request.user.profile
    profile_service = ProfileService()
    profile_cache = ProfileCache()
    video_context_cache = VideoContextCache()
    form_cache = FormSubmissionCache()
    
    if request.method == 'POST':
        # Generate hash from form data
        form_data = str(request.POST) + str(request.FILES)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        if form_cache.check_submission(submission_hash):
            messages.warning(request, "Form was already submitted")
            return redirect('profile', pk=profile.id)
            
        # Mark as submitted
        form_cache.set_submission(submission_hash)
        
        try:
            # Get all user fields - Handle None values safely
            username = request.POST.get('username') or ''
            username = username.strip()
            
            first_name = request.POST.get('first_name') or ''
            first_name = first_name.strip()
            
            last_name = request.POST.get('last_name') or ''
            last_name = last_name.strip()
            
            if not username or not first_name:
                form_cache.clear_submission(submission_hash)
                messages.error(request, "Username and first name cannot be empty")
                form = ProfileForm(instance=profile)
                return render(request, "users/profile_form.html", {
                    'form': form, 
                    'profile': profile,
                    'user': profile.user
                })
            
            try:
                # Update user fields
                user = profile.user
                old_username = user.username
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                
                # Username validation
                if User.objects.exclude(pk=user.pk).filter(username=username).exists():
                    form_cache.clear_submission(submission_hash)
                    messages.error(request, "This username is already taken")
                    form = ProfileForm(instance=profile)
                    return render(request, "users/profile_form.html", {
                        'form': form, 
                        'profile': profile,
                        'user': profile.user
                    })
                
                # If username changed, invalidate related video caches
                if old_username != username:
                    print(f"\n🔄 Username changed from {old_username} to {username}")
                    # Get all videos by this user
                    user_videos = profile.user.uploaded_videos.all()
                    for video in user_videos:
                        # Check if cache exists first
                        if video_context_cache.get_context(video.id):
                            print(f"\n🎯 Found cache for video: {video.id}")
                            video_context_cache.invalidate(video.id)
                
                user.save()
                
            except Exception as e:
                form_cache.clear_submission(submission_hash)
                messages.error(request, f"Error updating user: {str(e)}")
                return redirect('profile', pk=profile.id)
            
            # Handle profile picture clearing
            if request.POST.get('clear_profile_pic'):
                profile.profile_pics = None
                profile.save()
            
            # Process the profile form
            form = ProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save()
                # Invalidate profile cache
                profile_cache.invalidate(profile.id)
                print(f"\n🗑️ Cache invalidated for profile: {profile.id}")
                
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile', pk=profile.id)
            
        except Exception as e:
            # Clear submission cache on error
            form_cache.clear_submission(submission_hash)
            messages.error(request, str(e))
    else:
        form = ProfileForm(instance=profile)
    
    context = {
        'form': form, 
        'profile': profile,
        'user': profile.user
    }
    return render(request, "users/profile_form.html", context)


def user_videos(request, pk):
    profile_service = ProfileService()
    search_query = request.GET.get('search', '')  # Get search query from URL
    context = profile_service.get_user_videos(pk, Profile, search_query)
    return render(request, "users/user_video.html", context)

@login_required(login_url="login-page")
def user_history(request):
    # Use the logged-in user's profile directly
    profile = request.user.profile
    
    # Get the user's view history
    profile_service = ProfileService()
    history_data = profile_service.get_user_history(profile)

    # Add pagination
    paged_history, custom_range = VideoService.get_paginated_videos(
        history_data['history_videos'],
        request.GET.get('page', 1)
    )

    context = {
        'profile': profile,
        'view_history': paged_history,
        'custom_range': custom_range
    }
    
    return render(request, "users/view_history.html", context)

def login_user(request):
    if request.COOKIES.get('show_timeout') == 'true':
        print("Found timeout cookie, showing message")
        messages.error(request, 'Session expired due to inactivity')
        response = render(request, 'users/login_register.html', {"page": "login_page"})
        response.delete_cookie('show_timeout')
        return response
    
    if request.method == "POST":
        form_cache = FormSubmissionCache()
        # Generate hash from form data
        form_data = str(request.POST)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        if form_cache.check_submission(submission_hash):
            return JsonResponse({
                'message': 'Form already submitted'
            }, status=400)
            
        # Mark as submitted
        form_cache.set_submission(submission_hash)
        
        try:
            # Basic sanitization - just trim whitespace and lowercase
            username = request.POST.get("username", "").strip().lower()
            password = request.POST.get("password", "")
            
            # Simple validation - just check if they exist
            if not username or not password:
                form_cache.clear_submission(submission_hash)
                return JsonResponse({
                    'message': 'Username and password are required'
                }, status=400)
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                refresh = RefreshToken.for_user(user)
                return JsonResponse({
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'username': user.username,
                    'user_id': user.id,
                    'message': 'Login successful'
                })
            else:
                form_cache.clear_submission(submission_hash)
                return JsonResponse({
                    'message': 'Invalid username or password'
                }, status=400)
                
        except Exception as e:
            form_cache.clear_submission(submission_hash)
            print(f"Login error: {e}")
            return JsonResponse({
                'message': 'An error occurred during login'
            }, status=500)
    
    get_token(request)
    return render(request, "users/login_register.html", {"page": "login_page"})

@login_required(login_url="login-page")
def logout_user(request):
    if request.user.is_authenticated:
        active_session = UserSession.objects.filter(
            user=request.user,
            end_time__isnull=True
        ).first()
        
        if active_session:
            try:
                # Queue the activity save task
                task = save_session_activity.delay(
                    session_id=str(active_session.id),
                    user_id=request.user.id,
                    inactive=False
                )
                logger.info(f"✅ Queued session cleanup task: {task.id}")
            except Exception as e:
                logger.error(f"❌ Failed to queue cleanup task: {str(e)}")
        
        # Call the task to process video stats
        process_video_stats.delay(request.user.id)  # Use .delay() if using Celery


        # Handle timeout case
        if request.GET.get('timeout') == 'true':
            response = redirect('login-page')
            response.set_cookie('show_timeout', 'true', max_age=5)
            response.set_cookie('logout', 'true', max_age=5)
            logout(request)
            return response

        # Normal logout
        response = redirect('login-page')
        response.set_cookie('logout', 'true', max_age=5)
        logout(request)
        return response
    
    return redirect('login-page')

@csrf_protect
def register_user(request):
    page = "register_page"
    form = CustomUserCreationForm()

    if request.method == "POST":
        form_cache = FormSubmissionCache()
        # Generate hash from form data
        form_data = str(request.POST)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        if form_cache.check_submission(submission_hash):
            messages.warning(request, "Form already submitted")
            return redirect('login-page')
            
        # Mark as submitted
        form_cache.set_submission(submission_hash)
        
        try:
            form = CustomUserCreationForm(request.POST)
            if form.is_valid():
                user = form.save(commit=False)
                # Sanitizing username (already validated by Django's form)
                user.username = user.username.lower().strip()
                user.save()
                
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                request.session['temp_access_token'] = str(refresh.access_token)
                request.session['temp_refresh_token'] = str(refresh)
                
                login(request, user)
                return redirect('update-profile')
            else:
                form_cache.clear_submission(submission_hash)
                # Display more specific form errors
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
                
        except Exception as e:
            form_cache.clear_submission(submission_hash)
            messages.error(request, str(e))
            
    context = {
        "page": page,
        "form": form
    }
    return render(request, "users/login_register.html", context)


@login_required(login_url='login-page')
def inbox(request):
    profile = request.user.profile
    messageList = profile.messages.all()
    unreadCount = messageList.filter(is_read=False).count()
    context = {
        'messageList': messageList,
        'unreadCount': unreadCount
    }
    return render(request, "users/inbox.html", context)

@login_required(login_url="login-page")
def view_message(request,pk):
    profile = request.user.profile
    message=profile.messages.get(id=pk) 
    if message.is_read == False:
        message.is_read = True
        message.save()
    context = {
        'message': message
    }
    return render(request, "users/message.html", context)

def create_message(request, pk):
    recipient = get_object_or_404(Profile, id=pk)
    form = MessageForm()

    try:
        sender = request.user.profile
    except AttributeError:  # For anonymous users who don't have a profile
        sender = None
    
    if request.method == "POST":
        form_cache = FormSubmissionCache()
        # Generate hash from form data
        form_data = str(request.POST)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        if form_cache.check_submission(submission_hash):
            messages.warning(request, "Message already sent")
            return redirect('profile', pk=recipient.id)
            
        # Mark as submitted
        form_cache.set_submission(submission_hash)
        
        try:
            form_data = request.POST.copy()
            
            # For authenticated users, pre-fill name and email from their profile
            if sender:
                form_data['name'] = sender.name
                form_data['email'] = sender.email
            
            form = MessageForm(form_data)
            if form.is_valid():
                message = form.save(commit=False)
                message.sender = sender
                message.recipient = recipient
                
                # Set name and email based on authentication status
                if sender:
                    message.name = sender.name
                    message.email = sender.email
                else:
                    message.name = form.cleaned_data['name']
                    message.email = form.cleaned_data['email']
                
                message.save()
                messages.success(request, "Message sent successfully")
                return redirect('profile', pk=recipient.id)
            else:
                form_cache.clear_submission(submission_hash)
                # More specific error handling
                error_msg = "Please correct the errors below."
                messages.error(request, error_msg)
                
        except Exception as e:
            form_cache.clear_submission(submission_hash)
            messages.error(request, f"An error occurred: {str(e)}")
            
    context = {
        'recipient': recipient,
        'form': form
    }
    return render(request, "users/message_form.html", context)

@login_required(login_url="login-page") 
def settings(request):
    if request.method == 'POST':
        form_cache = FormSubmissionCache()
        # Generate hash from form data
        form_data = str(request.POST)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        if form_cache.check_submission(submission_hash):
            messages.warning(request, "Password change already submitted")
            return redirect('profile', pk=request.user.profile.id)
            
        # Mark as submitted
        form_cache.set_submission(submission_hash)
        
        try:
            password_form = PasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Your password was successfully updated!')
                return redirect('profile', pk=request.user.profile.id)
            else:
                form_cache.clear_submission(submission_hash)
                messages.error(request, 'Please correct the error below.')
                
        except Exception as e:
            form_cache.clear_submission(submission_hash)
            messages.error(request, str(e))
            
    else:
        password_form = PasswordChangeForm(user=request.user)
    
    context = {
        'password_form': password_form
    }
    
    return render(request, 'users/settings.html', context)

@require_POST
@login_required(login_url="login-page")
def clear_temp_tokens(request):
    if 'temp_access_token' in request.session:
        del request.session['temp_access_token']
        del request.session['temp_refresh_token']
    return JsonResponse({'status': 'success'})

@login_required(login_url="login-page")
@cache_control(max_age=3600, public=True)
def report(request, pk):
    try:
        profile = get_object_or_404(Profile, id=pk)
        report_type = request.GET.get('report_type')

        if not report_type:
            return render(request, 'users/report.html', {
                'error': 'Report type is required',
                'profile': profile,
                'report_exists': False  # Add this flag
            }, status=400)

        try:
            report = Report.objects.get(user=profile.user)
            
            # Check if this specific report type exists
            if report_type == 'user':
                if not report.user_report_url:  # If no user report exists
                    return render(request, 'users/report.html', {
                        'profile': profile,
                        'report_type': report_type,
                        'report_exists': False  # Add this flag
                    })
                created_at = report.user_report_generated_at
                report_url = report.user_report_url
                audio_url = report.user_report_audio_file_url
                audio_generated_at = report.user_report_audio_generated_at
                audio_is_generated = report.audio_is_generated

            elif report_type == 'video':
                if not report.video_report_url:  # If no video report exists
                    return render(request, 'users/report.html', {
                        'profile': profile,
                        'report_type': report_type,
                        'report_exists': False  # Add this flag
                    })
                created_at = report.video_report_generated_at
                report_url = report.video_report_url
                audio_url = report.video_report_audio_file_url
                audio_generated_at = report.video_report_audio_generated_at
                audio_is_generated = report.audio_is_generated
            else:
                return render(request, 'users/report.html', {
                    'profile': profile,
                    'report_exists': False  # Add this flag
                }, status=400)

        except Report.DoesNotExist:
            return render(request, 'users/report.html', {
                'profile': profile,
                'report_exists': False,
            })

        # Get content from the report URL - handling both local and remote URLs
        file_content = ""
        if report_url:
            try:
                if report_url.startswith('http'):
                    # Remote URL (DigitalOcean Spaces) - use requests to fetch content
                    import requests
                    response = requests.get(report_url)
                    if response.status_code == 200:
                        file_content = response.text
                    else:
                        print(f"Error fetching remote file: HTTP {response.status_code}")
                        file_content = f"Error fetching report: HTTP {response.status_code}"
                else:
                    # Local file - read from filesystem
                    report_url = f"{django_settings.MEDIA_URL}reports/{report_url.split('/')[-1]}"
                    file_path = os.path.join(django_settings.MEDIA_ROOT, 'reports', report_url.split('/')[-1])
                    with open(file_path, 'r') as file:
                        file_content = file.read()
            except Exception as e:
                print(f"Error reading file: {e}")
                file_content = f"Error reading file content: {str(e)}"

        # Handle audio URL with cache busting
        if audio_url and not audio_url.startswith('http'):
            # Clean up the cache buster to be a single integer
            cache_buster = int(audio_generated_at.timestamp()) if audio_generated_at else ''
            clean_filename = audio_url.split('/')[-1]
            # Use the serve_audio URL pattern instead of direct media URL
            audio_url = reverse('serve_audio', kwargs={
                'profile_id': pk,
                'report_type': report_type
            }) + f'?v={cache_buster}'
            print(f"🎵 Clean audio URL: {audio_url}")

        context = {
            'profile': profile,
            'report_type': report_type,
            'report_file_url': report_url,
            'file_content': file_content,
            'created_at': created_at,
            'audio_url': audio_url,
            'audio_generated_at': audio_generated_at,
            'audio_is_generated': audio_is_generated,
            'has_audio': bool(audio_url),
            'report_exists': True,
            'report_type': report_type
        }

        response = render(request, 'users/report.html', context)
        
        # Add strong caching headers for audio files
        if audio_url:
            response['Cache-Control'] = 'public, max-age=31536000, immutable'  # Cache for 1 year
            response['Expires'] = 'Thu, 31 Dec 2037 23:55:55 GMT'
            print("📦 Added strong caching headers for audio")

        return response

    except Http404:
        messages.error(request, "Profile not found")
        return render(request, 'users/report.html', {
            'error': 'Profile not found'
        }, status=404)
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return render(request, 'users/report.html', {
            'error': 'An unexpected error occurred'
        }, status=500)

@login_required(login_url="login-page")
def delete_message(request, pk):
    # Get the message and verify ownership
    profile = request.user.profile
    message = get_object_or_404(Message, id=pk)
    
    # Check if the logged-in user is the message recipient
    if message.recipient != profile:
        messages.error(request, "You don't have permission to delete this message.")
        return redirect('inbox')
    
    if request.method == 'POST':
        try:
            message.delete()
            messages.success(request, 'Message deleted successfully!')
            return redirect('inbox')
        except Exception as e:
            messages.error(request, f'Error deleting message: {str(e)}')
            return redirect('view-message', pk=pk)
    
    return render(request, 'delete_object.html', {
        'object': f"message from {message.name}"
    })

def blog_view(request, pk=None):
    blogs = Blog.objects.all().order_by('-created')
    
    if pk:
        selected_blog = get_object_or_404(Blog, pk=pk)
        # Increment the view counter
        selected_blog.views += 1
        selected_blog.save()
        
    elif blogs.exists():
        # When no specific blog is requested, use the first one
        selected_blog = blogs.first()
        # Also increment the view counter for this first blog
        selected_blog.views += 1
        selected_blog.save()

    else:
        selected_blog = None
    
    return render(request, 'users/blogs.html', {
        'blogs': blogs,
        'selected_blog': selected_blog
    })
