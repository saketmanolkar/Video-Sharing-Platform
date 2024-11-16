import os
import glob
import subprocess
import json
from django.conf import settings
from PIL import Image
import io
from django.core.files.uploadedfile import InMemoryUploadedFile
from datetime import datetime

def encode_video(input_path, output_path, size):
    """
    Encode video with compression while maintaining aspect ratio
    """
    try:
        if not os.path.exists(input_path):
            print(f"Input file not found: {input_path}")
            return False
            
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
        
        # Extract target dimensions from size parameter
        target_width = int(size.split('x')[0])
        target_height = int(size.split('x')[1])
        
        # Calculate dimensions maintaining aspect ratio
        width = int(video_info['streams'][0]['width'])
        height = int(video_info['streams'][0]['height'])
        
        if width/height > target_width/target_height:
            # Width limited
            new_width = target_width
            new_height = int((height * target_width/width) // 2) * 2  # Ensure even number
        else:
            # Height limited 
            new_height = target_height
            new_width = int((width * target_height/height) // 2) * 2  # Ensure even number
            
        # Generate unique output filename
        output_dir = os.path.dirname(output_path)
        output_name = os.path.basename(output_path)
        name, ext = os.path.splitext(output_name)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_output_path = os.path.join(output_dir, f"{name}_{timestamp}{ext}")
        
        # Encode video
        command = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264', '-crf', '23',
            '-preset', 'medium',
            '-c:a', 'aac', '-b:a', '128k',
            '-vf', f'scale={new_width}:{new_height}',
            '-movflags', '+faststart',
            '-y', unique_output_path
        ]
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Encoding error: {result.stderr}")
            return False
            
        return os.path.basename(unique_output_path)
        
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