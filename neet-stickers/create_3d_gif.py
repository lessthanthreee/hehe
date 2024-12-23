from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageChops
import math
import os
import colorsys
import numpy as np
import random

def create_3d_rotation_frame(image, angle, scale=1.0):
    """Create a frame with 3D rotation effect"""
    # Calculate dimensions
    width, height = image.size
    diagonal = math.sqrt(width**2 + height**2)
    new_size = int(diagonal * scale)
    
    # Create frame
    frame = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    
    # Apply perspective transformation
    angle_rad = math.radians(angle)
    scale_x = abs(math.cos(angle_rad)) * 0.7 + 0.3
    scale_y = 1.0
    
    # Scale image
    scaled_size = (int(width * scale_x), int(height * scale_y))
    transformed = image.resize(scaled_size, Image.Resampling.LANCZOS)
    
    # Calculate position to center the image
    x = (width - scaled_size[0]) // 2
    y = (height - scaled_size[1]) // 2
    
    # Paste transformed image
    frame.paste(transformed, (x, y), transformed)
    
    # Add holographic effect
    hue = (angle % 360) / 360.0
    rgb = tuple(int(x * 255) for x in colorsys.hsv_to_rgb(hue, 0.5, 1.0))
    overlay = Image.new('RGBA', frame.size, (*rgb, 50))
    frame = Image.alpha_composite(frame, overlay)
    
    # Add glow
    glow = frame.filter(ImageFilter.GaussianBlur(5))
    glow = ImageEnhance.Brightness(glow).enhance(1.5)
    frame = Image.alpha_composite(glow, frame)
    
    # Add particle effects
    if angle % 45 < 5:  # Add particles at certain angles
        particles = Image.new('RGBA', frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(particles)
        for _ in range(20):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(2, 5)
            color = (*rgb, random.randint(100, 200))
            draw.ellipse([x, y, x+size, y+size], fill=color)
        particles = particles.filter(ImageFilter.GaussianBlur(1))
        frame = Image.alpha_composite(frame, particles)
    
    return frame

def create_3d_animation(input_image_path, output_path, duration=3, fps=30):
    """Create a 3D spinning animation"""
    print(f"Loading image from {input_image_path}")
    base_img = Image.open(input_image_path).convert('RGBA')
    
    # Resize if needed
    max_size = 512
    if max(base_img.size) > max_size:
        ratio = max_size / max(base_img.size)
        new_size = tuple(int(dim * ratio) for dim in base_img.size)
        base_img = base_img.resize(new_size, Image.Resampling.LANCZOS)
    
    print("Creating frames...")
    frames = []
    total_frames = duration * fps
    
    for i in range(total_frames):
        if i % 10 == 0:  # Progress indicator
            print(f"Processing frame {i+1}/{total_frames}")
            
        # Calculate rotation angle
        angle = (i / total_frames) * 360
        
        # Create frame with 3D effect
        frame = create_3d_rotation_frame(
            base_img,
            angle,
            scale=1.0 + 0.1 * math.sin(2 * math.pi * i / total_frames)
        )
        
        frames.append(frame)
    
    print("Saving animation...")
    # Save as GIF
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000/fps),
        loop=0,
        optimize=False
    )
    print(f"Animation saved to {output_path}")

if __name__ == "__main__":
    # Create output directory
    os.makedirs('animated_gifs', exist_ok=True)
    
    # Create animation
    input_path = 'input/character.png'  # Using existing PNG file
    output_path = 'animated_gifs/neet_3d_spin.gif'
    
    create_3d_animation(input_path, output_path, duration=3, fps=30)
