import os
import ffmpeg
from django.conf import settings

def compress_video(video_file_path):
    # Create output filename
    filename = os.path.basename(video_file_path)
    name, ext = os.path.splitext(filename)
    output_filename = f"{name}_compressed{ext}"
    
    # Use the same directory as the input file
    output_path = os.path.join(os.path.dirname(video_file_path), output_filename)
    
    print(f"Compressing video from: {video_file_path}")
    print(f"Saving compressed video to: {output_path}")
    
    try:
        # Get video metadata
        probe = ffmpeg.probe(video_file_path)
        video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        width = int(video_info['width'])
        height = int(video_info['height'])
        
        # Set up compression
        stream = ffmpeg.input(video_file_path)
        stream = ffmpeg.output(
            stream, 
            output_path,
            **{
                'c:v': 'libx264',          # Video codec
                'crf': 23,                 # Quality (lower = better)
                'preset': 'medium',        # Compression speed
                'movflags': '+faststart',  # Web optimization
                'c:a': 'aac',             # Audio codec
                'b:a': '128k'             # Audio bitrate
            }
        )
        
        # Run compression
        ffmpeg.run(stream, overwrite_output=True)
        return output_filename
        
    except Exception as e:
        print(f"Error in compress_video: {str(e)}")
        raise