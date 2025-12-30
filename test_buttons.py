#!/usr/bin/env python3
"""
Interactive button mapping tool for controllers.
Prompts for each button and shows what code it sends.
"""

import evdev
from evdev import InputDevice, ecodes
import sys
import select
import time

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

# Buttons to test
buttons_to_test = [
    ("A button", "Press A button"),
    ("B button", "Press B button"),
    ("X button", "Press X button"),
    ("Y button", "Press Y button"),
    ("Left Bumper (LB)", "Press Left Bumper"),
    ("Right Bumper (RB)", "Press Right Bumper"),
    ("Left Trigger (LT)", "Press Left Trigger FULLY"),
    ("Right Trigger (RT)", "Press Right Trigger FULLY"),
    ("Back/Select", "Press Back/Select button"),
    ("Start", "Press Start button"),
    ("Guide/Home", "Press Guide/Home button"),
    ("Left Stick Click", "Click Left Stick"),
    ("Right Stick Click", "Click Right Stick"),
    ("D-pad Up", "Press D-pad Up"),
    ("D-pad Down", "Press D-pad Down"),
    ("D-pad Left", "Press D-pad Left"),
    ("D-pad Right", "Press D-pad Right"),
]

def wait_for_input(timeout=10):
    """Wait for button press/axis movement within timeout."""
    print(f"Waiting... ", end='', flush=True)
    events = []
    start_time = time.time()
    
    # Track initial axis values to detect significant changes
    initial_axes = {}
    axis_threshold = 3000  # Lower threshold for trigger detection
    
    while time.time() - start_time < timeout:
        # Check if there's data available (non-blocking)
        r, w, x = select.select([xbox.fd], [], [], 0.1)
        if r:
            event = xbox.read_one()
            if event:
                # Only capture button presses (EV_KEY) and axis movements (EV_ABS)
                if event.type == ecodes.EV_KEY and event.value == 1:  # Button press
                    btn_name = ecodes.BTN.get(event.code, f"UNKNOWN_{event.code}")
                    if isinstance(btn_name, list):
                        btn_name = btn_name[0] if btn_name else f"UNKNOWN_{event.code}"
                    events.append(('button', event.code, btn_name))
                    break  # Exit immediately after detecting button
                elif event.type == ecodes.EV_ABS:  # Axis movement
                    # Record initial value or check for significant change
                    if event.code not in initial_axes:
                        initial_axes[event.code] = event.value
                    else:
                        # Only record if movement exceeds threshold
                        delta = abs(event.value - initial_axes[event.code])
                        if delta > axis_threshold:
                            axis_name = ecodes.ABS.get(event.code, f"UNKNOWN_{event.code}")
                            if isinstance(axis_name, list):
                                axis_name = axis_name[0] if axis_name else f"UNKNOWN_{event.code}"
                            # Only add if not already recorded for this axis
                            if not any(e[0] == 'axis' and e[1] == event.code for e in events):
                                events.append(('axis', event.code, axis_name, event.value, initial_axes[event.code]))
                                break  # Exit immediately after detecting significant axis change
    
    print()
    return events

print("\nInteractive Button Mapping")
print("=" * 70)
print("For each prompt, press the specified button within 10 seconds.")
print("If you don't press anything, it will skip to the next one.")
print("=" * 70)
print()

results = {}

for name, prompt in buttons_to_test:
    print(f"\n📍 {prompt}")
    events = wait_for_input(10)
    
    if events:
        print(f"✓ Detected:")
        for event in events:
            if event[0] == 'button':
                _, code, btn_name = event
                print(f"   Button: {btn_name:20s} (code={code}, hex=0x{code:04x})")
                results[name] = ('button', code, btn_name)
            elif event[0] == 'axis':
                _, code, axis_name, value, initial = event
                print(f"   Axis:   {axis_name:20s} (code={code}, hex=0x{code:04x}, {initial}→{value})")
                results[name] = ('axis', code, axis_name, value, initial)
    else:
        print(f"✗ No input detected")
        results[name] = None
    
    # Clear any remaining events
    while xbox.read_one():
        pass

print("\n" + "=" * 70)
print("MAPPING SUMMARY")
print("=" * 70)

for name, prompt in buttons_to_test:
    result = results.get(name)
    if result:
        if result[0] == 'button':
            _, code, btn_name = result
            print(f"{name:25s} → Button code {code:3d} (0x{code:04x}) {btn_name}")
        else:
            _, code, axis_name, value, initial = result
            print(f"{name:25s} → Axis   code {code:3d} (0x{code:04x}) {axis_name} ({initial}→{value})")
    else:
        print(f"{name:25s} → NOT DETECTED")

print("\n" + "=" * 70)
print("Copy the mapping above to fix input_handler.py!")
print("=" * 70)

