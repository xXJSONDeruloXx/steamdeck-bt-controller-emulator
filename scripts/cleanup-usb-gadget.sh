#!/bin/bash
#
# Cleanup USB gadget HID configuration
#
# This script safely tears down the USB gadget configuration created by
# setup-usb-gadget.sh
#

set -e

GADGET_NAME="steamdeck_hid"
GADGET_DIR="/sys/kernel/config/usb_gadget/${GADGET_NAME}"

echo "=== Cleaning up USB Gadget HID ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

# Check if gadget exists
if [ ! -d "${GADGET_DIR}" ]; then
    echo "No gadget found at ${GADGET_DIR}"
    echo "Nothing to clean up."
    exit 0
fi

cd "${GADGET_DIR}"

# Disable gadget by unbinding from UDC
echo "Disabling USB gadget..."
if [ -f UDC ]; then
    # Read current UDC value
    CURRENT_UDC=$(cat UDC 2>/dev/null || echo "")
    if [ -n "$CURRENT_UDC" ]; then
        echo "" > UDC 2>/dev/null || echo "Note: UDC already unbound"
        echo "✓ Gadget disabled"
    else
        echo "✓ Gadget already disabled"
    fi
fi

# Small delay to ensure kernel releases resources
sleep 0.5

# Remove function symlinks from configuration
echo "Removing function links..."
rm -f configs/c.1/hid.usb0 2>/dev/null || true
rm -f configs/c.1/hid.usb1 2>/dev/null || true
rm -f configs/c.1/hid.usb2 2>/dev/null || true

# Remove configurations
echo "Removing configurations..."
rmdir configs/c.1/strings/0x409 2>/dev/null || true
rmdir configs/c.1 2>/dev/null || true

# Remove functions
echo "Removing functions..."
rmdir functions/hid.usb0 2>/dev/null || true
rmdir functions/hid.usb1 2>/dev/null || true
rmdir functions/hid.usb2 2>/dev/null || true

# Remove strings
echo "Removing strings..."
rmdir strings/0x409 2>/dev/null || true

# Remove gadget directory
cd ..
echo "Removing gadget directory..."
rmdir "${GADGET_DIR}" 2>/dev/null || true

if [ ! -d "${GADGET_DIR}" ]; then
    echo "✓ USB gadget cleaned up successfully"
else
    echo "Warning: Could not fully remove gadget directory"
    echo "Some resources may still be in use"
    exit 1
fi

echo
echo "=== Cleanup Complete ==="
echo

exit 0
