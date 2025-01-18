from django.http import JsonResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes, authentication_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from .serializers import VideoSerializer, LikeSerializer, ReviewSerializer
from projects.models import Video, Like, Review
from rest_framework import status
from projects.services.video_services import VideoService
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.shortcuts import get_object_or_404
from django.core.cache import cache
import json, uuid
from rest_framework.renderers import BaseRenderer, JSONRenderer
import time
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth.models import User
from django.views.decorators.http import require_GET
from django.contrib.auth import authenticate
import logging
from users.services.follow_services import FollowService
from users.models import Profile
import os
import re
from django.conf import settings
from users.services.cache_service import SessionActivityCache
from django.views.decorators.http import require_http_methods
from datetime import timedelta

logger = logging.getLogger(__name__)

class EventStreamRenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'text-stream'
    charset = 'utf-8'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        return f"data: {json.dumps(data)}\n\n"

@api_view(['GET'])
def getRoutes(request):
    routes = [
        # Projects
        {'GET': '/api/projects/'},
        {'GET': '/api/projects/id/'},

        # Stream Video
        {'GET': '/api/projects/id/stream/'},

        # Debug Videos
        {'GET': '/api/debug-videos/'},

        # Likes
        {'GET, POST': '/api/projects/id/like/'},
        
        # Reviews/Comments
        {'GET, POST': '/api/projects/id/reviews/'},
        {'GET': '/api/projects/id/reviews/stream/'},
        {'PUT, DELETE': '/api/projects/id/reviews/review_id/'},
        
        # Follow
        {'POST': '/api/users/id/follow/'},
        
        # Authentication
        {'POST': '/api/users/token/'},
        {'POST': '/api/users/token/refresh/'},
        {'GET': '/api/users/token-from-session/'},
    ]
    
    return Response(routes)

@api_view(['GET'])
def getProjects(request):
    try:
        projects = Video.objects.all()
        print(f"Found {projects.count()} videos")
        serializer = VideoSerializer(projects, many=True)
        print("Serialization successful")
        return Response(serializer.data)
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
def getProject(request, pk):
    try:
        project = Video.objects.get(id=pk)
        serializer = VideoSerializer(project, many=False)
        return Response(serializer.data)
    except Video.DoesNotExist:
        return Response({'error': 'Video not found'}, status=404)

