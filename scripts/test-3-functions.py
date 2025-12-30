#!/usr/bin/env python3
"""
Test the 3-function USB HID setup by sending test reports.
Run this on the Steam Deck while connected via USB-C to a host.
"""

import sys
import os
import time

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.hogp.usb_gadget import USBGadgetHID

def main():
    print("=== Testing 3-Function USB HID Setup ===\n")
    
    # Check devices exist
    for dev in ["/dev/hidg0", "/dev/hidg1", "/dev/hidg2"]:
        if not os.path.exists(dev):
            print(f"ERROR: {dev} does not exist!")
            print("Run: sudo bash scripts/setup-usb-gadget.sh")
            return 1
        print(f"✓ Found {dev}")
    
    print("\nCreating USB gadget...")
    gadget = USBGadgetHID(verbose=True)
    
    print("Opening devices...")
    if not gadget.open():
        print("ERROR: Failed to open devices!")
        return 1
    
    print(f"✓ Gamepad fd: {gadget._gamepad_fd}")
    print(f"✓ Keyboard fd: {gadget._keyboard_fd}")
    print(f"✓ Mouse fd: {gadget._mouse_fd}")
    
    try:
        print("\n=== Testing Gamepad (5 seconds) ===")
        print("Press buttons 0-10 in sequence...")
        for i in range(11):
            print(f"Button {i} press", end="", flush=True)
            gadget.set_button(i, True)
            time.sleep(0.2)
            print(" release")
            gadget.set_button(i, False)
            time.sleep(0.2)
        
        print("\n=== Testing Keyboard (3 seconds) ===")
        print("Typing: hello")
        for char in "hello":
            key_code = ord(char) - ord('a') + 0x04
            print(f"  {char}", end="", flush=True)
            gadget.send_key(key_code)
            time.sleep(0.3)
        print()
        
        print("\n=== Testing Mouse (3 seconds) ===")
        print("Moving mouse in circle...")
        for angle in range(0, 360, 30):
            import math
            x = int(50 * math.cos(math.radians(angle)))
            y = int(50 * math.sin(math.radians(angle)))
            print(f"  Move ({x:+3d}, {y:+3d})")
            gadget.send_mouse_movement(x, y)
            time.sleep(0.2)
        
        print("\n✓ Test complete!")
        print("\nCheck your host computer for:")
        print("  - Button presses in a game controller tester")
        print("  - 'hello' typed in a text field")
        print("  - Mouse movement in a circle")
        
    except Exception as e:
        print(f"\nERROR during test: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        print("\nClosing devices...")
        gadget.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
