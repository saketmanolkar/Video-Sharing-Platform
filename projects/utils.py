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
    """Video encoding function with detailed metrics"""
    try:
        start_time = datetime.now()
        print(f"🎬 Starting encode at: {start_time}")
        
        # Get input file size
        input_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
        
        # Enhanced probe command for input metrics
        probe_cmd = [
            'ffprobe', 
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration,bit_rate,codec_name,r_frame_rate',
            '-of', 'json',
            input_path
        ]
        
        metrics = {
            'input': {'size_mb': input_size},
            'output': {},
            'compression': {},
            'timing': {}
        }
        
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe_result.returncode == 0:
            video_info = json.loads(probe_result.stdout)
            stream_info = video_info['streams'][0]
            
            # Collect input metrics
            metrics['input'].update({
                'width': stream_info.get('width'),
                'height': stream_info.get('height'),
                'duration': float(stream_info.get('duration', 0)),
                'bitrate': int(stream_info.get('bit_rate', 0)) / 1000,  # Kbps
                'codec': stream_info.get('codec_name'),
                'fps': eval(stream_info.get('r_frame_rate', '0/1'))  # Convert fraction to number
            })
            
            target_width = int(size.split('x')[0])
            scale_filter = f'scale={target_width}:-2'
            
            # Encoding command
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
            
            # Run encoding
            encode_start = datetime.now()
            result = subprocess.run(command, capture_output=True, text=True)
            encode_end = datetime.now()
            
            if result.returncode == 0:
                # Get output metrics
                output_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                
                # Probe output file
                output_probe = subprocess.run(probe_cmd[:-1] + [output_path], 
                                           capture_output=True, text=True)
                if output_probe.returncode == 0:
                    output_info = json.loads(output_probe.stdout)
                    output_stream = output_info['streams'][0]
                    
                    metrics['output'].update({
                        'size_mb': round(output_size, 2),
                        'width': output_stream.get('width'),
                        'height': output_stream.get('height'),
                        'bitrate': int(output_stream.get('bit_rate', 0)) / 1000,  # Kbps
                        'codec': output_stream.get('codec_name')
                    })
                    
                    # Calculate compression metrics
                    metrics['compression'].update({
                        'size_reduction_percent': round((1 - output_size/input_size) * 100, 2),
                        'bitrate_reduction_percent': round((1 - metrics['output']['bitrate']/metrics['input']['bitrate']) * 100, 2)
                    })
                    
                    # Timing metrics
                    encode_duration = (encode_end - encode_start).total_seconds()
                    total_duration = (datetime.now() - start_time).total_seconds()
                    
                    metrics['timing'].update({
                        'encode_duration_sec': round(encode_duration, 2),
                        'total_duration_sec': round(total_duration, 2),
                        'processing_speed': round(metrics['input']['duration'] / encode_duration, 2)  # > 1 means faster than realtime
                    })
                    
                    # Log detailed metrics
                    logger.info("Video Encoding Metrics:")
                    logger.info(json.dumps(metrics, indent=2))
                    
                    print(f"""
🎯 Encoding Complete!
Input: {metrics['input']['width']}x{metrics['input']['height']}, {round(metrics['input']['size_mb'], 2)}MB, {round(metrics['input']['bitrate'])}Kbps
Output: {metrics['output']['width']}x{metrics['output']['height']}, {metrics['output']['size_mb']}MB, {round(metrics['output']['bitrate'])}Kbps
Compression: {metrics['compression']['size_reduction_percent']}% size reduction, {metrics['compression']['bitrate_reduction_percent']}% bitrate reduction
Speed: {metrics['timing']['processing_speed']}x realtime ({metrics['timing']['encode_duration_sec']}s)
                    """)
                    
                    return True
                    
        return False
            
    except Exception as e:
        logger.error(f"❌ Encoding error: {str(e)}")
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