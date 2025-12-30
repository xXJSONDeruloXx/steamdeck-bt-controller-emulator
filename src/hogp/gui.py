#!/usr/bin/env python3
"""
GTK GUI for HoG Peripheral - Steam Deck friendly interface.

Shows controller state, connection status, and input visualization.
"""

import logging
import sys
import os
import threading
from typing import Optional
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gdk

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hogp.bluez import (
    get_system_bus,
    find_adapter_path,
    ensure_adapter_powered_and_discoverable,
    register_application_async,
    unregister_application_async,
    register_advertisement_async,
    unregister_advertisement_async,
    set_static_ble_address,
    get_adapter_index,
)
from hogp.gatt_app import GattApplication
from hogp.adv import Advertisement
from hogp.input_handler import InputHandler

logger = logging.getLogger(__name__)


class ControllerVisualizer(Gtk.DrawingArea):
    """Custom widget to visualize controller state."""
    
    def __init__(self):
        super().__init__()
        self.set_size_request(600, 400)
        self.set_draw_func(self._draw_func)
        
        # Controller state
        self.buttons = 0
        self.axes = [0, 0, 0, 0]
        self.triggers = [0, 0]
        self.hat = 0x0F
        
    def update_state(self, buttons, axes, triggers, hat):
        """Update controller state and redraw."""
        self.buttons = buttons
        self.axes = axes
        self.triggers = triggers
        self.hat = hat
        self.queue_draw()
    
    def _draw_func(self, area, cr, width, height, user_data):
        """Draw the controller visualization."""
        # Background
        cr.set_source_rgb(0.15, 0.15, 0.15)
        cr.paint()
        
        # Draw controller outline
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.set_line_width(2)
        cr.rectangle(50, 50, width - 100, height - 100)
        cr.stroke()
        
        # Button layout (simplified gamepad representation)
        button_positions = [
            (width - 150, height/2, "A"),      # 0: BTN_SOUTH
            (width - 120, height/2 - 30, "B"), # 1: BTN_EAST
            (width - 150, height/2 - 60, "X"), # 2: BTN_NORTH
            (width - 180, height/2 - 30, "Y"), # 3: BTN_WEST
            (100, 100, "LB"),                  # 4: BTN_TL
            (width - 100, 100, "RB"),          # 5: BTN_TR
            (width/2 - 60, height - 120, "⋮"), # 6: BTN_SELECT
            (width/2 + 60, height - 120, "≡"), # 7: BTN_START
            (width/2, height - 150, "◉"),      # 8: BTN_MODE
            (180, height/2, "LS"),             # 9: BTN_THUMBL
            (width - 180, height/2 + 80, "RS"),# 10: BTN_THUMBR
        ]
        
        for i, (x, y, label) in enumerate(button_positions):
            pressed = (self.buttons >> i) & 1
            
            # Draw button circle
            if pressed:
                cr.set_source_rgb(0.3, 0.8, 0.3)  # Green when pressed
            else:
                cr.set_source_rgb(0.5, 0.5, 0.5)  # Gray when released
            
            cr.arc(x, y, 15, 0, 2 * 3.14159)
            cr.fill()
            
            # Draw label
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(10)
            extents = cr.text_extents(label)
            cr.move_to(x - extents.width/2, y + extents.height/2)
            cr.show_text(label)
        
        # Draw analog sticks
        self._draw_stick(cr, 150, height/2 - 20, self.axes[0], self.axes[1], "Left")
        self._draw_stick(cr, width - 150, height/2 + 80, self.axes[2], self.axes[3], "Right")
        
        # Draw triggers
        self._draw_trigger(cr, 100, 60, self.triggers[0], "LT")
        self._draw_trigger(cr, width - 100, 60, self.triggers[1], "RT")
        
        # Draw D-pad/HAT
        self._draw_dpad(cr, 230, height/2 + 80, self.hat)
    
    def _draw_stick(self, cr, cx, cy, x_val, y_val, label):
        """Draw an analog stick."""
        # Outer circle
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.arc(cx, cy, 30, 0, 2 * 3.14159)
        cr.fill()
        
        # Inner position
        # Convert -32768 to 32767 range to -1 to 1
        norm_x = x_val / 32768.0
        norm_y = y_val / 32768.0
        
        stick_x = cx + norm_x * 25
        stick_y = cy + norm_y * 25
        
        cr.set_source_rgb(0.8, 0.3, 0.3)
        cr.arc(stick_x, stick_y, 8, 0, 2 * 3.14159)
        cr.fill()
        
        # Label
        cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.set_font_size(9)
        extents = cr.text_extents(label)
        cr.move_to(cx - extents.width/2, cy + 50)
        cr.show_text(label)
    
    def _draw_trigger(self, cr, cx, cy, value, label):
        """Draw a trigger indicator."""
        # Background
        cr.set_source_rgb(0.3, 0.3, 0.3)
        cr.rectangle(cx - 20, cy, 40, 10)
        cr.fill()
        
        # Fill based on trigger value (0-255)
        fill_width = (value / 255.0) * 40
        cr.set_source_rgb(0.3, 0.8, 0.3)
        cr.rectangle(cx - 20, cy, fill_width, 10)
        cr.fill()
        
        # Label
        cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.set_font_size(9)
        extents = cr.text_extents(label)
        cr.move_to(cx - extents.width/2, cy - 5)
        cr.show_text(label)
    
    def _draw_dpad(self, cr, cx, cy, hat):
        """Draw D-pad/HAT indicator."""
        # Directions: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW, 0x0F=center
        directions = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
        
        # Draw cross
        cr.set_source_rgb(0.4, 0.4, 0.4)
        cr.rectangle(cx - 5, cy - 20, 10, 40)  # Vertical
        cr.rectangle(cx - 20, cy - 5, 40, 10)  # Horizontal
        cr.fill()
        
        # Highlight active direction
        if hat < 8:
            cr.set_source_rgb(0.3, 0.8, 0.3)
            angle = hat * 45 * (3.14159 / 180)
            dx = 15 * (-1 if hat in [5,6,7] else 1 if hat in [1,2,3] else 0)
            dy = 15 * (-1 if hat in [7,0,1] else 1 if hat in [3,4,5] else 0)
            cr.arc(cx + dx, cy + dy, 6, 0, 2 * 3.14159)
            cr.fill()
        
        # Label
        cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.set_font_size(9)
        cr.move_to(cx - 10, cy + 40)
        cr.show_text("D-Pad")


