from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageEnhance
import random
import math
import colorsys
import os

class ComfyCharacterGenerator:
    def __init__(self):
        self.size = (512, 512)
        self.center = (self.size[0] // 2, self.size[1] // 2)
        
        # NEET-core color palette
        self.colors = {
            'skin': (156, 187, 140),  # Pepe-inspired green
            'blanket': (255, 179, 186),  # Comfy pink
            'hoodie': (80, 80, 80),  # Comfy grey
            'eyes': (255, 255, 255),
            'pupils': (0, 0, 0),
            'blush': (255, 150, 150, 100),
        }

    def _create_base(self):
        """Create the base blob shape with a hoodie"""
        img = Image.new('RGBA', self.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw hoodie shape (slightly larger than head)
        hood_points = [
            (self.center[0] - 150, self.center[1] - 100),  # Top left
            (self.center[0] + 150, self.center[1] - 100),  # Top right
            (self.center[0] + 180, self.center[1] + 150),  # Bottom right
            (self.center[0] - 180, self.center[1] + 150),  # Bottom left
        ]
        draw.polygon(hood_points, fill=self.colors['hoodie'])
        
        # Draw head shape
        head_points = [
            (self.center[0] - 120, self.center[1] - 80),
            (self.center[0] + 120, self.center[1] - 80),
            (self.center[0] + 140, self.center[1] + 100),
            (self.center[0] - 140, self.center[1] + 100),
        ]
        draw.polygon(head_points, fill=self.colors['skin'])
        
        # Add blanket wrap (optional)
        if random.random() > 0.3:  # 70% chance to have blanket
            blanket_points = [
                (self.center[0] - 180, self.center[1] + 50),
                (self.center[0] + 180, self.center[1] + 50),
                (self.center[0] + 200, self.center[1] + 200),
                (self.center[0] - 200, self.center[1] + 200),
            ]
            draw.polygon(blanket_points, fill=self.colors['blanket'])
        
        return img

    def _add_eyes(self, img, expression):
        """Add expressive Pepe-style eyes"""
        draw = ImageDraw.Draw(img)
        
        # Base eye positions
        left_eye_pos = (self.center[0] - 60, self.center[1] - 20)
        right_eye_pos = (self.center[0] + 60, self.center[1] - 20)
        
        if expression == "sleepy":
            # Sleepy half-closed eyes
            for pos in [left_eye_pos, right_eye_pos]:
                draw.ellipse((pos[0]-30, pos[1], pos[0]+30, pos[1]+20), fill=self.colors['eyes'])
                draw.ellipse((pos[0]-20, pos[1]+5, pos[0]+20, pos[1]+15), fill=self.colors['pupils'])
        
        elif expression == "comfy":
            # Happy closed eyes with ^ shape
            for pos in [left_eye_pos, right_eye_pos]:
                points = [
                    (pos[0]-30, pos[1]+10),
                    (pos[0], pos[1]-10),
                    (pos[0]+30, pos[1]+10)
                ]
                draw.line(points, fill=self.colors['pupils'], width=5)
        
        elif expression == "sad":
            # Downturned worried eyes
            for pos in [left_eye_pos, right_eye_pos]:
                draw.ellipse((pos[0]-30, pos[1]-15, pos[0]+30, pos[1]+15), fill=self.colors['eyes'])
                draw.ellipse((pos[0]-20, pos[1]-10, pos[0]+20, pos[1]+20), fill=self.colors['pupils'])
        
        else:  # happy
            # Wide open happy eyes
            for pos in [left_eye_pos, right_eye_pos]:
                draw.ellipse((pos[0]-30, pos[1]-20, pos[0]+30, pos[1]+20), fill=self.colors['eyes'])
                draw.ellipse((pos[0]-25, pos[1]-15, pos[0]+25, pos[1]+15), fill=self.colors['pupils'])
        
        # Add blush
        if expression in ["comfy", "happy"]:
            draw.ellipse((left_eye_pos[0]-40, left_eye_pos[1]+20, left_eye_pos[0], left_eye_pos[1]+60), 
                        fill=self.colors['blush'])
            draw.ellipse((right_eye_pos[0], right_eye_pos[1]+20, right_eye_pos[0]+40, right_eye_pos[1]+60), 
                        fill=self.colors['blush'])
        
        return img

    def _add_mouth(self, img, expression):
        """Add expressive mouth"""
        draw = ImageDraw.Draw(img)
        mouth_center = (self.center[0], self.center[1] + 40)
        
        if expression == "sleepy":
            # Small neutral mouth
            draw.line(
                (mouth_center[0]-20, mouth_center[1], mouth_center[0]+20, mouth_center[1]),
                fill=self.colors['pupils'],
                width=5
            )
        
        elif expression == "comfy":
            # Small happy mouth
            draw.arc(
                [mouth_center[0]-20, mouth_center[1]-10, mouth_center[0]+20, mouth_center[1]+10],
                0, 180,
                fill=self.colors['pupils'],
                width=5
            )
        
        elif expression == "sad":
            # Worried mouth
            draw.arc(
                [mouth_center[0]-30, mouth_center[1], mouth_center[0]+30, mouth_center[1]+30],
                180, 0,
                fill=self.colors['pupils'],
                width=5
            )
        
        else:  # happy
            # Wide smile
            draw.arc(
                [mouth_center[0]-40, mouth_center[1]-20, mouth_center[0]+40, mouth_center[1]+20],
                0, 180,
                fill=self.colors['pupils'],
                width=5
            )
        
        return img

    def _add_accessories(self, img, accessory_type):
        """Add NEET-core accessories"""
        draw = ImageDraw.Draw(img)
        
        if accessory_type == "headphones":
            # Gaming headset
            # Headband
            draw.arc(
                [self.center[0]-100, self.center[1]-150, self.center[0]+100, self.center[1]-50],
                0, 180,
                fill=(40, 40, 40),
                width=15
            )
            # Ear cups
            for x_offset in [-90, 90]:
                draw.ellipse(
                    [self.center[0]+x_offset-25, self.center[1]-100, 
                     self.center[0]+x_offset+25, self.center[1]-50],
                    fill=(40, 40, 40)
                )
                # Add LED accent
                draw.arc(
                    [self.center[0]+x_offset-20, self.center[1]-95,
                     self.center[0]+x_offset+20, self.center[1]-55],
                    0, 360,
                    fill=(0, 255, 200),
                    width=3
                )
        
        elif accessory_type == "glasses":
            # Comfy round glasses
            for x_offset in [-45, 45]:
                draw.ellipse(
                    [self.center[0]+x_offset-25, self.center[1]-40,
                     self.center[0]+x_offset+25, self.center[1]+10],
                    outline=(40, 40, 40),
                    width=5
                )
            # Bridge
            draw.line(
                [self.center[0]-20, self.center[1]-15,
                 self.center[0]+20, self.center[1]-15],
                fill=(40, 40, 40),
                width=5
            )
        
        return img

    def generate_character(self, expression="comfy", accessory="none"):
        """Generate a complete NEET character"""
        # Create base character
        img = self._create_base()
        
        # Add features
        img = self._add_eyes(img, expression)
        img = self._add_mouth(img, expression)
        
        if accessory != "none":
            img = self._add_accessories(img, accessory)
        
        # Add some soft blur for a comfy feel
        img = img.filter(ImageFilter.GaussianBlur(radius=1))
        
        # Save base character for reference
        os.makedirs('character_base', exist_ok=True)
        filename = f'character_base/character_{expression}'
        if accessory != "none":
            filename += f'_{accessory}'
        filename += '.png'
        img.save(filename)
        print(f"Character saved to {filename}")
        
        return img

def main():
    generator = ComfyCharacterGenerator()
    
    # Generate different expressions and accessories combinations
    expressions = ["happy", "sad", "sleepy", "comfy"]
    accessories = ["none", "headphones", "glasses"]
    
    for expression in expressions:
        for accessory in accessories:
            generator.generate_character(expression, accessory)

if __name__ == "__main__":
    main()
