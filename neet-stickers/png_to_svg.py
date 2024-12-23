from PIL import Image, ImageOps
import svgwrite
import os

def convert_png_to_svg(input_path, output_path):
    # Open the image and ensure RGBA mode
    img = Image.open(input_path).convert('RGBA')
    width, height = img.size
    
    # Create SVG drawing
    dwg = svgwrite.Drawing(output_path, size=(width, height))
    
    # Create main group for the image
    main_group = dwg.g()
    
    # Process image in chunks to reduce complexity
    chunk_size = 10  # Process 10x10 pixel chunks
    for y in range(0, height, chunk_size):
        for x in range(0, width, chunk_size):
            # Get chunk bounds
            x2 = min(x + chunk_size, width)
            y2 = min(y + chunk_size, height)
            
            # Get chunk region
            region = img.crop((x, y, x2, y2))
            region_data = region.getdata()
            
            # Calculate average color for the chunk
            r_sum = g_sum = b_sum = a_sum = 0
            pixel_count = 0
            
            for pixel in region_data:
                r_sum += pixel[0]
                g_sum += pixel[1]
                b_sum += pixel[2]
                a_sum += pixel[3]
                pixel_count += 1
            
            if pixel_count > 0:
                r_avg = r_sum // pixel_count
                g_avg = g_sum // pixel_count
                b_avg = b_sum // pixel_count
                a_avg = a_sum // pixel_count
                
                if a_avg > 0:  # Only draw visible chunks
                    # Create rectangle for the chunk
                    rect = dwg.rect(
                        insert=(x, y),
                        size=(x2-x, y2-y),
                        fill=f'rgb({r_avg},{g_avg},{b_avg})',
                        fill_opacity=a_avg/255
                    )
                    main_group.add(rect)
    
    # Add the main group to the drawing
    dwg.add(main_group)
    
    # Save the SVG file
    dwg.save()
    print(f"SVG file created: {output_path}")

if __name__ == "__main__":
    input_file = "../neet.png"
    output_svg = "neet_simple.svg"
    
    # Convert PNG to SVG
    convert_png_to_svg(input_file, output_svg)
    
    print("Conversion complete!")
