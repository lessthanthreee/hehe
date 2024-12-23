import json
import numpy as np
from PIL import Image
import os
import svgpathtools
import math

class NEETAnimator3D:
    def __init__(self):
        self.animation_data = None
        self.svg_paths = None
    
    def load_base_animation(self, template_path):
        """Load the base 3D animation template"""
        with open(template_path, 'r') as f:
            self.animation_data = json.load(f)
    
    def process_svg(self, svg_path):
        """Process SVG file into 3D-ready paths"""
        paths, attributes = svgpathtools.svg2paths(svg_path)
        self.svg_paths = paths
        
        # Convert SVG paths to Lottie bezier paths
        lottie_paths = []
        for path in paths:
            vertices = []
            for segment in path:
                if hasattr(segment, 'start'):
                    vertices.append({
                        "x": float(segment.start.real),
                        "y": float(segment.start.imag),
                        "z": 0
                    })
            if vertices:
                lottie_paths.append({
                    "ty": "sh",
                    "ks": {
                        "a": 0,
                        "k": {
                            "i": [],
                            "o": [],
                            "v": vertices,
                            "c": True
                        }
                    }
                })
        
        return lottie_paths

    def add_3d_effects(self):
        """Add 3D lighting and perspective effects"""
        self.animation_data["layers"][0]["ef"].extend([
            {
                "ty": 5,
                "nm": "3D Lighting",
                "en": 1,
                "ef": [
                    {
                        "ty": 2,
                        "nm": "Light Position",
                        "v": {
                            "a": 1,
                            "k": [
                                {
                                    "t": 0,
                                    "s": [500, 500, 1000]
                                },
                                {
                                    "t": 90,
                                    "s": [-500, -500, 1000]
                                },
                                {
                                    "t": 180,
                                    "s": [500, 500, 1000]
                                }
                            ]
                        }
                    }
                ]
            }
        ])

    def add_particle_effects(self):
        """Add dynamic particle effects"""
        particle_layer = {
            "ddd": 1,
            "ind": len(self.animation_data["layers"]) + 1,
            "ty": 4,
            "nm": "Particles",
            "sr": 1,
            "ks": {
                "p": {"a": 0, "k": [256, 256, 0]},
                "s": {"a": 0, "k": [100, 100, 100]},
                "r": {"a": 0, "k": 0},
                "o": {"a": 0, "k": 75}
            }
        }
        self.animation_data["layers"].append(particle_layer)

    def add_holographic_effect(self):
        """Add holographic color shifting effect"""
        self.animation_data["layers"][0]["ef"].append({
            "ty": 5,
            "nm": "Holographic",
            "en": 1,
            "ef": [
                {
                    "ty": 2,
                    "nm": "Color Shift",
                    "v": {
                        "a": 1,
                        "k": [
                            {"t": 0, "s": [0.8, 0.2, 0.8, 1]},
                            {"t": 60, "s": [0.2, 0.8, 0.8, 1]},
                            {"t": 120, "s": [0.8, 0.8, 0.2, 1]},
                            {"t": 180, "s": [0.8, 0.2, 0.8, 1]}
                        ]
                    }
                }
            ]
        })

    def create_animation(self, svg_path, output_path):
        """Create the full 3D animation"""
        # Load base template
        self.load_base_animation('lottie_animations/neet_3d_spin.json')
        
        # Process SVG and add to animation
        lottie_paths = self.process_svg(svg_path)
        self.animation_data["layers"][0]["shapes"] = lottie_paths
        
        # Add effects
        self.add_3d_effects()
        self.add_particle_effects()
        self.add_holographic_effect()
        
        # Save final animation
        with open(output_path, 'w') as f:
            json.dump(self.animation_data, f, indent=2)

def main():
    # Ensure directories exist
    os.makedirs('lottie_animations', exist_ok=True)
    
    # Initialize animator
    animator = NEETAnimator3D()
    
    # Create animation
    animator.create_animation(
        svg_path='neet_simple.svg',
        output_path='lottie_animations/neet_3d_final.json'
    )
    
    print("3D animation created successfully!")

if __name__ == "__main__":
    main()
