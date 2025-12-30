#!/bin/bash
#
# Setup USB gadget HID for Steam Deck wired controller mode
#
# This script configures the Linux USB gadget framework (configfs) to create
# a virtual USB HID device that matches our Bluetooth HID profile.
#
# Requires: configfs mounted, USB gadget drivers loaded, root/sudo access
#

set -e

GADGET_NAME="steamdeck_hid"
GADGET_DIR="/sys/kernel/config/usb_gadget/${GADGET_NAME}"
UDC_DEVICE=""  # Will be auto-detected

# Get script directory before we cd elsewhere
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# USB IDs (using Xbox 360 controller for universal compatibility)
VENDOR_ID="0x045e"   # Microsoft Corporation
PRODUCT_ID="0x028e"  # Xbox 360 Controller
DEVICE_BCD="0x0114"  # Device version 1.14 (Xbox 360)
USB_BCD="0x0200"     # USB 2.0

# Strings
SERIAL="steamdeck001"
MANUFACTURER="Microsoft Corp."
PRODUCT="Controller"

# Configuration
CONFIG_NAME="c.1"
MAX_POWER="250"  # 250mA
CONFIG_STRING="HID Gadget Configuration"

echo "=== Setting up USB Gadget HID for Steam Deck ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

# Load modules if not loaded
echo "Loading USB gadget modules..."
modprobe libcomposite 2>/dev/null || echo "libcomposite already loaded"
modprobe usb_f_hid 2>/dev/null || echo "usb_f_hid already loaded"

# Mount configfs if not mounted
if ! mountpoint -q /sys/kernel/config; then
    echo "Mounting configfs..."
    mount -t configfs none /sys/kernel/config
fi

# Check if gadget already exists
if [ -d "${GADGET_DIR}" ]; then
    echo "Warning: Gadget ${GADGET_NAME} already exists"
    echo "Run cleanup-usb-gadget.sh first to remove it"
    exit 1
fi

# Create gadget directory
echo "Creating gadget: ${GADGET_NAME}"
mkdir -p "${GADGET_DIR}"
cd "${GADGET_DIR}"

# Set USB device descriptor
echo "${VENDOR_ID}" > idVendor
echo "${PRODUCT_ID}" > idProduct
echo "${DEVICE_BCD}" > bcdDevice
echo "${USB_BCD}" > bcdUSB

# Device class (0x00 = defined at interface level)
echo "0x00" > bDeviceClass
echo "0x00" > bDeviceSubClass
echo "0x00" > bDeviceProtocol

# Create English strings
mkdir -p strings/0x409
echo "${SERIAL}" > strings/0x409/serialnumber
echo "${MANUFACTURER}" > strings/0x409/manufacturer
echo "${PRODUCT}" > strings/0x409/product

# Create configuration
echo "Creating configuration..."
mkdir -p "configs/${CONFIG_NAME}/strings/0x409"
echo "${CONFIG_STRING}" > "configs/${CONFIG_NAME}/strings/0x409/configuration"
echo "${MAX_POWER}" > "configs/${CONFIG_NAME}/MaxPower"

# Create HID function (combined HID with Report IDs for gamepad, keyboard, mouse, touchpad)
echo "Creating HID function..."
mkdir -p functions/hid.usb0
echo 0 > functions/hid.usb0/protocol  # 0 = none (report protocol)
echo 0 > functions/hid.usb0/subclass  # 0 = no subclass
echo 14 > functions/hid.usb0/report_length  # Max report length (gamepad is largest at 14 bytes)

# Write HID report descriptor as binary using Python script
echo "Writing HID report descriptor..."
python3 "${SCRIPT_DIR}/write-hid-descriptor.py" "${GADGET_DIR}/functions/hid.usb0/report_desc"

# Link function to configuration
ln -s functions/hid.usb0 "configs/${CONFIG_NAME}/"

# Find available UDC
echo "Finding UDC (USB Device Controller)..."
UDC_DEVICE=$(ls /sys/class/udc | head -n1)

if [ -z "${UDC_DEVICE}" ]; then
    echo "Error: No UDC device found!"
    echo "Your system may not support USB gadget mode."
    exit 1
fi

echo "Using UDC: ${UDC_DEVICE}"

# Enable gadget by binding to UDC
echo "Enabling USB gadget..."
echo "${UDC_DEVICE}" > UDC

# Wait for devices to appear
sleep 1

# Check if HID devices were created
if [ -c /dev/hidg0 ]; then
    echo "✓ USB HID gadget device created successfully!"
    echo "  - /dev/hidg0 (Combined HID: gamepad + keyboard + mouse + touchpad)"
    ls -l /dev/hidg*
else
    echo "Warning: /dev/hidg0 not created yet. It may take a few seconds."
fi

# Set permissions for hidg devices
echo "Setting permissions on /dev/hidg*..."
sleep 1
chmod 666 /dev/hidg* 2>/dev/null || echo "Note: Run 'sudo chmod 666 /dev/hidg*' after devices appear"

echo
echo "=== USB Gadget HID Setup Complete ==="
echo
echo "The Steam Deck will now appear as a USB HID device when connected via USB-C."
echo "Write HID reports to /dev/hidg0 to send controller/keyboard/mouse inputs."
echo
echo "To disable: Run cleanup-usb-gadget.sh or:"
echo "  sudo echo \"\" > ${GADGET_DIR}/UDC"
echo

exit 0
