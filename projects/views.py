from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from .models import Video, Review, Playlist, ViewHistory
from .forms import ProjectForm, ReviewForm
from .recommendations import get_video_recommendations
from .utils import add_black_bars, encode_video
import os
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
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
import re
from django.db import transaction
import hashlib

logger = logging.getLogger(__name__)

def projects(request):
    videos = Video.objects.all().order_by('-created_at')
    paginator = Paginator(videos, 9)  # Show 9 videos per page
    page = request.GET.get('page')
    paged_videos = paginator.get_page(page)
    
    # Add counts to each video object
    for video in paged_videos:
        video.likes_count = VideoService.get_likes_count(video)
        video.dislikes_count = VideoService.get_dislikes_count(video)
    
    context = {
        'videos': paged_videos, 
        'page': 'Projects',
        'video_service': VideoService
    }
    return render(request, 'projects/projects.html', context)

def project(request, pk):    
    video_service = VideoService()
    video = video_service.get_video(pk, Video)
    
    # Get video context including recommendations
    context = video_service.get_video_context(video, get_video_recommendations)
    
    # Add video URL to context
    context['video_url'] = ModelService.get_video_url(video)
    
    # Record view if not cached
    if request.user.is_authenticated:
        video_service.record_view(video, request.user, None, ViewHistory)
    else:
        ip_address = UtilityService.get_client_ip(request)
        video_service.record_view(video, None, ip_address, ViewHistory)
    
    # Add likes/dislikes counts
    context['likes_count'] = video_service.get_likes_count(video)
    context['dislikes_count'] = video_service.get_dislikes_count(video)
    
    return render(request, 'projects/single-project.html', context)

def file_iterator(file_path, start=0, length=None, chunk_size=8192):
    with open(file_path, 'rb') as f:
        f.seek(start)
        remaining = length if length is not None else None
        while True:
            bytes_length = chunk_size if remaining is None else min(remaining, chunk_size)
            data = f.read(bytes_length)
            if not data:
                break
            if remaining is not None:
                remaining -= len(data)
                if remaining < 0:
                    data = data[:remaining]
            yield data
            if remaining is not None and remaining <= 0:
                break

@login_required(login_url="login-page")
def create_project(request):
    if request.method == 'POST':
        # Generate a unique key for this submission
        form_data = str(request.POST) + str(request.FILES)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        cache_key = f'submission_{submission_hash}'

        # Check if this exact submission was recently processed
        if cache.get(cache_key):
            messages.warning(request, 'This form was already submitted.')
            return redirect('projects')

        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Set cache to prevent duplicate submission
                    cache.set(cache_key, True, 300)  # Cache for 5 minutes

                    project = form.save(commit=False)
                    project.uploader = request.user
                    
                    if 'file' not in request.FILES:
                        raise ValueError("Video file is required")
                        
                    project.save()
                    form.save_m2m()
                    
                    messages.success(request, 'Project created successfully!')
                    return redirect('project', pk=project.id)
                    
            except Exception as e:
                logger.error(f"Error creating project: {str(e)}")
                # Clear the cache in case of error
                cache.delete(cache_key)
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

def stream_video(request, pk):
    video = get_object_or_404(Video, id=pk)
    
    # Get the actual file path from encoded versions or fallback to original
    if video.encoded_versions and '720p' in video.encoded_versions:
        file_path = os.path.join(settings.MEDIA_ROOT, 'videos', video.encoded_versions['720p'])
    else:
        file_path = video.file.path
        
    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"Video file not found: {file_path}")
        return HttpResponse("Video file not found", status=404)
    
    # Get file size
    file_size = os.path.getsize(file_path)
    
    # Handle range requests
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        length = end - start + 1
        
        response = StreamingHttpResponse(
            file_iterator(file_path, start=start, length=length),
            status=206,
            content_type='video/mp4'
        )
        
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = str(length)
        return response
    
    response = StreamingHttpResponse(
        file_iterator(file_path),
        content_type='video/mp4'
    )
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(file_size)
    return response
