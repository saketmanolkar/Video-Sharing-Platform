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
from django.views.decorators.csrf import csrf_exempt
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
        {'GET, POST': '/api/projects/id/like/'},
        
        # Reviews/Comments
        {'GET, POST': '/api/projects/id/reviews/'},
        {'GET': '/api/projects/id/reviews/stream/'},
        {'PUT, DELETE': '/api/projects/id/reviews/review_id/'},
        
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
def ProjectLike(request, pk):
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
    
    print("Debug - Auth:", request.auth)  # Debug JWT token
    print("Debug - User:", request.user)  # Debug authenticated user
    print("Debug - Headers:", request.headers)  # Debug request headers
    
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
