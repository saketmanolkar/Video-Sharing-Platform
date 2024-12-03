from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from users.models import Profile
from .services.user_services import ProfileService
from .services.follow_services import FollowService
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required
from .forms import ProfileForm
from django.http import JsonResponse

@login_required
def creator_studio(request, pk):
    profile_service = ProfileService()
    profile = profile_service.get_profile(pk, Profile)
    
    if request.user != profile.user:
        messages.error(request, "You don't have permission to access this creator studio")
        return redirect('profile', pk=pk)

    context = profile_service.get_creator_studio_data(pk, Profile)
    return render(request, "users/creator_studio.html", context)

def profile(request, pk):
    profile_service = ProfileService()
    follow_service = FollowService()
    
    # Get profile data
    context = profile_service.get_profile_data(pk, Profile)
    
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
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        
        # Use the service to handle the update
        success, message = profile_service.update_profile(
            profile=profile,
            user_data=request.POST,
            profile_form=form,
            should_clear_pic=request.POST.get('clear_profile_pic')
        )
        
        if success:
            messages.success(request, message)
            return redirect('profile', pk=profile.id)
        else:
            messages.error(request, message)
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