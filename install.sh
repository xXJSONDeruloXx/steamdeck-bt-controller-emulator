#!/bin/bash
# One-line installer for BT Controller Emulator
# Usage: curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/install.sh | bash

set -e

REPO_URL="https://github.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator.git"
INSTALL_DIR="$HOME/steamdeck-bt-controller-emulator"

echo "=== BT Controller Emulator - Installer ==="
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Don't run as root. Run as your regular user."
    exit 1
fi

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

# Add to groups
CURRENT_USER="$USER"
GROUPS_CHANGED=false

if ! groups "$CURRENT_USER" | grep -q "input"; then
    sudo usermod -a -G input "$CURRENT_USER"
    echo "✓ Added to 'input' group"
    GROUPS_CHANGED=true
fi

if ! getent group bluetooth > /dev/null 2>&1; then
    sudo groupadd -r bluetooth
fi

if ! groups "$CURRENT_USER" | grep -q "bluetooth"; then
    sudo usermod -a -G bluetooth "$CURRENT_USER"
    echo "✓ Added to 'bluetooth' group"
    GROUPS_CHANGED=true
fi

# Install D-Bus policy
sudo mkdir -p /etc/dbus-1/system.d
sudo cp "$INSTALL_DIR/config/bt-controller-emulator-dbus.conf" /etc/dbus-1/system.d/bt-controller-emulator.conf
echo "✓ D-Bus policy installed"

# Install sudoers rule
sudo mkdir -p /etc/sudoers.d
sudo cp "$INSTALL_DIR/config/bt-controller-emulator-sudoers" /etc/sudoers.d/bt-controller-emulator
sudo chmod 0440 /etc/sudoers.d/bt-controller-emulator
echo "✓ Sudoers rule installed"

# Reload D-Bus
sudo systemctl reload dbus 2>/dev/null || true

# Create desktop launcher
echo
echo "Creating launcher..."
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/Desktop"

DESKTOP_FILE="$HOME/.local/share/applications/bt-controller-emulator.desktop"
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
cp "$DESKTOP_FILE" "$HOME/Desktop/bt-controller-emulator.desktop"
chmod +x "$HOME/Desktop/bt-controller-emulator.desktop"

chmod +x "$INSTALL_DIR/scripts/run-gui.sh"
chmod +x "$INSTALL_DIR/scripts/launcher-wrapper.sh"

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo
echo "=== Installation Complete ==="
echo
if [ "$GROUPS_CHANGED" = true ]; then
    echo "⚠  Activating new group memberships..."
    exec sg input -c "exec sg bluetooth -c 'echo ✓ Groups activated. Launch BT Controller Emulator from your application menu; exec $SHELL'"
fi
echo "Launch 'BT Controller Emulator' from your application menu"
echo
echo "To update:  curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/install.sh | bash"
echo "To uninstall: cd $INSTALL_DIR && ./uninstall.sh"
echo
