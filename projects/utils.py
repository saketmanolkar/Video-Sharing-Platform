import os
import glob
import subprocess
import json
from django.conf import settings
from PIL import Image
import io
from django.core.files.uploadedfile import InMemoryUploadedFile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def encode_video(input_path, output_path, size):
    """Video encoding function with accurate metrics"""
    try:
        print(f"🎬 Encoding: {input_path} -> {output_path}")
        
        # Get target width from size parameter
        target_width = int(size.split('x')[0])
        
        # Enhanced probe command
        probe_cmd = [
            'ffprobe', 
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,bit_rate,codec_name',
            '-of', 'json',
            input_path
        ]
        
        # Default to horizontal scaling
        scale_filter = f'scale={target_width}:-2'
        
        try:
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            if probe_result.returncode == 0:
                video_info = json.loads(probe_result.stdout)
                stream_info = video_info['streams'][0]
                
                # Enhanced encoding parameters based on input
                command = [
                    'ffmpeg', '-i', input_path,
                    '-c:v', 'libx264',
                    '-preset', 'faster',
                    '-crf', '28',
                    '-c:a', 'aac',
                    '-b:a', '96k',
                    '-movflags', '+faststart',
                    '-profile:v', 'main',
                    '-level', '3.1',
                    '-pix_fmt', 'yuv420p',
                    '-vf', scale_filter,
                    '-maxrate', '2M',
                    '-bufsize', '4M',
                    '-y',
                    output_path
                ]
                
                print(f"🛠️ Running command: {' '.join(command)}")
                result = subprocess.run(command, capture_output=True, text=True)
                
                if result.returncode == 0:
                    return True
                    
        except Exception as e:
            print(f"⚠️ Encoding error: {str(e)}")
            
        return False
            
    except Exception as e:
        print(f"❌ Fatal encoding error: {str(e)}")
        return False

def add_black_bars(image_file):
    """Add black bars to make images 16:9 aspect ratio"""
    try:
        img = Image.open(image_file)
        width, height = img.size
        
        # Calculate target dimensions for 16:9
        target_ratio = 16/9
        current_ratio = width/height
        
        # Add black bars if not already 16:9
        if abs(current_ratio - target_ratio) > 0.01:  # Allow small deviation
            if current_ratio > target_ratio:  # Too wide
                new_height = int(width / target_ratio)
                new_width = width
                new_image = Image.new('RGB', (new_width, new_height), (0, 0, 0))
                paste_y = (new_height - height) // 2
                new_image.paste(img, (0, paste_y))
            else:  # Too tall or square
                new_width = int(height * target_ratio)
                new_height = height
                new_image = Image.new('RGB', (new_width, new_height), (0, 0, 0))
                paste_x = (new_width - width) // 2
                new_image.paste(img, (paste_x, 0))
            
            # Save to memory
            output = io.BytesIO()
            new_image.save(output, format='JPEG', quality=85)
            output.seek(0)
            
            return InMemoryUploadedFile(
                output,
                'ImageField',
                f"{image_file.name.split('.')[0]}_16_9.jpg",
                'image/jpeg',
                output.getbuffer().nbytes,
                None
            )
            
        print("✨ Image already in 16:9 ratio")
        return image_file
        
    except Exception as e:
        logger.error(f"Error processing thumbnail: {str(e)}")
        return None