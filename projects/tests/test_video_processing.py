import os
import tempfile
import mock
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.conf import settings
from PIL import Image
from unittest.mock import patch, MagicMock
from ..models import Video
from ..tasks import process_thumbnail_task, process_video_task

# Create a test media root for our test files
TEST_MEDIA_ROOT = os.path.join(tempfile.gettempdir(), 'test_media')

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class TaskTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test media directory
        os.makedirs(TEST_MEDIA_ROOT, exist_ok=True)
        os.makedirs(os.path.join(TEST_MEDIA_ROOT, 'videos'), exist_ok=True)
        os.makedirs(os.path.join(TEST_MEDIA_ROOT, 'thumbnails'), exist_ok=True)
        
    @classmethod
    def tearDownClass(cls):
        # Clean up test media
        import shutil
        if os.path.exists(TEST_MEDIA_ROOT):
            shutil.rmtree(TEST_MEDIA_ROOT)
        super().tearDownClass()
        
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(username='testuser', password='12345')
        
        # Create test images
        self.create_test_images()
        
        # Create a small test video file
        self.video_file = self.create_test_video()
        
        # Mock Redis lock
        self.redis_patcher = patch('redis.lock.Lock.acquire')
        self.mock_redis_acquire = self.redis_patcher.start()
        self.mock_redis_acquire.return_value = True
        
        # Mock the release method
        self.release_patcher = patch('redis.lock.Lock.release')
        self.mock_redis_release = self.release_patcher.start()
        
    def tearDown(self):
        # Stop patchers
        self.redis_patcher.stop()
        self.release_patcher.stop()
        
        # Cleanup test files
        for path in [self.square_image_path, self.wide_image_path, self.tall_image_path]:
            if os.path.exists(path):
                os.remove(path)
                
    def create_test_images(self):
        # Square image (800x800)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            Image.new('RGB', (800, 800), 'white').save(f, 'JPEG')
            self.square_image_path = f.name

        # Wide image (1600x800)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            Image.new('RGB', (1600, 800), 'white').save(f, 'JPEG')
            self.wide_image_path = f.name

        # Tall image (800x1600)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            Image.new('RGB', (800, 1600), 'white').save(f, 'JPEG')
            self.tall_image_path = f.name
            
    def create_test_video(self):
        """Create a small test video file"""
        # Using a tiny MP4 for testing
        file_content = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41\x00\x00\x00\x00'
        return SimpleUploadedFile(
            name='testvideo.mp4',
            content=file_content,
            content_type='video/mp4'
        )

    # THUMBNAIL TASK TESTS
    
    def test_thumbnail_square_image(self):
        """Test processing square thumbnail"""
        with open(self.square_image_path, 'rb') as f:
            thumbnail = SimpleUploadedFile('square.jpg', f.read(), content_type='image/jpeg')
        
        video = Video.objects.create(
            title='Square Thumbnail Test',
            uploader=self.user,
            thumbnail=thumbnail
        )
        
        # Create a better mock file
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            # Create a real temporary file instead of a MagicMock
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(b'processed_image_data')
                temp_file.flush()
                temp_file_path = temp_file.name
            
            # Open the real file to return from the mock
            result_file = open(temp_file_path, 'rb')
            mock_add_bars.return_value = result_file
            
            try:
                # Run the task
                result = process_thumbnail_task(str(video.pk))
                
                # Verify task execution
                self.assertTrue(result)
                self.assertTrue(mock_add_bars.called)
                
                # Verify video was updated
                video.refresh_from_db()
                self.assertTrue(video.thumbnail)
            finally:
                # Close and remove the temporary file
                result_file.close()
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

    def test_thumbnail_invalid_image(self):
        """Test handling invalid image file"""
        invalid_file = SimpleUploadedFile('invalid.jpg', b'not an image', content_type='image/jpeg')
        
        video = Video.objects.create(
            title='Invalid Thumbnail Test',
            uploader=self.user,
            thumbnail=invalid_file
        )
        
        with patch('projects.utils.add_black_bars') as mock_add_bars:
            # Mock failure in processing
            mock_add_bars.return_value = None
            
            # Run the task
            result = process_thumbnail_task(str(video.pk))
            
            # Verify task reports failure
            self.assertFalse(result)

    def test_thumbnail_no_image(self):
        """Test handling when no thumbnail provided"""
        video = Video.objects.create(
            title='No Thumbnail Test',
            uploader=self.user
        )
        
        # Run the task
        result = process_thumbnail_task(str(video.pk))
        
        # Verify task reports failure
        self.assertFalse(result)
        
    # VIDEO PROCESSING TESTS
    
    @patch('projects.utils.encode_video')
    def test_video_encoding(self, mock_encode):
        """Test video encoding task"""
        # Configure mock to indicate successful encoding
        mock_encode.return_value = True
        
        # Create a test video
        video = Video.objects.create(
            title='Test Video Encoding',
            description='Test description',
            uploader=self.user,
            file=self.video_file
        )
        
        # Save original state for comparison
        original_file = video.file.name
        
        # Run the task
        result = process_video_task(str(video.pk))
        
        # Verify task execution
        self.assertTrue(result)
        self.assertEqual(mock_encode.call_count, 2)  # Called twice for 720p and 360p
        
        # Verify video was updated
        video.refresh_from_db()
        self.assertTrue(video.processed)
        self.assertNotEqual(video.file.name, original_file)
        self.assertEqual(len(video.encoded_versions), 2)
        self.assertIn('720p', video.encoded_versions)
        self.assertIn('360p', video.encoded_versions)

    @patch('projects.utils.encode_video')
    def test_video_encoding_failure(self, mock_encode):
        """Test video encoding failure handling"""
        # Configure mock to indicate encoding failure
        mock_encode.return_value = False
        
        # Create a test video
        video = Video.objects.create(
            title='Test Video Encoding Failure',
            description='Test description',
            uploader=self.user,
            file=self.video_file
        )
        
        # Save original state for comparison
        original_file = video.file.name
        
        # Run the task
        result = process_video_task(str(video.pk))
        
        # Verify task reports failure
        self.assertFalse(result)
        
        # Verify video was not updated
        video.refresh_from_db()
        self.assertFalse(video.processed)
        self.assertEqual(video.file.name, original_file)
        self.assertFalse(hasattr(video, 'encoded_versions') and video.encoded_versions)

    def test_concurrent_task_protection(self):
        """Test tasks are protected against concurrent execution"""
        # Configure mock to indicate lock already acquired
        self.mock_redis_acquire.return_value = False
        
        # Create a test video
        video = Video.objects.create(
            title='Test Concurrent Protection',
            uploader=self.user,
            file=self.video_file
        )
        
        # Try to run tasks
        thumbnail_result = process_thumbnail_task(str(video.pk))
        video_result = process_video_task(str(video.pk))
        
        # Verify both tasks exit early
        self.assertFalse(thumbnail_result)
        self.assertFalse(video_result)