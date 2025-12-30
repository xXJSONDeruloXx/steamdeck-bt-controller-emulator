HID-over-GATT profile implementation using BlueZ D-Bus APIs. Emulates a Bluetooth LE gamepad peripheral that forwards controller input from a Steam Deck to other devices.

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/install.sh | bash
```

Installs to `~/steamdeck-bt-controller-emulator`. Creates desktop launcher. Configures Bluetooth and input permissions. Log out and back in after first install.

Update by running the same command. Uninstall with `cd ~/steamdeck-bt-controller-emulator && ./uninstall.sh`.

## Usage

Launch from application menu or run `python3 -m src.hogp` directly. GUI provides connection management and input monitoring. CLI mode available for testing without `--gui` flag. Use `--forward /dev/input/eventX` to map physical controller.

## Development

Project uses justfile for deployment. `just deploy` syncs to Steam Deck over SSH. `just run` executes remotely. `just logs` tails system logs. Source in src/hogp includes bluez.py (D-Bus interface), gatt_app.py (HID service), input_handler.py (evdev forwarding), and gui.py (GTK4 interface).

## References

EmuBTHID, BTGamepad, diyps3controller, GIMX 