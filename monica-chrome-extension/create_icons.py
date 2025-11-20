#!/usr/bin/env python3
"""Create simple placeholder icons for the Chrome extension"""

from PIL import Image, ImageDraw, ImageFont
import os

# Icon sizes
sizes = [16, 32, 48, 128]

# Colors
bg_color = '#667eea'
fg_color = '#ffffff'

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_icon(size):
    """Create a simple monitoring icon"""
    # Create image with purple background
    img = Image.new('RGB', (size, size), hex_to_rgb(bg_color))
    draw = ImageDraw.Draw(img)

    # Draw a simple radar/monitoring icon
    # Outer circle
    padding = size // 8
    draw.ellipse([padding, padding, size - padding, size - padding],
                 outline=hex_to_rgb(fg_color), width=max(1, size // 20))

    # Inner circle (center dot)
    center = size // 2
    dot_size = size // 8
    draw.ellipse([center - dot_size, center - dot_size,
                  center + dot_size, center + dot_size],
                 fill=hex_to_rgb(fg_color))

    # Radar sweep line
    sweep_length = size // 2 - padding
    draw.line([center, center, center + sweep_length, center - sweep_length],
              fill=hex_to_rgb(fg_color), width=max(1, size // 16))

    # Save icon
    output_path = os.path.join('icons', f'icon{size}.png')
    img.save(output_path, 'PNG')
    print(f'Created {output_path}')

if __name__ == '__main__':
    for size in sizes:
        create_icon(size)

    print('All icons created successfully!')
