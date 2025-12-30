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
    get_primary_connected_device,
)
from hogp.gatt_app import GattApplication
from hogp.adv import Advertisement
from hogp.input_handler import InputHandler

logger = logging.getLogger(__name__)

# HID Keyboard key codes
HID_KEY_CODES = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
    'g': 0x0a, 'h': 0x0b, 'i': 0x0c, 'j': 0x0d, 'k': 0x0e, 'l': 0x0f,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
    's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1a, 'x': 0x1b,
    'y': 0x1c, 'z': 0x1d,
    '1': 0x1e, '2': 0x1f, '3': 0x20, '4': 0x21, '5': 0x22,
    '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,
    'Enter': 0x28, 'Escape': 0x29, 'Backspace': 0x2a, 'Tab': 0x2b, 'Space': 0x2c,
    '-': 0x2d, '=': 0x2e, '[': 0x2f, ']': 0x30, '\\': 0x31, ';': 0x33,
    "'": 0x34, '`': 0x35, ',': 0x36, '.': 0x37, '/': 0x38,
    'F1': 0x3a, 'F2': 0x3b, 'F3': 0x3c, 'F4': 0x3d,
    'F5': 0x3e, 'F6': 0x3f, 'F7': 0x40, 'F8': 0x41,
    'F9': 0x42, 'F10': 0x43, 'F11': 0x44, 'F12': 0x45,
    'Left': 0x50, 'Right': 0x4f, 'Up': 0x52, 'Down': 0x51,
    # Media/Volume keys
    'VolUp': 0x80, 'VolDown': 0x81, 'Mute': 0x7f,
    'PlayPause': 0xcd, 'Stop': 0xb7, 'NextTrack': 0xb5, 'PrevTrack': 0xb6,
}

# Modifier keys (bitmask)
MOD_LCTRL = 0x01
MOD_LSHIFT = 0x02
MOD_LALT = 0x04
MOD_LGUI = 0x08


class ControllerVisualizer(Gtk.Box):
    """Placeholder widget for controller tab."""
    
    def __init__(self, gatt_app_getter):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(50)
        self.set_margin_bottom(50)
        self.set_margin_start(50)
        self.set_margin_end(50)
        
        self.gatt_app_getter = gatt_app_getter
        
        # Info text
        info_label = Gtk.Label()
        info_label.set_markup(
            "<big>Controller Input Forwarding Active</big>\n\n"
            "Physical controller inputs are being forwarded\n"
            "when a device is connected via Bluetooth."
        )
        info_label.set_justify(Gtk.Justification.CENTER)
        self.append(info_label)
        
        # On-screen buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_margin_top(30)
        
        # Home/Nexus button (sends Ctrl+1)
        self.home_button = Gtk.Button(label="⌂ Home")
        self.home_button.set_size_request(150, 60)
        self.home_button.connect("clicked", self._send_home)
        button_box.append(self.home_button)
        
        # QAM button (sends Ctrl+2)
        self.qam_button = Gtk.Button(label="⋯ QAM")
        self.qam_button.set_size_request(150, 60)
        self.qam_button.connect("clicked", self._send_qam)
        button_box.append(self.qam_button)
        
        self.append(button_box)
    
    def _send_home(self, button=None):
        """Send Ctrl+1 for Home button."""
        gatt_app = self.gatt_app_getter()
        logger.info(f"Home button clicked. gatt_app={gatt_app}, notifying={gatt_app.notifying if gatt_app else 'N/A'}")
        if gatt_app and gatt_app.notifying:
            # Press the key chord
            gatt_app._kbd_modifiers = MOD_LCTRL
            gatt_app._kbd_keys = [0x1e, 0, 0, 0, 0, 0]  # '1' key
            gatt_app._send_keyboard_notification()
            logger.info("Home: Sent Ctrl+1 press")
            # Release after 50ms
            GLib.timeout_add(50, self._release_keys)
    
    def _send_qam(self, button=None):
        """Send Ctrl+2 for QAM button."""
        gatt_app = self.gatt_app_getter()
        logger.info(f"QAM button clicked. gatt_app={gatt_app}, notifying={gatt_app.notifying if gatt_app else 'N/A'}")
        if gatt_app and gatt_app.notifying:
            # Press the key chord
            gatt_app._kbd_modifiers = MOD_LCTRL
            gatt_app._kbd_keys = [0x1f, 0, 0, 0, 0, 0]  # '2' key
            gatt_app._send_keyboard_notification()
            logger.info("QAM: Sent Ctrl+2 press")
            # Release after 50ms
            GLib.timeout_add(50, self._release_keys)
    
    def _release_keys(self):
        """Release all keyboard keys."""
        gatt_app = self.gatt_app_getter()
        if gatt_app:
            gatt_app._kbd_modifiers = 0
            gatt_app._kbd_keys = [0, 0, 0, 0, 0, 0]
            gatt_app._send_keyboard_notification()
            logger.info("Released keyboard keys")
        return False  # Don't repeat
        
    def update_state(self, buttons, axes, triggers, hat):
        """Placeholder method for compatibility."""
        pass


