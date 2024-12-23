import svgwrite
import math
import os

def create_base_svg(output_name, width=512, height=512):
    return svgwrite.Drawing(output_name, size=(width, height))

def create_spinning_neet(output_name, duration=3):
    dwg = create_base_svg(output_name)
    
    # Create a container group at the center
    container = dwg.g()
    
    # Create the NEET image
    image = dwg.image('neet_simple.svg',
                     insert=(0, 0),
                     size=(512, 512))
    
    # Add animation using animateTransform
    anim = dwg.animateTransform(
        attributeName="transform",
        type="rotate",
        from_="0 256 256",
        to="360 256 256",
        dur=f"{duration}s",
        repeatCount="indefinite"
    )
    
    image.add(anim)
    container.add(image)
    dwg.add(container)
    dwg.save()

def create_pulsing_neet(output_name, duration=3):
    dwg = create_base_svg(output_name)
    
    # Create the NEET image
    image = dwg.image('neet_simple.svg',
                     insert=(0, 0),
                     size=(512, 512))
    
    # Add scale animation
    anim = dwg.animateTransform(
        attributeName="transform",
        type="scale",
        from_="1 1",
        to="1.2 1.2",
        dur=f"{duration}s",
        repeatCount="indefinite",
        additive="sum"
    )
    
    image.add(anim)
    dwg.add(image)
    dwg.save()

def create_bouncing_neet(output_name, duration=3):
    dwg = create_base_svg(output_name)
    
    # Create the NEET image
    image = dwg.image('neet_simple.svg',
                     insert=(0, 0),
                     size=(512, 512))
    
    # Add vertical bounce animation
    anim = dwg.animate(
        attributeName="y",
        values="0;-30;0",
        dur=f"{duration}s",
        repeatCount="indefinite"
    )
    
    image.add(anim)
    dwg.add(image)
    dwg.save()

if __name__ == "__main__":
    # Create output directory
    os.makedirs('animated_stickers', exist_ok=True)
    
    # Create different animations
    animations = [
        ('spinning_neet.svg', create_spinning_neet),
        ('pulsing_neet.svg', create_pulsing_neet),
        ('bouncing_neet.svg', create_bouncing_neet)
    ]
    
    for filename, create_func in animations:
        output_path = f'animated_stickers/{filename}'
        print(f"Creating {filename}...")
        create_func(output_path)
    
    print("All stickers created successfully!")
    print("Note: These are animated SVGs. To use them as Telegram stickers,")
    print("you'll need to convert them to WebM format using a video converter.")
