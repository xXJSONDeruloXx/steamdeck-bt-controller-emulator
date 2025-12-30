"""
Main entrypoint for the HID-over-GATT peripheral emulator.

Usage:
    sudo python3 -m hogp --name SteamDeckHoG --rate 10
"""

import argparse
import logging
import signal
import sys
import threading
from typing import Optional

from gi.repository import GLib

from .bluez import (
    get_system_bus,
    find_adapter_path,
    ensure_adapter_powered_and_discoverable,
    register_application_async,
    unregister_application_async,
    register_advertisement_async,
    unregister_advertisement_async,
    get_le_advertising_active_instances,
    set_static_ble_address,
    get_adapter_index,
)
from .gatt_app import GattApplication
from .adv import Advertisement
from .input_handler import InputHandler

logger = logging.getLogger(__name__)


class HoGPeripheral:
    """
    HID-over-GATT peripheral controller.
    
    Manages the GATT application and advertisement lifecycle,
    and provides a simple CLI for testing.
    """

    def __init__(
        self,
        name: str = "SteamDeckHoG",
        rate: int = 10,
        adapter: str = "hci0",
        static_addr: Optional[str] = "C2:12:34:56:78:9A",
        input_device: Optional[str] = None,
        verbose: bool = False,
    ):
        self.name = name
        self.rate = rate
        self.adapter = adapter
        self.static_addr = static_addr
        self.input_device = input_device
        self.verbose = verbose
        
        self._bus: Optional[GLib.DBusConnection] = None
        self._adapter_path: Optional[str] = None
        self._gatt_app: Optional[GattApplication] = None
        self._advertisement: Optional[Advertisement] = None
        self._input_handler: Optional[InputHandler] = None
        self._main_loop: Optional[GLib.MainLoop] = None
        self._registered = False
        self._shutting_down = False
        
        # Test pattern state
        self._test_pattern_id: Optional[int] = None
        self._test_button_idx = 0
        self._test_axis_value = 0
        self._test_axis_direction = 1

    def run(self) -> int:
        """Run the peripheral. Returns exit code."""
        # Setup logging
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
        
        logger.info(f"Starting HoG Peripheral: name={self.name}, rate={self.rate}Hz")
        
        # Get D-Bus connection
        try:
            self._bus = get_system_bus()
            logger.info(f"Connected to system bus: {self._bus.get_unique_name()}")
        except Exception as e:
            logger.error(f"Failed to connect to system bus: {e}")
            return 1
        
        # Find adapter
        self._adapter_path = find_adapter_path(self._bus, self.adapter)
        if not self._adapter_path:
            logger.error(f"Adapter {self.adapter} not found")
            return 1
        logger.info(f"Using adapter: {self._adapter_path}")
        
        # Set static BLE address to prevent duplicate controller entries
        if self.static_addr:
            adapter_idx = get_adapter_index(self.adapter)
            if set_static_ble_address(adapter_idx, self.static_addr):
                logger.info(f"Static BLE address configured: {self.static_addr}")
            else:
                logger.warning("Could not set static BLE address - device may appear as duplicate controller on reconnect")
        else:
            logger.info("Static BLE address not configured (--no-static-addr)")
        
        # Ensure adapter is powered
        if not ensure_adapter_powered_and_discoverable(self._bus, self._adapter_path):
            logger.error("Failed to power on adapter")
            return 1
        
        # Create GATT application
        self._gatt_app = GattApplication(self._bus, device_name=self.name, verbose=self.verbose)
        self._gatt_app.set_report_rate(self.rate)
        
        if not self._gatt_app.register():
            logger.error("Failed to register GATT objects")
            return 1
        
        # Create advertisement
        self._advertisement = Advertisement(self._bus, self.name, verbose=self.verbose)
        if not self._advertisement.register():
            logger.error("Failed to register advertisement object")
            self._gatt_app.unregister()
            return 1
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Setup input handler if input device specified or auto-detect enabled
        if self.input_device or self.input_device != "none":
            logger.info("Setting up physical input forwarding...")
            self._input_handler = InputHandler(
                device_path=self.input_device if self.input_device != "auto" else None,
                on_button_change=self._on_physical_button,
                on_axis_change=self._on_physical_axis,
                verbose=self.verbose,
            )
            if self._input_handler.start():
                logger.info("Physical input forwarding enabled")
            else:
                logger.warning("Could not start input handler, falling back to CLI-only mode")
                self._input_handler = None
        else:
            logger.info("Physical input forwarding disabled (use --input-device to enable)")
        
        # Create main loop
        self._main_loop = GLib.MainLoop()
        
        # Register with BlueZ asynchronously
        self._register_with_bluez()
        
        # Start CLI input thread
        cli_thread = threading.Thread(target=self._cli_loop, daemon=True)
        cli_thread.start()
        
        # Run main loop
        try:
            logger.info("Running main loop (press Ctrl+C to stop)...")
            self._main_loop.run()
        except KeyboardInterrupt:
            pass
        
        return 0

    def _register_with_bluez(self) -> None:
        """Register GATT application and advertisement with BlueZ."""
        def on_app_registered(success, error):
            if not success:
                logger.error(f"GATT registration failed: {error}")
                self._shutdown()
                return
            
            # Now register advertisement
            register_advertisement_async(
                self._bus,
                self._adapter_path,
                Advertisement.ADV_PATH,
                on_adv_registered,
            )
        
        def on_adv_registered(success, error):
            if not success:
                logger.error(f"Advertisement registration failed: {error}")
                self._shutdown()
                return
            
            self._registered = True
            active = get_le_advertising_active_instances(self._bus, self._adapter_path)
            logger.info(f"Registration complete! ActiveInstances: {active}")
            logger.info(f"Device should be discoverable as '{self.name}'")
            self._print_cli_help()
        
        register_application_async(
            self._bus,
            self._adapter_path,
            GattApplication.APP_PATH,
            on_app_registered,
        )

    def _signal_handler(self, sig, frame) -> None:
        """Handle SIGINT/SIGTERM."""
        logger.info("Received shutdown signal")
        GLib.idle_add(self._shutdown)

    def _shutdown(self) -> None:
        """Clean shutdown procedure."""
        if self._shutting_down:
            return
        self._shutting_down = True
        
        logger.info("Shutting down...")
        
        # Stop test pattern
        if self._test_pattern_id:
            GLib.source_remove(self._test_pattern_id)
            self._test_pattern_id = None
        
        # Stop input handler
        if self._input_handler:
            self._input_handler.stop()
            self._input_handler = None
        
        # Unregister from BlueZ
        if self._registered and self._bus and self._adapter_path:
            unregister_advertisement_async(
                self._bus,
                self._adapter_path,
                Advertisement.ADV_PATH,
            )
            unregister_application_async(
                self._bus,
                self._adapter_path,
                GattApplication.APP_PATH,
            )
        
        # Unregister D-Bus objects
        if self._advertisement:
            self._advertisement.unregister()
        if self._gatt_app:
            self._gatt_app.unregister()
        
        # Quit main loop
        if self._main_loop and self._main_loop.is_running():
            self._main_loop.quit()

    def _print_cli_help(self) -> None:
        """Print CLI help."""
        print("\n--- CLI Commands ---")
        print("  b <0-15>     : Toggle button (e.g., 'b 0')")
        print("  a <0-3> <val>: Set axis value (e.g., 'a 0 16000')")
        print("  t            : Start/stop test pattern")
        print("  s            : Show current state")
        print("  q            : Quit")
        print("--------------------\n")

    def _cli_loop(self) -> None:
        """Simple CLI for testing input."""
        while not self._shutting_down:
            try:
                line = input().strip().lower()
                if not line:
                    continue
                
                parts = line.split()
                cmd = parts[0]
                
                if cmd == "q":
                    GLib.idle_add(self._shutdown)
                    break
                elif cmd == "b" and len(parts) >= 2:
                    try:
                        btn = int(parts[1])
                        if 0 <= btn < 16:
                            # Toggle button
                            current = (self._gatt_app._buttons >> btn) & 1
                            self._gatt_app.set_button(btn, not current)
                            print(f"Button {btn} {'pressed' if not current else 'released'}")
                    except ValueError:
                        print("Invalid button number")
                elif cmd == "a" and len(parts) >= 3:
                    try:
                        axis = int(parts[1])
                        value = int(parts[2])
                        if 0 <= axis < 4:
                            self._gatt_app.set_axis(axis, value)
                            print(f"Axis {axis} = {value}")
                    except ValueError:
                        print("Invalid axis/value")
                elif cmd == "t":
                    GLib.idle_add(self._toggle_test_pattern)
                elif cmd == "s":
                    self._show_state()
                else:
                    self._print_cli_help()
            except EOFError:
                break
            except Exception as e:
                logger.debug(f"CLI error: {e}")

    def _toggle_test_pattern(self) -> bool:
        """Toggle the test pattern on/off."""
        if self._test_pattern_id:
            GLib.source_remove(self._test_pattern_id)
            self._test_pattern_id = None
            print("Test pattern stopped")
        else:
            self._test_pattern_id = GLib.timeout_add(500, self._test_pattern_tick)
            print("Test pattern started (cycling buttons and sweeping axis)")
        return False

    def _on_physical_button(self, button_index: int, pressed: bool) -> None:
        """Callback for physical button events."""
        if self._gatt_app and not self._shutting_down:
            self._gatt_app.set_button(button_index, pressed)
            if self.verbose:
                logger.debug(f"Physical button {button_index} {'pressed' if pressed else 'released'}")

    def _on_physical_axis(self, axis_index: int, value: int) -> None:
        """Callback for physical axis events."""
        if self._gatt_app and not self._shutting_down:
            self._gatt_app.set_axis(axis_index, value)
            if self.verbose:
                logger.debug(f"Physical axis {axis_index} = {value}")

    def _test_pattern_tick(self) -> bool:
        """Update test pattern state."""
        if self._shutting_down:
            return False
        
        # Cycle through buttons
        self._gatt_app.set_button(self._test_button_idx, False)
        self._test_button_idx = (self._test_button_idx + 1) % 16
        self._gatt_app.set_button(self._test_button_idx, True)
        
        # Sweep axis 0
        self._test_axis_value += self._test_axis_direction * 4000
        if self._test_axis_value >= 32000:
            self._test_axis_direction = -1
        elif self._test_axis_value <= -32000:
            self._test_axis_direction = 1
        self._gatt_app.set_axis(0, self._test_axis_value)
        
        return True

    def _show_state(self) -> None:
        """Print current controller state."""
        buttons = self._gatt_app._buttons
        axes = self._gatt_app._axes
        notifying = self._gatt_app.notifying
        
        print(f"\nButtons: 0x{buttons:04X} (binary: {buttons:016b})")
        print(f"Axes: X={axes[0]}, Y={axes[1]}, Z={axes[2]}, Rz={axes[3]}")
        print(f"Notifying: {notifying}")
        print(f"Report: {self._gatt_app.get_current_report().hex()}\n")


