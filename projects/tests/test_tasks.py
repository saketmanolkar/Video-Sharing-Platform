from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from ..models import Video
from ..tasks import process_thumbnail_task
import os
from PIL import Image
import tempfile

class TaskTests(TestCase):
    def setUp(self):
        # Create test user
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='12345')
        
        # Create test images
        self.create_test_images()
        
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

    def tearDown(self):
        # Cleanup test files
        for path in [self.square_image_path, self.wide_image_path, self.tall_image_path]:
            if os.path.exists(path):
                os.remove(path)

    def test_thumbnail_square_image(self):
        """Test processing square thumbnail"""
        with open(self.square_image_path, 'rb') as f:
            thumbnail = SimpleUploadedFile('square.jpg', f.read(), content_type='image/jpeg')
        video = Video.objects.create(
            title='Square Thumbnail Test',
            uploader=self.user,
            thumbnail=thumbnail
        )
        result = process_thumbnail_task(str(video.pk))
        video.refresh_from_db()
        
        with Image.open(video.thumbnail.path) as img:
            width, height = img.size
            self.assertAlmostEqual(width/height, 16/9, places=2)

    def test_thumbnail_wide_image(self):
        """Test processing wide thumbnail"""
        with open(self.wide_image_path, 'rb') as f:
            thumbnail = SimpleUploadedFile('wide.jpg', f.read(), content_type='image/jpeg')
        video = Video.objects.create(
            title='Wide Thumbnail Test',
            uploader=self.user,
            thumbnail=thumbnail
        )
        result = process_thumbnail_task(str(video.pk))
        video.refresh_from_db()
        
        with Image.open(video.thumbnail.path) as img:
            width, height = img.size
            self.assertAlmostEqual(width/height, 16/9, places=2)

    def test_thumbnail_tall_image(self):
        """Test processing tall thumbnail"""
        with open(self.tall_image_path, 'rb') as f:
            thumbnail = SimpleUploadedFile('tall.jpg', f.read(), content_type='image/jpeg')
        video = Video.objects.create(
            title='Tall Thumbnail Test',
            uploader=self.user,
            thumbnail=thumbnail
        )
        result = process_thumbnail_task(str(video.pk))
        video.refresh_from_db()
        
        with Image.open(video.thumbnail.path) as img:
            width, height = img.size
            self.assertAlmostEqual(width/height, 16/9, places=2)

    def test_thumbnail_no_image(self):
        """Test handling when no thumbnail provided"""
        video = Video.objects.create(
            title='No Thumbnail Test',
            uploader=self.user
        )
        result = process_thumbnail_task(str(video.pk))
        video.refresh_from_db()
        self.assertFalse(video.thumbnail)

    def test_thumbnail_invalid_image(self):
        """Test handling invalid image file"""
        invalid_file = SimpleUploadedFile('invalid.jpg', b'not an image', content_type='image/jpeg')
        video = Video.objects.create(
            title='Invalid Thumbnail Test',
            uploader=self.user,
            thumbnail=invalid_file
        )
        result = process_thumbnail_task(str(video.pk))
        video.refresh_from_db()
        # Should handle error gracefully
        self.assertFalse(result)