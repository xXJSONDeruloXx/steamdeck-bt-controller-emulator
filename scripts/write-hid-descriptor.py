#!/usr/bin/env python3
"""Write HID report descriptor from gatt_app.py to USB gadget configfs."""

import sys
import os

# Add src to path to import gatt_app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hogp.gatt_app import REPORT_MAP

def main():
    if len(sys.argv) != 2:
        print("Usage: write-hid-descriptor.py <output_file>")
        sys.exit(1)
    
    output_file = sys.argv[1]
    
    # Convert REPORT_MAP (list of ints) to bytes
    descriptor_bytes = bytes(REPORT_MAP)
    
    # Write raw binary to file
    with open(output_file, 'wb') as f:
        f.write(descriptor_bytes)
    
    print(f"Wrote {len(descriptor_bytes)} bytes to {output_file}")

if __name__ == '__main__':
    main()
