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
    echo "Don't run this script as root (no sudo). Run as your regular user."
    exit 1
fi

CURRENT_USER="$USER"

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

# Configure system permissions for non-root operation
echo
echo "=== Configuring System Permissions ==="
echo "This requires sudo access to set up proper permissions."
echo "You'll run the app as a normal user (no pkexec/root needed)."
echo

# Add user to necessary groups
echo "Adding $CURRENT_USER to 'input' and 'bluetooth' groups..."
if ! groups "$CURRENT_USER" | grep -q "input"; then
    sudo usermod -a -G input "$CURRENT_USER" || {
        echo "✗ Failed to add user to 'input' group"
        exit 1
    }
    echo "✓ Added to 'input' group (controller access)"
    GROUPS_CHANGED=true
else
    echo "✓ Already in 'input' group"
fi

# Create bluetooth group if it doesn't exist
if ! getent group bluetooth > /dev/null 2>&1; then
    echo "Creating 'bluetooth' group..."
    sudo groupadd -r bluetooth || {
        echo "✗ Failed to create 'bluetooth' group"
        exit 1
    }
    echo "✓ Created 'bluetooth' group"
fi

if ! groups "$CURRENT_USER" | grep -q "bluetooth"; then
    sudo usermod -a -G bluetooth "$CURRENT_USER" || {
        echo "✗ Failed to add user to 'bluetooth' group"
        exit 1
    }
    echo "✓ Added to 'bluetooth' group (Bluetooth GATT access)"
    GROUPS_CHANGED=true
else
    echo "✓ Already in 'bluetooth' group"
fi

# Install D-Bus policy for BlueZ GATT registration
echo
echo "Installing D-Bus policy for BlueZ GATT operations..."
DBUS_POLICY="/etc/dbus-1/system.d/bt-controller-emulator.conf"
if [ -f "$INSTALL_DIR/config/bt-controller-emulator-dbus.conf" ]; then
    # Create directory if it doesn't exist
    sudo mkdir -p /etc/dbus-1/system.d
    sudo cp "$INSTALL_DIR/config/bt-controller-emulator-dbus.conf" "$DBUS_POLICY" || {
        echo "✗ Failed to install D-Bus policy"
        exit 1
    }
    echo "✓ D-Bus policy installed: $DBUS_POLICY"
else
    echo "✗ D-Bus policy file not found!"
    exit 1
fi

# Install sudoers rule for btmgmt (passwordless for bluetooth group)
echo
echo "Installing sudoers rule for btmgmt..."
SUDOERS_FILE="/etc/sudoers.d/bt-controller-emulator"
if [ -f "$INSTALL_DIR/config/bt-controller-emulator-sudoers" ]; then
    # Create directory if it doesn't exist
    sudo mkdir -p /etc/sudoers.d
    sudo cp "$INSTALL_DIR/config/bt-controller-emulator-sudoers" "$SUDOERS_FILE" || {
        echo "✗ Failed to install sudoers rule"
        exit 1
    }
    sudo chmod 0440 "$SUDOERS_FILE"
    echo "✓ Sudoers rule installed: $SUDOERS_FILE"
else
    echo "✗ Sudoers file not found!"
    exit 1
fi

# Reload D-Bus configuration
echo
echo "Reloading D-Bus configuration..."
sudo systemctl reload dbus || {
    echo "⚠ Warning: Could not reload D-Bus (may need reboot)"
}
echo "✓ D-Bus reloaded"

echo

# Create desktop file
echo "Creating desktop launcher..."
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=BT Controller Emulator
Comment=Bluetooth HID Controller Emulator for Steam Deck
Icon=input-gaming
Exec=$INSTALL_DIR/scripts/run-gui.sh
Terminal=false
Categories=Game;Utility;
Keywords=bluetooth;controller;gamepad;hid;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

# Make scripts executable
chmod +x "$INSTALL_DIR/scripts/run-gui.sh"
chmod +x "$INSTALL_DIR/scripts/launcher-wrapper.sh"

echo "✓ Desktop file created: $DESKTOP_FILE"

# Create desktop shortcut (actual desktop icon) - automatically without prompting
mkdir -p "$HOME/Desktop"
cp "$DESKTOP_FILE" "$DESKTOP_SHORTCUT"
chmod +x "$DESKTOP_SHORTCUT"
echo "✓ Desktop shortcut created: $DESKTOP_SHORTCUT"

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo
echo "=== Installation Complete! ==="
echo

if [ "${GROUPS_CHANGED:-false}" = true ]; then
    echo "⚠ IMPORTANT: You were added to new groups (input, bluetooth)."
    echo "   You MUST log out and log back in for changes to take effect!"
    echo "   Or run: newgrp input && newgrp bluetooth"
    echo
fi

echo "The BT Controller Emulator now runs as a normal user (no root needed)."
echo
echo "You can now launch 'BT Controller Emulator' from:"
echo "  - Desktop mode: Application menu"
echo "  - Game mode: Add as non-Steam game"
echo
echo "Usage:"
echo "  1. Launch the application (no password prompt!)"
echo "  2. Click 'Start Service'"
echo "  3. Connect from another device via Bluetooth"
echo "  4. Your Steam Deck controller inputs will be forwarded"
echo
echo "To uninstall:"
echo "  Run: ./uninstall-deck.sh"
echo
