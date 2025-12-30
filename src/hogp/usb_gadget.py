"""
USB Gadget HID driver for wired HID emulation.

Uses Linux USB gadget framework (configfs) to create virtual USB HID devices.
Writes HID reports to /dev/hidgX character devices created by the kernel.
"""

import logging
import os
import struct
import time
from typing import Optional

logger = logging.getLogger(__name__)


class USBGadgetHID:
    """
    USB Gadget HID controller for wired mode.
    
    Manages writing HID reports to /dev/hidg* devices created by the kernel's
    USB gadget framework. The gadget must be configured externally using configfs
    (see scripts/setup-usb-gadget.sh).
    """
    
    def __init__(
        self,
        gamepad_device: str = "/dev/hidg0",
        keyboard_device: str = "/dev/hidg1", 
        mouse_device: str = "/dev/hidg2",
        verbose: bool = False,
    ):
        """
        Initialize USB gadget HID handler.
        
        Args:
            gamepad_device: Path to HID gadget device for gamepad (Report ID 1)
            keyboard_device: Path to HID gadget device for keyboard (Report ID 2)
            mouse_device: Path to HID gadget device for mouse (Report ID 3)
            verbose: Enable verbose logging
        """
        self.gamepad_device = gamepad_device
        self.keyboard_device = keyboard_device
        self.mouse_device = mouse_device
        self.verbose = verbose
        
        self._gamepad_fd: Optional[int] = None
        self._keyboard_fd: Optional[int] = None
        self._mouse_fd: Optional[int] = None
        self._active = False
        
        # Current HID report state (mirrors gatt_app.py structure)
        # Gamepad report (13 bytes total)
        self._buttons = 0  # 11 buttons + 5 bits padding = 2 bytes
        self._axes = [0, 0, 0, 0]  # X, Y, RX, RY (signed 16-bit each = 8 bytes)
        self._triggers = [0, 0]  # LT, RT (unsigned 8-bit each = 2 bytes)
        self._hat = 0x0F  # D-pad (8-bit, 0x0F = neutral)
        
        # Keyboard report (9 bytes total)
        self._kbd_modifiers = 0  # Modifier keys bitfield (1 byte)
        self._kbd_reserved = 0  # Reserved byte (1 byte)
        self._kbd_keys = [0, 0, 0, 0, 0, 0]  # Up to 6 simultaneous keys (6 bytes)
        
        # Mouse report (5 bytes total)
        self._mouse_buttons = 0  # Button bitfield (1 byte)
        self._mouse_x = 0  # X movement (signed 8-bit)
        self._mouse_y = 0  # Y movement (signed 8-bit)
        self._mouse_wheel = 0  # Wheel movement (signed 8-bit)
        self._mouse_h_wheel = 0  # Horizontal wheel (signed 8-bit)

    def open(self) -> bool:
        """
        Open the HID gadget devices for writing.
        
        Returns:
            True if successful, False otherwise
        """
        if self._active:
            logger.warning("USB gadget HID already open")
            return True
        
        try:
            # Open gamepad device
            if os.path.exists(self.gamepad_device):
                self._gamepad_fd = os.open(self.gamepad_device, os.O_RDWR | os.O_NONBLOCK)
                logger.info(f"Opened gamepad device: {self.gamepad_device} (fd={self._gamepad_fd})")
            else:
                logger.warning(f"Gamepad device not found: {self.gamepad_device}")
            
            # Open keyboard device
            if os.path.exists(self.keyboard_device):
                self._keyboard_fd = os.open(self.keyboard_device, os.O_RDWR | os.O_NONBLOCK)
                logger.info(f"Opened keyboard device: {self.keyboard_device} (fd={self._keyboard_fd})")
            else:
                logger.warning(f"Keyboard device not found: {self.keyboard_device}")
            
            # Open mouse device
            if os.path.exists(self.mouse_device):
                self._mouse_fd = os.open(self.mouse_device, os.O_RDWR | os.O_NONBLOCK)
                logger.info(f"Opened mouse device: {self.mouse_device} (fd={self._mouse_fd})")
            else:
                logger.warning(f"Mouse device not found: {self.mouse_device}")
            
            if not any([self._gamepad_fd, self._keyboard_fd, self._mouse_fd]):
                logger.error("No USB gadget devices available")
                return False
            
            self._active = True
            logger.info("USB gadget HID opened successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to open USB gadget devices: {e}")
            self.close()
            return False

    def close(self) -> None:
        """Close all HID gadget devices."""
        if not self._active:
            return
        
        logger.info("Closing USB gadget HID devices...")
        
        if self._gamepad_fd is not None:
            try:
                os.close(self._gamepad_fd)
            except Exception as e:
                logger.warning(f"Error closing gamepad device: {e}")
            self._gamepad_fd = None
        
        if self._keyboard_fd is not None:
            try:
                os.close(self._keyboard_fd)
            except Exception as e:
                logger.warning(f"Error closing keyboard device: {e}")
            self._keyboard_fd = None
        
        if self._mouse_fd is not None:
            try:
                os.close(self._mouse_fd)
            except Exception as e:
                logger.warning(f"Error closing mouse device: {e}")
            self._mouse_fd = None
        
        self._active = False
        logger.info("USB gadget HID closed")

    def is_active(self) -> bool:
        """Check if USB gadget is active."""
        return self._active

    # === Gamepad Methods ===
    
    def set_button(self, button_idx: int, pressed: bool) -> None:
        """
        Set gamepad button state.
        
        Args:
            button_idx: Button index (0-10)
            pressed: True if pressed, False if released
        """
        if button_idx < 0 or button_idx > 10:
            logger.warning(f"Invalid button index: {button_idx}")
            return
        
        if pressed:
            self._buttons |= (1 << button_idx)
        else:
            self._buttons &= ~(1 << button_idx)
        
        self._send_gamepad_report()

    def set_axis(self, axis_idx: int, value: int) -> None:
        """
        Set gamepad axis value.
        
        Args:
            axis_idx: Axis index (0=X, 1=Y, 2=RX, 3=RY)
            value: Axis value (-32768 to 32767)
        """
        if axis_idx < 0 or axis_idx > 3:
            logger.warning(f"Invalid axis index: {axis_idx}")
            return
        
        # Clamp value
        value = max(-32768, min(32767, value))
        self._axes[axis_idx] = value
        self._send_gamepad_report()

    def set_trigger(self, trigger_idx: int, value: int) -> None:
        """
        Set gamepad trigger value.
        
        Args:
            trigger_idx: Trigger index (0=LT, 1=RT)
            value: Trigger value (0-255)
        """
        if trigger_idx < 0 or trigger_idx > 1:
            logger.warning(f"Invalid trigger index: {trigger_idx}")
            return
        
        # Clamp value
        value = max(0, min(255, value))
        self._triggers[trigger_idx] = value
        self._send_gamepad_report()

    def set_hat(self, value: int) -> None:
        """
        Set gamepad HAT/D-pad value.
        
        Args:
            value: HAT value (0-7 for directions, 0x0F for neutral)
        """
        if value not in [0, 1, 2, 3, 4, 5, 6, 7, 0x0F]:
            logger.warning(f"Invalid HAT value: {value}")
            return
        
        self._hat = value
        self._send_gamepad_report()

    def _send_gamepad_report(self) -> None:
        """Send gamepad HID report to USB gadget."""
        if not self._active or self._gamepad_fd is None:
            return
        
        try:
            # Build report matching gatt_app.py REPORT_MAP structure
            # Report ID (1) + 2 bytes buttons + 8 bytes axes + 2 bytes triggers + 1 byte hat = 14 bytes
            report = bytearray(14)
            report[0] = 0x01  # Report ID
            
            # Buttons (11 buttons in lower 11 bits of 2 bytes)
            report[1] = self._buttons & 0xFF
            report[2] = (self._buttons >> 8) & 0xFF
            
            # Axes (4 signed 16-bit values, little-endian)
            struct.pack_into('<hhhh', report, 3, *self._axes)
            
            # Triggers (2 unsigned 8-bit values)
            report[11] = self._triggers[0]
            report[12] = self._triggers[1]
            
            # HAT switch
            report[13] = self._hat
            
            os.write(self._gamepad_fd, bytes(report))
            
            if self.verbose:
                logger.debug(f"Gamepad report: {report.hex()}")
                
        except Exception as e:
            logger.error(f"Failed to send gamepad report: {e}")

    # === Keyboard Methods ===
    
    def send_key(self, key_code: int, modifiers: int = 0) -> None:
        """
        Send keyboard key press and release.
        
        Args:
            key_code: HID key code
            modifiers: Modifier keys bitfield
        """
        # Press
        self._kbd_modifiers = modifiers
        self._kbd_keys[0] = key_code
        self._send_keyboard_report()
        
        # Small delay
        time.sleep(0.05)
        
        # Release
        self._kbd_modifiers = 0
        self._kbd_keys = [0, 0, 0, 0, 0, 0]
        self._send_keyboard_report()

    def set_keyboard_state(self, modifiers: int, keys: list[int]) -> None:
        """
        Set keyboard state (for held keys).
        
        Args:
            modifiers: Modifier keys bitfield
            keys: List of up to 6 key codes
        """
        self._kbd_modifiers = modifiers
        self._kbd_keys = (keys + [0, 0, 0, 0, 0, 0])[:6]
        self._send_keyboard_report()

    def _send_keyboard_report(self) -> None:
        """Send keyboard HID report to USB gadget."""
        if not self._active or self._keyboard_fd is None:
            return
        
        try:
            # Build report matching REPORT_MAP structure
            # Report ID (2) + 1 byte modifiers + 1 byte reserved + 6 bytes keys = 9 bytes
            report = bytearray(9)
            report[0] = 0x02  # Report ID
            report[1] = self._kbd_modifiers
            report[2] = self._kbd_reserved
            report[3:9] = self._kbd_keys
            
            os.write(self._keyboard_fd, bytes(report))
            
            if self.verbose:
                logger.debug(f"Keyboard report: {report.hex()}")
                
        except Exception as e:
            logger.error(f"Failed to send keyboard report: {e}")

    # === Mouse Methods ===
    
    def send_mouse_move(self, x: int, y: int, wheel: int = 0, h_wheel: int = 0) -> None:
        """
        Send mouse movement.
        
        Args:
            x: X movement (-127 to 127)
            y: Y movement (-127 to 127)
            wheel: Wheel movement (-127 to 127)
            h_wheel: Horizontal wheel movement (-127 to 127)
        """
        self._mouse_x = max(-127, min(127, x))
        self._mouse_y = max(-127, min(127, y))
        self._mouse_wheel = max(-127, min(127, wheel))
        self._mouse_h_wheel = max(-127, min(127, h_wheel))
        self._send_mouse_report()

    def send_mouse_click(self, buttons: int) -> None:
        """
        Send mouse button press and release.
        
        Args:
            buttons: Button bitfield (0x01=left, 0x02=right, 0x04=middle)
        """
        # Press
        self._mouse_buttons = buttons
        self._send_mouse_report()
        
        # Small delay
        time.sleep(0.05)
        
        # Release
        self._mouse_buttons = 0
        self._send_mouse_report()

    def set_mouse_buttons(self, buttons: int) -> None:
        """
        Set mouse button state (for held buttons).
        
        Args:
            buttons: Button bitfield (0x01=left, 0x02=right, 0x04=middle)
        """
        self._mouse_buttons = buttons
        self._send_mouse_report()

    def _send_mouse_report(self) -> None:
        """Send mouse HID report to USB gadget."""
        if not self._active or self._mouse_fd is None:
            return
        
        try:
            # Build report matching REPORT_MAP structure
            # Report ID (3) + 1 byte buttons + 4 bytes movement = 6 bytes
            report = bytearray(6)
            report[0] = 0x03  # Report ID
            report[1] = self._mouse_buttons
            
            # Pack signed 8-bit values
            report[2] = self._mouse_x & 0xFF
            report[3] = self._mouse_y & 0xFF
            report[4] = self._mouse_wheel & 0xFF
            report[5] = self._mouse_h_wheel & 0xFF
            
            os.write(self._mouse_fd, bytes(report))
            
            # Reset movement values after sending
            self._mouse_x = 0
            self._mouse_y = 0
            self._mouse_wheel = 0
            self._mouse_h_wheel = 0
            
            if self.verbose:
                logger.debug(f"Mouse report: {report.hex()}")
                
        except Exception as e:
            logger.error(f"Failed to send mouse report: {e}")
