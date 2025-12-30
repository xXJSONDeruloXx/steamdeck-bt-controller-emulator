#!/bin/bash
#
# Diagnostic script for USB Gadget HID wired mode
#

echo "=== USB Gadget HID Diagnostic ==="
echo

# Check if running on the device (Steam Deck)
echo "1. Checking USB Device Controller (UDC)..."
if [ -d /sys/class/udc ]; then
    UDC_COUNT=$(ls /sys/class/udc 2>/dev/null | wc -l)
    echo "   ✓ UDC directory exists"
    echo "   Found $UDC_COUNT UDC device(s):"
    ls -1 /sys/class/udc 2>/dev/null | sed 's/^/     - /'
else
    echo "   ✗ No /sys/class/udc - USB gadget mode not supported"
    exit 1
fi

echo

# Check configfs
echo "2. Checking configfs..."
if mountpoint -q /sys/kernel/config; then
    echo "   ✓ configfs is mounted"
else
    echo "   ✗ configfs not mounted"
    echo "   Run: sudo mount -t configfs none /sys/kernel/config"
fi

echo

# Check for gadget configuration
echo "3. Checking USB gadget configuration..."
GADGET_DIR="/sys/kernel/config/usb_gadget/steamdeck_hid"
if [ -d "$GADGET_DIR" ]; then
    echo "   ✓ Gadget configured at $GADGET_DIR"
    
    # Check UDC binding
    if [ -f "$GADGET_DIR/UDC" ] && [ -s "$GADGET_DIR/UDC" ]; then
        UDC_BOUND=$(cat "$GADGET_DIR/UDC")
        echo "   ✓ Gadget bound to UDC: $UDC_BOUND"
    else
        echo "   ✗ Gadget not bound to UDC"
        echo "   Run setup script again"
    fi
else
    echo "   ✗ No gadget configuration found"
    echo "   Run: sudo ~/steamdeck-bt-controller-emulator/scripts/setup-usb-gadget.sh"
fi

echo

# Check for HID devices
echo "4. Checking /dev/hidg* devices..."
if ls /dev/hidg* > /dev/null 2>&1; then
    echo "   ✓ HID gadget devices found:"
    ls -lh /dev/hidg* | sed 's/^/     /'
    
    # Check permissions
    for dev in /dev/hidg*; do
        if [ -w "$dev" ]; then
            echo "   ✓ $dev is writable"
        else
            echo "   ✗ $dev is NOT writable (check permissions)"
        fi
    done
else
    echo "   ✗ No /dev/hidg* devices found"
    echo "   The gadget may need a few seconds to initialize after setup"
fi

echo

# Check kernel modules
echo "5. Checking kernel modules..."
if lsmod | grep -q usb_f_hid; then
    echo "   ✓ usb_f_hid module loaded"
else
    echo "   ✗ usb_f_hid module not loaded"
    echo "   Run: sudo modprobe usb_f_hid"
fi

if lsmod | grep -q libcomposite; then
    echo "   ✓ libcomposite module loaded"
else
    echo "   ✗ libcomposite module not loaded"
    echo "   Run: sudo modprobe libcomposite"
fi

echo

# Check USB cable connection
echo "6. Checking USB connection..."
if dmesg | tail -20 | grep -qi "usb.*gadget"; then
    echo "   ✓ Recent USB gadget activity in dmesg"
    echo "   Last 5 relevant lines:"
    dmesg | grep -i "usb.*gadget" | tail -5 | sed 's/^/     /'
else
    echo "   ⚠ No recent USB gadget activity"
    echo "   Make sure USB-C cable is connected and supports data"
fi

echo

# Summary
echo "=== Summary ==="
if ls /dev/hidg* > /dev/null 2>&1 && [ -f "$GADGET_DIR/UDC" ] && [ -s "$GADGET_DIR/UDC" ]; then
    echo "✓ USB gadget appears to be configured correctly"
    echo
    echo "If the PC still doesn't detect the controller:"
    echo "  1. Try a different USB-C cable (must support data, not just charging)"
    echo "  2. Try a different USB port on the PC"
    echo "  3. Check PC device manager / lsusb for new USB devices"
    echo "  4. Run: dmesg -w  (on Steam Deck to see live USB events)"
    echo "  5. On the PC, try: lsusb -v | grep -A 10 'Valve'"
else
    echo "✗ USB gadget not fully configured"
    echo
    echo "Run this to set up:"
    echo "  sudo ~/steamdeck-bt-controller-emulator/scripts/setup-usb-gadget.sh"
fi
echo
