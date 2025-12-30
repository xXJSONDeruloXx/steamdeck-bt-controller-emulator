#!/bin/bash
# Quick launcher for BT Controller Emulator GUI
# Run this on the Steam Deck to launch the GUI

cd "$(dirname "$0")"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Error: Don't run as root"
    echo "The app runs as a normal user with proper permissions"
    exit 1
fi

# Launch the GUI directly as normal user
echo "Launching BT Controller Emulator..."
python3 -m src.hogp.gui