class VirtualKeyboard(Gtk.Box):
    """Virtual keyboard widget that sends HID keyboard reports."""
    
    def __init__(self, gatt_app_getter):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(6)
        self.set_margin_end(6)
        
        self.gatt_app_getter = gatt_app_getter
        
        # Common keys
        keys_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        
        # Row 0: F keys
        row0 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        row0.set_homogeneous(True)
        for i in range(1, 13):
            btn = self._create_key_button(f'F{i}')
            row0.append(btn)
        keys_box.append(row0)
        
        # Row 1: Numbers
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        row1.set_homogeneous(True)
        for key in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']:
            btn = self._create_key_button(key)
            row1.append(btn)
        keys_box.append(row1)
        
        # Row 2: QWERTY
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        row2.set_homogeneous(True)
        for key in ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p']:
            btn = self._create_key_button(key)
            row2.append(btn)
        keys_box.append(row2)
        
        # Row 3: ASDFGH
        row3 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        row3.set_homogeneous(True)
        for key in ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l']:
            btn = self._create_key_button(key)
            row3.append(btn)
        keys_box.append(row3)
        
        # Row 4: ZXCVBN
        row4 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        row4.set_homogeneous(True)
        for key in ['z', 'x', 'c', 'v', 'b', 'n', 'm']:
            btn = self._create_key_button(key)
            row4.append(btn)
        keys_box.append(row4)
        
        # Row 5: Special keys
        row5 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        row5.set_homogeneous(True)
        for key in ['Space', 'Enter', 'Backspace', 'Tab', 'Escape']:
            btn = self._create_key_button(key)
            row5.append(btn)
        keys_box.append(row5)
        
        # Row 6: Arrow keys
        row6 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        row6.set_homogeneous(True)
        for key in ['Left', 'Up', 'Down', 'Right']:
            btn = self._create_key_button(key)
            row6.append(btn)
        keys_box.append(row6)
        
        self.append(keys_box)
        
        # Shortcut keys section
        shortcuts_label = Gtk.Label(label="Shortcuts")
        shortcuts_label.set_margin_top(10)
        shortcuts_label.set_markup("<b>Shortcuts</b>")
        self.append(shortcuts_label)
        
        # First row: Copy, Paste, Cut, Select All, Super
        shortcuts_row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        shortcuts_row1.set_halign(Gtk.Align.CENTER)
        
        shortcuts1 = [
            ('Copy', 'c', MOD_LCTRL),
            ('Paste', 'v', MOD_LCTRL),
            ('Cut', 'x', MOD_LCTRL),
            ('Sel All', 'a', MOD_LCTRL),
            ('Super', None, MOD_LGUI),
        ]
        
        for label, key, modifier in shortcuts1:
            btn = Gtk.Button(label=label)
            if key:
                btn.connect("clicked", lambda b, k=key, m=modifier: self._send_shortcut(k, m))
            else:
                # Super key - just press modifier
                btn.connect("clicked", lambda b, m=modifier: self._send_modifier_only(m))
            shortcuts_row1.append(btn)
        
        self.append(shortcuts_row1)
    
    def _create_key_button(self, key):
        """Create a button for a keyboard key."""
        label = key.upper() if len(key) == 1 else key
        btn = Gtk.Button(label=label)
        btn.connect("clicked", lambda b: self._send_key(key))
        return btn
    
    def _send_key(self, key):
        """Send a single key press."""
        gatt_app = self.gatt_app_getter()
        if not gatt_app or not gatt_app.notifying:
            return
        
        key_lower = key.lower()
        key_code = HID_KEY_CODES.get(key_lower) or HID_KEY_CODES.get(key)
        if key_code:
            gatt_app.send_key(key_code, 0)
    
    def _send_shortcut(self, key, modifier):
        """Send a keyboard shortcut (key + modifier)."""
        gatt_app = self.gatt_app_getter()
        if not gatt_app or not gatt_app.notifying:
            return
        
        key_lower = key.lower()
        key_code = HID_KEY_CODES.get(key_lower) or HID_KEY_CODES.get(key)
        if key_code:
            gatt_app.send_key(key_code, modifier)
    
    def _send_modifier_only(self, modifier):
        """Send just a modifier key press (like Super key)."""
        gatt_app = self.gatt_app_getter()
        if not gatt_app or not gatt_app.notifying:
            return
        
        # Send modifier with no key
        gatt_app.send_key(0, modifier)


