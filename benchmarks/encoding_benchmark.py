#!/usr/bin/env python
import os
import json
import time
import psutil
import statistics
import subprocess
from datetime import datetime
import argparse
import logging

# Setup logging like in your Django code
logger = logging.getLogger(__name__)

def encode_video_with_preset(input_path, output_path, size, preset):
    """Video encoding function with resource usage monitoring - focused on preset testing"""
    try:
        start_time = datetime.now()
        print(f"🎬 Starting encode with preset '{preset}' at: {start_time}")
        
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
            'resource_usage': {}  # Added for resource monitoring
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
            
            # Encoding command - using your exact same parameters except preset
            command = [
                'ffmpeg', '-i', input_path,
                '-c:v', 'libx264',
                '-preset', preset,  # This is the parameter we're testing
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
            
            # Resource tracking variables
            cpu_percentages = []
            ram_usage_mb = []
            
            # Run encoding with resource monitoring
            encode_start = datetime.now()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Get the process to monitor
            proc = psutil.Process(process.pid)
            
            # Monitor resources while encoding is running
            while process.poll() is None:
                try:
                    # CPU percentage for this process
                    cpu_percent = proc.cpu_percent(interval=0.5)
                    cpu_percentages.append(cpu_percent)
                    
                    # Memory usage in MB
                    memory_info = proc.memory_info()
                    ram_mb = memory_info.rss / (1024 * 1024)
                    ram_usage_mb.append(ram_mb)
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process might have ended
                    break
            
            stdout, stderr = process.communicate()
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
                    
                    # Add resource usage metrics
                    if cpu_percentages and ram_usage_mb:
                        metrics['resource_usage'] = {
                            'avg_cpu_percent': round(sum(cpu_percentages) / len(cpu_percentages), 2),
                            'max_cpu_percent': round(max(cpu_percentages), 2),
                            'avg_ram_mb': round(sum(ram_usage_mb) / len(ram_usage_mb), 2),
                            'max_ram_mb': round(max(ram_usage_mb), 2)
                        }
                    
                    # Log detailed metrics
                    logger.info(f"Video Encoding Metrics for preset '{preset}':")
                    logger.info(json.dumps(metrics, indent=2))
                    
                    print(f"""
🎯 Encoding Complete!
Preset: {preset}
Input: {metrics['input']['width']}x{metrics['input']['height']}, {round(metrics['input']['size_mb'], 2)}MB, {round(metrics['input']['bitrate'])}Kbps
Output: {metrics['output']['width']}x{metrics['output']['height']}, {metrics['output']['size_mb']}MB, {round(metrics['output']['bitrate'])}Kbps
Compression: {metrics['compression']['size_reduction_percent']}% size reduction, {metrics['compression']['bitrate_reduction_percent']}% bitrate reduction
Speed: {metrics['timing']['processing_speed']}x realtime ({metrics['timing']['encode_duration_sec']}s)
CPU: {metrics['resource_usage']['avg_cpu_percent']}% avg, {metrics['resource_usage']['max_cpu_percent']}% max
RAM: {metrics['resource_usage']['avg_ram_mb']} MB avg, {metrics['resource_usage']['max_ram_mb']} MB max
                    """)
                    
                    return metrics
        
        print(f"❌ Encoding failed for preset '{preset}'")
        return None
            
    except Exception as e:
        logger.error(f"❌ Encoding error with preset '{preset}': {str(e)}")
        return None

def benchmark_presets(input_path, output_dir, iterations=5):
    """Benchmark different preset values"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Define presets to test - include 'faster' since it's your current setting
    presets = ['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow']
    
    results = []
    
    for preset in presets:
        print(f"\n\n==== BENCHMARKING PRESET: {preset} ====")
        
        preset_results = []
        
        for i in range(iterations):
            print(f"\n--- Run {i+1}/{iterations} ---")
            output_path = os.path.join(output_dir, f"preset_{preset}_run{i+1}.mp4")
            
            # Run encoding
            metrics = encode_video_with_preset(input_path, output_path, "1280x720", preset)
            
            if metrics:
                preset_results.append(metrics)
        
        # Calculate averages across iterations
        if preset_results:
            avg_result = {
                'preset': preset,
                'cpu_avg': round(statistics.mean([r['resource_usage']['avg_cpu_percent'] for r in preset_results]), 2),
                'ram_avg': round(statistics.mean([r['resource_usage']['avg_ram_mb'] for r in preset_results]), 2),
                'cpu_max': round(statistics.mean([r['resource_usage']['max_cpu_percent'] for r in preset_results]), 2),
                'ram_max': round(statistics.mean([r['resource_usage']['max_ram_mb'] for r in preset_results]), 2),
                'time': round(statistics.mean([r['timing']['encode_duration_sec'] for r in preset_results]), 2),
                'speed': round(statistics.mean([r['timing']['processing_speed'] for r in preset_results]), 2),
                'size': round(statistics.mean([r['output']['size_mb'] for r in preset_results]), 2),
                'compression': round(statistics.mean([r['compression']['size_reduction_percent'] for r in preset_results]), 2)
            }
            
            results.append(avg_result)
    
    # Print summary table
    print("\n\n📊 PRESET BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"{'Preset':<10} {'CPU Avg%':<10} {'RAM (MB)':<10} {'Time (s)':<10} {'Speed (x)':<10} {'Size (MB)':<10} {'Comp %':<10}")
    print("-" * 80)
    
    # Sort by encoding time (fastest first)
    results.sort(key=lambda x: x['time'])
    
    for result in results:
        print(f"{result['preset']:<10} {result['cpu_avg']:<10} {result['ram_avg']:<10} {result['time']:<10} {result['speed']:<10} {result['size']:<10} {result['compression']:<10}")
    
    print("=" * 80)
    
    # Save results to file
    results_file = os.path.join(output_dir, "preset_benchmark_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to {results_file}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Video Encoding Preset Benchmark")
    parser.add_argument("input_video", help="Path to input video file")
    parser.add_argument("--output-dir", default="preset_benchmark_results", help="Output directory")
    parser.add_argument("--iterations", type=int, default=5, help="Iterations per preset")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                       help="Logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print(f"🚀 Starting video encoding preset benchmark")
    print(f"Input video: {args.input_video}")
    print(f"Output directory: {args.output_dir}")
    print(f"Iterations per preset: {args.iterations}")
    
    # Run the benchmark
    benchmark_presets(args.input_video, args.output_dir, args.iterations)

if __name__ == "__main__":
    main()
