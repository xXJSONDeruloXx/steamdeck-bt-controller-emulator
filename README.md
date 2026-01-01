# Steamin Ma HoG

Emulates a Bluetooth LE or **Wired USB** gamepad peripheral that forwards controller input from a Steam Deck to other devices. Not only that, but you also get full keyboard, trackpad, and media controls tabs. 

![controller view](assets/controller-tab.png) ![keyboard view](assets/keyboard-tab.png) ![media view](assets/media-tab.png) ![trackpad view](assets/trackpad-tab.png)

This is a HID-over-GATT profile implementation using BlueZ D-Bus APIs for Bluetooth, plus USB Gadget (configfs) support for wired connections. Primarily built with Steam Deck and Steam OS in mind, but other linux devices could take advantage too, just be sure to install any dependencies the install script may complain about not having.

## Installation

**Do Not Blindly Run Scripts You Find On The Internet!** Review the contents first: [install.sh](install.sh)

Copy the following command and paste into your terminal (konsole on Steam Deck):

```bash
curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/install.sh | bash
```

- Installs to `~/steamdeck-bt-controller-emulator`
- Creates desktop launcher and shortcuts
- Configures Bluetooth and input permissions
- **Log out and back in after first install** for group changes to take effect

I recommend right clicking/long pressing on the app or desktop shortcut and adding to Steam. From there you can take advantage of Steam Input for gyro, back buttons, dual trackpads etc.

Run the same installation command to update to the latest version:

```bash
curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/install.sh | bash
```

### Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/xXJSONDeruloXx/steamdeck-bt-controller-emulator/main/uninstall.sh | bash
```


## Usage

### Bluetooth Mode (Wireless)

Launch from application menu, desktop shortcut or run `python3 -m src.hogp` directly. GUI provides connection management and input monitoring. 

1. Select **Bluetooth** mode in the GUI
2. Press "Start Service"
3. On the device you want to control, open bluetooth settings
4. Look for "SteamDeckPad" or "BlueZ 597" and connect
5. Follow pairing prompts on both devices

After a few seconds, the device should now recognize an hid controller over bluetooth, as well as a keyboard and mouse hid device.

### Wired Mode

For wired connection:

1. Go into bios (hold + while booting up or in terminal run `systemctl reboot --firmware`)
2. in Utility > Advanced > USB Config > USB Dual Role and set to `DRD`.
2. Connect Steam Deck to target device with data usb c cable
3. Select **Wired USB** mode in the GUI
4. Press "Start Service" (input pass if asked)

Your Steam Deck will appear as a USB HID controller/keyboard/mouse.

CLI mode available for testing without `--gui` flag. Use `--forward /dev/input/eventX` to map physical controller.

## Troubleshooting

- if you make the connection to the computer but steam does not recognize any controller, first try a reboot (especially if you have not logged out/rebooted since first install). If you still have issues, try forgetting both the deck from the PC and the pc from the deck in their respective bluetooth settings.

- When pairing, be sure on both devices to affirm the pin matches when asked, generally I find acknowledging on the PC first, then steam deck second is the best way to go, but it shouldn't matter much

- on first pair, you will probably have to jump into controller config settings in steam and do the mapping routine, things like triggers and bumpers may not map exactly right by default but all inputs are exposed so Steam can assign to the right places. skip guide and qam buttons, those are mapped inside the GUI rather than the physical controllers pass through (since the actual decks guide and qam are reserved for its nav needs).

## Development

`just deploy` syncs to Steam Deck over SSH (be sure to change the ip). `just run` executes remotely. `just logs` tails system logs. Source in src/hogp includes bluez.py (D-Bus interface), gatt_app.py (HID service), input_handler.py (evdev forwarding), and gui.py (GTK4 interface).

## References

[EmuBTHID](https://github.com/Alkaid-Benetnash/EmuBTHID), [BTGamepad](https://github.com/007durgesh219/BTGamepad), [diyps3controller](https://github.com/rafikel/diyps3controller), [GIMX](https://github.com/matlo/GIMX) 