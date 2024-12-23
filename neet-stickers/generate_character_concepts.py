from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops, ImageOps
import numpy as np
import colorsys
import math
import os

class Character3DGenerator:
    def __init__(self):
        self.size = (512, 512)
        self.center = (self.size[0] // 2, self.size[1] // 2)

    def create_gradient_sphere(self, color, highlight_color, shadow_color, center, radius):
        """Create a 3D sphere with gradient lighting"""
        img = Image.new('RGBA', self.size, (0, 0, 0, 0))
        data = np.zeros((self.size[1], self.size[0], 4), dtype=np.uint8)
        
        for y in range(self.size[1]):
            for x in range(self.size[0]):
                dx = x - center[0]
                dy = y - center[1]
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance <= radius:
                    # Calculate 3D position
                    z = math.sqrt(radius*radius - distance*distance)
                    normal = [dx/radius, dy/radius, z/radius]
                    
                    # Light direction (top-right)
                    light = [0.5, -0.5, 1]
                    light_len = math.sqrt(sum(x*x for x in light))
                    light = [x/light_len for x in light]
                    
                    # Calculate lighting
                    dot = sum(n*l for n,l in zip(normal, light))
                    dot = max(0.2, min(1.0, dot))  # Clamp for ambient light
                    
                    # Mix colors based on lighting
                    if dot > 0.8:  # Highlight
                        final_color = [int(c * dot) for c in highlight_color]
                    elif dot < 0.4:  # Shadow
                        shadow_strength = (0.4 - dot) / 0.4
                        final_color = [int(c1 + (c2-c1)*shadow_strength) 
                                     for c1, c2 in zip(color, shadow_color)]
                    else:  # Base color
                        final_color = [int(c * dot) for c in color]
                    
                    # Add alpha
                    final_color.append(255)
                    data[y, x] = final_color
        
        img = Image.fromarray(data)
        return img

    def generate_concept_1(self):
        """Cyber Pepe: A futuristic take on the classic"""
        img = Image.new('RGBA', self.size, (0, 0, 0, 0))
        
        # Base head - cybernetic green
        base = self.create_gradient_sphere(
            (100, 200, 150),  # Base green
            (150, 255, 200),  # Highlight
            (50, 100, 75),    # Shadow
            (self.center[0], self.center[1]), 
            180
        )
        
        # Add cyber patterns
        draw = ImageDraw.Draw(base)
        # Circuit lines
        for i in range(5):
            y = self.center[1] - 100 + i * 40
            draw.line([(self.center[0]-100, y), (self.center[0]+100, y)], 
                     fill=(0, 255, 200, 100), width=2)
        
        # Glowing eyes
        eye_glow = self.create_gradient_sphere(
            (0, 255, 255),    # Cyan
            (200, 255, 255),  # Light cyan
            (0, 150, 150),    # Dark cyan
            (self.center[0]-50, self.center[1]-20),
            30
        )
        base = Image.alpha_composite(base, eye_glow)
        
        eye_glow = self.create_gradient_sphere(
            (0, 255, 255),
            (200, 255, 255),
            (0, 150, 150),
            (self.center[0]+50, self.center[1]-20),
            30
        )
        base = Image.alpha_composite(base, eye_glow)
        
        return base

    def generate_concept_2(self):
        """Comfy Ghost: A soft, ethereal character"""
        img = Image.new('RGBA', self.size, (0, 0, 0, 0))
        
        # Create multiple translucent layers
        for i in range(5):
            offset = i * 10
            ghost = self.create_gradient_sphere(
                (255-offset, 255-offset, 255-offset),
                (255, 255, 255),
                (200-offset, 200-offset, 220-offset),
                (self.center[0], self.center[1]-offset),
                150-offset
            )
            ghost = ghost.filter(ImageFilter.GaussianBlur(radius=2))
            img = Image.alpha_composite(img, ghost)
        
        # Add sleepy eyes
        draw = ImageDraw.Draw(img)
        draw.arc((self.center[0]-80, self.center[1]-30, self.center[0]-20, self.center[1]+10),
                0, 180, fill=(100, 100, 120), width=5)
        draw.arc((self.center[0]+20, self.center[1]-30, self.center[0]+80, self.center[1]+10),
                0, 180, fill=(100, 100, 120), width=5)
        
        return img

    def generate_concept_3(self):
        """Pixel Wizard: A magical 3D pixel art character"""
        img = Image.new('RGBA', self.size, (0, 0, 0, 0))
        
        # Create base wizard hat
        hat_color = (80, 50, 120)
        hat_highlight = (120, 80, 180)
        hat_shadow = (40, 25, 60)
        
        hat = self.create_gradient_sphere(
            hat_color, hat_highlight, hat_shadow,
            (self.center[0], self.center[1]-50),
            120
        )
        
        # Add magical particles
        particles = []
        for _ in range(20):
            x = self.center[0] + np.random.randint(-100, 100)
            y = self.center[1] + np.random.randint(-100, 100)
            size = np.random.randint(10, 30)
            hue = np.random.random()
            rgb = tuple(int(x*255) for x in colorsys.hsv_to_rgb(hue, 0.8, 1.0))
            particle = self.create_gradient_sphere(
                rgb,
                tuple(min(255, c+50) for c in rgb),
                tuple(max(0, c-50) for c in rgb),
                (x, y),
                size
            )
            particles.append(particle)
        
        # Combine all elements
        for particle in particles:
            img = Image.alpha_composite(img, particle)
        img = Image.alpha_composite(img, hat)
        
        return img

    def generate_concept_4(self):
        """Blob King: A regal gelatinous creature"""
        img = Image.new('RGBA', self.size, (0, 0, 0, 0))
        
        # Create crown
        crown_color = (255, 215, 0)  # Gold
        crown_highlight = (255, 235, 100)
        crown_shadow = (180, 150, 0)
        
        for i in range(3):
            spike = self.create_gradient_sphere(
                crown_color, crown_highlight, crown_shadow,
                (self.center[0] + (i-1)*80, self.center[1]-100),
                40
            )
            img = Image.alpha_composite(img, spike)
        
        # Create blob body
        body_color = (180, 100, 255)  # Royal purple
        body_highlight = (220, 180, 255)
        body_shadow = (100, 50, 150)
        
        body = self.create_gradient_sphere(
            body_color, body_highlight, body_shadow,
            (self.center[0], self.center[1]+50),
            150
        )
        
        # Add wobble effect
        body = body.filter(ImageFilter.GaussianBlur(radius=3))
        
        img = Image.alpha_composite(img, body)
        return img

    def generate_concept_5(self):
        """Mecha NEET: A robotic comfort seeker"""
        img = Image.new('RGBA', self.size, (0, 0, 0, 0))
        
        # Create base mechanical head
        base_color = (200, 200, 220)
        highlight_color = (240, 240, 255)
        shadow_color = (120, 120, 140)
        
        head = self.create_gradient_sphere(
            base_color, highlight_color, shadow_color,
            (self.center[0], self.center[1]),
            160
        )
        
        # Add mechanical details
        draw = ImageDraw.Draw(head)
        
        # Panel lines
        for i in range(-2, 3):
            x = self.center[0] + i * 40
            draw.line([(x, self.center[1]-100), (x, self.center[1]+100)],
                     fill=(100, 100, 120, 150), width=3)
        
        # Visor
        visor_color = (0, 200, 255)
        visor = self.create_gradient_sphere(
            visor_color,
            tuple(min(255, c+50) for c in visor_color),
            tuple(max(0, c-50) for c in visor_color),
            (self.center[0], self.center[1]-20),
            80
        )
        
        img = Image.alpha_composite(img, head)
        img = Image.alpha_composite(img, visor)
        
        return img

def generate_concepts():
    """Generate all character concepts"""
    os.makedirs('character_concepts', exist_ok=True)
    
    generator = Character3DGenerator()
    concepts = {
        'cyber_pepe': generator.generate_concept_1,
        'comfy_ghost': generator.generate_concept_2,
        'pixel_wizard': generator.generate_concept_3,
        'blob_king': generator.generate_concept_4,
        'mecha_neet': generator.generate_concept_5
    }
    
    for name, func in concepts.items():
        print(f"Generating {name}...")
        concept = func()
        
        # Add some final polish
        concept = concept.filter(ImageFilter.GaussianBlur(radius=1))
        enhancer = ImageEnhance.Contrast(concept)
        concept = enhancer.enhance(1.2)
        
        concept.save(f'character_concepts/{name}.png')
        print(f"Saved {name}.png")

if __name__ == "__main__":
    print("Generating character concepts...")
    generate_concepts()
    print("\nDone! Check the character_concepts directory for the results.")
