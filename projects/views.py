from django.shortcuts import render, get_object_or_404,redirect
from django.http import HttpResponse
from .models import Video, Review, Playlist
from .forms import ProjectForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

def projects(request):
    videos = Video.objects.all()
    context = {'videos': videos, 'page': 'Projects'}
    return render(request, 'projects/projects.html', context)


def project(request, pk):    
    # Use get_object_or_404 instead of .get()
    video = get_object_or_404(Video, id=pk)
    print(f"Video file: {video.file}")  # Debug print
    print(f"Video file URL: {video.file.url}")  # Debug print
    print(f"Video file path: {video.file.path}")
    # Get all related data
    tags = video.tags.all()
    reviews = video.review_set.all().order_by('-created_at')
    
    context = {
        'video': video,
        'reviews': reviews,
        'tags': tags,
        'MEDIA_URL': settings.MEDIA_URL,
    }
    return render(request, 'projects/single-project.html', context)


def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                video = form.save()
                messages.success(request, 'Video uploaded successfully!')
                return redirect('project', pk=video.id)
            except Exception as e:
                messages.error(request, f'Error saving video: {str(e)}')
    else:
        form = ProjectForm()
    
    return render(request, 'projects/project_form.html', {'form': form})

def update_project(request, pk):
    project = Video.objects.get(id=pk)
    form = ProjectForm(instance=project)
    if request.method == 'POST':
        # Pass both the instance and the POST/FILES data
        form = ProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            try:
                project = form.save()
                print("Project updated successfully:", project)  # Debug print
                return redirect('projects')
            except Exception as e:
                print("Error updating project:", str(e))  # Debug print
        else:
            print("Form errors:", form.errors)  # Debug print
    context = {'form': form}
    return render(request, 'projects/project_form.html', context)

def delete_project(request,pk):
    project = Video.objects.get(id=pk)
    if request.method == 'POST':
        project.delete()
        return redirect('projects')
    context ={'object':project}
    return render(request,'projects/delete_object.html',context)

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


# Create your views here.
 