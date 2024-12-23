import praw
import requests
import os
import time
import random
from urllib.parse import urljoin

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Create directories for different types of assets
ASSET_DIRS = {
    'pepe': 'assets/pepe',
    'wojak': 'assets/wojak',
    'reaction': 'assets/reaction',
    'transparent': 'assets/transparent'
}

def create_directories():
    """Create necessary directories if they don't exist"""
    for directory in ASSET_DIRS.values():
        os.makedirs(directory, exist_ok=True)

def download_file(url, filepath):
    """Download a file with proper headers and error handling"""
    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=10)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def scrape_reddit_images():
    """Scrape images from relevant subreddits using PRAW"""
    print("Scraping Reddit content...")
    
    # Initialize Reddit instance
    reddit = praw.Reddit(
        client_id="YOUR_CLIENT_ID",  # You'll need to provide these
        client_secret="YOUR_CLIENT_SECRET",
        user_agent="NEET_Sticker_Scraper/1.0"
    )
    
    subreddits = [
        'NEET',
        'Wojak',
        'pepethefrog',
        'doomer',
        'comfy'
    ]
    
    search_terms = [
        'neet',
        'comfy',
        'pepe',
        'wojak',
        'doomer',
        'cozy',
        'comf'
    ]
    
    for subreddit_name in subreddits:
        print(f"\nSearching r/{subreddit_name}...")
        subreddit = reddit.subreddit(subreddit_name)
        
        try:
            # Get top posts from the subreddit
            for post in subreddit.top(limit=50):
                if hasattr(post, 'url'):
                    url = post.url
                    if url.endswith(('.jpg', '.png', '.gif')):
                        # Create filename
                        ext = os.path.splitext(url)[1]
                        filename = f"reddit_{subreddit_name}_{int(time.time())}_{random.randint(1000, 9999)}{ext}"
                        
                        # Choose appropriate directory based on content
                        if 'pepe' in post.title.lower():
                            save_dir = ASSET_DIRS['pepe']
                        elif 'wojak' in post.title.lower():
                            save_dir = ASSET_DIRS['wojak']
                        else:
                            save_dir = ASSET_DIRS['reaction']
                        
                        filepath = os.path.join(save_dir, filename)
                        
                        print(f"Downloading {filename}...")
                        if download_file(url, filepath):
                            print(f"Successfully downloaded {filename}")
                        
                        time.sleep(random.uniform(1, 2))
            
            # Search for specific terms
            for term in search_terms:
                for post in subreddit.search(term, limit=20):
                    if hasattr(post, 'url'):
                        url = post.url
                        if url.endswith(('.jpg', '.png', '.gif')):
                            ext = os.path.splitext(url)[1]
                            filename = f"reddit_{subreddit_name}_{term}_{int(time.time())}_{random.randint(1000, 9999)}{ext}"
                            
                            if 'pepe' in term or 'pepe' in post.title.lower():
                                save_dir = ASSET_DIRS['pepe']
                            elif 'wojak' in term or 'wojak' in post.title.lower():
                                save_dir = ASSET_DIRS['wojak']
                            else:
                                save_dir = ASSET_DIRS['reaction']
                            
                            filepath = os.path.join(save_dir, filename)
                            
                            print(f"Downloading {filename}...")
                            if download_file(url, filepath):
                                print(f"Successfully downloaded {filename}")
                            
                            time.sleep(random.uniform(1, 2))
        
        except Exception as e:
            print(f"Error processing r/{subreddit_name}: {e}")
        
        time.sleep(random.uniform(2, 3))

def scrape_imgur_gallery():
    """Scrape images from Imgur galleries"""
    print("\nScraping Imgur galleries...")
    
    # List of Imgur gallery IDs known to have NEET/comfy content
    gallery_ids = [
        'neet',
        'comfy',
        'wojak',
        'pepe',
        'doomer'
    ]
    
    for gallery_id in gallery_ids:
        url = f"https://api.imgur.com/3/gallery/search/?q={gallery_id}"
        
        try:
            response = requests.get(url, headers={
                **HEADERS,
                'Authorization': 'Client-ID 6db4a4f2c9f3d9a'  # Public client ID for anonymous access
            })
            response.raise_for_status()
            data = response.json()
            
            for item in data.get('data', []):
                if 'images' in item:
                    for image in item['images']:
                        if image['type'] in ['image/png', 'image/gif', 'image/jpeg']:
                            url = image['link']
                            filename = f"imgur_{gallery_id}_{int(time.time())}_{random.randint(1000, 9999)}{os.path.splitext(url)[1]}"
                            filepath = os.path.join(ASSET_DIRS['reaction'], filename)
                            
                            print(f"Downloading {filename}...")
                            download_file(url, filepath)
                            time.sleep(random.uniform(1, 2))
        
        except Exception as e:
            print(f"Error scraping Imgur gallery '{gallery_id}': {e}")
        
        time.sleep(random.uniform(2, 3))

def main():
    print("Starting asset scraper...")
    print("\nNote: To use this script, you need to:")
    print("1. Install PRAW: pip install praw")
    print("2. Get Reddit API credentials from https://www.reddit.com/prefs/apps")
    print("3. Update the client_id and client_secret in the script")
    
    create_directories()
    scrape_reddit_images()
    scrape_imgur_gallery()
    
    print("\nAsset scraping completed!")
    print("Check the assets directory for downloaded files.")

if __name__ == "__main__":
    main()
