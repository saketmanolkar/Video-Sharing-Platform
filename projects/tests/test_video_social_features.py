from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from ..models import Video, Like, Review
from users.models import Profile, Follow

class SocialFeatureAPITests(TestCase):
    def setUp(self):
        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='testuser1@example.com',
            password='testpassword'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='testuser2@example.com',
            password='testpassword'
        )
        
        # Create test video
        self.video = Video.objects.create(
            title="Test Video",
            description="Test Description",
            uploader=self.user1,
            processed=True
        )
        
    def test_like_api_get(self):
        """Test getting like information"""
        client = APIClient()
        client.force_authenticate(user=self.user1)
        
        url = reverse('api-handle-like', kwargs={'pk': self.video.id})
        response = client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['likes_count'], 0)
        self.assertEqual(response.data['dislikes_count'], 0)
        self.assertIsNone(response.data['user_reaction'])
    
    def test_like_api_post(self):
        """Test liking a video"""
        client = APIClient()
        client.force_authenticate(user=self.user1)
        
        url = reverse('api-handle-like', kwargs={'pk': self.video.id})
        response = client.post(url, {'is_like': True})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')
        
        # Verify like was added in database
        self.assertEqual(Like.objects.count(), 1)
        like = Like.objects.first()
        self.assertEqual(like.user, self.user1)
        self.assertEqual(like.video, self.video)
        self.assertTrue(like.is_like)
    
    def test_review_create(self):
        """Test creating a review"""
        client = APIClient()
        client.force_authenticate(user=self.user1)
        
        # Use direct URL string since there's no name in urls.py
        url = f'/api/projects/{self.video.id}/reviews/'
        comment_text = "This is a test review"
        response = client.post(url, {'comment': comment_text})
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        
        # Verify review was added to database
        self.assertEqual(Review.objects.count(), 1)
        review = Review.objects.first()
        self.assertEqual(review.user, self.user1)
        self.assertEqual(review.video, self.video)
        self.assertEqual(review.comment, comment_text)
    
    def test_review_get(self):
        """Test getting reviews for a video"""
        # Create a test review first
        Review.objects.create(
            user=self.user1,
            video=self.video,
            comment="Test review comment"
        )
        
        client = APIClient()
        # Use direct URL string
        url = f'/api/projects/{self.video.id}/reviews/'
        response = client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['comment'], "Test review comment")
    
    def test_review_update(self):
        """Test updating a review"""
        # Create a test review first
        review = Review.objects.create(
            user=self.user1,
            video=self.video,
            comment="Original comment"
        )
        
        client = APIClient()
        client.force_authenticate(user=self.user1)
        
        # Use direct URL string
        url = f'/api/projects/{self.video.id}/reviews/{review.id}/'
        updated_text = "Updated comment"
        response = client.put(url, {'comment': updated_text})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['comment'], updated_text)
        
        # Verify review was updated in database
        review.refresh_from_db()
        self.assertEqual(review.comment, updated_text)
    
    def test_review_delete(self):
        """Test deleting a review"""
        # Create a test review first
        review = Review.objects.create(
            user=self.user1,
            video=self.video,
            comment="Comment to delete"
        )
        
        client = APIClient()
        client.force_authenticate(user=self.user1)
        
        # Use direct URL string
        url = f'/api/projects/{self.video.id}/reviews/{review.id}/'
        response = client.delete(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        
        # Verify review was deleted from database
        self.assertEqual(Review.objects.count(), 0)
    
    def test_follow_api(self):
        """Test following a user"""
        client = APIClient()
        client.force_authenticate(user=self.user1)
        
        # Get user2's profile ID
        profile2 = Profile.objects.get(user=self.user2)
        
        url = reverse('api-handle-follow', kwargs={'pk': profile2.id})
        response = client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')
        self.assertTrue(response.data['is_following'])
        
        # The API uses either UserActivitySummary or direct count - use direct count assertion
        # to avoid testing implementation details
        self.assertEqual(Follow.objects.filter(following=self.user2).count(), 1)
        
        # Verify follow was added in database
        self.assertEqual(Follow.objects.count(), 1)
        follow = Follow.objects.first()
        self.assertEqual(follow.user, self.user1)
        self.assertEqual(follow.following, self.user2)