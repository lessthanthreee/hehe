import os
import subprocess

def convert_to_webm(input_file, output_file):
    """Convert GIF to WebM format suitable for Telegram stickers"""
    # FFmpeg command for converting GIF to WebM with transparency
    command = [
        'ffmpeg',
        '-i', input_file,
        '-c:v', 'libvpx-vp9',
        '-pix_fmt', 'yuva420p',
        '-metadata', 'title="NEET Sticker"',
        '-b:v', '600k',
        '-minrate', '500k',
        '-maxrate', '700k',
        '-crf', '30',
        '-t', '3',  # Limit to 3 seconds (Telegram requirement)
        '-vf', 'scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=#00000000',  # Ensure 512x512
        '-an',  # No audio
        '-f', 'webm',
        output_file
    ]
    
    try:
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_file}: {e}")
        return False

def main():
    # Create output directory
    os.makedirs('telegram_stickers', exist_ok=True)
    
    # Convert all GIFs in sticker_pack directory
    success_count = 0
    total_count = 0
    
    print("Starting conversion to Telegram WebM format...")
    for filename in os.listdir('sticker_pack'):
        if filename.endswith('.gif'):
            total_count += 1
            input_path = os.path.join('sticker_pack', filename)
            output_path = os.path.join('telegram_stickers', filename.replace('.gif', '.webm'))
            
            print(f"Converting {filename} to WebM...")
            if convert_to_webm(input_path, output_path):
                success_count += 1
    
    print(f"\nConversion complete! Successfully converted {success_count} out of {total_count} stickers.")
    print("\nNext steps:")
    print("1. Contact @Stickers bot on Telegram")
    print("2. Use /newpack command to create a new sticker pack")
    print("3. Send each .webm file from the 'telegram_stickers' directory")
    print("4. Use /publish command to make your sticker pack available")

if __name__ == "__main__":
    main()
