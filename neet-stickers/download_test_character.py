import requests
import os
from PIL import Image
from io import BytesIO
import xml.etree.ElementTree as ET

def download_test_character():
    # Search for a suitable anime character with hoodie/comfy clothing
    search_tags = [
        "1girl hoodie white_background",
        "1girl casual_clothes white_background",
        "1girl comfy white_background"
    ]
    
    base_url = "https://safebooru.org/index.php"
    
    for tags in search_tags:
        try:
            # Search for posts with our tags
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "tags": tags,
                "limit": "10"
            }
            
            print(f"Searching for character with tags: {tags}")
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            posts = root.findall("post")
            
            for post in posts:
                file_url = post.get("file_url")
                if file_url and any(file_url.lower().endswith(ext) for ext in [".jpg", ".png"]):
                    if not file_url.startswith("http"):
                        file_url = f"https:{file_url}"
                    
                    print(f"Downloading image from {file_url}")
                    img_response = requests.get(file_url)
                    img_response.raise_for_status()
                    
                    # Open the image to verify it's valid
                    img = Image.open(BytesIO(img_response.content))
                    
                    # Save the image
                    output_path = os.path.join('input', 'character.png')
                    img.save(output_path, 'PNG')
                    
                    print(f"Successfully downloaded test character to {output_path}")
                    return True
            
        except Exception as e:
            print(f"Failed to download with tags {tags}: {str(e)}")
            continue
    
    print("Failed to download test character from any source")
    return False

if __name__ == "__main__":
    # Ensure input directory exists
    os.makedirs('input', exist_ok=True)
    
    # Download test character
    success = download_test_character()
    
    if success:
        print("\nNext steps:")
        print("1. Run prepare_live2d_layers.py to process the character")
        print("2. Check output/live2d_layers for the generated layers")
        print("3. Import the layers into Live2D Cubism")
    else:
        print("\nPlease manually download an anime character image and save it as 'input/character.png'")
