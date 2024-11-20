from django.shortcuts import render, get_object_or_404,redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from users.models import Profile
from .services.user_services import ProfileService
from .services.follow_services import FollowService
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.views.decorators.csrf import csrf_protect

def profile(request, pk):

    profile_service = ProfileService()
    profile = profile_service.get_profile(pk, Profile)

    context = {
        'profile': profile,
        'videos': profile.user.uploaded_videos.all()[:2],
        'view_history': profile.user.view_history.all()[:2],
    }
    return render(request, "users/profile.html", context)

def user_videos(request, pk):
    profile_service = ProfileService()
    context = profile_service.get_user_videos(pk, Profile)
    return render(request, "projects/user_video.html", context)

def user_history(request, pk):
    profile_service = ProfileService()
    context = profile_service.get_user_history(pk, Profile)
    return render(request, "projects/view_history.html", context)

def login_user(request):
    page = "login_page"

    if request.user.is_authenticated:
        return redirect("projects")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            print("User does not exist")
            
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("projects")
        else:
            print("Invalid credentials")

    return render(request, "users/login_register.html")

def logout_user(request):
    logout(request)
    return redirect("login-page")

@csrf_protect
def register_user(request):
    page = "register_page"
    form = UserCreationForm()

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.username.lower()
            user.save()
            
            messages.success(request, "User account was created")
            return redirect('login-page')
    context = {
        "page": page,
        "form": form
    }
    return render(request, "users/login_register.html", context)