class HoGPeripheralGUI(Gtk.ApplicationWindow):
    """Main GUI window."""
    
    def __init__(self, app):
        super().__init__(application=app, title="BT Controller Emulator")
        self.set_default_size(700, 600)
        
        # State
        self._bus = None
        self._adapter_path = None
        self._gatt_app = None
        self._advertisement = None
        self._input_handler = None
        self._main_loop = None
        self._registered = False
        self._running = False
        self._update_timeout_id = None
        
        # Build UI
        self._build_ui()
        
    def _build_ui(self):
        """Build the user interface."""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        
        # Header bar
        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="BT Controller Emulator"))
        self.set_titlebar(header)
        
        # Status box
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        self.status_label = Gtk.Label(label="Status: Stopped")
        self.status_label.set_markup("<big><b>Status: Stopped</b></big>")
        status_box.append(self.status_label)
        
        self.connection_label = Gtk.Label(label="Not connected")
        status_box.append(self.connection_label)
        
        main_box.append(status_box)
        
        # Controller visualizer
        self.visualizer = ControllerVisualizer()
        frame = Gtk.Frame()
        frame.set_child(self.visualizer)
        main_box.append(frame)
        
        # Control buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        
        self.start_button = Gtk.Button(label="Start Controller")
        self.start_button.connect("clicked", self._on_start_clicked)
        button_box.append(self.start_button)
        
        self.stop_button = Gtk.Button(label="Stop Controller")
        self.stop_button.set_sensitive(False)
        self.stop_button.connect("clicked", self._on_stop_clicked)
        button_box.append(self.stop_button)
        
        main_box.append(button_box)
        
        # Info label
        info_label = Gtk.Label(
            label="Physical controller inputs will be forwarded when active.\n"
                  "Connect from another device via Bluetooth settings."
        )
        info_label.set_wrap(True)
        main_box.append(info_label)
        
        self.set_child(main_box)
    
    def _on_start_clicked(self, button):
        """Start the controller service."""
        self.start_button.set_sensitive(False)
        self.status_label.set_markup("<big><b>Status: Starting...</b></big>")
        threading.Thread(target=self._start_service, daemon=True).start()
    
    def _on_stop_clicked(self, button):
        """Stop the controller service."""
        self.stop_button.set_sensitive(False)
        self.status_label.set_markup("<big><b>Status: Stopping...</b></big>")
        GLib.idle_add(self._stop_service)
    
    def _start_service(self):
        """Start the BLE HoG service (runs in thread)."""
        try:
            # Get D-Bus connection
            self._bus = get_system_bus()
            
            # Find adapter
            self._adapter_path = find_adapter_path(self._bus, "hci0")
            if not self._adapter_path:
                GLib.idle_add(self._show_error, "Bluetooth adapter not found")
                return
            
            # Set static address
            adapter_idx = get_adapter_index("hci0")
            set_static_ble_address(adapter_idx, "C2:12:34:56:78:9A")
            
            # Ensure adapter is powered
            if not ensure_adapter_powered_and_discoverable(self._bus, self._adapter_path):
                GLib.idle_add(self._show_error, "Failed to power on Bluetooth")
                return
            
            # Create GATT application
            self._gatt_app = GattApplication(self._bus, device_name="SteamDeckPad", verbose=False)
            self._gatt_app.set_report_rate(60)
            
            if not self._gatt_app.register():
                GLib.idle_add(self._show_error, "Failed to register GATT service")
                return
            
            # Create advertisement
            self._advertisement = Advertisement(self._bus, "SteamDeckPad", verbose=False)
            if not self._advertisement.register():
                GLib.idle_add(self._show_error, "Failed to register advertisement")
                return
            
            # Register with BlueZ
            GLib.idle_add(self._register_with_bluez)
            
        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            GLib.idle_add(self._show_error, f"Error: {e}")
    
    def _register_with_bluez(self):
        """Register application and advertisement with BlueZ."""
        def on_app_registered(success, error):
            if not success:
                self._show_error(f"GATT registration failed: {error}")
                return
            
            register_advertisement_async(
                self._bus,
                self._adapter_path,
                Advertisement.ADV_PATH,
                on_adv_registered,
            )
        
        def on_adv_registered(success, error):
            if not success:
                self._show_error(f"Advertisement failed: {error}")
                return
            
            self._registered = True
            self._running = True
            self._start_input_handler()
            self.status_label.set_markup("<big><b>Status: Active - Discoverable</b></big>")
            self.connection_label.set_label("Waiting for connection...")
            self.stop_button.set_sensitive(True)
            
            # Start update loop
            self._update_timeout_id = GLib.timeout_add(50, self._update_visualizer)
        
        register_application_async(
            self._bus,
            self._adapter_path,
            GattApplication.APP_PATH,
            on_app_registered,
        )
    
    def _start_input_handler(self):
        """Start forwarding physical controller input."""
        self._input_handler = InputHandler(
            device_path=None,  # Auto-detect
            on_button_change=self._on_button,
            on_axis_change=self._on_axis,
            on_trigger_change=self._on_trigger,
            on_hat_change=self._on_hat,
            verbose=False,
        )
        
        if self._input_handler.start():
            logger.info("Input forwarding started")
            GLib.idle_add(self._update_connection_label, "Input device connected")
        else:
            logger.warning("No input device detected")
            GLib.idle_add(self._update_connection_label, "No physical controller found")
    
    def _on_button(self, index, pressed):
        """Handle button event from physical controller."""
        if self._gatt_app:
            self._gatt_app.set_button(index, pressed)
    
    def _on_axis(self, index, value):
        """Handle axis event from physical controller."""
        if self._gatt_app:
            self._gatt_app.set_axis(index, value)
    
    def _on_trigger(self, index, value):
        """Handle trigger event from physical controller."""
        if self._gatt_app:
            self._gatt_app.set_trigger(index, value)
    
    def _on_hat(self, direction):
        """Handle HAT/D-pad event from physical controller."""
        if self._gatt_app:
            self._gatt_app.set_hat(direction)
    
    def _update_visualizer(self):
        """Update the controller visualization."""
        if not self._running or not self._gatt_app:
            return False
        
        self.visualizer.update_state(
            self._gatt_app._buttons,
            self._gatt_app._axes,
            self._gatt_app._triggers,
            self._gatt_app._hat,
        )
        
        # Update connection status if notifying
        if self._gatt_app.notifying:
            self.connection_label.set_label("✓ Connected and sending data")
        elif self._registered:
            self.connection_label.set_label("Waiting for connection...")
        
        return True
    
    def _update_connection_label(self, text):
        """Update connection label."""
        self.connection_label.set_label(text)
    
    def _stop_service(self):
        """Stop the BLE HoG service."""
        self._running = False
        
        if self._update_timeout_id:
            GLib.source_remove(self._update_timeout_id)
            self._update_timeout_id = None
        
        if self._input_handler:
            self._input_handler.stop()
            self._input_handler = None
        
        if self._registered and self._bus and self._adapter_path:
            unregister_advertisement_async(self._bus, self._adapter_path, Advertisement.ADV_PATH)
            unregister_application_async(self._bus, self._adapter_path, GattApplication.APP_PATH)
            self._registered = False
        
        if self._advertisement:
            self._advertisement.unregister()
            self._advertisement = None
        
        if self._gatt_app:
            self._gatt_app.unregister()
            self._gatt_app = None
        
        self.status_label.set_markup("<big><b>Status: Stopped</b></big>")
        self.connection_label.set_label("Not connected")
        self.start_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
    
    def _show_error(self, message):
        """Show error message."""
        logger.error(message)
        self.status_label.set_markup(f"<big><b>Error: {message}</b></big>")
        self.start_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)


class HoGApp(Gtk.Application):
    """Main application."""
    
    def __init__(self):
        super().__init__(application_id="com.steamdeck.hogp.gui")
        
    def do_activate(self):
        """Application activated."""
        win = HoGPeripheralGUI(self)
        win.present()


def main():
    """Main entrypoint for GUI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    
    app = HoGApp()
    return app.run(None)


if __name__ == "__main__":
    import sys
    sys.exit(main())
