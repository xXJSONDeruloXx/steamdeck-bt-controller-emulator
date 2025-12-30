This project implements a **HID-over-GATT (HoG) profile** peripheral using BlueZ's D-Bus APIs. When running on a Steam Deck (SteamOS), it:

1. Advertises as a BLE peripheral named "SteamDeckHoG" (configurable)
2. Exposes a GATT HID Service (UUID 0x1812) with standard characteristics
3. Sends HID input reports via BLE notifications
4. Forwards physical controller inputs to the Bluetooth HoG device
5. Provides a simple CLI for testing button presses and axis movements

## Prerequisites

**Required Python packages:**
```bash
# On Steam Deck / SteamOS:
sudo pacman -S python-gobject python-dbus python-evdev

# Or using pip:
pip install PyGObject dbus-python evdev
```

## Research References

These projects were referenced during development:

- [EmuBTHID](https://github.com/Alkaid-Benetnash/EmuBTHID) - Bluetooth HID emulation
- [BTGamepad](https://github.com/007durgesh219/BTGamepad) - Android Bluetooth gamepad
- [diyps3controller](https://github.com/rafikel/diyps3controller) - PS3 controller emulation
- [GIMX](https://github.com/matlo/GIMX) - Game Input Multiplexer
