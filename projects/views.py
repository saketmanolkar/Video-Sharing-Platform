from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Video, Review, Playlist, ViewHistory, PlaylistItem
from .forms import ProjectForm, ReviewForm, MovieRecommendationForm, CreatePlaylistForm
from .recommendations import get_video_recommendations
import os
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from datetime import datetime
from django.contrib.auth.decorators import login_required
import logging
from .services.video_services import VideoService, UtilityService
from .services.media_servies import ModelService
from django.core.cache import cache
import json
import uuid
import re
from django.db import transaction
import hashlib
from .fun_corner.movie_recs import create_optimized_clusters, get_optimized_recommendations
import pandas as pd
from pathlib import Path
from .fun_corner.hollywood_analytics import get_current_movies_data
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from users.models import Profile  # Import Profile model
from .services.cache_service import ProjectsCacheService, FormSubmissionCache
from users.services.follow_services import FollowService

logger = logging.getLogger(__name__)

def projects(request):
    # If user is authenticated, prefetch their profile
    if request.user.is_authenticated:
        request.user = User.objects.select_related('profile').get(id=request.user.id)
    
    search_query = request.GET.get('search', '')
    videos = VideoService.search_videos(search_query)
    
    paged_videos, custom_range = VideoService.get_paginated_videos(
        videos, 
        request.GET.get('page', 1)
    )
    
    context = {
        'videos': paged_videos, 
        'page': 'Projects',
        'video_service': VideoService,
        'search_query': search_query,
        'custom_range': custom_range
    }
    
    return render(request, 'projects/projects.html', context)

@login_required(login_url="login-page")
def project(request, pk):    
    video_service = VideoService()
    
    # Fetch the video with related fields to reduce future queries
    video = video_service.get_video(
        pk, 
        Video, 
        select_related_fields=['uploader', 'uploader__profile']
    )
    
    # Pre-compute profile-related values to avoid template queries
    if video and hasattr(video, 'uploader') and hasattr(video.uploader, 'profile'):
        # Store these values directly to avoid nested lookups in templates
        context = {
            'uploader_profile_id': video.uploader.profile.id,
            'uploader_username': video.uploader.profile.username,
        }
    else:
        context = {
            'uploader_profile_id': None,
            'uploader_username': 'Unknown',
        }
    
    # Get video context (includes cached static data + fresh dynamic data)
    video_context = video_service.get_video_context(video, get_video_recommendations)
    context.update(video_context)  # Merge with our pre-computed values
    
    # Add video URL to context
    context['video_url'] = ModelService.get_video_url(video)
    
    # Pre-compute all user-related flags
    context['is_authenticated'] = request.user.is_authenticated
    context['user_id'] = request.user.id if request.user.is_authenticated else None
    context['user_username'] = request.user.username if request.user.is_authenticated else ""
    
    # Pre-compute the comparison between request.user and video.uploader
    context['is_uploader'] = (request.user.id == video.uploader.id) if request.user.is_authenticated else False
    context['is_not_uploader'] = (request.user.id != video.uploader.id) if request.user.is_authenticated else False
    
    # Record view if not cached
    ip_address = UtilityService.get_client_ip(request)
    if request.user.is_authenticated:
        view_history = video_service.record_view(video, request.user, ip_address, ViewHistory)
        context['view_history'] = view_history  # Add to context
        # Add fresh following status for authenticated users
        follow_service = FollowService()
        context['is_following'] = follow_service.check_following_status(request.user, video.uploader)
        # Add fresh like status for authenticated users
        user_like = video_service.get_user_like_status(video, request.user)
        print(f"\n👍 Checking like status for user {request.user.username} on video {pk}")
        print(f"Like status: {user_like}")
        context['user_like'] = user_like
    else:
        view_history = video_service.record_view(video, None, ip_address, ViewHistory)
        context['view_history'] = view_history  # Add to context
        context['is_following'] = False
        context['user_like'] = None
    
    # Add fresh likes/dislikes counts
    context['likes_count'] = video_service.get_likes_count_optimized(video)
    context['dislikes_count'] = video_service.get_dislikes_count_optimized(video)
    
    return render(request, 'projects/single_project.html', context)

@login_required(login_url="login-page")
def create_project(request):
    if request.method == 'POST':
        # Generate a unique key for this submission
        form_data = str(request.POST) + str(request.FILES)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        # Use the new cache service
        form_cache = FormSubmissionCache()

        # Check if this exact submission was recently processed
        if form_cache.check_submission(submission_hash):
            messages.warning(request, 'This form was already submitted.')
            return redirect('projects')

        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Set cache to prevent duplicate submission
                    form_cache.set_submission(submission_hash)

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
                form_cache.clear_submission(submission_hash)
                messages.error(request, f'Error creating project: {str(e)}')
                return render(request, 'projects/project_form.html', {'form': form})
    else:
        form = ProjectForm()
    return render(request, 'projects/project_form.html', {
        'form': form,
        'page_type': 'create'
    })

