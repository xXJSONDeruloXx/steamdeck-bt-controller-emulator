"""
HID Keyboard Scan Codes Reference

For use with gatt_app.send_key(key_code, modifiers)
"""

# Modifier bitmasks (OR these together if needed)
MOD_LCTRL = 0x01   # Left Control
MOD_LSHIFT = 0x02  # Left Shift
MOD_LALT = 0x04    # Left Alt
MOD_LGUI = 0x08    # Left GUI (Windows/Command key)
MOD_RCTRL = 0x10   # Right Control
MOD_RSHIFT = 0x20  # Right Shift
MOD_RALT = 0x40    # Right Alt
MOD_RGUI = 0x80    # Right GUI

# Key codes
KEY_CODES = {
    # Letters
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07,
    'e': 0x08, 'f': 0x09, 'g': 0x0a, 'h': 0x0b,
    'i': 0x0c, 'j': 0x0d, 'k': 0x0e, 'l': 0x0f,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13,
    'q': 0x14, 'r': 0x15, 's': 0x16, 't': 0x17,
    'u': 0x18, 'v': 0x19, 'w': 0x1a, 'x': 0x1b,
    'y': 0x1c, 'z': 0x1d,
    
    # Numbers
    '1': 0x1e, '2': 0x1f, '3': 0x20, '4': 0x21,
    '5': 0x22, '6': 0x23, '7': 0x24, '8': 0x25,
    '9': 0x26, '0': 0x27,
    
    # Special characters (unshifted)
    '-': 0x2d, '=': 0x2e, '[': 0x2f, ']': 0x30,
    '\\': 0x31, ';': 0x33, "'": 0x34, '`': 0x35,
    ',': 0x36, '.': 0x37, '/': 0x38,
    
    # Control keys
    'Enter': 0x28, 'Return': 0x28,
    'Escape': 0x29, 'Esc': 0x29,
    'Backspace': 0x2a, 'Delete': 0x2a,
    'Tab': 0x2b,
    'Space': 0x2c, ' ': 0x2c,
    
    # Function keys
    'F1': 0x3a, 'F2': 0x3b, 'F3': 0x3c, 'F4': 0x3d,
    'F5': 0x3e, 'F6': 0x3f, 'F7': 0x40, 'F8': 0x41,
    'F9': 0x42, 'F10': 0x43, 'F11': 0x44, 'F12': 0x45,
    
    # Navigation
    'Right': 0x4f, 'Left': 0x50, 'Down': 0x51, 'Up': 0x52,
    'PageUp': 0x4b, 'PageDown': 0x4e,
    'Home': 0x4a, 'End': 0x4d,
    'Insert': 0x49,
}

# Usage examples:
# 
# # Send lowercase 'a'
# gatt_app.send_key(0x04, 0)
#
# # Send uppercase 'A' (shift + a)
# gatt_app.send_key(0x04, MOD_LSHIFT)
#
# # Send Ctrl+C
# gatt_app.send_key(0x06, MOD_LCTRL)
#
# # Send Ctrl+Shift+Esc (Task Manager on Windows)
# gatt_app.send_key(0x29, MOD_LCTRL | MOD_LSHIFT)
