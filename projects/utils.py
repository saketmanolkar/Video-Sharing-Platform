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
import psutil
import time
import threading

logger = logging.getLogger(__name__)

def encode_video(input_path, output_path, size):
    """Video encoding function with detailed metrics including CPU and RAM usage"""
    try:
        # For consistency and debugging, define preset at the start
        preset = "faster"
        
        start_time = datetime.now()
        print(f"🎬 Starting encode at: {start_time} with preset '{preset}'")
        
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
            'timing': {},
            'resource_usage': {},
            'encoding_settings': {'preset': preset}  # Store preset in metrics
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
                '-preset', preset,
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
            
            # Improved resource tracking to work better with fast presets
            cpu_percentages = []
            ram_usage_mb = []
            monitoring_active = True
            
            def monitor_resources():
                # Ensure we have initial CPU reading
                proc.cpu_percent()
                logger.debug(f"Starting resource monitoring for {preset} preset encoding")
                sample_count = 0
                
                while monitoring_active:
                    try:
                        if proc.is_running():
                            # Get CPU usage
                            cpu_percent = proc.cpu_percent(interval=0.1)  # Faster sampling
                            if cpu_percent > 0:  # Skip zero readings
                                cpu_percentages.append(cpu_percent)
                            
                            # Get memory usage
                            memory_info = proc.memory_info()
                            ram_mb = memory_info.rss / (1024 * 1024)
                            ram_usage_mb.append(ram_mb)
                            
                            sample_count += 1
                            # Log more frequently for ultrafast preset
                            if sample_count % 5 == 0:  
                                logger.debug(f"Resource sample {sample_count}: CPU={cpu_percent}%, RAM={ram_mb}MB")
                                
                        time.sleep(0.1)  # Much faster polling for ultrafast preset
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        logger.debug(f"Resource monitoring exception: {str(e)}")
                        break
            
            # Run encoding with resource monitoring
            encode_start = datetime.now()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Get the process to monitor
            proc = psutil.Process(process.pid)
            
            # Start monitoring thread
            monitoring_thread = threading.Thread(target=monitor_resources)
            monitoring_thread.daemon = True
            monitoring_thread.start()
            
            # Wait for encoding to complete
            stdout, stderr = process.communicate()
            
            # Stop resource monitoring
            monitoring_active = False
            monitoring_thread.join(timeout=2)  # Wait for monitoring thread to end
            
            encode_end = datetime.now()
            
            if process.returncode == 0:
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
                    
                    # Calculate resource usage metrics with fallback values
                    if cpu_percentages and ram_usage_mb:
                        # Filter out any extreme outliers (values >3× the median)
                        cpu_median = sorted(cpu_percentages)[len(cpu_percentages)//2]
                        filtered_cpu = [c for c in cpu_percentages if c < cpu_median*3]
                        
                        metrics['resource_usage'] = {
                            'avg_cpu_percent': round(sum(filtered_cpu) / len(filtered_cpu), 2) if filtered_cpu else 0,
                            'max_cpu_percent': round(max(filtered_cpu), 2) if filtered_cpu else 0,
                            'avg_ram_mb': round(sum(ram_usage_mb) / len(ram_usage_mb), 2) if ram_usage_mb else 0,
                            'max_ram_mb': round(max(ram_usage_mb), 2) if ram_usage_mb else 0,
                            'samples_collected': len(cpu_percentages)  # Debugging info
                        }
                        
                        logger.debug(f"Collected {len(cpu_percentages)} CPU samples, {len(ram_usage_mb)} RAM samples")
                    else:
                        # Fallback if no samples were collected
                        logger.warning("No resource samples collected, using fallback values")
                        metrics['resource_usage'] = {
                            'avg_cpu_percent': 0,
                            'max_cpu_percent': 0, 
                            'avg_ram_mb': 0,
                            'max_ram_mb': 0,
                            'samples_collected': 0
                        }
                    
                    # Log detailed metrics
                    logger.info("Video Encoding Metrics:")
                    logger.info(json.dumps(metrics, indent=2))
                    
                    print(f"""
🎯 Encoding Complete!
Preset: {preset}
Input: {metrics['input']['width']}x{metrics['input']['height']}, {round(metrics['input']['size_mb'], 2)}MB, {round(metrics['input']['bitrate'])}Kbps
Output: {metrics['output']['width']}x{metrics['output']['height']}, {metrics['output']['size_mb']}MB, {round(metrics['output']['bitrate'])}Kbps
Compression: {metrics['compression']['size_reduction_percent']}% size reduction, {metrics['compression']['bitrate_reduction_percent']}% bitrate reduction
Speed: {metrics['timing']['processing_speed']}x realtime ({metrics['timing']['encode_duration_sec']}s)
Resource Usage: {metrics['resource_usage']['avg_cpu_percent']}% CPU avg, {metrics['resource_usage']['max_cpu_percent']}% CPU max
               {metrics['resource_usage']['avg_ram_mb']} MB RAM avg, {metrics['resource_usage']['max_ram_mb']} MB RAM max
Samples: {metrics['resource_usage'].get('samples_collected', 0)}
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
        
        print(f"📐 Original dimensions: {width}x{height}")
        
        # Calculate target dimensions for 16:9
        target_ratio = 16/9
        current_ratio = width/height
        
        print(f"📊 Current ratio: {current_ratio:.2f}, Target: {target_ratio:.2f}")
        
        # Always process the image to ensure consistent format
        if abs(current_ratio - target_ratio) > 0.01:  # Need black bars
            if current_ratio > target_ratio:  # Too wide
                new_height = int(width / target_ratio)
                new_width = width
                new_image = Image.new('RGB', (new_width, new_height), (0, 0, 0))
                paste_y = (new_height - height) // 2
                new_image.paste(img, (0, paste_y))
                print(f"↕️ Adding vertical bars: {new_width}x{new_height}")
            else:  # Too tall or square
                new_width = int(height * target_ratio)
                new_height = height
                new_image = Image.new('RGB', (new_width, new_height), (0, 0, 0))
                paste_x = (new_width - width) // 2
                new_image.paste(img, (paste_x, 0))
                print(f"↔️ Adding horizontal bars: {new_width}x{new_height}")
        else:
            print("✨ Image already 16:9, still processing for consistency")
            new_image = img
            
        # Always save to memory
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
        
    except Exception as e:
        print(f"❌ Error processing image: {str(e)}")
        return None