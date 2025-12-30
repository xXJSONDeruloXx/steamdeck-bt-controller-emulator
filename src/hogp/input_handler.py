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
    
    # Xbox 360 controller button mapping matching evtest output
    # evtest shows: BTN_SOUTH(304), BTN_EAST(305), BTN_NORTH(307), BTN_WEST(308)
    # BTN_TL(310), BTN_TR(311), BTN_SELECT(314), BTN_START(315), BTN_MODE(316)
    # BTN_THUMBL(317), BTN_THUMBR(318)
    BUTTON_MAP = {
        304: 0,   # BTN_SOUTH = A button (button 0)
        305: 1,   # BTN_EAST = B button (button 1)
        307: 2,   # BTN_NORTH = X button (button 2)
        308: 3,   # BTN_WEST = Y button (button 3)
        310: 4,   # BTN_TL = Left bumper (button 4)
        311: 5,   # BTN_TR = Right bumper (button 5)
        314: 6,   # BTN_SELECT = Back/Select button (button 6)
        315: 7,   # BTN_START = Start button (button 7)
        316: 8,   # BTN_MODE = Guide/Home button (button 8)
        317: 9,   # BTN_THUMBL = Left stick click (button 9)
        318: 10,  # BTN_THUMBR = Right stick click (button 10)
    }
    
    # D-pad mapping (treated as buttons 11-14 in our report)
    DPAD_MAP = {
        # ABS_HAT0X and ABS_HAT0Y for D-pad
        # We'll handle these specially as they're axes, not buttons
    }
    
    # Axis mapping matching evtest output
    # evtest shows: ABS_X(0), ABS_Y(1), ABS_Z(2), ABS_RX(3), ABS_RY(4), ABS_RZ(5)
    AXIS_MAP = {
        0: 0,    # ABS_X = Left stick X -> axis 0 (X)
        1: 1,    # ABS_Y = Left stick Y -> axis 1 (Y)
        3: 2,    # ABS_RX = Right stick X -> axis 2 (RX)
        4: 3,    # ABS_RY = Right stick Y -> axis 3 (RY)
    }
    
    # Trigger axes mapped to separate trigger values (0-255)
    TRIGGER_MAP = {
        2: 0,   # ABS_Z = LT -> trigger 0
        5: 1,   # ABS_RZ = RT -> trigger 1
    }

    def __init__(
        self,
        device_path: Optional[str] = None,
        on_button_change: Optional[Callable[[int, bool], None]] = None,
        on_axis_change: Optional[Callable[[int, int], None]] = None,
        on_trigger_change: Optional[Callable[[int, int], None]] = None,
        on_hat_change: Optional[Callable[[int], None]] = None,
        verbose: bool = False,
    ):
        """
        Initialize the input handler.
        
        Args:
            device_path: Path to input device (e.g., /dev/input/event6)
                        If None, will try to auto-detect Xbox 360 pad
            on_button_change: Callback for button changes (button_index, pressed)
            on_axis_change: Callback for axis changes (axis_index, value)
            on_trigger_change: Callback for trigger changes (trigger_index, value 0-255)
            on_hat_change: Callback for HAT/D-pad changes (direction 0-7 or 0x0F for center)
            verbose: Enable verbose logging
        """
        self.device_path = device_path
        self.on_button_change = on_button_change
        self.on_axis_change = on_axis_change
        self.on_trigger_change = on_trigger_change
        self.on_hat_change = on_hat_change
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
            abs_info = self._device.absinfo(axis_code)
            
            # Normalize to -32768 to 32767 range
            range_size = abs_info.max - abs_info.min
            normalized = ((raw_value - abs_info.min) / range_size) * 65535 - 32768
            value = int(max(-32768, min(32767, normalized)))
            
            if self.verbose:
                logger.debug(f"Axis {axis_index} = {value}")
            
            if self.on_axis_change:
                self.on_axis_change(axis_index, value)
        
        # Handle triggers (separate from axes)
        elif axis_code in self.TRIGGER_MAP:
            trigger_index = self.TRIGGER_MAP[axis_code]
            
            # Get the absolute info for proper scaling
            abs_info = self._device.absinfo(axis_code)
            
            # Normalize to 0-255 range
            range_size = abs_info.max - abs_info.min
            normalized = ((raw_value - abs_info.min) / range_size) * 255
            value = int(max(0, min(255, normalized)))
            
            if self.verbose:
                logger.debug(f"Trigger {trigger_index} = {value}")
            
            if self.on_trigger_change:
                self.on_trigger_change(trigger_index, value)
        
        # Handle D-pad (HAT axes -> HAT switch direction)
        elif axis_code == 16:  # ABS_HAT0X
            old_x = self._dpad_x
            self._dpad_x = raw_value  # -1, 0, or 1
            
            if old_x != self._dpad_x:
                self._update_hat()
        
        elif axis_code == 17:  # ABS_HAT0Y
            old_y = self._dpad_y
            self._dpad_y = raw_value  # -1, 0, or 1
            
            if old_y != self._dpad_y:
                self._update_hat()

    def _update_hat(self) -> None:
        """Convert D-pad X/Y state to HAT direction (0-7 or 0x0F for center)."""
        # HAT switch encoding:
        # 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW, 0x0F=center
        hat_map = {
            ( 0, -1): 0,   # Up
            ( 1, -1): 1,   # Up-Right
            ( 1,  0): 2,   # Right
            ( 1,  1): 3,   # Down-Right
            ( 0,  1): 4,   # Down
            (-1,  1): 5,   # Down-Left
            (-1,  0): 6,   # Left
            (-1, -1): 7,   # Up-Left
            ( 0,  0): 0x0F # Center
        }
        
        direction = hat_map.get((self._dpad_x, self._dpad_y), 0x0F)
        
        if self.verbose:
            logger.debug(f"HAT = {direction:02X}")
        
        if self.on_hat_change:
            self.on_hat_change(direction)

    @property
    def is_running(self) -> bool:
        """Check if the input handler is running."""
        return self._running
