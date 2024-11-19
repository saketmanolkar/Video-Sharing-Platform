from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from .models import Video, Review, Playlist, ViewHistory
from .forms import ProjectForm, ReviewForm
from .recommendations import get_video_recommendations
from .utils import add_black_bars, encode_video
import os
from django.http import JsonResponse
from datetime import datetime
from django.contrib.auth.decorators import login_required
import logging
from .services.video_services import VideoService, UtilityService
from django.core.cache import cache

logger = logging.getLogger(__name__)

def projects(request):
    videos = Video.objects.all().order_by('-created_at')
    paginator = Paginator(videos, 9)  # Show 9 videos per page
    page = request.GET.get('page')
    videos = paginator.get_page(page)
    
    context = {'videos': videos, 'page': 'Projects'}
    return render(request, 'projects/projects.html', context)

def project(request, pk):    
    video_service = VideoService()
    utility_service = UtilityService()
    
    video = video_service.get_video(pk, Video)
    
    # Record view using service with utility service for IP
    video_service.record_view(
        video=video,
        user=request.user if request.user.is_authenticated else None,
        ip_address=utility_service.get_client_ip(request),
        view_history_model=ViewHistory
    )
    
    # Get context using service
    context = video_service.get_video_context(
        video=video,
        get_recommendations_func=get_video_recommendations
    )
    context['form'] = ReviewForm()
    context['reviews'] = video.reviews.all().order_by('-created_at')
    
    return render(request, 'projects/single-project.html', context)

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                project = form.save(commit=False)
                project.uploader = request.user
                
                if 'file' not in request.FILES:
                    raise ValueError("Video file is required")
                    
                project.save()  # This triggers the signal processing
                form.save_m2m()  # Save tags
                
                messages.success(request, 'Project created successfully!')
                return redirect('project', pk=project.id)
                
            except Exception as e:
                logger.error(f"Error creating project: {str(e)}")
                messages.error(request, f'Error creating project: {str(e)}')
                return render(request, 'projects/project_form.html', {'form': form})
    else:
        form = ProjectForm()
    return render(request, 'projects/project_form.html', {'form': form})

def update_project(request, pk):
    project = get_object_or_404(Video, id=pk)
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            try:
                project = form.save()
                messages.success(request, 'Project updated successfully!')
                return redirect('project', pk=project.id)
            except Exception as e:
                messages.error(request, f'Error updating project: {str(e)}')
    else:
        form = ProjectForm(instance=project)
    
    return render(request, 'projects/project_form.html', {'form': form})

def delete_project(request, pk):
    project = get_object_or_404(Video, id=pk)
    if request.method == 'POST':
        try:
            project.delete()
            messages.success(request, 'Video deleted successfully!')
            return redirect('projects')
        except Exception as e:
            messages.error(request, f'Error deleting video: {str(e)}')
            return redirect('project', pk=pk)
    
    return render(request, 'projects/delete_object.html', {
        'object': project.title
    })

@login_required
def add_review(request, pk):
    video = get_object_or_404(Video, id=pk)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.video = video
            review.user = request.user
            review.save()
            
            # Invalidate video context cache
            cache.delete(f'video_context_{pk}')
            
            messages.success(request, 'Review added successfully!')
        else:
            messages.error(request, 'Error adding review')
    
    return redirect('project', pk=pk)

@login_required
def update_review(request, pk):
    review = get_object_or_404(Review, id=pk)
    video_id = review.video.id
    
    # Check if user owns this review
    if review.user != request.user:
        messages.error(request, 'You do not have permission to edit this review')
        return redirect('project', pk=str(video_id))
    
    if request.method == 'POST':
        comment = request.POST.get('comment')
        if comment:
            review.comment = comment
            review.save()
            
            # Invalidate cache
            cache.delete(f'video_context_{video_id}')
            messages.success(request, 'Review updated successfully!')
        else:
            messages.error(request, 'Comment cannot be empty')
    
    return redirect('project', pk=str(video_id))

def delete_review(request, pk):
    review = get_object_or_404(Review, id=pk)
    video_id = review.video.id
    
    if request.method == 'POST':
        try:
            review.delete()
            messages.success(request, 'Comment deleted successfully!')
            return redirect('project', pk=str(video_id))
        except Exception as e:
            messages.error(request, f'Error deleting comment: {str(e)}')
            return redirect('project', pk=str(video_id))
    
    return redirect('project', pk=str(video_id))

def debug_videos(request):
    videos = Video.objects.all()
    debug_info = []
    
    for video in videos:
        # Database info
        video_info = {
            'id': str(video.id),
            'title': video.title,
            'file_path': str(video.file),
            'thumbnail_path': str(video.thumbnail),
            'encoded_versions': video.encoded_versions,
        }
        
        # Check if files actually exist
        if video.file:
            full_path = os.path.join(settings.MEDIA_ROOT, str(video.file))
            video_info['file_exists'] = os.path.exists(full_path)
            
        if video.thumbnail:
            thumb_path = os.path.join(settings.MEDIA_ROOT, str(video.thumbnail))
            video_info['thumbnail_exists'] = os.path.exists(thumb_path)
            
        # Check encoded versions
        if video.encoded_versions:
            existing_versions = {}
            for quality, filename in video.encoded_versions.items():
                version_path = os.path.join(settings.MEDIA_ROOT, 'videos', filename)
                existing_versions[quality] = os.path.exists(version_path)
            video_info['encoded_versions_exist'] = existing_versions
            
        debug_info.append(video_info)
    
    return JsonResponse({'videos': debug_info})
