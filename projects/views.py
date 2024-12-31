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
from .fun_corner.hollywood_analytics import get_major_studios_data, get_current_movies_data
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden
from users.models import Profile  # Import Profile model

logger = logging.getLogger(__name__)

def projects(request):
    search_query = request.GET.get('search', '')
    videos = VideoService.search_videos(search_query)
    
    paged_videos, custom_range = VideoService.get_paginated_videos(
        videos, 
        request.GET.get('page', 1)
    )
    
    for video in paged_videos:
        video.likes_count = VideoService.get_likes_count(video)
        video.dislikes_count = VideoService.get_dislikes_count(video)
    
    context = {
        'videos': paged_videos, 
        'page': 'Projects',
        'video_service': VideoService,
        'search_query': search_query,
        'custom_range': custom_range
    }
    
    return render(request, 'projects/projects.html', context)

def project(request, pk):    
    video_service = VideoService()
    video = video_service.get_video(pk, Video)
    
    # Add the user to the video object before getting context
    video.request_user = request.user
    
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
    
    return render(request, 'projects/single_project.html', context)

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
        try:
            with transaction.atomic():
                form = ProjectForm(request.POST, request.FILES, instance=project)
                if form.is_valid():
                    project = form.save(commit=False)
                    
                    print("\n🎥 View Debug:")
                    print(f"File in request: {'file' in request.FILES}")
                    
                    if 'file' in request.FILES:
                        project._file_changed = True
                        project._original_file = project.file
                        print("✅ File change detected")
                    
                    if 'file' in request.FILES:
                        # Clear any existing encoding cache
                        cache.delete(f'encoding_{project.id}')
                        
                        from .tasks import process_video_task
                        task = process_video_task.delay(str(project.id))
                        print(f"🎯 Queued task: {task.id}")
                        
                        # Set new cache
                        cache.set(f'encoding_{project.id}', True, timeout=60)  # Reduced timeout
                    
                    project.save()
                    form.save_m2m()
                    
                    # Invalidate caches
                    VideoService.invalidate_video_cache(project.id)
                    cache.delete(f'video_context_{project.id}')
                    
                    messages.success(request, 'Project updated successfully!')
                    return redirect('creator-studio', pk=request.user.profile.id)
                    
        except Exception as e:
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
            return redirect('projects')
        except Exception as e:
            messages.error(request, f'Error deleting video: {str(e)}')
            return redirect('project', pk=pk)
    
    return render(request, 'delete_object.html', {
        'object': project.title
    })


def fun_corner(request):
    # Keep all existing movie recommendation code unchanged
    if request.method == 'POST':
        movie_form = MovieRecommendationForm(request.POST)
        if movie_form.is_valid():
            # Print form data
            print("\nMovie Recommendation Form Data:")
            print(f"Media Type: {movie_form.cleaned_data['media_type']}")
            print(f"Genres: {movie_form.cleaned_data['genres']}")
            print(f"Time Period: {movie_form.cleaned_data['time_period']}")
            print(f"Language: {movie_form.cleaned_data['language']}")
            
            # Get the correct path to CSV
            csv_path = os.path.join(os.path.dirname(__file__), 'fun_corner', 'data', 'tmdb_all_media.csv')
            df = pd.read_csv(csv_path)
            
            query = {
                'media_type': movie_form.cleaned_data['media_type'],
                'genres': movie_form.cleaned_data['genres'],
                'language': movie_form.cleaned_data['language'],
                'time_period': movie_form.cleaned_data['time_period']
            }
            
            df_clustered, X, kmeans = create_optimized_clusters(df)
            recommendations, metrics = get_optimized_recommendations(df_clustered, X, query)
            
            if isinstance(recommendations, pd.DataFrame):
                recommendations = recommendations.to_dict('records')
    else:
        movie_form = MovieRecommendationForm()
    
    # Get the data for both charts
    box_office_data = get_major_studios_data()
    current_movies_data = get_current_movies_data()
    
    context = {
        'movie_form': movie_form,
        'recommendations': recommendations if 'recommendations' in locals() else None,
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
        form = CreatePlaylistForm(request.POST)
        video_ids = request.POST.getlist('videos')
        
        if not video_ids:
            messages.error(request, 'Please select at least one video for your playlist.')
            videos = Video.objects.all()
            return render(request, 'projects/playlist_form.html', {'form': form, 'videos': videos})
            
        if form.is_valid():
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
            
            return redirect('profile', pk=pk)
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
            
            return redirect('profile', pk=playlist.user.profile.id)
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