#!/bin/bash
# Installation script for BT Controller Emulator on Steam Deck

set -e

echo "=== BT Controller Emulator - Steam Deck Installer ==="
echo

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
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ "$PROJECT_DIR" = "$INSTALL_DIR" ]; then
    echo "✓ Already in install directory, skipping file copy..."
elif [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation at $INSTALL_DIR..."
    # Force overwrite all files
    cp -rf "$PROJECT_DIR"/* "$INSTALL_DIR/"
    echo "✓ Files updated"
else
    # New installation
    echo "Installing to $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    cp -r "$PROJECT_DIR"/* "$INSTALL_DIR/"
    echo "✓ Files installed"
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
    exit 1
else
    echo "✓ All Python dependencies found"
fi

# Configure system permissions for non-root operation
echo
echo "=== Configuring System Permissions ==="
echo "This requires sudo access to set up proper permissions."
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
    sudo cp -f "$INSTALL_DIR/config/bt-controller-emulator-dbus.conf" "$DBUS_POLICY" || {
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
    # Replace INSTALL_DIR_PLACEHOLDER with actual install directory
    sed "s|INSTALL_DIR_PLACEHOLDER|$INSTALL_DIR|g" "$INSTALL_DIR/config/bt-controller-emulator-sudoers" | sudo tee "$SUDOERS_FILE" > /dev/null || {
        echo "✗ Failed to install sudoers rule"
        exit 1
    }
    sudo chmod 0440 "$SUDOERS_FILE"
    # Validate sudoers syntax
    if ! sudo visudo -c -f "$SUDOERS_FILE" > /dev/null 2>&1; then
        echo "✗ Sudoers file has syntax errors!"
        sudo cat "$SUDOERS_FILE"
        exit 1
    fi
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

# Generate desktop file with actual install directory
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=BT Controller Emulator
Comment=Bluetooth HID Controller Emulator for Steam Deck
Icon=input-gaming
Exec=$INSTALL_DIR/scripts/run-gui.sh
Path=$INSTALL_DIR
Terminal=false
Categories=Game;Utility;
Keywords=bluetooth;controller;gamepad;hid;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

# Make scripts executable
chmod +x "$INSTALL_DIR/scripts/run-gui.sh"
chmod +x "$INSTALL_DIR/scripts/launcher-wrapper.sh"
chmod +x "$INSTALL_DIR/scripts/bt-controller-emulator-btmgmt.sh"

echo "✓ Desktop file created: $DESKTOP_FILE"

# Create desktop shortcut (actual desktop icon) - automatically without prompting
mkdir -p "$HOME/Desktop"
cp -f "$DESKTOP_FILE" "$DESKTOP_SHORTCUT"
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
