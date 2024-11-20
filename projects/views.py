from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from .models import Video, Review, Playlist, ViewHistory
from .forms import ProjectForm, ReviewForm
from .recommendations import get_video_recommendations
from .utils import add_black_bars, encode_video
import os
from django.http import JsonResponse, StreamingHttpResponse
from datetime import datetime
from django.contrib.auth.decorators import login_required
import logging
from .services.video_services import VideoService, UtilityService
from .services.media_servies import ModelService
from django.core.cache import cache
import json
import time
from django.db.models import Q
from django.utils import timezone
import uuid

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
    
    # Make sure video_url is included in context
    context.update({
        'likes_count': VideoService.get_likes_count(video),
        'dislikes_count': VideoService.get_dislikes_count(video),
        'video_url': ModelService.get_video_url(video),
        'form': ReviewForm(),
        'reviews': video.reviews.all().order_by('-created_at')
    })
    
    return render(request, 'projects/single-project.html', context)

@login_required(login_url="login-page")
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

@login_required(login_url="login-page")
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

@login_required(login_url="login-page")
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

@login_required(login_url="login-page")
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
            
            # Return JSON response
            return JsonResponse({
                'success': True,
                'comment': {
                    'id': str(review.id),
                    'username': review.user.username,
                    'comment': review.comment,
                    'is_owner': True,
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid form data'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required(login_url="login-page")
def update_review(request, pk):
    review = get_object_or_404(Review, id=pk)
    
    if request.method == 'POST':
        comment = request.POST.get('comment')
        if comment:
            review.comment = comment
            review.save()
            
            # Invalidate cache
            cache.delete(f'video_context_{review.video.id}')
            
            return JsonResponse({
                'success': True,
                'comment': {
                    'id': str(review.id),
                    'username': review.user.username,
                    'comment': comment,
                    'is_owner': True,
                }
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required(login_url="login-page")
def delete_review(request, pk):
    review = get_object_or_404(Review, id=pk)
    video_id = review.video.id  # Get video ID before deletion
    
    if request.method == 'POST':
        try:
            review.delete()
            # Invalidate cache
            cache.delete(f'video_context_{video_id}')
            return JsonResponse({
                'success': True,
                'message': 'Comment deleted successfully!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

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

def comments_stream(request, video_id):
    last_id = request.GET.get('last_id')
    
    try:
        video = get_object_or_404(Video, id=video_id)
        comments = Review.objects.filter(video=video)
        
        if last_id and last_id != 'null' and last_id != '':
            try:
                last_id_uuid = uuid.UUID(last_id)
                comments = comments.filter(id__gt=last_id_uuid)
            except ValueError:
                # Handle invalid UUID gracefully
                pass
        
        comments = comments.order_by('-created_at')[:10]
        
        data = []
        for comment in comments:
            data.append({
                'id': str(comment.id),
                'username': comment.user.username,
                'comment': comment.comment,
                'is_owner': comment.user == request.user
            })
        
        return StreamingHttpResponse(
            f"data: {json.dumps(data)}\n\n",
            content_type='text/event-stream'
        )
    except Exception as e:
        logger.error(f"Error in comment stream: {str(e)}")
        return StreamingHttpResponse(
            "data: []\n\n",
            content_type='text/event-stream'
        )
