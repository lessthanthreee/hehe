import subprocess
import os
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def setup_html_renderer():
    """Create an HTML file to render Lottie animations"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.7.14/lottie.min.js"></script>
        <style>
            #animation-container {
                width: 512px;
                height: 512px;
                background: transparent;
            }
        </style>
    </head>
    <body style="margin: 0; background: transparent;">
        <div id="animation-container"></div>
        <script>
            function loadAnimation(jsonData) {
                const animationContainer = document.getElementById('animation-container');
                const anim = lottie.loadAnimation({
                    container: animationContainer,
                    renderer: 'svg',
                    loop: true,
                    autoplay: true,
                    animationData: jsonData
                });
            }
        </script>
    </body>
    </html>
    """
    with open("lottie_renderer.html", "w") as f:
        f.write(html_content)

def convert_lottie_to_webm(lottie_file, output_file):
    """Convert a Lottie JSON file to WebM format"""
    # Setup Chrome options for headless rendering
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=512,512")
    chrome_options.add_argument("--transparent-background")
    
    # Create HTML renderer if it doesn't exist
    if not os.path.exists("lottie_renderer.html"):
        setup_html_renderer()
    
    # Load Lottie JSON
    with open(lottie_file, 'r') as f:
        lottie_data = json.load(f)
    
    # Start Chrome and render animation
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.get(f"file://{os.path.abspath('lottie_renderer.html')}")
        driver.execute_script(f"loadAnimation({json.dumps(lottie_data)})")
        
        # Wait for animation to render
        time.sleep(3)
        
        # Capture video using ffmpeg
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-f', 'image2pipe',
            '-r', '30',  # 30 fps
            '-i', '-',  # Read from pipe
            '-c:v', 'libvpx-vp9',
            '-pix_fmt', 'yuva420p',
            '-t', '3',  # 3 seconds duration
            '-b:v', '1M',
            output_file
        ]
        
        # Capture frames and pipe to ffmpeg
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for _ in range(90):  # 3 seconds at 30fps
            driver.save_screenshot(proc.stdin)
            time.sleep(1/30)
        
        proc.stdin.close()
        proc.wait()
        
    finally:
        driver.quit()

def process_all_lottie_files():
    """Process all Lottie JSON files in the lottie_animations directory"""
    lottie_dir = "lottie_animations"
    output_dir = "animated_stickers"
    
    os.makedirs(output_dir, exist_ok=True)
    
    for file in os.listdir(lottie_dir):
        if file.endswith('.json'):
            input_path = os.path.join(lottie_dir, file)
            output_path = os.path.join(output_dir, f"{os.path.splitext(file)[0]}.webm")
            try:
                convert_lottie_to_webm(input_path, output_path)
                print(f"Successfully converted {file}")
            except Exception as e:
                print(f"Error converting {file}: {e}")

if __name__ == "__main__":
    process_all_lottie_files()
