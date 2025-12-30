#!/bin/bash
#
# Test USB gadget by sending test HID reports
#

echo "=== USB Gadget HID Test ==="
echo

if [ ! -c /dev/hidg0 ]; then
    echo "Error: /dev/hidg0 not found"
    echo "Run setup-usb-gadget.sh first"
    exit 1
fi

echo "Sending test gamepad report (press A button)..."
# Report ID 1 (gamepad) + button A pressed
# Format: ReportID + 2 bytes buttons + 8 bytes axes + 2 bytes triggers + 1 byte hat
# Button A = bit 0 of first byte = 0x01
echo -ne '\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' > /dev/hidg0
sleep 0.1

echo "Releasing button..."
echo -ne '\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' > /dev/hidg0
sleep 0.5

echo
echo "Sending test keyboard report (press 'a' key)..."
# Report ID 2 (keyboard) + modifiers + reserved + 6 key codes
# Key 'a' = HID code 0x04
echo -ne '\x02\x00\x00\x04\x00\x00\x00\x00\x00' > /dev/hidg0
sleep 0.1

echo "Releasing key..."
echo -ne '\x02\x00\x00\x00\x00\x00\x00\x00\x00' > /dev/hidg0
sleep 0.5

echo
echo "Sending test mouse report (move right)..."
# Report ID 3 (mouse) + buttons + X + Y + wheel + h_wheel
# Move right: X = 10, others = 0
echo -ne '\x03\x00\x0a\x00\x00\x00\x00' > /dev/hidg0
sleep 0.1

echo "Resetting mouse..."
echo -ne '\x03\x00\x00\x00\x00\x00\x00' > /dev/hidg0

echo
echo "=== Test Complete ==="
echo "Check your PC for:"
echo "  - Gamepad button press (A button)"
echo "  - Keyboard 'a' character typed"
echo "  - Mouse cursor moving right"
echo
