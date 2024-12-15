from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth import login, authenticate, logout
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
    
    # Get analytics data using the existing method
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
    profile = profile_service.get_profile(pk, Profile)
    
    if request.user != profile.user:
        messages.error(request, "You don't have permission to edit this profile")
        return redirect('profile', pk=pk)
    
    if request.method == 'POST':
        # Get all user fields
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        if not username or not first_name:
            messages.error(request, "Username and first name cannot be empty")
            form = ProfileForm(instance=profile)
            return render(request, "users/profile_form.html", {
                'form': form, 
                'profile': profile,
                'user': profile.user
            })
            
        # Update user fields
        user = profile.user
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        
        try:
            if User.objects.exclude(pk=user.pk).filter(username=username).exists():
                messages.error(request, "This username is already taken")
                form = ProfileForm(instance=profile)
                return render(request, "users/profile_form.html", {
                    'form': form, 
                    'profile': profile,
                    'user': profile.user
                })
            
            user.save()
            
            # Handle profile picture clearing
            if request.POST.get('clear_profile_pic'):
                profile.profile_pics = None
                profile.save()
            
            # Now process the profile form
            form = ProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile', pk=profile.id)
            
        except Exception as e:
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
    context = profile_service.get_user_videos(pk, Profile)
    return render(request, "projects/user_video.html", context)

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
    context = profile_service.get_user_history(pk, Profile)
    return render(request, "projects/view_history.html", context)

def login_user(request):
    page = "login_page"

    if request.user.is_authenticated:
        return redirect("projects")

    if request.method == "POST":
        username = request.POST.get("username").lower()
        password = request.POST.get("password")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(request, "Username does not exist")
            return render(request, "users/login_register.html", {"page": page})

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Successfully logged in!")
            return redirect("projects")
        else:
            messages.error(request, "Username OR password is incorrect")

    return render(request, "users/login_register.html", {"page": page})

def logout_user(request):
    logout(request)
    messages.info(request, "You have been logged out")
    return redirect("login-page")

@csrf_protect
def register_user(request):
    page = "register_page"
    form = CustomUserCreationForm()

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            
            messages.success(request, "User account was created")

            login(request, user)
            return redirect('update-profile', pk=user.profile.id)
        else:
            messages.error(request, "An error occurred during registration")
    context = {
        "page": page,
        "form": form
    }
    return render(request, "users/login_register.html", context)

@login_required
def handle_follow(request, pk):
    if request.method == 'POST':
        follow_service = FollowService()
        profile = get_object_or_404(Profile, id=pk)
        
        # Handle follow/unfollow
        success, message = follow_service.follow_user(request.user, profile.user) \
            if not follow_service.check_following_status(request.user, profile.user) \
            else follow_service.unfollow_user(request.user, profile.user)
        
        # Get updated stats
        stats = follow_service.get_follower_stats(profile)
        
        return JsonResponse({
            'status': 'success' if success else 'error',
            'message': message,
            'is_following': follow_service.check_following_status(request.user, profile.user),
            'followers_count': stats['followers_count'],
            'following_count': stats['following_count']
        })
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

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

def create_message(request,pk):
    recipient= Profile.objects.get(id=pk)
    form = MessageForm()

    try:
        sender = request.user.profile
    except:
        sender = None
    
    if request.method == "POST":
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
            messages.error(request, "An error occurred during message creation")
    context = {
        'recipient': recipient,
        'form': form
    }
    return render(request, "users/message_form.html", context)