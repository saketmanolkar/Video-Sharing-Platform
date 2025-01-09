from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.models import User
from users.models import Profile, Message
from .services.user_services import ProfileService
from .services.follow_services import FollowService
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required
from .forms import ProfileForm, MessageForm
from django.http import JsonResponse, HttpResponseForbidden
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordChangeForm
from rest_framework_simplejwt.tokens import RefreshToken
from django.middleware.csrf import get_token
from django.views.decorators.http import require_POST
from .services.cache_service import ProfileCache
from django.core.cache import cache
from projects.services.cache_service import VideoContextCache,FormSubmissionCache
import hashlib
from django.core.paginator import Paginator
from projects.services.video_services import VideoService
from django.utils import timezone
from .models import UserSession
from django_redis import get_redis_connection
from .services.cache_service import SessionActivityCache
from django.contrib.auth.models import User
from django.contrib.auth import logout
from .tasks import save_session_activity
from users.tasks import save_session_activity 
import logging

logger = logging.getLogger(__name__)

@login_required
def creator_studio(request, pk):
    profile_service = ProfileService()
    profile = profile_service.get_profile(pk, Profile)
    
    if request.user != profile.user:
        messages.error(request, "You don't have permission to access this creator studio")
        return redirect('profile', pk=pk)

    context = profile_service.get_creator_studio_data(pk, Profile)
    return render(request, "users/creator_studio.html", context)

@login_required
def analytics(request, pk):
    profile_service = ProfileService()
    profile = profile_service.get_profile(pk, Profile)
    
    # Check if the requested profile matches current user
    if request.user.profile != profile:
        messages.error(request, "You don't have permission to access this analytics")
        return redirect('profile', pk=pk)
    
    context = profile_service.get_analytics_data(pk, Profile)
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

@login_required
def update_profile(request, pk):
    profile_service = ProfileService()
    profile_cache = ProfileCache()
    video_context_cache = VideoContextCache()
    form_cache = FormSubmissionCache()
    profile = profile_service.get_profile(pk, Profile)
    
    if request.user != profile.user:
        messages.error(request, "You don't have permission to edit this profile")
        return redirect('profile', pk=pk)
    
    if request.method == 'POST':
        # Generate hash from form data like other views
        form_data = str(request.POST) + str(request.FILES)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        if form_cache.check_submission(submission_hash):
            messages.warning(request, "Form was already submitted")
            return redirect('profile', pk=pk)
            
        # Mark as submitted
        form_cache.set_submission(submission_hash)
        
        try:
            # Get all user fields
            username = request.POST.get('username')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            
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

@login_required
def user_history(request, pk):
    # Get the profile first
    profile = get_object_or_404(Profile, id=pk)
    
    # Check if the user owns this profile
    if request.user != profile.user:
        messages.error(request, "You don't have permission to view this history")
        return redirect('profile', pk=pk)
    
    # If authorized, proceed with getting the history
    profile_service = ProfileService()
    history_data = profile_service.get_user_history(pk, Profile)

    # Add pagination similar to projects view
    paged_history, custom_range = VideoService.get_paginated_videos(
        history_data['history_videos'],
        request.GET.get('page', 1)
    )

    context = {
        'profile': history_data['profile'],
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
            username = request.POST.get("username").lower()
            password = request.POST.get("password")
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
                form_cache.clear_submission(submission_hash)  # Clear on failed login
                return JsonResponse({
                    'message': 'Invalid username or password'
                }, status=400)
                
        except Exception as e:
            form_cache.clear_submission(submission_hash)  # Clear on error
            print(f"Login error: {e}")
            return JsonResponse({
                'message': 'An error occurred during login'
            }, status=500)
    
    get_token(request)
    return render(request, "users/login_register.html", {"page": "login_page"})

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
                    user_id=request.user.id
                )
                logger.info(f"✅ Queued session cleanup task: {task.id}")
            except Exception as e:
                logger.error(f"❌ Failed to queue cleanup task: {str(e)}")
        
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
                user.username = user.username.lower()
                user.save()
                
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                request.session['temp_access_token'] = str(refresh.access_token)
                request.session['temp_refresh_token'] = str(refresh)
                
                login(request, user)
                return redirect('update-profile', pk=user.profile.id)
            else:
                form_cache.clear_submission(submission_hash)
                messages.error(request, "An error occurred during registration")
                
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
    recipient = Profile.objects.get(id=pk)
    form = MessageForm()

    try:
        sender = request.user.profile
    except Profile.DoesNotExist:
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
            form = MessageForm(request.POST)
            if form.is_valid():
                message = form.save(commit=False)
                message.sender = sender
                message.recipient = recipient
                
                if sender:
                    message.name = sender.name
                    message.email = sender.email
                
                message.save()
                messages.success(request, "Message sent successfully")
                return redirect('profile', pk=recipient.id)
            else:
                form_cache.clear_submission(submission_hash)
                messages.error(request, "An error occurred during message creation")
                
        except Exception as e:
            form_cache.clear_submission(submission_hash)
            messages.error(request, str(e))
            
    context = {
        'recipient': recipient,
        'form': form
    }
    return render(request, "users/message_form.html", context)

@login_required
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
def clear_temp_tokens(request):
    if 'temp_access_token' in request.session:
        del request.session['temp_access_token']
        del request.session['temp_refresh_token']
    return JsonResponse({'status': 'success'})