@login_required(login_url="login-page")
def update_project(request, pk):
    project = get_object_or_404(Video, id=pk)
    
    if project.uploader != request.user:
        messages.error(request, "You don't have permission to edit this project.")
        return redirect('project', pk=project.id)
    
    if request.method == 'POST':
        # Generate a unique key for this update submission
        form_data = str(request.POST) + str(request.FILES)
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        # Use the form cache service
        form_cache = FormSubmissionCache()

        # Check if this exact update was recently processed
        if form_cache.check_submission(submission_hash):
            messages.warning(request, 'This update was already submitted.')
            return redirect('project', pk=project.id)

        try:
            with transaction.atomic():
                form = ProjectForm(request.POST, request.FILES, instance=project)
                if form.is_valid():
                    # Set cache to prevent duplicate submission
                    form_cache.set_submission(submission_hash)
                    
                    project = form.save(commit=False)
                    
                    print("\n🎥 View Debug:")
                    print(f"File in request: {'file' in request.FILES}")
                    
                    if 'file' in request.FILES:
                        project._file_changed = True
                        project._original_file = project.file
                        print("✅ File change detected")
                    
                    if 'file' in request.FILES:
                        from .tasks import process_video_task
                        task = process_video_task.delay(str(project.id))
                        print(f"🎯 Queued task: {task.id}")
                        
                    project.save()
                    form.save_m2m()
                    
                    # Invalidate caches
                    VideoService.invalidate_video_cache(project.id)
                    cache.delete(f'video_context_{project.id}')
                    
                    messages.success(request, 'Project updated successfully!')
                    return redirect('creator-studio', pk=request.user.profile.id)
                    
        except Exception as e:
            # Clear the cache in case of error
            form_cache.clear_submission(submission_hash)
            messages.error(request, f'Error updating project: {str(e)}')
            print(f"❌ Error: {str(e)}")
    else:
        form = ProjectForm(instance=project)
    
    return render(request, 'projects/project_form.html', {
        'form': form,
        'page_type': 'update',
        'project': project
    })

@login_required(login_url="login-page")
def delete_project(request, pk):
    project = get_object_or_404(Video, id=pk)
    
    # Check if the logged-in user is the project owner
    if project.uploader != request.user:
        messages.error(request, "You don't have permission to delete this project.")
        return redirect('project', pk=project.id)
    
    if request.method == 'POST':
        try:
            project.delete()
            messages.success(request, 'Video deleted successfully!')
            return redirect('creator-studio', pk=request.user.profile.id)
        except Exception as e:
            messages.error(request, f'Error deleting video: {str(e)}')
            return redirect('project', pk=pk)
    
    return render(request, 'delete_object.html', {
        'object': project.title
    })


def fun_corner(request):
    # Initialize form and recommendations
    movie_form = MovieRecommendationForm(request.POST if request.method == 'POST' else None)
    recommendations = None
    
    # Only process recommendations on POST
    if request.method == 'POST' and movie_form.is_valid():
        try:
            # Get cached model data
            model_data = ProjectsCacheService.get_movie_recs_model()
            if model_data is None:
                raise Exception("Failed to load recommendation model")
            
            query = {
                'media_type': movie_form.cleaned_data['media_type'],
                'genres': movie_form.cleaned_data['genres'],
                'language': movie_form.cleaned_data['language'],
                'time_period': movie_form.cleaned_data['time_period']
            }
            
            # Use cached model for recommendations
            from .fun_corner.movie_recs import get_optimized_recommendations
            recommendations, metrics = get_optimized_recommendations(
                model_data['df_clustered'],
                model_data['X'],
                query
            )
            
        except Exception as e:
            print(f"Error getting recommendations: {str(e)}")
            recommendations = None

    # Only get box office and movies data if they're not in the session
    box_office_data = request.session.get('box_office_data')
    current_movies_data = request.session.get('current_movies_data')
    
    if box_office_data is None:
        box_office_data = ProjectsCacheService.get_studio_data()
        request.session['box_office_data'] = box_office_data
        
    if current_movies_data is None:
        current_movies_data = ProjectsCacheService.get_current_movies()
        request.session['current_movies_data'] = current_movies_data

    context = {
        'movie_form': movie_form,
        'recommendations': recommendations,
        'box_office_data': json.dumps(box_office_data),
        'current_movies_data': json.dumps(current_movies_data)
    }
    
    return render(request, 'projects/fun_corner.html', context)

def movie_recommendation(request):
    form = MovieRecommendationForm()
    return render(request, 'projects/movie_rec.html', {'form': form})