@api_view(['GET', 'POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])  # Require authentication
def api_handle_like(request, pk):
    try:
        video_service = VideoService()
        video = video_service.get_video(pk, Video)
        
        if request.method == 'GET':
            likes_count = Like.objects.filter(video=video, is_like=True).count()
            dislikes_count = Like.objects.filter(video=video, is_like=False).count()
            user_reaction = None
            
            like = Like.objects.filter(video=video, user=request.user).first()
            if like:
                user_reaction = 'like' if like.is_like else 'dislike'
            
            return Response({
                'status': 'success',
                'likes_count': likes_count,
                'dislikes_count': dislikes_count,
                'user_reaction': user_reaction
            })
        
        is_like = request.data.get('is_like', True)
        result = VideoService.handle_like_action(video, request.user, is_like)
        return Response(result)

    except Exception as e:
        logger.error(f"Like action error: {str(e)}")
        return Response(
            {'status': 'error', 'message': str(e)}, 
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([])  # Allow any
def get_token_for_user(request):
    if request.user.is_authenticated:
        refresh = RefreshToken.for_user(request.user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })
    return Response({
        'error': 'User not authenticated'
    }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticatedOrReadOnly])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def review_actions(request, pk=None, review_id=None):
    """Consolidated view for all review operations except streaming"""
    
    if request.method == 'GET':
        try:
            video = get_object_or_404(Video, id=pk)
            reviews = Review.objects.filter(video=video).order_by('-created_at')
            serializer = ReviewSerializer(reviews, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # For all write operations, ensure user is authenticated
    if not request.user.is_authenticated:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    # PUT - Update review
    if request.method == 'PUT':
        try:
            review = get_object_or_404(Review, id=review_id)
            
            # Check ownership
            if review.user != request.user:
                return Response({'error': 'Not authorized to edit this review'}, 
                              status=status.HTTP_403_FORBIDDEN)
            
            serializer = ReviewSerializer(
                review,
                data={'comment': request.data.get('comment', '').strip()},
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # POST - Create review
    elif request.method == 'POST':
        try:
            video = get_object_or_404(Video, id=pk)
            review = Review.objects.create(
                user=request.user,
                video=video,
                comment=request.data.get('comment', '').strip()
            )
            serializer = ReviewSerializer(review, context={'request': request})
            return Response({
                'success': True,
                'comment': serializer.data
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            })
    # DELETE - Delete review
    elif request.method == 'DELETE':
        review = get_object_or_404(Review, id=review_id)
        
        # Strict check for comment owner
        if review.user != request.user:
            return Response({
                'success': False,
                'error': "You can only delete your own comments"
            }, status=403)
        
        try:
            review.delete()
            return Response({
                'success': True,
                'message': 'Comment deleted successfully!'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            })

@require_GET
@csrf_exempt
def stream_reviews(request, pk):
    """Stream reviews - no auth required"""
    try:
        video = get_object_or_404(Video, id=pk)
        
        # Get token if available (for is_owner check)
        auth_token = request.GET.get('auth')
        user = None
        
        if auth_token:
            try:
                validated_token = AccessToken(auth_token)
                user = User.objects.get(id=validated_token['user_id'])
            except:
                pass  # Ignore token errors, just continue without user

        def event_stream():
            while True:
                comments = Review.objects.filter(video=video).order_by('-created_at')[:10]
                data = []
                for comment in comments:
                    data.append({
                        'id': str(comment.id),
                        'username': comment.user.username,
                        'comment': comment.comment,
                        'created_at': comment.created_at.isoformat(),
                        'is_owner': user and comment.user == user
                    })
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(2)

        response = StreamingHttpResponse(
            streaming_content=event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        response['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        print(f"Stream error: {str(e)}")
        response = StreamingHttpResponse(
            "data: {\"error\": \"Stream error\"}\n\n",
            content_type='text/event-stream'
        )
        response['Access-Control-Allow-Origin'] = '*'
        return response

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_handle_follow(request, pk):
    follow_service = FollowService()
    profile = get_object_or_404(Profile, id=pk)
    
    # Handle follow/unfollow
    success, message = follow_service.follow_user(request.user, profile.user) \
        if not follow_service.check_following_status(request.user, profile.user) \
        else follow_service.unfollow_user(request.user, profile.user)
    
    # Get updated stats
    stats = follow_service.get_follower_stats(profile)
    
    return Response({
        'status': 'success' if success else 'error',
        'message': message,
        'is_following': follow_service.check_following_status(request.user, profile.user),
        'followers_count': stats['followers_count'],
        'following_count': stats['following_count']
    })

@api_view(['GET'])
def stream_video_api(request, pk):
    def file_iterator(file_path, start=0, length=None, chunk_size=262144):
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

    video = get_object_or_404(Video, id=pk)
    
    # Prefer 360p for initial load to reduce bandwidth
    if video.encoded_versions and '360p' in video.encoded_versions:
        file_path = os.path.join(settings.MEDIA_ROOT, 'videos', video.encoded_versions['360p'])
    elif video.encoded_versions and '720p' in video.encoded_versions:
        file_path = os.path.join(settings.MEDIA_ROOT, 'videos', video.encoded_versions['720p'])
    else:
        file_path = video.file.path

    if not os.path.exists(file_path):
        logger.error(f"Video file not found: {file_path}")
        return Response({"error": "Video file not found"}, status=404)
    
    file_size = os.path.getsize(file_path)
    
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    
    
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        length = end - start + 1
        
        print(f"Streaming chunk: {start}-{end} (size: {length})")
        
        response = StreamingHttpResponse(
            file_iterator(file_path, start=start, length=length),
            status=206,
            content_type='video/mp4'
        )
        
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = str(length)
        # Add caching headers
        response['Cache-Control'] = 'public, max-age=3600'
        return response
    
    response = StreamingHttpResponse(
        file_iterator(file_path),
        content_type='video/mp4'
    )
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(file_size)
    response['Cache-Control'] = 'public, max-age=3600'

    return response


@api_view(['GET'])
@permission_classes([IsAdminUser])  # Only allow admin users to access this debug endpoint
def api_debug_videos(request):
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
    
    return Response({'videos': debug_info})

@csrf_exempt  # Allow all requests
@require_http_methods(["POST"])  # Only allow POST
def update_video_stats(request):
    from projects.models import ViewHistory
    from datetime import timedelta
    from django.contrib.auth.models import User

    try:
        # Load the stats from the request body
        stats = json.loads(request.body)

        # Print the received stats for debugging
        print("🎥 Video Watch Stats Received via API:", stats)

        # Extract stats
        window_id = stats.get('window_id')
        video_id = stats.get('video_id')
        total_watched = stats.get('total_watched')
        user_id = stats.get('user_id')
        is_completed = stats.get('is_completed', False)  # Default to False if not provided

        # Check for required fields
        if not all([window_id, video_id, total_watched, user_id]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        # Additional check for window_id
        if not window_id:
            return JsonResponse({'error': 'window_id is required'}, status=400)

        # Convert total_watched to timedelta
        try:
            total_watched_duration = timedelta(seconds=float(total_watched))
        except ValueError as ve:
            return JsonResponse({'error': f'Invalid total_watched value: {total_watched}'}, status=400)

        # Get the user object
        try:
            user = User.objects.get(id=user_id)  # Assuming user_id is the actual user ID
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)

        # Save the stats to the database
        try:
            view_history = ViewHistory.objects.get(
                video_id=video_id, 
                window_id=window_id, 
                user=user
            )
            view_history.duration_watched = total_watched_duration
            view_history.completed = is_completed
            view_history.save()
            print(f"🔄 Updated ViewHistory entry for Video ID via API: {video_id}, Window ID: {window_id}")
        except ViewHistory.DoesNotExist:
            return JsonResponse({'error': 'No ViewHistory entry found'}, status=404)

        return JsonResponse({'status': 'success', 'message': 'Video stats updated successfully.'})
    except Exception as e:
        print(f"❌ Error processing request: {str(e)}")  # Log the error for debugging
        return JsonResponse({'error': str(e)}, status=400)