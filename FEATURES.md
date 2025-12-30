# New Features Added

## Enhanced GUI with Multiple Input Modes

Your Bluetooth controller emulator now supports **three input modes** in a tabbed interface:

### 1. **Controller Tab** (Original)
- Visual representation of gamepad state
- Forwards physical controller inputs when connected
- Shows button presses, analog sticks, triggers, and D-pad

### 2. **Keyboard Tab** (NEW)
- Virtual on-screen keyboard with common keys (A-Z, 0-9)
- Special keys: Enter, Escape, Backspace, Tab, Space, Arrow keys
- Text entry field to type and send full sentences
- Sends proper HID keyboard reports over Bluetooth

### 3. **Trackpad Tab** (NEW)
- Touch/drag area that converts to mouse movements
- Adjustable sensitivity slider
- Left, Right, and Middle click buttons
- Sends relative mouse movement HID reports

## Connection Information Display

The GUI now shows:
- **Connection Status**: Whether a device is connected
- **Device Name**: Name of the connected device (e.g., "iPhone", "Android Phone")
- **Device Address**: MAC address of the connected device

## Technical Details

### HID Report Map Changes
- Updated to support **multi-function HID device** with Report IDs
- **Report ID 1**: Gamepad (14 bytes) - 11 buttons, 4 axes, 2 triggers, HAT switch
- **Report ID 2**: Keyboard (9 bytes) - modifiers + 6 key codes
- **Report ID 3**: Mouse (7 bytes) - 3 buttons + X/Y movement + wheel

### New API Methods

#### GattApplication (gatt_app.py)
```python
# Keyboard
gatt_app.send_key(key_code, modifiers)  # Send a key press
gatt_app.get_keyboard_report()  # Get current keyboard state

# Mouse
gatt_app.send_mouse_movement(dx, dy, buttons, wheel)  # Send mouse input
gatt_app.get_mouse_report()  # Get current mouse state
```

#### BlueZ Helpers (bluez.py)
```python
# Get connected device info
device = get_primary_connected_device(bus, adapter_path)
# Returns: {'name': 'Device Name', 'address': 'AA:BB:CC:DD:EE:FF'}

devices = get_connected_devices(bus, adapter_path)
# Returns: List of all connected devices
```

## Usage

1. **Start the Service**: Click "Start Service" button
2. **Connect from another device**: 
   - Open Bluetooth settings on your phone/tablet/PC
   - Look for "SteamDeckPad"
   - Pair and connect
3. **Use the inputs**:
   - **Controller tab**: Physical gamepad inputs are forwarded automatically
   - **Keyboard tab**: Click keys or type text to send to connected device
   - **Trackpad tab**: Drag to move mouse, click buttons to click

## Testing

To test without sudo (gamepad only):
```bash
python3 -m hogp.gui
```

To test with full functionality (requires sudo for BLE):
```bash
sudo python3 -m hogp.gui
```

## Compatibility

- Connected device must support HID over GATT (HoG) profile
- Most modern smartphones, tablets, and PCs support this
- iOS, Android, Windows, macOS, Linux all compatible
- The device sees your Steam Deck as:
  - A gamepad
  - A keyboard
  - A mouse
  - All at the same time!

## What Changed

### Modified Files
- **src/hogp/gatt_app.py**: Added keyboard/mouse HID reports and notification methods
- **src/hogp/bluez.py**: Added connection info query functions
- **src/hogp/gui.py**: Complete redesign with tabbed interface, keyboard widget, trackpad widget

### No Changes Required
- Installation scripts work as before
- Desktop file launches the same way
- All existing functionality preserved