@login_required
def create_playlist(request, pk):
    profile = get_object_or_404(Profile, id=pk)
    
    if request.user != profile.user:
        return HttpResponseForbidden("You can only create playlists on your own profile")
    
    if request.method == 'POST':
        # Generate unique key for this playlist submission
        form_data = str(request.POST)  # Include selected videos in hash
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        # Use the form cache service
        form_cache = FormSubmissionCache()

        # Check if this exact playlist was recently submitted
        if form_cache.check_submission(submission_hash):
            messages.warning(request, 'This playlist was already submitted.')
            return redirect('profile', pk=pk)

        form = CreatePlaylistForm(request.POST)
        video_ids = request.POST.getlist('videos')
        
        if not video_ids:
            messages.error(request, 'Please select at least one video for your playlist.')
            videos = Video.objects.all()
            return render(request, 'projects/playlist_form.html', {'form': form, 'videos': videos})
            
        if form.is_valid():
            try:
                # Set cache to prevent duplicate submission
                form_cache.set_submission(submission_hash)

                playlist = form.save(commit=False)
                playlist.user = request.user
                playlist.save()
                
                # Create PlaylistItems for selected videos
                for position, video_id in enumerate(video_ids, 1):
                    video = Video.objects.get(id=video_id)
                    PlaylistItem.objects.create(
                        playlist=playlist,
                        video=video,
                        position=position
                    )
                
                # Set thumbnail from first video
                first_video = Video.objects.get(id=video_ids[0])
                if first_video.thumbnail:
                    playlist.thumbnail = first_video.thumbnail
                    playlist.save()
                    messages.success(request, 'Playlist created successfully!')
                
                return redirect('profile', pk=pk)
                
            except Exception as e:
                # Clear cache if something goes wrong
                form_cache.clear_submission(submission_hash)
                messages.error(request, f'Error creating playlist: {str(e)}')
                videos = Video.objects.all()
                return render(request, 'projects/playlist_form.html', {'form': form, 'videos': videos})
    else:
        form = CreatePlaylistForm()
    
    videos = Video.objects.all()
    context = {
        'form': form,
        'videos': videos
    }
    return render(request, 'projects/playlist_form.html', context)

@login_required
def update_playlist(request, pk):
    playlist = get_object_or_404(Playlist, id=pk)
    
    # Check if user owns this playlist
    if request.user != playlist.user:
        return HttpResponseForbidden("You can only edit your own playlists")
    
    if request.method == 'POST':
        # Generate unique key for this update submission
        form_data = str(request.POST)  # Includes selected videos
        submission_hash = hashlib.md5(form_data.encode()).hexdigest()
        
        # Use the form cache service
        form_cache = FormSubmissionCache()

        # Check if this exact update was recently submitted
        if form_cache.check_submission(submission_hash):
            messages.warning(request, 'This update was already submitted.')
            return redirect('profile', pk=playlist.user.profile.id)

        form = CreatePlaylistForm(request.POST, instance=playlist)
        video_ids = request.POST.getlist('videos')
        
        if not video_ids:
            messages.error(request, 'Please select at least one video for your playlist.')
            videos = Video.objects.all()
            return render(request, 'projects/playlist_form.html', {
                'form': form, 
                'videos': videos,
                'playlist': playlist,
                'selected_videos': [int(vid) for vid in video_ids]
            })
            
        if form.is_valid():
            try:
                # Set cache to prevent duplicate submission
                form_cache.set_submission(submission_hash)

                playlist = form.save()
                
                # Clear existing playlist items
                playlist.items.all().delete()
                
                # Create new PlaylistItems for selected videos
                for position, video_id in enumerate(video_ids, 1):
                    video = Video.objects.get(id=video_id)
                    PlaylistItem.objects.create(
                        playlist=playlist,
                        video=video,
                        position=position
                    )
                
                # Update thumbnail from first video
                first_video = Video.objects.get(id=video_ids[0])
                if first_video.thumbnail:
                    playlist.thumbnail = first_video.thumbnail
                    playlist.save()
                    messages.success(request, 'Playlist updated successfully!')
                return redirect('profile', pk=playlist.user.profile.id)
                
            except Exception as e:
                # Clear cache if something goes wrong
                form_cache.clear_submission(submission_hash)
                messages.error(request, f'Error updating playlist: {str(e)}')
                videos = Video.objects.all()
                return render(request, 'projects/playlist_form.html', {
                    'form': form,
                    'videos': videos,
                    'playlist': playlist,
                    'selected_videos': [int(vid) for vid in video_ids]
                })
    else:
        form = CreatePlaylistForm(instance=playlist)
        
    videos = Video.objects.all()
    selected_videos = list(playlist.items.values_list('video_id', flat=True))
    
    context = {
        'form': form,
        'videos': videos,
        'playlist': playlist,
        'selected_videos': selected_videos,
    }
    return render(request, 'projects/playlist_form.html', context)

@login_required(login_url="login-page")
def delete_playlist(request, pk):
    playlist = get_object_or_404(Playlist, id=pk)
    
    # Check if the logged-in user is the playlist owner
    if playlist.user != request.user:
        messages.error(request, "You don't have permission to delete this playlist.")
        return redirect('profile', pk=request.user.profile.id)
    
    if request.method == 'POST':
        try:
            playlist.delete()
            messages.success(request, 'Playlist deleted successfully!')
            return redirect('profile', pk=request.user.profile.id)
        except Exception as e:
            messages.error(request, f'Error deleting playlist: {str(e)}')
            return redirect('profile', pk=request.user.profile.id)
    
    return render(request, 'delete_object.html', {
        'object': playlist.name
    })

def video_status(request, video_id):
    video = get_object_or_404(Video, id=video_id)
    return JsonResponse({
        'encoded': bool(video.encoded_versions),
        'status': video.processing_status
    })