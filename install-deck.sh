#!/bin/bash
# Installation script for BT Controller Emulator on Steam Deck

set -e

echo "=== BT Controller Emulator - Steam Deck Installer ==="
echo

# Check if running on Steam Deck
if [ ! -f /etc/os-release ] || ! grep -q "SteamOS" /etc/os-release; then
    echo "Warning: This doesn't appear to be SteamOS/Steam Deck"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Determine install location
if [ "$EUID" -eq 0 ]; then
    echo "Don't run this script as root (no sudo). Run as deck user."
    exit 1
fi

INSTALL_DIR="$HOME/steamdeck-bt-controller-emulator"
DESKTOP_FILE="$HOME/.local/share/applications/bt-controller-emulator.desktop"
DESKTOP_SHORTCUT="$HOME/Desktop/bt-controller-emulator.desktop"

echo "Install location: $INSTALL_DIR"
echo

# Check if we're already in the install directory
CURRENT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$CURRENT_DIR" = "$INSTALL_DIR" ]; then
    echo "✓ Already in install directory, skipping file copy..."
elif [ -d "$INSTALL_DIR" ]; then
    echo "Existing installation found at $INSTALL_DIR"
    read -p "Update installation? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
    # Copy files
    echo "Copying files..."
    cp -r "$CURRENT_DIR"/* "$INSTALL_DIR/"
else
    # New installation
    echo "Installing to $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    cp -r "$CURRENT_DIR"/* "$INSTALL_DIR/"
fi

# Verify source files exist
if [ ! -f "$INSTALL_DIR/src/hogp/gui.py" ]; then
    echo "Error: Installation failed - gui.py not found"
    exit 1
fi

# Verify Python dependencies
echo
echo "Checking Python dependencies..."
DEPS_OK=true

python3 -c "import gi" 2>/dev/null || DEPS_OK=false
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" 2>/dev/null || DEPS_OK=false
python3 -c "import evdev" 2>/dev/null || DEPS_OK=false

if [ "$DEPS_OK" = false ]; then
    echo "✗ Missing required Python dependencies"
    echo "  Required: python-gobject, gtk4, python-evdev"
    echo "  These should be pre-installed on SteamOS 3.x"
    exit 1
else
    echo "✓ All Python dependencies found"
fi

# Create desktop file
echo
echo "Creating desktop launcher..."
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=BT Controller Emulator
Comment=Bluetooth HID Controller Emulator for Steam Deck
Icon=input-gaming
Exec=sh -c 'pkexec env DISPLAY="${DISPLAY}" XAUTHORITY="${XAUTHORITY}" bash -c "cd $HOME/steamdeck-bt-controller-emulator && ./launcher-wrapper.sh $HOME/steamdeck-bt-controller-emulator/src/hogp/gui.py"'
Terminal=false
Categories=Game;Utility;
Keywords=bluetooth;controller;gamepad;hid;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

# Make scripts executable
chmod +x "$INSTALL_DIR/src/hogp/gui.py"
chmod +x "$INSTALL_DIR/launcher-wrapper.sh"

echo "✓ Desktop file created: $DESKTOP_FILE"

# Create desktop shortcut (actual desktop icon)
echo
read -p "Create desktop shortcut? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mkdir -p "$HOME/Desktop"
    cp "$DESKTOP_FILE" "$DESKTOP_SHORTCUT"
    chmod +x "$DESKTOP_SHORTCUT"
    echo "✓ Desktop shortcut created: $DESKTOP_SHORTCUT"
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo
echo "=== Installation Complete! ==="
echo
echo "You can now launch 'BT Controller Emulator' from:"
echo "  - Desktop mode: Application menu"
echo "  - Game mode: Add as non-Steam game"
echo
echo "Usage:"
echo "  1. Launch the application"
echo "  2. Click 'Start Controller'"
echo "  3. Connect from another device via Bluetooth"
echo "  4. Your Steam Deck controller inputs will be forwarded"
echo
echo "If the app doesn't start, check the log:"
echo "  cat /tmp/bt-controller-emulator.log"
echo
echo "To add to Steam (Game Mode):"
echo "  1. Switch to Desktop mode"
echo "  2. Open Steam"
echo "  3. Games > Add a Non-Steam Game"
echo "  4. Browse and select: $DESKTOP_FILE"
echo
echo "Note: The app requires root access (via pkexec) to access Bluetooth."
echo
