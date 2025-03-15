import os
import tempfile
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from projects.models import Video, Tag
from unittest.mock import patch

class VideoUploadTest(TestCase):
    def setUp(self):
        # Create test user
        self.client = Client()
        self.user = User.objects.create_user(
            username='testvideocreator',
            email='creator@example.com',
            password='password123'
        )
        
        # Create some test tags
        self.tag1 = Tag.objects.create(name='Python')
        self.tag2 = Tag.objects.create(name='Django')
        
        # Login the user
        self.client.login(username='testvideocreator', password='password123')
        
        # URL for video upload
        self.upload_url = reverse('create-project')
        self.update_url_name = 'update-project'
        
        # Create test files
        # For testing, we'll use small dummy files
        self.video_file = self._create_test_video()
        self.thumbnail_file = self._create_test_image()
        
        # Basic form data
        self.valid_form_data = {
            'title': 'Test Video Title',
            'description': 'This is a test description with more than five words',
            'privacy_status': 'public',
            'tags': [self.tag1.id, self.tag2.id]
        }
    
    def _create_test_video(self):
        """Create a small test video file"""
        # Using a tiny MP4 for testing
        file_content = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41\x00\x00\x00\x00'
        return SimpleUploadedFile(
            name='testvideo.mp4',
            content=file_content,
            content_type='video/mp4'
        )
    
    def _create_test_image(self):
        """Create a small test image file"""
        # Simple PNG file header
        file_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        return SimpleUploadedFile(
            name='testimage.png',
            content=file_content,
            content_type='image/png'
        )
    
    def test_upload_page_requires_login(self):
        """Test that the upload page requires login"""
        # Logout first
        self.client.logout()
        response = self.client.get(self.upload_url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/users/login-register/' in response.url)
    
    def test_upload_form_renders(self):
        """Test that the upload form renders correctly"""
        response = self.client.get(self.upload_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Upload Your Video')
        self.assertContains(response, 'enctype="multipart/form-data"')
    
    def test_successful_video_upload(self):
        """Test a successful video upload with all valid data"""
        # Combine form data with files
        form_data = self.valid_form_data.copy()
        form_data['file'] = self.video_file
        form_data['thumbnail'] = self.thumbnail_file
        
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            response = self.client.post(self.upload_url, form_data)
        
        # Should redirect to success page or video detail
        self.assertEqual(response.status_code, 302)
        
        # Verify video was created
        self.assertEqual(Video.objects.count(), 1)
        video = Video.objects.first()
        self.assertEqual(video.title, 'Test Video Title')
        self.assertEqual(video.uploader, self.user)
        self.assertEqual(video.tags.count(), 2)
    
    def test_missing_required_fields(self):
        """Test that required fields are enforced"""
        # Test without title
        form_data = self.valid_form_data.copy()
        form_data.pop('title')
        form_data['file'] = self.video_file
        form_data['thumbnail'] = self.thumbnail_file
        
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            response = self.client.post(self.upload_url, form_data)
        self.assertEqual(response.status_code, 200)  # Stays on form page
        self.assertEqual(Video.objects.count(), 0)
        
        # Test without description
        form_data = self.valid_form_data.copy()
        form_data.pop('description')
        form_data['file'] = self.video_file
        form_data['thumbnail'] = self.thumbnail_file
        
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            response = self.client.post(self.upload_url, form_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Video.objects.count(), 0)
        
        # Test without tags
        form_data = self.valid_form_data.copy()
        form_data.pop('tags')
        form_data['file'] = self.video_file
        form_data['thumbnail'] = self.thumbnail_file
        
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            response = self.client.post(self.upload_url, form_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Video.objects.count(), 0)
    
    def test_invalid_video_file_type(self):
        """Test rejecting invalid video file types"""
        invalid_video = SimpleUploadedFile(
            name='test.txt',
            content=b'This is not a video file',
            content_type='text/plain'
        )
        
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            form_data = self.valid_form_data.copy()
            form_data['file'] = invalid_video
            form_data['thumbnail'] = self.thumbnail_file
            
            response = self.client.post(self.upload_url, form_data)
        
        # Check that the form validation failed
        self.assertEqual(response.status_code, 200)  # Stays on form page
        
        # Check that no video was created
        self.assertEqual(Video.objects.count(), 0)
    
    def test_invalid_thumbnail_file_type(self):
        """Test rejecting invalid thumbnail file types"""
        invalid_thumbnail = SimpleUploadedFile(
            name='test.txt',
            content=b'This is not an image file',
            content_type='text/plain'
        )
        
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            form_data = self.valid_form_data.copy()
            form_data['file'] = self.video_file
            form_data['thumbnail'] = invalid_thumbnail
            
            response = self.client.post(self.upload_url, form_data)
        
        # Check that the form validation failed
        self.assertEqual(response.status_code, 200)  # Stays on form page
        
        # Check that no video was created
        self.assertEqual(Video.objects.count(), 0)
    
    def test_short_description(self):
        """Test that short descriptions are rejected"""
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            form_data = self.valid_form_data.copy()
            form_data['description'] = 'Too short'  # Less than 5 words
            form_data['file'] = self.video_file
            form_data['thumbnail'] = self.thumbnail_file
            
            response = self.client.post(self.upload_url, form_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'at least 5 words')
        self.assertEqual(Video.objects.count(), 0)
    
    def test_update_video(self):
        """Test updating an existing video"""
        # First create a video
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            form_data = self.valid_form_data.copy()
            form_data['file'] = self.video_file
            form_data['thumbnail'] = self.thumbnail_file
            self.client.post(self.upload_url, form_data)
        
        video = Video.objects.first()
        
        # Now update it
        update_data = {
            'title': 'Updated Title',
            'description': 'This is an updated description with more than five words',
            'privacy_status': 'private',
            'tags': [self.tag1.id]  # Changed tags
        }
        
        update_url = reverse(self.update_url_name, args=[video.id])
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            response = self.client.post(update_url, update_data)
        
        # Should redirect after successful update
        self.assertEqual(response.status_code, 302)
        
        # Verify the video was updated
        video.refresh_from_db()
        self.assertEqual(video.title, 'Updated Title')
        self.assertEqual(video.privacy_status, 'private')
        self.assertEqual(video.tags.count(), 1)