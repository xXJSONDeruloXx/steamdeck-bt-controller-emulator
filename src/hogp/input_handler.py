"""
Input device handler for forwarding physical controller inputs to HoG peripheral.

Reads from Linux evdev devices (e.g., /dev/input/event6 for Xbox 360 pad)
and maps events to the HID report format.
"""

import logging
import threading
from typing import Optional, Callable
import evdev
from evdev import InputDevice, ecodes, categorize

logger = logging.getLogger(__name__)


class InputHandler:
    """
    Handles input from a physical controller device and forwards to HoG report.
    """
    
    # Xbox 360 controller button mapping to our 16-button report
    # Our HID report: buttons 0-15 correspond to standard gamepad layout
    # Xbox 360 uses BTN_A, BTN_B, BTN_X, BTN_Y instead of BTN_SOUTH, BTN_EAST, etc.
    BUTTON_MAP = {
        304: 0,   # BTN_A / BTN_SOUTH = A button
        305: 1,   # BTN_B / BTN_EAST = B button
        307: 2,   # BTN_X / BTN_WEST = X button
        308: 3,   # BTN_Y / BTN_NORTH = Y button
        310: 4,   # BTN_TL = Left bumper (LB)
        311: 5,   # BTN_TR = Right bumper (RB)
        314: 6,   # BTN_SELECT = Back/Select button
        315: 7,   # BTN_START = Start button
        316: 8,   # BTN_MODE = Guide/Home button
        317: 9,   # BTN_THUMBL = Left stick click (LS)
        318: 10,  # BTN_THUMBR = Right stick click (RS)
    }
    
    # D-pad mapping (treated as buttons 11-14 in our report)
    DPAD_MAP = {
        # ABS_HAT0X and ABS_HAT0Y for D-pad
        # We'll handle these specially as they're axes, not buttons
    }
    
    # Axis mapping to our 4-axis report (X, Y, Z, Rz)
    AXIS_MAP = {
        0: 0,    # ABS_X = Left stick X -> axis 0 (X)
        1: 1,    # ABS_Y = Left stick Y -> axis 1 (Y)
        3: 2,    # ABS_RX = Right stick X -> axis 2 (Z)
        4: 3,    # ABS_RY = Right stick Y -> axis 3 (Rz)
    }
    
    # Trigger axes (will be mapped to buttons or axes depending on implementation)
    TRIGGER_MAP = {
        2: 'left_trigger',   # ABS_Z = LT
        5: 'right_trigger',  # ABS_RZ = RT
    }

    def __init__(
        self,
        device_path: Optional[str] = None,
        on_button_change: Optional[Callable[[int, bool], None]] = None,
        on_axis_change: Optional[Callable[[int, int], None]] = None,
        verbose: bool = False,
    ):
        """
        Initialize the input handler.
        
        Args:
            device_path: Path to input device (e.g., /dev/input/event6)
                        If None, will try to auto-detect Xbox 360 pad
            on_button_change: Callback for button changes (button_index, pressed)
            on_axis_change: Callback for axis changes (axis_index, value)
            verbose: Enable verbose logging
        """
        self.device_path = device_path
        self.on_button_change = on_button_change
        self.on_axis_change = on_axis_change
        self.verbose = verbose
        
        self._device: Optional[InputDevice] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        
        # D-pad state (for converting hat axes to buttons)
        self._dpad_x = 0  # -1 left, 0 center, 1 right
        self._dpad_y = 0  # -1 up, 0 center, 1 down

    def find_xbox_controller(self) -> Optional[str]:
        """
        Auto-detect Xbox 360 controller device.
        
        Returns:
            Device path if found, None otherwise
        """
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            for device in devices:
                name = device.name.lower()
                # Look for Xbox 360 controller or similar
                if 'xbox' in name or '360 pad' in name or 'x-box' in name:
                    logger.info(f"Found controller: {device.name} at {device.path}")
                    return device.path
            
            # Fallback: look for any gamepad with the right capabilities
            for device in devices:
                caps = device.capabilities()
                # Check if it has gamepad buttons and axes
                if ecodes.EV_KEY in caps and ecodes.EV_ABS in caps:
                    keys = caps[ecodes.EV_KEY]
                    # Check for common gamepad buttons
                    if ecodes.BTN_SOUTH in keys and ecodes.BTN_EAST in keys:
                        logger.info(f"Found gamepad: {device.name} at {device.path}")
                        return device.path
            
            logger.warning("No Xbox controller or suitable gamepad found")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting controller: {e}")
            return None

    def start(self) -> bool:
        """
        Start reading input from the device.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            logger.warning("Input handler already running")
            return True
        
        # Auto-detect device if not specified
        if not self.device_path:
            self.device_path = self.find_xbox_controller()
            if not self.device_path:
                logger.error("No input device specified and auto-detection failed")
                return False
        
        try:
            self._device = InputDevice(self.device_path)
            logger.info(f"Opened input device: {self._device.name} at {self.device_path}")
            logger.info(f"Capabilities: {self._device.capabilities(verbose=True)}")
            
            # Try to grab the device (exclusive access)
            # This prevents other applications from seeing the input
            try:
                self._device.grab()
                logger.info("Grabbed exclusive access to input device")
            except Exception as e:
                logger.warning(f"Could not grab device (non-exclusive mode): {e}")
            
            # Start reading thread
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            
            logger.info("Input handler started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start input handler: {e}")
            return False

    def stop(self) -> None:
        """Stop reading input from the device."""
        if not self._running:
            return
        
        logger.info("Stopping input handler...")
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=2.0)
        
        if self._device:
            try:
                self._device.ungrab()
            except:
                pass
            self._device.close()
            self._device = None
        
        logger.info("Input handler stopped")

    def _read_loop(self) -> None:
        """Main loop for reading input events."""
        logger.info("Input reading loop started")
        
        try:
            for event in self._device.read_loop():
                if not self._running:
                    break
                
                self._handle_event(event)
                
        except Exception as e:
            if self._running:  # Only log if not intentionally stopped
                logger.error(f"Error in input reading loop: {e}")
        
        logger.info("Input reading loop stopped")

    def _handle_event(self, event: evdev.InputEvent) -> None:
        """Handle a single input event."""
        # Only process key and absolute axis events
        if event.type == ecodes.EV_KEY:
            self._handle_button_event(event)
        elif event.type == ecodes.EV_ABS:
            self._handle_axis_event(event)

    def _handle_button_event(self, event: evdev.InputEvent) -> None:
        """Handle button press/release events."""
        button_code = event.code
        pressed = event.value == 1  # 1 = pressed, 0 = released
        
        if button_code in self.BUTTON_MAP:
            button_index = self.BUTTON_MAP[button_code]
            if self.verbose:
                logger.info(f"Button {button_index} ({'pressed' if pressed else 'released'})")
            
            if self.on_button_change:
                self.on_button_change(button_index, pressed)

    def _handle_axis_event(self, event: evdev.InputEvent) -> None:
        """Handle analog axis events."""
        axis_code = event.code
        raw_value = event.value
        
        # Handle regular axes (sticks)
        if axis_code in self.AXIS_MAP:
            axis_index = self.AXIS_MAP[axis_code]
            
            # Convert from device range to our range (-32768 to 32767)
            # Xbox 360 controller typically uses 0-255 or similar
            abs_info = self._device.absinfo(axis_code)
            
            # Normalize to -32768 to 32767 range
            range_size = abs_info.max - abs_info.min
            normalized = ((raw_value - abs_info.min) / range_size) * 65535 - 32768
            value = int(max(-32768, min(32767, normalized)))
            
            if self.verbose:
                logger.debug(f"Axis {axis_index} = {value}")
            
            if self.on_axis_change:
                self.on_axis_change(axis_index, value)
        
        # Handle D-pad (HAT axes -> buttons 11-14)
        elif axis_code == 16:  # ABS_HAT0X
            old_x = self._dpad_x
            self._dpad_x = raw_value  # -1, 0, or 1
            
            # D-pad left = button 11, D-pad right = button 12
            if old_x != self._dpad_x:
                if old_x == -1 and self.on_button_change:
                    self.on_button_change(11, False)  # D-pad left released
                if old_x == 1 and self.on_button_change:
                    self.on_button_change(12, False)  # D-pad right released
                
                if self._dpad_x == -1 and self.on_button_change:
                    self.on_button_change(11, True)   # D-pad left pressed
                if self._dpad_x == 1 and self.on_button_change:
                    self.on_button_change(12, True)   # D-pad right pressed
        
        elif axis_code == 17:  # ABS_HAT0Y
            old_y = self._dpad_y
            self._dpad_y = raw_value  # -1, 0, or 1
            
            # D-pad up = button 13, D-pad down = button 14
            if old_y != self._dpad_y:
                if old_y == -1 and self.on_button_change:
                    self.on_button_change(13, False)  # D-pad up released
                if old_y == 1 and self.on_button_change:
                    self.on_button_change(14, False)  # D-pad down released
                
                if self._dpad_y == -1 and self.on_button_change:
                    self.on_button_change(13, True)   # D-pad up pressed
                if self._dpad_y == 1 and self.on_button_change:
                    self.on_button_change(14, True)   # D-pad down pressed
        
        # Handle triggers (could map to buttons or axes)
        elif axis_code in self.TRIGGER_MAP:
            trigger_name = self.TRIGGER_MAP[axis_code]
            
            # Get the absolute info for proper scaling
            abs_info = self._device.absinfo(axis_code)
            
            # Normalize to 0-32767 range (half of our axis range, since triggers are 0-max)
            range_size = abs_info.max - abs_info.min
            normalized = ((raw_value - abs_info.min) / range_size) * 32767
            value = int(max(0, min(32767, normalized)))
            
            if self.verbose:
                logger.debug(f"Trigger {trigger_name} = {value}")
            
            # For now, we could map triggers to buttons 15 when pressed past threshold
            # Or we could use them to modulate axis values
            # Let's map left trigger to button 15 when > 50% pressed
            if trigger_name == 'left_trigger' and self.on_button_change:
                if value > 16384:  # > 50%
                    self.on_button_change(15, True)
                else:
                    self.on_button_change(15, False)

    @property
    def is_running(self) -> bool:
        """Check if the input handler is running."""
        return self._running
