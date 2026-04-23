#!/usr/bin/env python3
"""
Create a placeholder DECK MOUNT logo image
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_placeholder_logo():
    # Create a 44x44 pixel image with transparent background
    img = Image.new('RGBA', (44, 44), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a simple "DM" text as placeholder
    try:
        # Try to use a system font
        font = ImageFont.truetype("Arial.ttf", 16)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Draw "DM" text in dark color
    draw.text((10, 12), "DM", fill=(50, 50, 50, 255), font=font)
    
    # Save the image
    output_path = os.path.join("assets", "images", "deck_mount_logo.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Placeholder logo created at: {output_path}")

if __name__ == "__main__":
    create_placeholder_logo()
