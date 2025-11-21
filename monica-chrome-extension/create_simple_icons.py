#!/usr/bin/env python3
"""Create very simple placeholder icons without PIL"""

import struct
import zlib
import os

def create_simple_png(size, filename):
    """Create a simple purple PNG file"""
    # Purple color: RGB(102, 126, 234)
    r, g, b = 102, 126, 234

    # Create image data (each pixel is RGB)
    img_data = bytes([r, g, b] * size * size)

    # Create scanlines with filter byte (0 = no filter)
    scanlines = b''
    for y in range(size):
        scanlines += b'\x00'  # Filter byte
        scanlines += img_data[y * size * 3:(y + 1) * size * 3]

    # Compress the scanlines
    compressed = zlib.compress(scanlines, 9)

    # Create PNG chunks
    def create_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

    # PNG signature
    png = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    png += create_chunk(b'IHDR', ihdr)

    # IDAT chunk
    png += create_chunk(b'IDAT', compressed)

    # IEND chunk
    png += create_chunk(b'IEND', b'')

    # Write file
    with open(filename, 'wb') as f:
        f.write(png)

    print(f'Created {filename}')

if __name__ == '__main__':
    os.makedirs('icons', exist_ok=True)

    sizes = [16, 32, 48, 128]
    for size in sizes:
        create_simple_png(size, f'icons/icon{size}.png')

    print('\nSimple placeholder icons created!')
    print('Note: These are basic purple squares. For Chrome Web Store,')
    print('consider replacing with proper designed icons.')
