#!/bin/bash
# Uninstallation script for BT Controller Emulator on Steam Deck

set -e

echo "=== BT Controller Emulator - Uninstaller ==="
echo

if [ "$EUID" -eq 0 ]; then
    echo "Don't run this script as root (no sudo). Run as your regular user."
    exit 1
fi

CURRENT_USER="$USER"
INSTALL_DIR="$HOME/steamdeck-bt-controller-emulator"
DESKTOP_FILE="$HOME/.local/share/applications/bt-controller-emulator.desktop"
DESKTOP_SHORTCUT="$HOME/Desktop/bt-controller-emulator.desktop"

echo "This will remove:"
echo "  - Application files from: $INSTALL_DIR"
echo "  - Desktop shortcuts"
echo "  - System permissions (D-Bus policies, sudoers rules)"
echo "  - User from 'bluetooth' group (will keep 'input' group)"
echo
read -p "Continue with uninstall? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Remove desktop files
echo
echo "Removing desktop shortcuts..."
if [ -f "$DESKTOP_FILE" ]; then
    rm "$DESKTOP_FILE"
    echo "✓ Removed: $DESKTOP_FILE"
fi

if [ -f "$DESKTOP_SHORTCUT" ]; then
    rm "$DESKTOP_SHORTCUT"
    echo "✓ Removed: $DESKTOP_SHORTCUT"
fi

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

# Remove system configuration files
echo
echo "Removing system configuration files (requires sudo)..."

# Remove D-Bus policy
DBUS_POLICY="/etc/dbus-1/system.d/bt-controller-emulator.conf"
if [ -f "$DBUS_POLICY" ]; then
    sudo rm "$DBUS_POLICY" || {
        echo "⚠ Warning: Could not remove D-Bus policy: $DBUS_POLICY"
    }
    echo "✓ Removed D-Bus policy"
fi

# Remove sudoers rule
SUDOERS_FILE="/etc/sudoers.d/bt-controller-emulator"
if [ -f "$SUDOERS_FILE" ]; then
    sudo rm "$SUDOERS_FILE" || {
        echo "⚠ Warning: Could not remove sudoers rule: $SUDOERS_FILE"
    }
    echo "✓ Removed sudoers rule"
fi

# Reload D-Bus
echo
echo "Reloading D-Bus configuration..."
sudo systemctl reload dbus || {
    echo "⚠ Warning: Could not reload D-Bus"
}

# Remove user from bluetooth group (keep input group as it might be needed for other apps)
echo
echo "Removing user from 'bluetooth' group..."
if groups "$CURRENT_USER" | grep -q "bluetooth"; then
    sudo gpasswd -d "$CURRENT_USER" bluetooth || {
        echo "⚠ Warning: Could not remove user from bluetooth group"
    }
    echo "✓ Removed from 'bluetooth' group"
    GROUPS_CHANGED=true
    
    # Check if bluetooth group is now empty and was created by us
    if ! getent group bluetooth | grep -q ':.*:'; then
        echo "Bluetooth group is now empty. Removing it..."
        sudo groupdel bluetooth 2>/dev/null || true
        echo "✓ Removed 'bluetooth' group"
    fi
else
    echo "✓ Already not in 'bluetooth' group"
fi

echo
echo "Note: You are still in the 'input' group (for controller access)."
echo "      This is generally useful and safe to keep."
read -p "Remove from 'input' group as well? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if groups "$CURRENT_USER" | grep -q "input"; then
        sudo gpasswd -d "$CURRENT_USER" input || {
            echo "⚠ Warning: Could not remove user from input group"
        }
        echo "✓ Removed from 'input' group"
        GROUPS_CHANGED=true
    fi
fi

# Ask about removing application files
echo
read -p "Remove application files from $INSTALL_DIR? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$INSTALL_DIR" ]; then
        # Check if we're currently in the install directory
        CURRENT_DIR="$(pwd)"
        if [[ "$CURRENT_DIR" == "$INSTALL_DIR"* ]]; then
            cd "$HOME"
            echo "Changed directory to $HOME (was inside install directory)"
        fi
        
        rm -rf "$INSTALL_DIR"
        echo "✓ Removed: $INSTALL_DIR"
    else
        echo "✓ Directory already removed or not found"
    fi
fi

echo
echo "=== Uninstall Complete! ==="
echo

if [ "${GROUPS_CHANGED:-false}" = true ]; then
    echo "⚠ IMPORTANT: Group memberships were changed."
    echo "   You should log out and log back in for changes to take effect."
    echo
fi

echo "BT Controller Emulator has been uninstalled."
echo
