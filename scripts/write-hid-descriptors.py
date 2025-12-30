#!/usr/bin/env python3
"""Write separate HID descriptors for gamepad, keyboard, and mouse."""

import sys
import os

# Add src to path to import gatt_app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hogp.gatt_app import REPORT_MAP

def get_item_size(byte):
    """Get the size of an HID item from its first byte."""
    size_bits = byte & 0x03
    if size_bits == 3:
        return 5  # 1 byte prefix + 4 bytes data
    return size_bits + 1  # 1 byte prefix + 0/1/2 bytes data

def extract_descriptor(report_id):
    """
    Extract a single function's descriptor from the combined REPORT_MAP.
    Removes the Report ID tag (0x85, 0xXX) since we're using separate interfaces.
    
    Strategy: Find the Report ID tag, then extract from the most recent
    Usage Page + Usage pair before the collection up to the matching End Collection.
    """
    result = []
    i = 0
    
    # First, find where our Report ID is
    report_id_pos = -1
    while i < len(REPORT_MAP):
        item_byte = REPORT_MAP[i]
        item_size = get_item_size(item_byte)
        
        if i + item_size > len(REPORT_MAP):
            break
        
        # Check for our Report ID tag (0x85)
        if item_byte == 0x85 and i + item_size <= len(REPORT_MAP):
            if REPORT_MAP[i + 1] == report_id:
                report_id_pos = i
                break
        
        i += item_size
    
    if report_id_pos == -1:
        return bytes()  # Report ID not found
    
    # Now work backwards from report_id_pos to find the collection start (0xA1)
    # and the Usage Page (0x05) + Usage (0x09) immediately before it
    collection_start = -1
    i = report_id_pos - 1
    while i >= 0:
        if REPORT_MAP[i] == 0xA1:  # Collection
            collection_start = i
            break
        i -= 1
    
    if collection_start == -1:
        return bytes()  # No collection found
    
    # Now find Usage Page and Usage before the collection
    preamble_start = collection_start
    i = collection_start - 1
    found_usage = False
    found_usage_page = False
    
    # Scan backwards to find Usage (0x09) and Usage Page (0x05)
    while i >= 0 and (not found_usage or not found_usage_page):
        item_byte = REPORT_MAP[i]
        
        # We need to find the start of items, so scan backwards carefully
        # Try different item sizes to find valid item boundaries
        for test_size in [1, 2, 3, 5]:  # Possible HID item sizes
            if i >= test_size - 1:
                test_start = i - test_size + 1
                test_item_byte = REPORT_MAP[test_start]
                expected_size = get_item_size(test_item_byte)
                
                if expected_size == test_size:
                    # Found a valid item
                    if test_item_byte == 0x09 and not found_usage:  # Usage
                        found_usage = True
                        preamble_start = test_start
                    elif test_item_byte == 0x05 and not found_usage_page:  # Usage Page
                        found_usage_page = True
                        preamble_start = test_start
                    
                    i = test_start - 1
                    break
        else:
            i -= 1
    
    # Extract from preamble_start to the end of the matching collection
    collection_depth = 0
    i = preamble_start
    in_collection = False
    
    while i < len(REPORT_MAP):
        item_byte = REPORT_MAP[i]
        item_size = get_item_size(item_byte)
        
        if i + item_size > len(REPORT_MAP):
            break
        
        item = REPORT_MAP[i:i + item_size]
        
        # Collection start
        if item_byte == 0xA1:
            result.extend(item)
            collection_depth += 1
            in_collection = True
        
        # End Collection
        elif item_byte == 0xC0:
            result.extend(item)
            collection_depth -= 1
            if collection_depth == 0:
                break
        
        # Report ID - skip it
        elif item_byte == 0x85 and in_collection:
            pass  # Skip Report ID tags
        
        # All other items
        else:
            result.extend(item)
        
        i += item_size
    
    return bytes(result)

def main():
    if len(sys.argv) != 4:
        print("Usage: write-hid-descriptors.py <gamepad_file> <keyboard_file> <mouse_file>")
        sys.exit(1)
    
    gamepad_file = sys.argv[1]
    keyboard_file = sys.argv[2]
    mouse_file = sys.argv[3]
    
    # Extract each descriptor (Report ID 1=gamepad, 2=keyboard, 3=mouse)
    gamepad_desc = extract_descriptor(0x01)
    keyboard_desc = extract_descriptor(0x02)
    mouse_desc = extract_descriptor(0x03)
    
    # Write to files
    with open(gamepad_file, 'wb') as f:
        f.write(gamepad_desc)
    print(f"Wrote {len(gamepad_desc)} bytes to {gamepad_file}")
    
    with open(keyboard_file, 'wb') as f:
        f.write(keyboard_desc)
    print(f"Wrote {len(keyboard_desc)} bytes to {keyboard_file}")
    
    with open(mouse_file, 'wb') as f:
        f.write(mouse_desc)
    print(f"Wrote {len(mouse_desc)} bytes to {mouse_file}")

if __name__ == '__main__':
    main()
