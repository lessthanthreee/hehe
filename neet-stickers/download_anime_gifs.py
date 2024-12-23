import requests
import os
import json
import time
from urllib.parse import urlencode
import shutil

TENOR_API_KEY = "AIzaSyDURhjkVWnp9oBQxCwBxVpKR4__PQ2zifk"
SAVE_DIR = "meme_gifs"

def create_save_directory():
    """Create directory to save GIFs if it doesn't exist"""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

def search_tenor_gifs(search_term, limit=50, pos=""):
    """Search Tenor for GIFs"""
    endpoint = "https://tenor.googleapis.com/v2/search"
    params = {
        "q": search_term,
        "key": TENOR_API_KEY,
        "limit": limit,
        "pos": pos,
        "media_filter": "minimal",
        "contentfilter": "medium"
    }
    
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error searching Tenor: {e}")
        return None

def download_gif(url, filename):
    """Download a GIF file"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(filename, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        return True
    except requests.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return False

def download_meme_gifs(total_gifs=100):
    """Download NEET and meme GIFs from Tenor"""
    create_save_directory()
    
    search_terms = [
        "neet meme",
        "pepe comfy",
        "wojak neet",
        "doomer meme",
        "cozy pepe",
        "comfy wojak",
        "pepe sticker",
        "wojak sticker",
        "comfy meme",
        "doomer wojak",
        "pepe transparent",
        "wojak transparent",
        "neet life",
        "comfy pepe sticker",
        "wojak reaction"
    ]
    
    downloaded_count = 0
    pos = ""
    
    while downloaded_count < total_gifs:
        for search_term in search_terms:
            if downloaded_count >= total_gifs:
                break
                
            print(f"\nSearching for '{search_term}'...")
            results = search_tenor_gifs(search_term, limit=50, pos=pos)
            
            if not results:
                continue
            
            for result in results.get('results', []):
                if downloaded_count >= total_gifs:
                    break
                
                try:
                    # Get the GIF URL from the media formats
                    media_formats = result.get('media_formats', {})
                    if 'gif' in media_formats:
                        gif_url = media_formats['gif']['url']
                    else:
                        continue
                    
                    # Create filename
                    filename = f"{SAVE_DIR}/meme_{downloaded_count+1:03d}.gif"
                    
                    print(f"Downloading {filename}...")
                    if download_gif(gif_url, filename):
                        downloaded_count += 1
                        print(f"Progress: {downloaded_count}/{total_gifs}")
                        
                        # Add small delay to avoid rate limiting
                        time.sleep(0.5)
                
                except (KeyError, IndexError) as e:
                    print(f"Error processing result: {e}")
                    continue
            
            # Update position for next batch
            pos = results.get('next', "")
            
            # Add delay between searches
            time.sleep(1)
    
    print(f"\nDownloaded {downloaded_count} meme GIFs successfully!")

if __name__ == "__main__":
    print("Starting NEET meme GIF downloader...")
    # Download 100 GIFs
    download_meme_gifs(total_gifs=100)
