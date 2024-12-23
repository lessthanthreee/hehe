from generate_character import ComfyCharacterGenerator
from create_animated_gif import create_unique_animation, generate_effect_combo
from PIL import Image
import os

def create_sticker_variations():
    """Create a full set of animated stickers from our character base"""
    # Create output directory
    os.makedirs('sticker_pack', exist_ok=True)
    
    # Generate base characters
    print("Generating base characters...")
    generator = ComfyCharacterGenerator()
    
    # Expression and accessory combinations
    expressions = ["happy", "sad", "sleepy", "comfy"]
    accessories = ["none", "headphones", "glasses"]
    
    # Generate stickers for each combination
    for expression in expressions:
        for accessory in accessories:
            print(f"\nCreating stickers for {expression} expression with {accessory}")
            
            # Generate base character
            base_img = generator.generate_character(expression, accessory)
            
            # Create 3 variations of each combination
            for i in range(3):
                # Generate effect combination
                effect_combo = generate_effect_combo()
                
                # Create output filename
                output_name = f'sticker_pack/neet_{expression}_{accessory}_{i+1:02d}.gif'
                print(f"Creating {output_name}...")
                
                # Create animated sticker
                create_unique_animation(
                    base_img, 
                    output_name, 
                    effect_combo,
                    duration=2,  # Shorter duration for Telegram
                    fps=30
                )

def convert_to_telegram_format():
    """Convert GIFs to Telegram sticker format"""
    # This function will be implemented later to convert
    # the GIFs to the proper format for Telegram stickers
    pass

def main():
    print("Starting sticker pack creation...")
    create_sticker_variations()
    print("\nSticker pack creation completed!")
    print("Check the sticker_pack directory for the results.")
    print("\nNote: The stickers need to be converted to Telegram format before uploading.")

if __name__ == "__main__":
    main()
