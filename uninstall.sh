#!/bin/bash
# Uninstaller for BT Controller Emulator

set -e

echo "=== BT Controller Emulator - Uninstaller ==="
echo

if [ "$EUID" -eq 0 ]; then
    echo "Don't run as root. Run as your regular user."
    exit 1
fi

INSTALL_DIR="$HOME/steamdeck-bt-controller-emulator"
read -p "Remove $INSTALL_DIR and system configuration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

# Remove desktop files
rm -f "$HOME/.local/share/applications/bt-controller-emulator.desktop"
rm -f "$HOME/Desktop/bt-controller-emulator.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# Remove system config
sudo rm -f /etc/dbus-1/system.d/bt-controller-emulator.conf
sudo rm -f /etc/sudoers.d/bt-controller-emulator
sudo systemctl reload dbus 2>/dev/null || true

# Remove from bluetooth group
if groups "$USER" | grep -q "bluetooth"; then
    sudo gpasswd -d "$USER" bluetooth
    if ! getent group bluetooth | grep -q ':.*:'; then
        sudo groupdel bluetooth 2>/dev/null || true
    fi
fi

# Remove installation directory
rm -rf "$INSTALL_DIR"

echo
echo "✓ Uninstall complete"
echo "Note: You are still in 'input' group (other apps may need it)"
echo
