import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import requests
import random
import math
from download_anime_gifs import download_meme_gifs, SAVE_DIR

# Telegram sticker requirements
MAX_SIZE = 512  # Maximum dimension
TARGET_SIZE = (512, 512)  # Target size for stickers
OUTPUT_DIR = "telegram_stickers"

# NEET-themed captions
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
    "stay comfy",
    "peak neet",
    "maximum comf"
]

def resize_for_telegram(image):
    """Resize image to meet Telegram sticker requirements"""
    # Get original dimensions
    width, height = image.size
    
    # Calculate scaling factor
    scale = min(MAX_SIZE / width, MAX_SIZE / height)
    
    # Calculate new dimensions
    new_width = int(width * scale)
    new_height = int(height * scale)
    
    # Resize image
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Create new image with padding to reach target size
    final = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
    
    # Calculate position to paste resized image
    x = (TARGET_SIZE[0] - new_width) // 2
    y = (TARGET_SIZE[1] - new_height) // 2
    
    # Paste resized image
    final.paste(resized, (x, y))
    
    return final

def add_neet_effects(frame, progress):
    """Add NEET-themed visual effects to a frame"""
    # Random color tint
    enhancer = ImageEnhance.Color(frame)
    frame = enhancer.enhance(1.2)  # Slightly boost colors
    
    # Add slight glow effect
    frame = frame.filter(ImageFilter.GaussianBlur(radius=0.5))
    enhancer = ImageEnhance.Brightness(frame)
    frame = enhancer.enhance(1.1)  # Slight brightness boost
    
    # Add comfy vignette effect
    width, height = frame.size
    vignette = Image.new('RGBA', frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)
    
    # Create radial gradient for vignette
    for i in range(min(width, height) // 2):
        alpha = int(255 * (i / (min(width, height) // 2)) ** 2)
        draw.ellipse([i, i, width - i, height - i], 
                    fill=(0, 0, 0, 255 - alpha))
    
    # Blend vignette with frame
    frame = Image.alpha_composite(frame, vignette)
    
    return frame

def add_neet_text(frame, progress):
    """Add NEET-themed text overlay"""
    draw = ImageDraw.Draw(frame)
    width, height = frame.size
    
    # Choose a random caption
    text = random.choice(CAPTIONS)
    
    # Calculate text position with some movement
    angle = progress * 2 * math.pi
    x = width // 2 + int(10 * math.sin(angle))
    y = height * 0.8 + int(5 * math.cos(angle))
    
    # Add text shadow for better visibility
    shadow_color = (0, 0, 0, 180)
    text_color = (255, 255, 255, 255)
    
    # Try to use a meme-friendly font, fallback to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    # Draw shadow
    draw.text((x+2, y+2), text, font=font, fill=shadow_color, anchor="mm")
    # Draw main text
    draw.text((x, y), text, font=font, fill=text_color, anchor="mm")
    
    return frame

def convert_to_telegram_sticker(input_path, output_path):
    """Convert a GIF to a Telegram-compatible sticker with NEET effects"""
    try:
        # Open original GIF
        with Image.open(input_path) as img:
            # Get frame count
            frames = []
            durations = []
            n_frames = 0
            
            try:
                while True:
                    # Convert frame to RGBA if necessary
                    if img.mode != 'RGBA':
                        frame = img.convert('RGBA')
                    else:
                        frame = img.copy()
                    
                    # Calculate progress for effects
                    progress = n_frames / (img.n_frames if hasattr(img, 'n_frames') else 1)
                    
                    # Resize frame
                    frame = resize_for_telegram(frame)
                    
                    # Add NEET effects
                    frame = add_neet_effects(frame, progress)
                    
                    # Add text overlay
                    if random.random() < 0.7:  # 70% chance to add text
                        frame = add_neet_text(frame, progress)
                    
                    frames.append(frame)
                    durations.append(img.info.get('duration', 100))  # Default to 100ms if duration not found
                    
                    img.seek(img.tell() + 1)
                    n_frames += 1
            except EOFError:
                pass  # We've hit the end of the frames
            
            # Save as animated webp (Telegram sticker format)
            frames[0].save(
                output_path,
                format='WEBP',
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                quality=95,
                method=6,  # Maximum compression
                lossless=True,
                exact=True
            )
            return True
    except Exception as e:
        print(f"Error converting {input_path}: {str(e)}")
        return False

def create_sticker_pack():
    """Create a complete sticker pack from downloaded GIFs"""
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # First, download some GIFs if we don't have any
    if not os.path.exists(SAVE_DIR) or len(os.listdir(SAVE_DIR)) == 0:
        print("Downloading NEET meme GIFs...")
        download_meme_gifs(total_gifs=20)  # Start with 20 GIFs
    
    # Process each GIF
    successful_conversions = 0
    for gif_file in os.listdir(SAVE_DIR):
        if not gif_file.endswith('.gif'):
            continue
            
        input_path = os.path.join(SAVE_DIR, gif_file)
        output_name = f"neet_sticker_{os.path.splitext(gif_file)[0]}.webp"
        output_path = os.path.join(OUTPUT_DIR, output_name)
        
        print(f"Converting {gif_file} to Telegram sticker format...")
        if convert_to_telegram_sticker(input_path, output_path):
            successful_conversions += 1
            print(f"Successfully created sticker: {output_name}")

    print(f"\nSticker pack creation complete! Created {successful_conversions} stickers in the '{OUTPUT_DIR}' directory.")
    if successful_conversions > 0:
        print("\nTo add these stickers to Telegram:")
        print("1. Contact @Stickers bot on Telegram")
        print("2. Send /newpack command")
        print("3. Choose a name for your pack")
        print("4. Send each .webp file as a document")
        print("5. Send /publish command when done")

if __name__ == "__main__":
    print("Starting NEET sticker pack creation...")
    create_sticker_pack()
