# Wired USB Mode

## Overview

The BT Controller Emulator now supports **Wired USB mode** in addition to Bluetooth mode! When connected via USB-C, your Steam Deck can act as a wired USB HID controller, keyboard, and mouse.

## How It Works

Wired mode uses the Linux USB Gadget framework (configfs) to create virtual USB HID devices. The Steam Deck appears as a USB controller/keyboard/mouse to the connected device.

### Comparison

| Feature | Bluetooth Mode | Wired USB Mode |
|---------|----------------|----------------|
| Connection | Wireless via BLE | USB-C cable |
| Latency | ~10-20ms | < 1ms |
| Setup | Auto-pairing | Requires setup script |
| Battery | Uses Bluetooth radio | No additional power |
| Host Support | BLE-capable devices | Any USB host |

## Setup Instructions

### One-Time Setup

1. **Run the USB gadget setup script** (requires sudo):
   ```bash
   sudo ~/steamdeck-bt-controller-emulator/scripts/setup-usb-gadget.sh
   ```

   This script:
   - Loads USB gadget kernel modules
   - Configures `/sys/kernel/config/usb_gadget`
   - Creates HID descriptor matching your Bluetooth profile
   - Creates `/dev/hidg0` device for HID reports

2. **Connect via USB-C**
   - Use a USB-C cable between Steam Deck and your target device
   - The cable must support data transfer (not charging-only)

### Using Wired Mode

1. Launch the BT Controller Emulator GUI
2. Select **"Wired USB"** mode (radio button at top)
3. Click **"Start Service"**
4. Your Steam Deck inputs will now be sent via USB!

### Cleanup

To remove the USB gadget configuration:
```bash
sudo ~/steamdeck-bt-controller-emulator/scripts/cleanup-usb-gadget.sh
```

## Technical Details

### USB Gadget Configuration

- **Vendor ID**: `0x28de` (Valve Corporation)
- **Product ID**: `0x1205` (Steam Deck Controller)
- **Device Class**: HID (Human Interface Device)
- **Report IDs**:
  - ID 1: Gamepad (11 buttons, 4 axes, 2 triggers, D-pad)
  - ID 2: Keyboard (modifiers + 6 simultaneous keys)
  - ID 3: Mouse (3 buttons, X/Y movement, wheel)

### Architecture

```
Physical Controller Input (evdev)
         ↓
  Input Handler
         ↓
    [Mode Switch]
    /           \
Bluetooth       Wired
(GATT/BLE)    (USB Gadget)
   ↓              ↓
Remote Device  Connected Device
```

### Files

- `src/hogp/usb_gadget.py` - USB Gadget HID handler
- `scripts/setup-usb-gadget.sh` - Configure USB gadget
- `scripts/cleanup-usb-gadget.sh` - Remove USB gadget
- `src/hogp/gui.py` - GUI with mode selection

## Troubleshooting

### "No USB gadget devices available"
- Run `sudo ~/steamdeck-bt-controller-emulator/scripts/setup-usb-gadget.sh`
- Check if `/dev/hidg0` exists: `ls -l /dev/hidg*`
- Verify USB gadget modules: `lsmod | grep usb_f_hid`

### "No UDC device found"
- Your system may not support USB gadget mode
- Check for USB Device Controller: `ls /sys/class/udc/`
- Steam Deck should have a UDC for its USB-C port

### Permissions Issues
- USB gadget devices require root/sudo to create
- After creation, `/dev/hidg*` should be readable/writable by your user
- The setup script attempts to set permissions: `chmod 666 /dev/hidg*`

### Cable Not Working
- Ensure USB-C cable supports data transfer
- Some cables are charging-only
- Try a different cable or USB port

## Advanced Usage

### Manual USB Gadget Testing

Write raw HID reports to test:
```bash
# Gamepad report (Report ID 1 + 13 bytes data)
echo -ne '\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' > /dev/hidg0

# Keyboard report (Report ID 2 + modifier + reserved + 6 keys)
echo -ne '\x02\x00\x00\x04\x00\x00\x00\x00\x00' > /dev/hidg0  # Press 'A'
echo -ne '\x02\x00\x00\x00\x00\x00\x00\x00\x00' > /dev/hidg0  # Release
```

### Persistent Setup

To make USB gadget persist across reboots, you could:
1. Create a systemd service to run setup-usb-gadget.sh at boot
2. Add it to `/etc/rc.local` or similar init system

## Limitations

- Wired and Bluetooth modes cannot run simultaneously
- USB gadget requires the Steam Deck to be in device mode (not host mode)
- Some USB hosts may not recognize composite HID devices

## Future Improvements

- [ ] Auto-setup USB gadget on first wired mode use
- [ ] Systemd service for persistent configuration
- [ ] Support for switching modes without stopping service
- [ ] USB gadget mode indicator in GUI
- [ ] Per-report-ID device files for better OS compatibility
