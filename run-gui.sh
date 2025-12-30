#!/bin/bash
# Quick launcher for BT Controller Emulator GUI
# Run this on the Steam Deck to launch the GUI

cd "$(dirname "$0")"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Error: Don't run with sudo directly"
    echo "The app will request root access when needed"
    exit 1
fi

# Capture display variables before pkexec
SAVED_DISPLAY="${DISPLAY}"
SAVED_XAUTH="${XAUTHORITY}"

# Launch with pkexec to get root for Bluetooth access
echo "Launching BT Controller Emulator..."
echo "Display: $SAVED_DISPLAY"
echo "You will be prompted for your password..."
echo
echo "Logs will be written to: /tmp/bt-controller-emulator.log"
echo

pkexec env DISPLAY="${SAVED_DISPLAY}" XAUTHORITY="${SAVED_XAUTH}" bash -c "cd '$(pwd)' && ./launcher-wrapper.sh '$(pwd)/src/hogp/gui.py'"

# Show log if it failed
if [ $? -ne 0 ]; then
    echo
    echo "=== Error Log ==="
    cat /tmp/bt-controller-emulator.log 2>/dev/null || echo "No log file found"
fi