def main():
    """Main entrypoint."""
    parser = argparse.ArgumentParser(
        description="Steam Deck BLE HID-over-GATT Peripheral",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    sudo python3 -m hogp --name SteamDeckHoG --rate 10
    sudo python3 -m hogp --verbose

Verification commands (run in another terminal):
    # Check advertisement is active:
    busctl --system get-property org.bluez /org/bluez/hci0 \\
        org.bluez.LEAdvertisingManager1 ActiveInstances

    # Check GATT objects (replace :1.xxx with actual bus name):
    busctl --system list | grep python3
    busctl --system call :1.xxx /com/steamdeck/hogp \\
        org.freedesktop.DBus.ObjectManager GetManagedObjects
""",
    )
    parser.add_argument(
        "--name",
        default="SteamDeckHoG",
        help="Local name for advertisement (default: SteamDeckHoG)",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=10,
        help="Notification rate in Hz (default: 10)",
    )
    parser.add_argument(
        "--adapter",
        default="hci0",
        help="Bluetooth adapter name (default: hci0)",
    )
    parser.add_argument(
        "--input-device",
        default="auto",
        help="Input device path for physical controller forwarding (default: auto, use 'none' to disable)",
    )
    parser.add_argument(
        "--static-addr",
        default="C2:12:34:56:78:9A",
        help="Static BLE address to prevent duplicate controllers (default: C2:12:34:56:78:9A)",
    )
    parser.add_argument(
        "--no-static-addr",
        action="store_true",
        help="Skip setting static BLE address",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    peripheral = HoGPeripheral(
        name=args.name,
        rate=args.rate,
        adapter=args.adapter,
        static_addr=None if args.no_static_addr else args.static_addr,
        input_device=args.input_device,
        verbose=args.verbose,
    )
    
    sys.exit(peripheral.run())


if __name__ == "__main__":
    main()
