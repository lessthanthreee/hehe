import cv2
import numpy as np
from moviepy.editor import VideoFileClip
import os

def prepare_animated_sticker(input_path, output_path, target_size=(512, 512)):
    """
    Convert and prepare animated sticker according to Telegram requirements:
    - Must be WebM format (VP9 codec)
    - Max size: 512x512
    - Max length: 3 seconds
    - Should be looped
    - Must have transparent background
    """
    # Load the video
    clip = VideoFileClip(input_path)
    
    # Resize to target size
    clip_resized = clip.resize(target_size)
    
    # Ensure max duration is 3 seconds
    if clip.duration > 3:
        clip_resized = clip_resized.subclip(0, 3)
    
    # Save as WebM with VP9 codec
    clip_resized.write_videofile(
        output_path,
        codec='libvpx-vp9',
        fps=30,
        bitrate='1000k',
        audio=False,
        ffmpeg_params=[
            '-auto-alt-ref', '0',
            '-deadline', 'best',
            '-cpu-used', '0'
        ]
    )
    
    clip.close()
    clip_resized.close()

def process_folder(input_folder, output_folder):
    """Process all animations in a folder"""
    os.makedirs(output_folder, exist_ok=True)
    
    for filename in os.listdir(input_folder):
        if filename.endswith(('.gif', '.mp4')):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, f"{os.path.splitext(filename)[0]}.webm")
            try:
                prepare_animated_sticker(input_path, output_path)
                print(f"Successfully converted {filename}")
            except Exception as e:
                print(f"Error converting {filename}: {e}")

if __name__ == "__main__":
    # Create directories if they don't exist
    os.makedirs("raw_animations", exist_ok=True)
    os.makedirs("animated_stickers", exist_ok=True)
    
    # Process animations
    process_folder("raw_animations", "animated_stickers")
