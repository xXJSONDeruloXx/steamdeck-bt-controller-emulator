#!/usr/bin/env python3
"""
Quick test to discover Xbox 360 controller button codes.
Run this and press each button to see what code it sends.
"""

import evdev
from evdev import InputDevice, ecodes, categorize

# Find Xbox controller
devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
xbox = None
for device in devices:
    if 'xbox' in device.name.lower() or '360 pad' in device.name.lower():
        xbox = device
        break

if not xbox:
    print("No Xbox controller found!")
    exit(1)

print(f"Found: {xbox.name}")
print(f"Path: {xbox.path}")
print("\nPress buttons to see their codes (Ctrl+C to quit):")
print("-" * 60)

for event in xbox.read_loop():
    if event.type == ecodes.EV_KEY:
        # Find the button name
        btn_name = ecodes.BTN[event.code] if event.code in ecodes.BTN else f"UNKNOWN_{event.code}"
        state = "PRESSED" if event.value == 1 else "RELEASED" if event.value == 0 else f"STATE_{event.value}"
        print(f"Button: {btn_name:20s} (code={event.code:#06x}) - {state}")