class VirtualMediaControls(Gtk.Box):
    """Virtual media controls widget that sends HID keyboard media keys."""
    
    def __init__(self, gatt_app_getter):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(50)
        self.set_margin_bottom(50)
        self.set_margin_start(50)
        self.set_margin_end(50)
        
        self.gatt_app_getter = gatt_app_getter
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<big><b>Media Controls</b></big>")
        self.append(title_label)
        
        # Volume controls
        volume_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        volume_box.set_halign(Gtk.Align.CENTER)
        volume_box.set_margin_top(20)
        
        vol_down_btn = Gtk.Button(label="🔉 Vol Down")
        vol_down_btn.set_size_request(150, 60)
        vol_down_btn.connect("clicked", lambda b: self._send_media_key('VolDown'))
        volume_box.append(vol_down_btn)
        
        mute_btn = Gtk.Button(label="🔇 Mute")
        mute_btn.set_size_request(150, 60)
        mute_btn.connect("clicked", lambda b: self._send_media_key('Mute'))
        volume_box.append(mute_btn)
        
        vol_up_btn = Gtk.Button(label="🔊 Vol Up")
        vol_up_btn.set_size_request(150, 60)
        vol_up_btn.connect("clicked", lambda b: self._send_media_key('VolUp'))
        volume_box.append(vol_up_btn)
        
        self.append(volume_box)
        
        # Playback controls
        playback_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        playback_box.set_halign(Gtk.Align.CENTER)
        playback_box.set_margin_top(20)
        
        prev_btn = Gtk.Button(label="⏮ Previous")
        prev_btn.set_size_request(150, 60)
        prev_btn.connect("clicked", lambda b: self._send_media_key('PrevTrack'))
        playback_box.append(prev_btn)
        
        play_pause_btn = Gtk.Button(label="⏯ Play/Pause")
        play_pause_btn.set_size_request(150, 60)
        play_pause_btn.connect("clicked", lambda b: self._send_media_key('PlayPause'))
        playback_box.append(play_pause_btn)
        
        stop_btn = Gtk.Button(label="⏹ Stop")
        stop_btn.set_size_request(150, 60)
        stop_btn.connect("clicked", lambda b: self._send_media_key('Stop'))
        playback_box.append(stop_btn)
        
        next_btn = Gtk.Button(label="⏭ Next")
        next_btn.set_size_request(150, 60)
        next_btn.connect("clicked", lambda b: self._send_media_key('NextTrack'))
        playback_box.append(next_btn)
        
        self.append(playback_box)
    
    def _send_media_key(self, key):
        """Send a media key press."""
        gatt_app = self.gatt_app_getter()
        if not gatt_app or not gatt_app.notifying:
            return
        
        key_code = HID_KEY_CODES.get(key)
        if key_code:
            gatt_app.send_key(key_code, 0)


