from django.http import JsonResponse, StreamingHttpResponse, HttpResponse, FileResponse, HttpResponseRedirect
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
from django.shortcuts import get_object_or_404, redirect
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
from users.models import Profile , Report
import os
import re
from django.conf import settings
from users.services.cache_service import SessionActivityCache
from django.views.decorators.http import require_http_methods
from datetime import timedelta
from django.shortcuts import render
from users.services.user_services import UserReportService, SpeechService
from users.services.user_analytics_service import UserAnalyticsService
from projects.services.analytics_service import VideoReportService
from django.utils import timezone
logger = logging.getLogger(__name__)
from django.contrib import messages
from django.views.decorators.cache import cache_control
from celery import Celery
from users.tasks import generate_speech_task
from users.services.cache_service import TTSLockCache
from django.db import connection
import requests
import socket
from django.contrib.auth.decorators import login_required

class EventStreamRenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'text-stream'
    charset = 'utf-8'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        return f"data: {json.dumps(data)}\n\n"

@api_view(['GET'])
@permission_classes([IsAdminUser])
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
        
        # Video Statistics
        {'POST': '/api/video-stats/'},
        
        # Report Generation
        {'POST': '/api/generate-report/'},
        
        # Speech Generation
        {'POST': '/api/generate-speech/'},
        
        # Audio Serving
        {'GET': '/api/audio/profile_id/report_type/'},
        
        # TTS Status Check
        {'GET': '/api/check-tts-status/username/'},

        # Regional Performance Test
        {'GET': '/api/test/'},

        # Presigned URL
        {'GET': '/api/presigned-url/'},
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
@authentication_classes([JWTAuthentication, SessionAuthentication])
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
@authentication_classes([JWTAuthentication, SessionAuthentication])
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
    """Stream video from DigitalOcean Spaces with support for Range requests"""
    from django.conf import settings
    import boto3
    import re
    
    video = get_object_or_404(Video, id=pk)
    
    # Connect to DO Spaces
    s3 = boto3.client('s3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
    # Determine which version to stream
    if video.encoded_versions and '720p' in video.encoded_versions:
        file_key = video.encoded_versions['720p']
    elif video.encoded_versions and '360p' in video.encoded_versions:
        file_key = video.encoded_versions['360p']
    else:
        file_key = video.file.name
    
    print(f"🎥 Streaming video from DO Spaces - Key: {file_key}")
    
    try:
        # Get file metadata from DO Spaces
        file_metadata = s3.head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=file_key
        )
        
        file_size = file_metadata['ContentLength']
        content_type = file_metadata.get('ContentType', 'video/mp4')
        
        # Check for Range header
        range_header = request.META.get('HTTP_RANGE', '').strip()
        range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        
        if range_match:
            # Handle partial content request
            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
            length = end - start + 1
            
            print(f"📊 Streaming chunk: {start}-{end}/{file_size} (size: {length})")
            
            # Get range of bytes from DO Spaces
            response = s3.get_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=file_key,
                Range=f'bytes={start}-{end}'
            )
            
            # Create streaming response
            content = response['Body'].read()
            stream_response = HttpResponse(
                content,
                status=206,
                content_type=content_type
            )
            
            # Set headers for partial content
            stream_response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            stream_response['Accept-Ranges'] = 'bytes'
            stream_response['Content-Length'] = str(length)
            stream_response['Cache-Control'] = 'public, max-age=3600'
            
            return stream_response
        else:
            # Redirect to the actual file URL for full content requests
            # This is more efficient than proxying the entire file
            file_url = f"{settings.AWS_S3_ENDPOINT_URL}/{settings.AWS_STORAGE_BUCKET_NAME}/{file_key}"
            
            # For security, you might want to generate a signed URL instead
            # signed_url = s3.generate_presigned_url(
            #     'get_object',
            #     Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': file_key},
            #     ExpiresIn=3600  # URL expires in 1 hour
            # )
            
            print(f"🔄 Redirecting to DO Spaces URL: {file_url}")
            return HttpResponseRedirect(file_url)
            
    except Exception as e:
        print(f"❌ Error streaming video: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)

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
@authentication_classes([JWTAuthentication, SessionAuthentication])
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

        # Handle user_id with "user_" prefix
        if isinstance(user_id, str) and user_id.startswith('user_'):
            user_id = user_id.replace('user_', '')
            print(f"⚙️ Extracted user ID from prefixed value: {user_id}")

        # Get the user object
        try:
            user = User.objects.get(id=user_id)  # Now using the numeric ID
        except User.DoesNotExist:
            return JsonResponse({'error': f'User not found with ID: {user_id}'}, status=404)
        except ValueError:
            return JsonResponse({'error': f'Invalid user ID format: {user_id}'}, status=400)

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

@csrf_exempt
@authentication_classes([JWTAuthentication, SessionAuthentication])
def generate_report(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            username = data.get("username")
            report_type = data.get("type", "user")

            # Get user
            user = User.objects.get(username=username)
            
            # Check report type
            if report_type == "video":
                videos = Video.objects.filter(uploader=user)
                prompt = VideoReportService.format_video_data_for_prompt(user, videos)
                
                if not prompt:
                    return JsonResponse({"error": "Could not generate video data prompt"}, status=400)
            else:
                analytics_service = UserAnalyticsService()
                prompt = analytics_service.format_user_data_for_prompt(user)
                
                if not prompt:
                    return JsonResponse({"error": "Could not generate user data prompt"}, status=400)
            
            # Generate AI report
            api_key = "AIzaSyBOB5FpLu0hsHrfZuML-6VfrKVck1W8xP4"
            report_service = UserReportService(api_key)
            report_content = report_service.generate_report_content(
                prompt=prompt,
                report_type=report_type,
                username=username
            )
            
            # Return success message along with report content
            timestamp = int(timezone.now().timestamp())
            
            report_url = f"{report_content}?v={timestamp}"
            
            return JsonResponse({
                'success': True,
                'report_url': report_url,
                'message': f"New {report_type.title()} Data Report generated for {username}.\n",
                'is_new_report': True
            })
            
        except User.DoesNotExist:
            return JsonResponse({"error": "User not found"}, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'message': 'Failed to generate report'
            }, status=400)
            
    return JsonResponse({"error": "Invalid request method"}, status=400)

@csrf_exempt
@authentication_classes([JWTAuthentication, SessionAuthentication])
@require_http_methods(["POST"])
def generate_speech(request):
    try:
        # Handle both JSON and FormData
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            username = data.get('username')
            report_type = data.get('report_type')
        else:
            username = request.POST.get('username')
            report_type = request.POST.get('report_type')
            
        # Validate input parameters
        if not username or not report_type:
            return JsonResponse({"error": "Username and report type are required."}, status=400)

        print(f"Username: {username}, Report Type: {report_type}")

        # Get the report for the user FIRST and check time-based rate limiting
        try:
            report = Report.objects.get(user__username=username)
            print(f"Report found: {report}")
            
            # Check for rate limiting (1 generation per day per report type)
            now = timezone.now()
            one_day_ago = now - timezone.timedelta(days=1)
            
            print(f"DEBUG TIME CHECK - Current time: {now}")
            print(f"DEBUG TIME CHECK - One day ago: {one_day_ago}")

            # TIME-BASED RATE LIMITING CHECK - HAPPENS BEFORE ACQUIRING LOCK
            if report_type == 'user' and report.user_report_audio_generated_at:
                print(f"DEBUG TIME CHECK - Last user audio generated at: {report.user_report_audio_generated_at}")
                print(f"DEBUG TIME CHECK - Is recent? {report.user_report_audio_generated_at > one_day_ago}")
                
                if report.user_report_audio_generated_at > one_day_ago:
                    # Generated less than 24 hours ago
                    time_remaining = 24 - (now - report.user_report_audio_generated_at).total_seconds() / 3600
                    hours = int(time_remaining)
                    minutes = int((time_remaining - hours) * 60)
                    
                    error_msg = f"Rate limit reached. You can generate user audio again after {hours} hours and {minutes} minutes."
                    print(f"DEBUG RATE LIMIT: {error_msg}")
                    
                    return JsonResponse({
                        "error": error_msg
                    }, status=429)  # 429 Too Many Requests
            
            elif report_type == 'video' and report.video_report_audio_generated_at:
                print(f"DEBUG TIME CHECK - Last video audio generated at: {report.video_report_audio_generated_at}")
                print(f"DEBUG TIME CHECK - Is recent? {report.video_report_audio_generated_at > one_day_ago}")
                
                if report.video_report_audio_generated_at > one_day_ago:
                    # Generated less than 24 hours ago
                    time_remaining = 24 - (now - report.video_report_audio_generated_at).total_seconds() / 3600
                    hours = int(time_remaining)
                    minutes = int((time_remaining - hours) * 60)
                    
                    error_msg = f"Rate limit reached. You can generate video audio again after {hours} hours and {minutes} minutes."
                    print(f"DEBUG RATE LIMIT: {error_msg}")
                    
                    return JsonResponse({
                        "error": error_msg
                    }, status=429)  # 429 Too Many Requests

            # ONLY TRY TO ACQUIRE GLOBAL LOCK AFTER TIME CHECK PASSES
            # Check if TTS generation is already in progress
            tts_lock = TTSLockCache()
            if not tts_lock.acquire_global_lock():
                # Could not acquire lock - TTS is already running
                print("TTS generation is already in progress. Please try again in a few minutes.")
                return JsonResponse({
                    "error": "TTS generation is already in progress. Please try again in a few minutes."
                }, status=409)  # 409 Conflict

            # Set audio_is_generated to False before starting
            report.audio_is_generated = False
            report.save()

            # Queue just the speech generation
            generate_speech_task.delay(username, report_type)

            # Return immediately
            return JsonResponse({
                "status": "processing",
                "message": "Speech generation started"
            })

        except Report.DoesNotExist:
            return JsonResponse({"error": "Report not found"}, status=404)
        except Exception as e:
            # Release the lock if there's an error
            try:
                tts_lock.release_global_lock()
            except:
                pass
            print(f"Error: {str(e)}")
            return JsonResponse({"error": "Failed to update report."}, status=500)

    except Exception as e:
        print(f"Error in generate_speech: {str(e)}")
        return JsonResponse({"error": "Failed to generate speech."}, status=500)
    
@cache_control(max_age=31536000, public=True, immutable=True)
def serve_audio(request, profile_id, report_type):
    """API endpoint to serve audio files with proper caching"""
    from django.utils.http import http_date
    
    profile = get_object_or_404(Profile, id=profile_id)
    
    try:
        # Get the report
        report = Report.objects.get(user=profile.user)
        
        # Get the audio URL based on report type
        if report_type == 'user':
            audio_url = report.user_report_audio_file_url
        elif report_type == 'video':
            audio_url = report.video_report_audio_file_url
        else:
            return HttpResponse("Invalid report type", status=400)
        
        if not audio_url:
            return HttpResponse("Audio not found", status=404)
        
        # If it's a remote URL, redirect to it
        if audio_url.startswith('http'):
            # Add cache control headers to the redirect
            response = redirect(audio_url)
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
            return response
        
        # Handle local file path
        filename = audio_url.split('/')[-1]
        file_path = os.path.join(settings.MEDIA_ROOT, 'reports', filename)
        
        print(f"🎵 Serving local audio: {filename}")
        
        if not os.path.exists(file_path):
            return HttpResponse(f"Audio file not found: {filename}", status=404)
            
        # Get file modification time for ETag
        stat = os.stat(file_path)
        etag = f'"{stat.st_mtime}"'
        
        # Check if client has valid cached version
        if_none_match = request.META.get('HTTP_IF_NONE_MATCH')
        if if_none_match and if_none_match == etag:
            return HttpResponse(status=304)  # Not Modified
            
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Type'] = 'audio/wav'
        response['Accept-Ranges'] = 'bytes'
        response['Cache-Control'] = 'public, max-age=31536000, immutable'
        response['ETag'] = etag
        response['Last-Modified'] = http_date(stat.st_mtime)
        
        # Add CORS headers if needed
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Max-Age'] = '86400'
        
        return response
    except Report.DoesNotExist:
        return HttpResponse("Report not found", status=404)
    except Exception as e:
        print(f"❌ Error serving audio: {str(e)}")
        return HttpResponse("Error serving audio file", status=500)

@require_http_methods(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def check_tts_status(request, username):
    try:
        report = Report.objects.get(user__username=username)
        return JsonResponse({
            "user_report": {
                "is_completed": report.audio_is_generated,
                "audio_url": report.user_report_audio_file_url
            },
            "video_report": {
                "is_completed": report.audio_is_generated,
                "audio_url": report.video_report_audio_file_url
            }
        })
    except Report.DoesNotExist:
        return JsonResponse({
            "user_report": {
                "is_completed": False,
                "audio_url": None
            },
            "video_report": {
                "is_completed": False,
                "audio_url": None
            }
        })

@require_GET
def api_performance_test(request):
    """
    Comprehensive diagnostic API with geolocation
    """
    overall_start = time.time()
    
    # Get real IP (works with proxies)
    ip = get_client_ip(request)
    
    results = {
        'timestamp': time.time(),
        'client_info': {
            'ip': ip,
            'geo_info': get_ip_geolocation(ip),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
        },
        'timings': {},
        'network': {},
    }
    
    # Network test - DNS lookup time for your domain
    dns_start = time.time()
    try:
        socket.gethostbyname('saketmanolkar.me')  # Replace with your domain
        results['network']['dns_lookup'] = time.time() - dns_start
    except:
        results['network']['dns_lookup'] = -1
    
    # Database tests
    db_start = time.time()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    results['timings']['database_connection'] = time.time() - db_start
    
    # Test Video model queries
    videos_start = time.time()
    from projects.models import Video
    video_count = Video.objects.count()
    recent_videos = list(Video.objects.filter(privacy_status='public')[:5].values('id', 'title'))
    results['timings']['video_query'] = time.time() - videos_start
    results['video_count'] = video_count
    
    # Test comment queries
    comments_start = time.time()
    from projects.models import Review
    if recent_videos:
        video_id = recent_videos[0]['id']
        comments = list(Review.objects.filter(video_id=video_id)[:5])
        comments_count = len(comments)
    else:
        comments_count = 0
    results['timings']['comments_query'] = time.time() - comments_start
    results['comments_count'] = comments_count
    
    # Total server processing time
    results['timings']['total_backend'] = time.time() - overall_start
    
    # Add frontend performance instructions
    results['frontend_test'] = {
        'instructions': 'Open browser DevTools (F12), go to Network tab, refresh the page, and check timings',
        'key_metrics': [
            'TTFB (Time To First Byte)',
            'DOM Content Loaded',
            'Load Time',
            'Size of largest assets'
        ]
    }
    
    return JsonResponse(results)

def get_client_ip(request):
    """Get real client IP, handling proxies"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip

def get_ip_geolocation(ip):
    """Get geolocation data for an IP address"""
    if ip == 'unknown' or ip.startswith('10.') or ip.startswith('172.') or ip.startswith('192.168.'):
        # Don't try to geolocate private IPs
        return {
            'country': 'Unknown (private IP)',
            'city': 'Unknown',
            'region': 'Unknown'
        }
    
    try:
        # Use a free geolocation API
        response = requests.get(f'https://ipinfo.io/{ip}/json')
        if response.status_code == 200:
            data = response.json()
            return {
                'country': data.get('country', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'region': data.get('region', 'Unknown')
            }
    except:
        pass
    
    return {
        'country': 'Unknown (lookup failed)',
        'city': 'Unknown',
        'region': 'Unknown'
    }

@login_required
def get_presigned_url(request):
    """Generate a presigned URL for direct upload to Spaces"""
    import boto3
    import uuid
    import re
    from django.http import JsonResponse
    from django.conf import settings
    
    # Only accept POST requests
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Get file info from request
    filename = request.POST.get('filename')
    filetype = request.POST.get('filetype')
    
    if not filename or not filetype:
        return JsonResponse({'error': 'Missing filename or filetype'}, status=400)
    
    # Generate a unique path in the videos folder
    original_name = filename
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', original_name)  # Sanitize
    uploaded_file_path = f"videos/{str(uuid.uuid4())[:8]}_{safe_name}"
    
    # Create S3 client with DO credentials
    s3_client = boto3.client('s3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
    # Generate presigned URL WITHOUT the ACL param (this is key)
    presigned_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': uploaded_file_path,
            'ContentType': filetype,
            # Remove ACL from here
        },
        ExpiresIn=600  # 10 minutes
    )
    
    # Set ACL after upload
    try:
        # Create a presigned URL for the ACL operation too
        acl_url = s3_client.generate_presigned_url(
            'put_object_acl',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': uploaded_file_path,
                'ACL': 'public-read'
            },
            ExpiresIn=600
        )
    except Exception as e:
        print(f"Error generating ACL URL: {e}")
        acl_url = None
    
    # Return URLs and file path to client
    return JsonResponse({
        'presigned_url': presigned_url,
        'acl_url': acl_url,
        'file_path': uploaded_file_path
    })

