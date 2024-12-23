import cv2
import numpy as np
from rembg import remove
import mediapipe as mp
from PIL import Image
import os

class Live2DLayerPreparator:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )

    def remove_background(self, image_path):
        """Remove background from image using rembg"""
        input_image = Image.open(image_path)
        output_image = remove(input_image)
        return output_image

    def extract_face_landmarks(self, image):
        """Extract facial landmarks using MediaPipe"""
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(image_rgb)
        return results.multi_face_landmarks[0] if results.multi_face_landmarks else None

    def separate_layers(self, image_path, output_dir):
        """Separate image into layers for Live2D"""
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Remove background
        image_no_bg = self.remove_background(image_path)
        image_np = np.array(image_no_bg)

        # Save base image without background
        cv2.imwrite(os.path.join(output_dir, "base.png"), cv2.cvtColor(image_np, cv2.COLOR_RGBA2BGRA))

        # Extract face landmarks
        landmarks = self.extract_face_landmarks(image_np)
        
        if landmarks:
            # Create mask for different facial features
            height, width = image_np.shape[:2]
            
            # Eyes mask
            eyes_mask = np.zeros((height, width), dtype=np.uint8)
            for idx in [33, 133, 157, 158, 159, 160, 161, 246]:  # Eye landmarks
                x = int(landmarks.landmark[idx].x * width)
                y = int(landmarks.landmark[idx].y * height)
                cv2.circle(eyes_mask, (x, y), 5, 255, -1)
            
            # Extract eyes
            eyes_layer = cv2.bitwise_and(image_np, image_np, mask=eyes_mask)
            cv2.imwrite(os.path.join(output_dir, "eyes.png"), cv2.cvtColor(eyes_layer, cv2.COLOR_RGBA2BGRA))

            # Mouth mask
            mouth_mask = np.zeros((height, width), dtype=np.uint8)
            for idx in [0, 17, 61, 291]:  # Mouth landmarks
                x = int(landmarks.landmark[idx].x * width)
                y = int(landmarks.landmark[idx].y * height)
                cv2.circle(mouth_mask, (x, y), 5, 255, -1)
            
            # Extract mouth
            mouth_layer = cv2.bitwise_and(image_np, image_np, mask=mouth_mask)
            cv2.imwrite(os.path.join(output_dir, "mouth.png"), cv2.cvtColor(mouth_layer, cv2.COLOR_RGBA2BGRA))

            # Hair mask (upper part of head)
            hair_mask = np.zeros((height, width), dtype=np.uint8)
            for idx in [10, 338, 297, 332]:  # Hair landmarks
                x = int(landmarks.landmark[idx].x * width)
                y = int(landmarks.landmark[idx].y * height)
                cv2.circle(hair_mask, (x, y), 10, 255, -1)
            
            # Extract hair
            hair_layer = cv2.bitwise_and(image_np, image_np, mask=hair_mask)
            cv2.imwrite(os.path.join(output_dir, "hair.png"), cv2.cvtColor(hair_layer, cv2.COLOR_RGBA2BGRA))

        # Create NEET-specific accessories
        self.create_neet_accessories(output_dir, width, height)

    def create_neet_accessories(self, output_dir, width, height):
        """Create NEET-themed accessories"""
        # Create a hoodie layer
        hoodie = np.zeros((height, width, 4), dtype=np.uint8)
        # Draw a simple hoodie shape
        pts = np.array([[int(width*0.2), int(height*0.4)], 
                       [int(width*0.8), int(height*0.4)],
                       [int(width*0.9), height],
                       [int(width*0.1), height]], np.int32)
        cv2.fillPoly(hoodie, [pts], (100, 100, 100, 255))
        cv2.imwrite(os.path.join(output_dir, "hoodie.png"), hoodie)

        # Create gaming headphones
        headphones = np.zeros((height, width, 4), dtype=np.uint8)
        # Draw simple headphone shapes
        cv2.circle(headphones, (int(width*0.2), int(height*0.3)), 30, (200, 50, 50, 255), -1)
        cv2.circle(headphones, (int(width*0.8), int(height*0.3)), 30, (200, 50, 50, 255), -1)
        cv2.imwrite(os.path.join(output_dir, "headphones.png"), headphones)

def main():
    """Main function to prepare Live2D layers"""
    # Initialize the layer preparator
    preparator = Live2DLayerPreparator()

    # Define input and output paths
    input_image = "input/character.png"  # Replace with your character image
    output_dir = "output/live2d_layers"

    # Process the image and create layers
    preparator.separate_layers(input_image, output_dir)

if __name__ == "__main__":
    main()