class VirtualTrackpad(Gtk.Box):
    """Virtual trackpad widget that sends HID mouse reports."""
    
    def __init__(self, gatt_app_getter):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.set_margin_start(6)
        self.set_margin_end(6)
        
        self.gatt_app_getter = gatt_app_getter
        
        # Info label
        info = Gtk.Label(label="Drag to move cursor • Tap to click • Double-tap & hold to drag • Scroll on right side")
        self.append(info)
        
        # Main horizontal box for trackpad + scroll wheel
        trackpad_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        # Trackpad area (left side)
        self.trackpad = Gtk.DrawingArea()
        self.trackpad.set_size_request(500, 300)
        self.trackpad.set_hexpand(True)
        self.trackpad.set_vexpand(True)
        self.trackpad.set_draw_func(self._draw_trackpad, None)
        
        # Add drag controller for mouse movement
        drag_controller = Gtk.GestureDrag()
        drag_controller.connect("drag-update", self._on_drag_update)
        drag_controller.connect("drag-end", self._on_drag_end)
        self.trackpad.add_controller(drag_controller)
        
        # Add click controller for tap-to-click and double-tap detection
        click_controller = Gtk.GestureClick()
        click_controller.connect("released", self._on_tap_click)
        click_controller.connect("pressed", self._on_tap_press)
        self.trackpad.add_controller(click_controller)
        
        # Track last position for delta calculation
        self._last_x = 0
        self._last_y = 0
        self._is_dragging = False
        self._drag_button_held = False  # Track if we're in drag mode (button held)
        self._last_tap_time = 0
        self._tap_count = 0
        
        trackpad_frame = Gtk.Frame()
        trackpad_frame.set_child(self.trackpad)
        trackpad_container.append(trackpad_frame)
        
        # Scroll wheel area (right side)
        self.scroll_area = Gtk.DrawingArea()
        self.scroll_area.set_size_request(80, 300)
        self.scroll_area.set_vexpand(True)
        self.scroll_area.set_draw_func(self._draw_scroll_area, None)
        
        # Add drag controller for scroll wheel
        scroll_drag_controller = Gtk.GestureDrag()
        scroll_drag_controller.connect("drag-update", self._on_scroll_drag)
        scroll_drag_controller.connect("drag-end", self._on_scroll_end)
        self.scroll_area.add_controller(scroll_drag_controller)
        
        self._scroll_last_y = 0
        self._is_scrolling = False
        
        scroll_frame = Gtk.Frame()
        scroll_frame.set_child(self.scroll_area)
        trackpad_container.append(scroll_frame)
        
        self.append(trackpad_container)
        
        # Mouse buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        
        left_btn = Gtk.Button(label="Left Click")
        left_btn.connect("clicked", lambda b: self._send_click(0x01))
        button_box.append(left_btn)
        
        right_btn = Gtk.Button(label="Right Click")
        right_btn.connect("clicked", lambda b: self._send_click(0x02))
        button_box.append(right_btn)
        
        middle_btn = Gtk.Button(label="Middle Click")
        middle_btn.connect("clicked", lambda b: self._send_click(0x04))
        button_box.append(middle_btn)
        
        self.append(button_box)
        
        # Sensitivity slider
        sens_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sens_label = Gtk.Label(label="Sensitivity:")
        sens_box.append(sens_label)
        
        self.sensitivity = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.1, 5.0, 0.1)
        self.sensitivity.set_value(1.0)
        self.sensitivity.set_hexpand(True)
        sens_box.append(self.sensitivity)
        
        self.append(sens_box)
    
    def _draw_trackpad(self, area, cr, width, height, user_data):
        """Draw the trackpad area."""
        # Background
        cr.set_source_rgb(0.2, 0.2, 0.25)
        cr.paint()
        
        # Border
        cr.set_source_rgb(0.4, 0.4, 0.5)
        cr.set_line_width(2)
        cr.rectangle(5, 5, width - 10, height - 10)
        cr.stroke()
        
        # Instructions
        cr.set_source_rgb(0.6, 0.6, 0.7)
        cr.select_font_face("Sans", 0, 0)
        cr.set_font_size(14)
        text = "Drag here to move mouse"
        extents = cr.text_extents(text)
        cr.move_to(width/2 - extents.width/2, height/2)
        cr.show_text(text)
    
    def _on_drag_update(self, gesture, offset_x, offset_y):
        """Handle drag motion."""
        if not self._is_dragging:
            self._is_dragging = True
            start_point = gesture.get_start_point()
            self._last_x = start_point.x
            self._last_y = start_point.y
            return
        
        # Get current position
        start_point = gesture.get_start_point()
        current_x = start_point.x + offset_x
        current_y = start_point.y + offset_y
        
        # Calculate delta
        dx = int((current_x - self._last_x) * self.sensitivity.get_value())
        dy = int((current_y - self._last_y) * self.sensitivity.get_value())
        
        # Update last position
        self._last_x = current_x
        self._last_y = current_y
        
        # Send mouse movement
        if dx != 0 or dy != 0:
            gatt_app = self.gatt_app_getter()
            if gatt_app and gatt_app.notifying:
                # If in drag mode, keep button pressed while moving
                button_state = 0x01 if self._drag_button_held else 0
                gatt_app.send_mouse_movement(dx, dy, button_state, 0)
    
    def _on_drag_end(self, gesture, offset_x, offset_y):
        """Handle drag end."""
        self._is_dragging = False
        # If we were in drag mode, release the button
        if self._drag_button_held:
            self._drag_button_held = False
            gatt_app = self.gatt_app_getter()
            if gatt_app and gatt_app.notifying:
                gatt_app.send_mouse_movement(0, 0, 0, 0)
    
    def _on_tap_press(self, gesture, n_press, x, y):
        """Handle tap press - detect double-tap and hold."""
        import time
        current_time = time.time()
        
        # Check if this is a double-tap (within 500ms)
        if n_press == 2 or (current_time - self._last_tap_time < 0.5 and self._tap_count == 1):
            # This is the second tap - enter drag mode
            self._drag_button_held = True
            self._tap_count = 0
            # Press and hold the left button
            gatt_app = self.gatt_app_getter()
            if gatt_app and gatt_app.notifying:
                gatt_app.send_mouse_movement(0, 0, 0x01, 0)
        else:
            self._tap_count = 1
        
        self._last_tap_time = current_time
    
    def _on_tap_click(self, gesture, n_press, x, y):
        """Handle tap to click (left click)."""
        # Only trigger single click if we didn't drag and not in drag mode
        if not self._is_dragging and not self._drag_button_held and n_press == 1:
            self._send_click(0x01)  # Left click
    
    def _draw_scroll_area(self, area, cr, width, height, user_data):
        """Draw the scroll wheel area."""
        # Background
        cr.set_source_rgb(0.15, 0.15, 0.20)
        cr.paint()
        
        # Border
        cr.set_source_rgb(0.4, 0.4, 0.5)
        cr.set_line_width(2)
        cr.rectangle(2, 5, width - 4, height - 10)
        cr.stroke()
        
        # Up arrow
        cr.set_source_rgb(0.6, 0.6, 0.7)
        cr.move_to(width/2, 30)
        cr.line_to(width/2 - 10, 45)
        cr.line_to(width/2 + 10, 45)
        cr.close_path()
        cr.fill()
        
        # Down arrow
        cr.move_to(width/2, height - 30)
        cr.line_to(width/2 - 10, height - 45)
        cr.line_to(width/2 + 10, height - 45)
        cr.close_path()
        cr.fill()
        
        # Text
        cr.select_font_face("Sans", 0, 1)
        cr.set_font_size(11)
        text = "Scroll"
        extents = cr.text_extents(text)
        cr.move_to(width/2 - extents.width/2, height/2 + extents.height/2)
        cr.show_text(text)
    
    def _on_scroll_drag(self, gesture, offset_x, offset_y):
        """Handle scroll wheel drag."""
        if not self._is_scrolling:
            self._is_scrolling = True
            start_point = gesture.get_start_point()
            self._scroll_last_y = start_point.y
            return
        
        # Get current position
        start_point = gesture.get_start_point()
        current_y = start_point.y + offset_y
        
        # Calculate scroll delta
        dy = current_y - self._scroll_last_y
        
        # Send scroll if moved enough (every 10 pixels)
        if abs(dy) >= 10:
            scroll_amount = int(dy / 10)
            gatt_app = self.gatt_app_getter()
            if gatt_app and gatt_app.notifying:
                # Negative scroll for down, positive for up
                gatt_app.send_mouse_movement(0, 0, 0, -scroll_amount)
            self._scroll_last_y = current_y
    
    def _on_scroll_end(self, gesture, offset_x, offset_y):
        """Handle scroll drag end."""
        self._is_scrolling = False
    
    def _send_click(self, button_mask):
        """Send a mouse button click."""
        gatt_app = self.gatt_app_getter()
        if not gatt_app or not gatt_app.notifying:
            return
        
        # Press
        gatt_app.send_mouse_movement(0, 0, button_mask, 0)
        # Release after delay
        GLib.timeout_add(50, lambda: gatt_app.send_mouse_movement(0, 0, 0, 0) if gatt_app.notifying else None)


