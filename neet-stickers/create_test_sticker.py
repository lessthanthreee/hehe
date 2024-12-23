from PIL import Image, ImageDraw, ImageFont
import math
import os
from colorsys import hsv_to_rgb

def create_frame(size, text, angle, frame_num, total_frames):
    # Create a new image with transparency
    image = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Calculate position
    center = (size[0] // 2, size[1] // 2)
    radius = 100
    x = center[0] + int(radius * math.cos(angle))
    y = center[1] + int(radius * math.sin(angle))
    
    # Create rainbow color effect
    hue = frame_num / total_frames
    rgb = hsv_to_rgb(hue, 1.0, 1.0)
    color = (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255), 255)
    
    # Draw background circle
    circle_radius = 30
    draw.ellipse(
        [x - circle_radius, y - circle_radius, 
         x + circle_radius, y + circle_radius],
        fill=(0, 0, 0, 128)
    )
    
    # Draw text with outline
    font_size = 48
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    # Draw text outline
    outline_color = (0, 0, 0, 255)
    for offset_x, offset_y in [(1,1), (-1,-1), (1,-1), (-1,1)]:
        draw.text((x - font_size/2 + offset_x, y - font_size/2 + offset_y), 
                 text, font=font, fill=outline_color)
    
    # Draw main text
    draw.text((x - font_size/2, y - font_size/2), text, 
              font=font, fill=color)
    
    return image

def create_test_animation():
    # Parameters
    size = (512, 512)
    frames = []
    duration = 3  # seconds
    fps = 30
    total_frames = fps * duration
    
    # Create frames
    for i in range(total_frames):
        angle = (i / total_frames) * 2 * math.pi
        frame = create_frame(size, "NEET", angle, i, total_frames)
        frames.append(frame)
    
    # Save as GIF first
    os.makedirs('test_stickers', exist_ok=True)
    frames[0].save(
        'test_stickers/test.gif',
        save_all=True,
        append_images=frames[1:],
        duration=int(1000/fps),
        loop=0
    )
    
    # Convert to WebM using ffmpeg
    os.system('ffmpeg -i test_stickers/test.gif -c:v libvpx-vp9 -pix_fmt yuva420p test_stickers/test.webm')
    
    print("Animation created successfully!")

if __name__ == "__main__":
    create_test_animation()
