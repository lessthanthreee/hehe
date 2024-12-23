from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageEnhance, ImageFilter
import math
import os
import colorsys
import random
import numpy as np

CAPTIONS = [
    "comfy neet life",
    "wagmi",
    "ngmi",
    "touch grass",
    "just neet it",
    "neetpilled",
    "comfy gains",
    ">be me",
    "anon pls",
    "based neet",
    "ngmi normie",
    "cope harder",
    "neet vibes",
    "comfy mode",
    "neet energy",
    "stay comfy",
    "neet lyfe",
    "no work only neet",
    "neet mode: activated",
    "maximum comf"
]

COLORS = [
    (255, 0, 128),  # Hot pink
    (0, 255, 128),  # Cyber green
    (128, 0, 255),  # Purple
    (255, 128, 0),  # Orange
    (0, 128, 255),  # Sky blue
    (255, 0, 255),  # Magenta
    (0, 255, 255),  # Cyan
    (255, 255, 0),  # Yellow
]

def random_color(alpha=255):
    color = random.choice(COLORS)
    return color + (alpha,)

def clean_frame(size):
    """Create a clean transparent frame"""
    return Image.new('RGBA', size, (0, 0, 0, 0))

def add_text(frame, text, position, size=40, color=(255, 255, 255, 255), glow_color=(0, 0, 0, 100)):
    """Add text with glow effect"""
    draw = ImageDraw.Draw(frame)
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except:
        font = ImageFont.load_default()
    
    # Add glow/shadow effect
    for dx in [-2, -1, 0, 1, 2]:
        for dy in [-2, -1, 0, 1, 2]:
            if dx != 0 or dy != 0:
                draw.text((position[0]+dx, position[1]+dy), text, glow_color, font=font)
    
    # Draw main text
    draw.text(position, text, color, font=font)

def create_effect_variation(base_img, effect_type, params=None):
    """Create a variation of an effect based on parameters"""
    if params is None:
        params = {}
    
    width, height = base_img.size
    frame = clean_frame((width, height))
    
    if effect_type == "glitch":
        intensity = params.get('intensity', 0.2)
        channels = base_img.split()
        for i, channel in enumerate(channels[:3]):
            offset = int(random.gauss(0, intensity * width))
            shifted = ImageChops.offset(channel, offset, 0)
            frame.paste(shifted, mask=shifted)
        frame.putalpha(channels[3])
    
    elif effect_type == "rainbow":
        hue = params.get('hue', random.random())
        rgb = tuple(int(x * 255) for x in colorsys.hsv_to_rgb(hue, 0.8, 1.0))
        overlay = Image.new('RGBA', base_img.size, rgb + (100,))
        frame = Image.alpha_composite(base_img, overlay)
    
    elif effect_type == "wave":
        angle = params.get('angle', 0)
        amplitude = params.get('amplitude', 10)
        offset_x = int(amplitude * math.sin(angle))
        offset_y = int(amplitude * math.cos(angle))
        frame.paste(base_img, (offset_x, offset_y), base_img)
    
    elif effect_type == "zoom":
        scale = params.get('scale', 1.2)
        new_size = (int(width * scale), int(height * scale))
        zoomed = base_img.resize(new_size, Image.Resampling.LANCZOS)
        x = (width - new_size[0]) // 2
        y = (height - new_size[1]) // 2
        frame.paste(zoomed, (x, y), zoomed)
    
    elif effect_type == "spin":
        angle = params.get('angle', 0)
        rotated = base_img.rotate(angle, expand=False)
        frame.paste(rotated, (0, 0), rotated)
    
    elif effect_type == "pixel":
        block_size = params.get('block_size', 8)
        small = base_img.resize((width//block_size, height//block_size), Image.Resampling.NEAREST)
        pixelated = small.resize((width, height), Image.Resampling.NEAREST)
        frame.paste(pixelated, (0, 0), pixelated)
    
    return frame

def create_unique_animation(base_img, output_name, effect_combo, duration=3, fps=30):
    """Create a unique animation from a base image with given effects"""
    # Load the base image
    if isinstance(base_img, str):
        base_img = Image.open(base_img)
    
    # Convert to RGBA if needed
    if base_img.mode != 'RGBA':
        base_img = base_img.convert('RGBA')
    
    # Get dimensions
    width, height = base_img.size
    frame_count = int(duration * fps)
    
    # Create frames list
    frames = []
    
    for i in range(frame_count):
        # Create a new frame
        frame = base_img.copy()
        
        # Apply each effect in the combo
        for effect, params in effect_combo:
            # Update params with current frame info if needed
            if params is None:
                params = {}
            params.update({
                'frame': i,
                'total_frames': frame_count,
                'progress': i / frame_count
            })
            
            # Apply the effect
            frame = create_effect_variation(frame, effect, params)
        
        frames.append(frame)
    
    # Save the animation
    frames[0].save(
        output_name,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000/fps),  # Duration in ms
        loop=0
    )

def generate_effect_combo():
    """Generate a random combination of effects with parameters"""
    effects = [
        ("glitch", lambda p, a: {'intensity': 0.1 + 0.2 * abs(math.sin(a))}),
        ("rainbow", lambda p, a: {'hue': p}),
        ("wave", lambda p, a: {'angle': a, 'amplitude': 5 + 15 * abs(math.sin(a))}),
        ("zoom", lambda p, a: {'scale': 1.0 + 0.3 * abs(math.sin(a))}),
        ("spin", lambda p, a: {'angle': 360 * p}),
        ("pixel", {'block_size': random.randint(4, 16)})
    ]
    
    # Choose 2-3 effects to combine
    num_effects = random.randint(2, 3)
    combo = random.sample(effects, num_effects)
    
    return combo

if __name__ == "__main__":
    # Create output directory
    os.makedirs('animated_gifs', exist_ok=True)
    
    # Load and prepare base image
    print("Loading base image...")
    base_img = Image.open('../neet.png').convert('RGBA')
    
    # Resize to 512x512 if needed
    if base_img.size != (512, 512):
        base_img = base_img.resize((512, 512), Image.Resampling.LANCZOS)
    
    # Generate 50 unique variations
    print("Generating 50 unique sticker variations...")
    for i in range(50):
        effect_combo = generate_effect_combo()
        output_name = f'animated_gifs/neet_variation_{i+1:02d}.gif'
        print(f"Creating {output_name}...")
        create_unique_animation(base_img, output_name, effect_combo)
    
    print("All GIF stickers created successfully!")
    print("Check the animated_gifs directory for the results.")