class HoGPeripheralGUI(Gtk.ApplicationWindow):
    """Main GUI window."""
    
    def __init__(self, app):
        super().__init__(application=app, title="BT Controller Emulator")
        # Steam Deck optimized size (1280x800 native resolution, use ~80% for window)
        self.set_default_size(1024, 650)
        # Allow window resizing
        self.set_resizable(True)
        
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
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_margin_top(6)
        main_box.set_margin_bottom(6)
        main_box.set_margin_start(6)
        main_box.set_margin_end(6)
        
        # Header bar
        header = Gtk.HeaderBar()
        header.set_title_widget(Gtk.Label(label="BT Controller Emulator"))
        self.set_titlebar(header)
        
        # Status box
        status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        
        self.status_label = Gtk.Label(label="Status: Stopped")
        self.status_label.set_markup("<big><b>Status: Stopped</b></big>")
        status_box.append(self.status_label)
        
        self.connection_label = Gtk.Label(label="Not connected")
        status_box.append(self.connection_label)
        
        self.device_info_label = Gtk.Label(label="")
        self.device_info_label.set_wrap(True)
        status_box.append(self.device_info_label)
        
        main_box.append(status_box)
        
        # Tabbed interface
        notebook = Gtk.Notebook()
        notebook.set_vexpand(True)
        
        # Controller tab
        self.visualizer = ControllerVisualizer(lambda: self._gatt_app)
        notebook.append_page(self.visualizer, Gtk.Label(label="Controller"))
        
        # Keyboard tab
        self.keyboard = VirtualKeyboard(lambda: self._gatt_app)
        notebook.append_page(self.keyboard, Gtk.Label(label="Keyboard"))
        
        # Media controls tab
        self.media = VirtualMediaControls(lambda: self._gatt_app)
        notebook.append_page(self.media, Gtk.Label(label="Media"))
        
        # Trackpad tab
        self.trackpad = VirtualTrackpad(lambda: self._gatt_app)
        notebook.append_page(self.trackpad, Gtk.Label(label="Trackpad"))
        
        main_box.append(notebook)
        
        # Control buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_halign(Gtk.Align.CENTER)
        
        self.start_button = Gtk.Button(label="Start Service")
        self.start_button.connect("clicked", self._on_start_clicked)
        button_box.append(self.start_button)
        
        self.stop_button = Gtk.Button(label="Stop Service")
        self.stop_button.set_sensitive(False)
        self.stop_button.connect("clicked", self._on_stop_clicked)
        button_box.append(self.stop_button)
        
        main_box.append(button_box)
        
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
        
        # Update connection status
        if self._gatt_app.notifying:
            # Query connected device info
            if self._bus and self._adapter_path:
                device_info = get_primary_connected_device(self._bus, self._adapter_path)
                if device_info:
                    self.connection_label.set_label("✓ Connected and sending data")
                    self.device_info_label.set_markup(
                        f"<b>Device:</b> {device_info['name']}\n"
                        f"<b>Address:</b> {device_info['address']}"
                    )
                else:
                    self.connection_label.set_label("✓ Sending data")
                    self.device_info_label.set_label("")
            else:
                self.connection_label.set_label("✓ Sending data")
        elif self._registered:
            self.connection_label.set_label("Waiting for connection...")
            self.device_info_label.set_label("")
        
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
        self.device_info_label.set_label("")
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
        level=logging.DEBUG,  # Changed to DEBUG for more verbose logging
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    
    app = HoGApp()
    return app.run(None)


if __name__ == "__main__":
    import sys
    sys.exit(main())
