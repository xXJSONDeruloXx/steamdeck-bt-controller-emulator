#!/bin/bash
# One-line installer for BT Controller Emulator
# Usage: curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/install.sh | bash

set -euo pipefail

REPO_URL="https://github.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator.git"
INSTALL_DIR="$HOME/steamdeck-bt-controller-emulator"

echo "=== BT Controller Emulator - Installer ==="
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Error: Don't run as root. Run as your regular user."
    exit 1
fi

CURRENT_USER="$USER"

# Check if git is available
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed"
    echo "Install with: sudo pacman -S git"
    exit 1
fi

# Clone or update repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "Installing to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Verify source files
if [ ! -f "$INSTALL_DIR/src/hogp/gui.py" ]; then
    echo "Error: Installation failed - source files not found"
    exit 1
fi

# Check Python dependencies
echo
echo "Checking dependencies..."
DEPS_OK=true

python3 -c "import gi" 2>/dev/null || DEPS_OK=false
python3 -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk" 2>/dev/null || DEPS_OK=false
python3 -c "import evdev" 2>/dev/null || DEPS_OK=false

if [ "$DEPS_OK" = false ]; then
    echo "Error: Missing Python dependencies (python-gobject, gtk4, python-evdev)"
    echo "These should be pre-installed on SteamOS 3.x"
    exit 1
fi
echo "✓ Dependencies OK"

# Configure system permissions
echo
echo "=== Configuring Permissions ==="
echo "This requires sudo to configure Bluetooth and input device access."
echo

GROUPS_CHANGED=false

# Add to input group
if ! groups "$CURRENT_USER" | grep -q "input"; then
    echo "Adding user to 'input' group..."
    sudo usermod -a -G input "$CURRENT_USER" || {
        echo "✗ Failed to add user to 'input' group"
        exit 1
    }
    echo "✓ Added to 'input' group (controller access)"
    GROUPS_CHANGED=true
else
    echo "✓ Already in 'input' group"
fi

# Create bluetooth group if needed
if ! getent group bluetooth > /dev/null 2>&1; then
    echo "Creating 'bluetooth' group..."
    sudo groupadd -r bluetooth || {
        echo "✗ Failed to create 'bluetooth' group"
        exit 1
    }
    echo "✓ Created 'bluetooth' group"
fi

# Add to bluetooth group
if ! groups "$CURRENT_USER" | grep -q "bluetooth"; then
    echo "Adding user to 'bluetooth' group..."
    sudo usermod -a -G bluetooth "$CURRENT_USER" || {
        echo "✗ Failed to add user to 'bluetooth' group"
        exit 1
    }
    echo "✓ Added to 'bluetooth' group (Bluetooth GATT access)"
    GROUPS_CHANGED=true
else
    echo "✓ Already in 'bluetooth' group"
fi

# Install D-Bus policy
echo
echo "Installing D-Bus policy..."
sudo mkdir -p /etc/dbus-1/system.d
sudo cp "$INSTALL_DIR/config/bt-controller-emulator-dbus.conf" /etc/dbus-1/system.d/bt-controller-emulator.conf || {
    echo "✗ Failed to install D-Bus policy"
    exit 1
}
echo "✓ D-Bus policy installed"

# Install sudoers rule
echo "Installing sudoers rule..."
sudo mkdir -p /etc/sudoers.d
sudo cp "$INSTALL_DIR/config/bt-controller-emulator-sudoers" /etc/sudoers.d/bt-controller-emulator || {
    echo "✗ Failed to install sudoers rule"
    exit 1
}
sudo chmod 0440 /etc/sudoers.d/bt-controller-emulator
echo "✓ Sudoers rule installed"

# Reload D-Bus
echo "Reloading D-Bus..."
sudo systemctl reload dbus 2>/dev/null || {
    echo "⚠ Warning: Could not reload D-Bus (may need reboot)"
}
echo "✓ D-Bus reloaded"

# Create desktop launcher
echo
echo "Creating launcher..."
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/Desktop"

DESKTOP_FILE="$HOME/.local/share/applications/bt-controller-emulator.desktop"
DESKTOP_SHORTCUT="$HOME/Desktop/bt-controller-emulator.desktop"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=BT Controller Emulator
Comment=Bluetooth/USB HID Controller Emulator for Steam Deck
Icon=input-gaming
Exec=$INSTALL_DIR/scripts/run-gui.sh
Terminal=false
Categories=Game;Utility;
Keywords=bluetooth;controller;gamepad;hid;usb;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"
cp "$DESKTOP_FILE" "$DESKTOP_SHORTCUT"
chmod +x "$DESKTOP_SHORTCUT"
echo "✓ Desktop launcher created"

chmod +x "$INSTALL_DIR/scripts/run-gui.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/scripts/launcher-wrapper.sh" 2>/dev/null || true

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo
echo "=== Installation Complete ==="
echo
if [ "$GROUPS_CHANGED" = true ]; then
    echo "⚠ Activating new group memberships..."
    exec sg input -c "exec sg bluetooth -c 'echo; echo ✓ Groups activated; echo; echo The BT Controller Emulator runs as a normal user (no root needed).; exec $SHELL'"
fi
echo "The BT Controller Emulator runs as a normal user (no root needed)."
echo
echo "You can now launch 'BT Controller Emulator' from:"
echo "  - Desktop mode: Application menu"
echo "  - Game mode: Add as non-Steam game"
echo
echo "Usage:"
echo "  1. Launch the application"
echo "  2. Select Bluetooth or Wired USB mode"
echo "  3. Click 'Start Service'"
echo "  4. Connect from another device"
echo
echo "To update:  curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/install.sh | bash"
echo "To uninstall: curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/uninstall.sh | bash"
echo
