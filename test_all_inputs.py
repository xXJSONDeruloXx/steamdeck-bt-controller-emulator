#!/usr/bin/env python3
"""
Comprehensive input test to find ALL axis and button codes.
Run this and press/move everything to see what codes appear.
"""

import evdev
from evdev import InputDevice, ecodes
import sys

# List all available devices
devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

print("Available input devices:")
for i, dev in enumerate(devices):
    print(f"  {i}: {dev.path} - {dev.name}")

# Let user select device
print()
choice = input("Enter device number to test: ").strip()
try:
    device_idx = int(choice)
    if device_idx < 0 or device_idx >= len(devices):
        print("Invalid device number!")
        exit(1)
    xbox = devices[device_idx]
except ValueError:
    print("Invalid input!")
    exit(1)

print()
print(f"Testing: {xbox.name}")
print(f"Path: {xbox.path}")
print("=" * 70)
print("\nPress ALL buttons and move ALL controls.")
print("This will show you the actual codes being sent.")
print("Press Ctrl+C when done.")
print("=" * 70)
print()

seen_buttons = {}
seen_axes = {}

try:
    for event in xbox.read_loop():
        if event.type == ecodes.EV_KEY:
            btn_name = ecodes.BTN.get(event.code, f"UNKNOWN_{event.code}")
            if isinstance(btn_name, list):
                btn_name = btn_name[0]
            state = "PRESSED" if event.value == 1 else "RELEASED"
            
            if event.value == 1 and event.code not in seen_buttons:
                seen_buttons[event.code] = btn_name
                print(f"🔘 Button code {event.code:3d} (0x{event.code:04x}) = {btn_name:20s} [{state}]")
        
        elif event.type == ecodes.EV_ABS:
            axis_name = ecodes.ABS.get(event.code, f"UNKNOWN_{event.code}")
            if isinstance(axis_name, list):
                axis_name = axis_name[0]
            
            # Only show significant changes
            if event.code not in seen_axes:
                abs_info = xbox.absinfo(event.code)
                seen_axes[event.code] = {
                    'name': axis_name,
                    'value': event.value,
                    'min': abs_info.min,
                    'max': abs_info.max,
                }
                print(f"📊 Axis   code {event.code:3d} (0x{event.code:04x}) = {axis_name:20s} "
                      f"[value={event.value}, range={abs_info.min} to {abs_info.max}]")
            else:
                # Update if significant change
                old_val = seen_axes[event.code]['value']
                if abs(event.value - old_val) > 1000:
                    seen_axes[event.code]['value'] = event.value
                    print(f"📊 Axis   code {event.code:3d} (0x{event.code:04x}) = {axis_name:20s} "
                          f"[{old_val} → {event.value}]")

except KeyboardInterrupt:
    print("\n" + "=" * 70)
    print("SUMMARY OF ALL DETECTED INPUTS")
    print("=" * 70)
    print("\nBUTTONS:")
    for code, name in sorted(seen_buttons.items()):
        print(f"  {code:3d} (0x{code:04x}) = {name}")
    
    print("\nAXES:")
    for code, info in sorted(seen_axes.items()):
        print(f"  {code:3d} (0x{code:04x}) = {info['name']:20s} "
              f"[range: {info['min']} to {info['max']}]")
    print()
