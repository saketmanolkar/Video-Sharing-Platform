from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from .models import Video, Review, Playlist
from .forms import ProjectForm
from .recommendations import get_video_recommendations
from django.core.cache import cache

def projects(request):
    videos = Video.objects.all()
    context = {'videos': videos, 'page': 'Projects'}
    return render(request, 'projects/projects.html', context)

def project(request, pk):    
    video = get_object_or_404(Video, id=pk)
    video.views += 1
    video.save()
    
    tags = video.tags.all()
    reviews = video.review_set.all().order_by('-created_at')
    recommended_videos = get_video_recommendations(video)
    
    context = {
        'video': video,
        'reviews': reviews,
        'tags': tags,
        'MEDIA_URL': settings.MEDIA_URL,
        'recommended_videos': recommended_videos
    }
    return render(request, 'projects/single-project.html', context)

def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            video = form.save()
            return redirect('project', pk=video.id)
    else:
        form = ProjectForm()
    return render(request, 'projects/project_form.html', {'form': form})

def update_project(request, pk):
    project = Video.objects.get(id=pk)
    form = ProjectForm(instance=project)
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            project = form.save()
            return redirect('projects')
    context = {'form': form}
    return render(request, 'projects/project_form.html', context)

def delete_project(request, pk):
    project = Video.objects.get(id=pk)
    if request.method == 'POST':
        project.delete()
        return redirect('projects')
    context = {'object': project}
    return render(request, 'projects/delete_object.html', context)

def add_review(request, pk):
    video = get_object_or_404(Video, id=pk)
    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        print(f"Received comment: {comment}")  # Debug print
        
        if comment:
            try:
                review = Review.objects.create(
                    video=video,
                    comment=comment
                )
                print(f"Created review: {review.id}")  # Debug print
                return redirect('project', pk=str(pk))
            except Exception as e:
                print(f"Error creating review: {str(e)}")  # Debug print
        else:
            print("Comment was empty")  # Debug print
            
    return redirect('project', pk=str(pk))

def update_review(request, pk):
    review = get_object_or_404(Review, id=pk)
    video = review.video
    
    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        if comment:
            try:
                review.comment = comment
                review.save()
                print("Review updated successfully:", review)
                return redirect('project', pk=str(video.id))
            except Exception as e:
                print("Error updating review:", str(e))
        else:
            print("Error: Comment field is empty")
    
    context = {
        'review': review,
        'video': video
    }
    return render(request, 'projects/update_review_form.html', context)

def delete_review(request, pk):
    review = get_object_or_404(Review, id=pk)
    video = review.video  # Store the video before deleting the review
    if request.method == 'POST':
        review.delete()
        return redirect('project', pk=video.id)
    context = {'object': review}
    return render(request, 'projects/delete_object.html', context)

def upload_project(request):
    if request.method == 'POST':
        # ... your existing form handling code ...
        
        if 'thumbnail' in request.FILES:
            thumbnail = request.FILES['thumbnail']
            
            # Open image using PIL
            img = Image.open(thumbnail)
            
            # Add letterbox if needed
            processed_img = add_letterbox(img)
            
            # Save processed image to memory
            output = io.BytesIO()
            processed_img.save(output, format='JPEG', quality=85)
            output.seek(0)
            
            # Create new file object
            processed_thumbnail = InMemoryUploadedFile(
                output,
                'ImageField',
                f"{thumbnail.name.split('.')[0]}_processed.jpg",
                'image/jpeg',
                output.getbuffer().nbytes,
                None
            )
            
            # Save to model
            project.thumbnail = processed_thumbnail
            project.save()
            
        return redirect('projects')

# Create your views here.
cache.clear()
 