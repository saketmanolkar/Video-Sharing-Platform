import os
import glob
import subprocess
import json
from django.conf import settings
from PIL import Image
import io
from django.core.files.uploadedfile import InMemoryUploadedFile

def encode_video(input_path, output_path, size):
    """
    Encode video with compression while maintaining aspect ratio
    """
    try:
        if not os.path.exists(input_path):
            print(f"Input file not found: {input_path}")
            return False
            
        # Get file size before encoding
        original_size = os.path.getsize(input_path)
        print(f"Original size: {original_size/1024/1024:.2f}MB")
        
        # Get video dimensions using ffprobe
        probe_command = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            input_path
        ]
        probe_result = subprocess.run(probe_command, capture_output=True, text=True)
        video_info = json.loads(probe_result.stdout)
        
        # Extract original dimensions
        original_width = int(video_info['streams'][0]['width'])
        original_height = int(video_info['streams'][0]['height'])
        
        # Parse target height from size parameter (e.g., "1280x720" -> 720)
        target_height = int(size.split('x')[1])
        
        # Make target height even
        target_height = target_height - (target_height % 2)
        
        # Calculate new width maintaining aspect ratio
        new_width = int((original_width / original_height) * target_height)
        # Make width even (required by some codecs)
        new_width = new_width - (new_width % 2)
        
        # For vertical videos, swap target dimensions if original is vertical
        if original_height > original_width:
            # Use height as the controlling dimension
            new_height = target_height
            new_width = int((original_width / original_height) * new_height)
            # Ensure both dimensions are even
            new_width = new_width - (new_width % 2)
            new_height = new_height - (new_height % 2)
            dimensions = f"{new_width}x{new_height}"
        else:
            dimensions = f"{new_width}x{target_height}"
            
        command = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',     # Video codec
            '-crf', '23',          # Compression quality (23 is a good balance)
            '-preset', 'medium',    # Encoding speed preset
            '-vf', f'scale={dimensions}',  # Scale to exact dimensions
            '-c:a', 'aac',         # Audio codec
            '-b:a', '128k',        # Audio bitrate
            '-y',                  # Overwrite output files
            output_path
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            encoded_size = os.path.getsize(output_path)
            print(f"Encoded size ({dimensions}): {encoded_size/1024/1024:.2f}MB")
            return True
        else:
            print(f"FFmpeg error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Encoding error: {str(e)}")
        return False

def cleanup_media_files(base_filename, media_type='videos'):
    """
    Clean up encoded video files
    """
    try:
        media_dir = os.path.join(settings.MEDIA_ROOT, media_type)
        name, ext = os.path.splitext(base_filename)
        
        # Only look for encoded versions
        patterns = [
            f"{name}*_720p{ext}",
            f"{name}*_360p{ext}",
            f"{name}*_versions.json"
        ]
        
        for pattern in patterns:
            full_pattern = os.path.join(media_dir, pattern)
            for file_path in glob.glob(full_pattern):
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Removed: {file_path}")
                    
    except Exception as e:
        print(f"Cleanup error: {str(e)}")

def add_black_bars(image_file):
    """Add black bars to vertical images to make them 16:9"""
    try:
        img = Image.open(image_file)
        width, height = img.size
        
        # If vertical, add black bars
        if width < height:
            new_width = int(height * (16/9))
            new_image = Image.new('RGB', (new_width, height), (0, 0, 0))
            paste_x = (new_width - width) // 2
            new_image.paste(img, (paste_x, 0))
            
            # Save to memory
            output = io.BytesIO()
            new_image.save(output, format='JPEG', quality=85)
            output.seek(0)
            
            # Return processed image
            return InMemoryUploadedFile(
                output,
                'ImageField',
                f"{image_file.name.split('.')[0]}.jpg",
                'image/jpeg',
                output.getbuffer().nbytes,
                None
            )
    except Exception as e:
        print(f"Error processing thumbnail: {str(e)}")
        return None
    
    return image_file  # Return original if no processing needed