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
        
        # First, probe the input video
        probe_cmd = [
            'ffprobe', 
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'json',
            input_path
        ]
        
        # Default to horizontal scaling
        scale_filter = f'scale={target_width}:-2'
        
        try:
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            if probe_result.returncode == 0:
                video_info = json.loads(probe_result.stdout)
                original_width = int(video_info['streams'][0]['width'])
                original_height = int(video_info['streams'][0]['height'])
                
                print(f"📐 Original dimensions: {original_width}x{original_height}")
                
                # For vertical videos, calculate appropriate target height
                if original_height > original_width:
                    # Calculate target height maintaining aspect ratio
                    target_height = min(720, int(target_width * (original_height / original_width)))
                    scale_filter = f'scale=-2:{target_height}'
                    print(f"🔄 Vertical video detected, scaling to height: {target_height}")
                
        except Exception as e:
            print(f"⚠️ Video probe failed, using default scaling: {str(e)}")
        
        # Adjust CRF based on resolution
        crf = '23' if target_width >= 1280 else '26'
        
        command = [
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',        # Video codec
            '-preset', 'medium',       # Encoding speed preset
            '-crf', crf,              # Quality (18-28, lower = better)
            '-c:a', 'aac',            # Audio codec
            '-b:a', '128k',           # Audio bitrate
            '-vf', scale_filter,      # Video scaling with aspect ratio
            '-movflags', '+faststart', # Web optimization
            '-y',                      # Overwrite output
            output_path
        ]
        
        print(f"🛠️ Running command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✨ Encoding successful")
            # Get accurate file sizes in bytes
            original_size = os.path.getsize(input_path)
            print(f"📊 Original size: {original_size:,} bytes ({original_size/1024/1024:.2f}MB)")
            
            # After encoding
            encoded_size = os.path.getsize(output_path)
            size_change = encoded_size - original_size
            ratio = (size_change / original_size) * 100
            
            print(f"📊 Encoding metrics:")
            print(f"   Original: {original_size:,} bytes ({original_size/1024/1024:.2f}MB)")
            print(f"   Encoded:  {encoded_size:,} bytes ({encoded_size/1024/1024:.2f}MB)")
            print(f"   Change:   {'+' if size_change > 0 else ''}{ratio:.1f}% ({'+' if size_change > 0 else ''}{size_change:,} bytes)")
            
            # Warning if size increased
            if encoded_size > original_size:
                print("⚠️ Warning: Encoded file is larger than original!")
            
            return True
            
        print(f"❌ FFmpeg error: {result.stderr}")
        return False
        
    except Exception as e:
        print(f"❌ Encoding error: {str(e)}")
        return False

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
        logger.error(f"Error processing thumbnail: {str(e)}")
        return None
    
    return image_file  # Return original if no processing needed