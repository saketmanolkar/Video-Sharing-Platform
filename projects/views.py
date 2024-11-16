from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from .models import Video, Review, Playlist
from .forms import ProjectForm, ReviewForm
from .recommendations import get_video_recommendations
from .utils import add_black_bars, encode_video, cleanup_media_files
import os
from django.http import JsonResponse
from datetime import datetime

def projects(request):
    videos = Video.objects.all().order_by('-created_at')
    paginator = Paginator(videos, 9)  # Show 9 videos per page
    page = request.GET.get('page')
    videos = paginator.get_page(page)
    
    context = {'videos': videos, 'page': 'Projects'}
    return render(request, 'projects/projects.html', context)

def project(request, pk):    
    video = get_object_or_404(Video, id=pk)
    video.views += 1
    video.save()
    
    context = {
        'video': video,
        'reviews': video.review_set.all().order_by('-created_at'),
        'tags': video.tags.all(),
        'MEDIA_URL': settings.MEDIA_URL,
        'recommended_videos': get_video_recommendations(video),
        'form': ReviewForm()
    }
    return render(request, 'projects/single-project.html', context)

def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        print("Files received:", request.FILES)  # Debug line
        if form.is_valid():
            try:
                project = form.save(commit=False)
                
                # Process video if provided
                if 'file' in request.FILES:
                    video_file = request.FILES['file']
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_name = f"{os.path.splitext(video_file.name)[0]}_{timestamp}"
                    input_path = os.path.join(settings.MEDIA_ROOT, 'videos', f"{unique_name}_original.mp4")
                    
                    # Save original temporarily
                    with open(input_path, 'wb+') as destination:
                        for chunk in video_file.chunks():
                            destination.write(chunk)
                    
                    # Encode video in different qualities
                    encoded_versions = {}
                    encoding_success = False
                    
                    for quality in ['1280x720', '640x360']:
                        output_name = f"{unique_name}_{quality.split('x')[1]}p.mp4"
                        output_path = os.path.join(settings.MEDIA_ROOT, 'videos', output_name)
                        encoded_file = encode_video(input_path, output_path, quality)
                        if encoded_file:
                            quality_key = f"{quality.split('x')[1]}p"
                            encoded_versions[quality_key] = encoded_file
                            encoding_success = True
                    
                    # Only proceed if encoding was successful
                    if encoding_success:
                        # Set the main video file to 720p version
                        if '720p' in encoded_versions:
                            project.file = f"videos/{encoded_versions['720p']}"
                        
                        # Save encoded versions info
                        project.encoded_versions = encoded_versions
                        project.save()
                        form.save_m2m()  # Save the tags
                        
                        # Cleanup original
                        if os.path.exists(input_path):
                            os.remove(input_path)
                            print(f"Deleted original file: {input_path}")
                        
                        messages.success(request, 'Project created successfully!')
                        return redirect('project', pk=project.id)
                    else:
                        raise Exception("Video encoding failed")
                else:
                    project.save()
                    form.save_m2m()  # Save the tags
                    messages.success(request, 'Project created successfully!')
                    return redirect('project', pk=project.id)
                    
            except Exception as e:
                messages.error(request, f'Error creating project: {str(e)}')
                return render(request, 'projects/project_form.html', {'form': form})
        else:
            print("Form errors:", form.errors)  # Debug line
            messages.error(request, 'Please correct the errors below.')
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

def add_review(request, pk):
    video = get_object_or_404(Video, id=pk)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.video = video
            review.save()
            messages.success(request, 'Review added successfully!')
            return redirect('project', pk=str(pk))
    else:
        form = ReviewForm()
    
    return render(request, 'projects/review_form.html', {
        'form': form,
        'video': video
    })

def update_review(request, pk):
    review = get_object_or_404(Review, id=pk)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Review updated successfully!')
            except Exception as e:
                messages.error(request, f'Error updating review: {str(e)}')
        else:
            messages.error(request, 'Invalid form data')
    
    return redirect('project', pk=str(review.video.id))

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
 