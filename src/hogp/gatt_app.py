"""
GATT Application implementation for HID-over-GATT (HoG) profile.

Implements:
- org.freedesktop.DBus.ObjectManager on the application root
- org.bluez.GattService1 for HID Service (UUID 0x1812)
- org.bluez.GattCharacteristic1 for HID characteristics
- org.bluez.GattDescriptor1 for Report Reference descriptor
"""

import logging
import struct
from typing import Dict, List, Any, Optional, Callable

from gi.repository import Gio, GLib

logger = logging.getLogger(__name__)

# Standard UUIDs
HID_SERVICE_UUID = "00001812-0000-1000-8000-00805f9b34fb"
HID_INFO_UUID = "00002a4a-0000-1000-8000-00805f9b34fb"
REPORT_MAP_UUID = "00002a4b-0000-1000-8000-00805f9b34fb"
HID_CONTROL_POINT_UUID = "00002a4c-0000-1000-8000-00805f9b34fb"
REPORT_UUID = "00002a4d-0000-1000-8000-00805f9b34fb"
REPORT_REFERENCE_UUID = "00002908-0000-1000-8000-00805f9b34fb"

# Generic Access Profile (GAP) UUIDs
GAP_SERVICE_UUID = "00001800-0000-1000-8000-00805f9b34fb"
DEVICE_NAME_UUID = "00002a00-0000-1000-8000-00805f9b34fb"

# Device Information Service UUIDs
DEVICE_INFO_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
MANUFACTURER_NAME_UUID = "00002a29-0000-1000-8000-00805f9b34fb"
MODEL_NUMBER_UUID = "00002a24-0000-1000-8000-00805f9b34fb"
PNP_ID_UUID = "00002a50-0000-1000-8000-00805f9b34fb"

# D-Bus interfaces
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHAR_IFACE = "org.bluez.GattCharacteristic1"
GATT_DESC_IFACE = "org.bluez.GattDescriptor1"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"

# Simple HID Report Map: 16 buttons + 4 axes (X, Y, Z, Rz) as int16
# This is a minimal gamepad descriptor
REPORT_MAP = bytes([
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x05,        # Usage (Gamepad)
    0xA1, 0x01,        # Collection (Application)
    
    # 16 buttons
    0x05, 0x09,        #   Usage Page (Button)
    0x19, 0x01,        #   Usage Minimum (Button 1)
    0x29, 0x10,        #   Usage Maximum (Button 16)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x10,        #   Report Count (16)
    0x81, 0x02,        #   Input (Data, Variable, Absolute)
    
    # 4 axes: X, Y, Z, Rz - each int16
    0x05, 0x01,        #   Usage Page (Generic Desktop)
    0x09, 0x30,        #   Usage (X)
    0x09, 0x31,        #   Usage (Y)
    0x09, 0x32,        #   Usage (Z)
    0x09, 0x35,        #   Usage (Rz)
    0x16, 0x00, 0x80,  #   Logical Minimum (-32768)
    0x26, 0xFF, 0x7F,  #   Logical Maximum (32767)
    0x75, 0x10,        #   Report Size (16)
    0x95, 0x04,        #   Report Count (4)
    0x81, 0x02,        #   Input (Data, Variable, Absolute)
    
    0xC0,              # End Collection
])

# HID Information: bcdHID=1.11, bCountryCode=0, Flags=0x02 (normally connectable)
HID_INFO = bytes([0x11, 0x01, 0x00, 0x02])

# Device Information values
MANUFACTURER_NAME = b"SteamDeck"
MODEL_NUMBER = b"HoG_Controller"
# PnP ID: Vendor ID Source (Bluetooth SIG), Vendor ID (0x28DE = Valve), Product ID, Product Version
PNP_ID = bytes([0x01, 0xDE, 0x28, 0x01, 0x00, 0x01, 0x00])  # Valve's VID


class GattApplication:
    """
    GATT Application that implements HID-over-GATT profile.
    
    Registers D-Bus objects at:
    - APP_PATH (ObjectManager root)
    - APP_PATH/service0 (HID Service)
    - APP_PATH/service0/char0 (HID Information)
    - APP_PATH/service0/char1 (Report Map)
    - APP_PATH/service0/char2 (HID Control Point)
    - APP_PATH/service0/char3 (Report - with notifications)
    - APP_PATH/service0/char3/desc0 (Report Reference)
    - APP_PATH/service1 (Device Information Service)
    - APP_PATH/service1/char0 (Manufacturer Name)
    - APP_PATH/service1/char1 (Model Number)
    - APP_PATH/service1/char2 (PnP ID)
    - APP_PATH/service2 (Generic Access Profile)
    - APP_PATH/service2/char0 (Device Name)
    """

    APP_PATH = "/com/steamdeck/hogp"

    def __init__(self, bus: Gio.DBusConnection, device_name: str = "SteamDeckHoG", verbose: bool = False):
        self.bus = bus
        self.device_name = device_name
        self.verbose = verbose
        self._registrations: List[int] = []
        self._notifying = False
        self._notify_timeout_id: Optional[int] = None
        self._report_rate_hz = 10
        
        # Current report state (2 bytes buttons + 8 bytes axes = 10 bytes)
        self._buttons = 0  # 16-bit button mask
        self._axes = [0, 0, 0, 0]  # X, Y, Z, Rz as int16
        
        # Callbacks for external control
        self._on_notify_start: Optional[Callable[[], None]] = None
        self._on_notify_stop: Optional[Callable[[], None]] = None

    def set_report_rate(self, hz: int) -> None:
        """Set the notification rate in Hz."""
        self._report_rate_hz = max(1, min(hz, 125))
        logger.info(f"Report rate set to {self._report_rate_hz} Hz")

    def set_button(self, button_index: int, pressed: bool) -> None:
        """Set a button state (0-15)."""
        if 0 <= button_index < 16:
            if pressed:
                self._buttons |= (1 << button_index)
            else:
                self._buttons &= ~(1 << button_index)

    def set_axis(self, axis_index: int, value: int) -> None:
        """Set an axis value (0-3, value -32768 to 32767)."""
        if 0 <= axis_index < 4:
            self._axes[axis_index] = max(-32768, min(32767, value))

    def get_current_report(self) -> bytes:
        """Build the current 10-byte HID report."""
        return struct.pack("<H4h", self._buttons, *self._axes)

    def register(self) -> bool:
        """Register all GATT objects on D-Bus."""
        try:
            self._register_object_manager()
            self._register_service()
            self._register_hid_info_char()
            self._register_report_map_char()
            self._register_hid_control_point_char()
            self._register_report_char()
            self._register_report_reference_desc()
            self._register_device_info_service()
            self._register_dis_manufacturer_char()
            self._register_dis_model_char()
            self._register_dis_pnp_id_char()
            self._register_gap_service()
            self._register_gap_device_name_char()
            logger.info(f"GATT objects registered under {self.APP_PATH}")
            return True
        except Exception as e:
            logger.error(f"Failed to register GATT objects: {e}")
            self.unregister()
            return False

    def unregister(self) -> None:
        """Unregister all D-Bus objects."""
        self.stop_notify()
        for reg_id in self._registrations:
            try:
                self.bus.unregister_object(reg_id)
            except Exception as e:
                logger.debug(f"Error unregistering object {reg_id}: {e}")
        self._registrations.clear()
        logger.info("GATT objects unregistered")

    def _register_object_manager(self) -> None:
        """Register ObjectManager interface at APP_PATH."""
        xml = """
        <node>
            <interface name="org.freedesktop.DBus.ObjectManager">
                <method name="GetManagedObjects">
                    <arg type="a{oa{sa{sv}}}" direction="out"/>
                </method>
            </interface>
        </node>
        """
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)
        reg_id = self.bus.register_object(
            self.APP_PATH,
            node_info.interfaces[0],
            self._handle_om_method_call,
            None,
            None,
        )
        self._registrations.append(reg_id)

    def _handle_om_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        """Handle ObjectManager.GetManagedObjects."""
        if method_name == "GetManagedObjects":
            if self.verbose:
                logger.info(f"GetManagedObjects called by {sender}")
            objects = self._get_managed_objects()
            invocation.return_value(GLib.Variant("(a{oa{sa{sv}}})", (objects,)))
        else:
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.UnknownMethod",
                f"Unknown method: {method_name}",
            )

    def _get_managed_objects(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Build the managed objects dictionary for GetManagedObjects."""
        service_path = f"{self.APP_PATH}/service0"
        char0_path = f"{service_path}/char0"
        char1_path = f"{service_path}/char1"
        char2_path = f"{service_path}/char2"
        char3_path = f"{service_path}/char3"
        desc0_path = f"{char3_path}/desc0"
        
        # Device Information Service paths
        dis_service_path = f"{self.APP_PATH}/service1"
        dis_char0_path = f"{dis_service_path}/char0"
        dis_char1_path = f"{dis_service_path}/char1"
        dis_char2_path = f"{dis_service_path}/char2"

        return {
            service_path: {
                GATT_SERVICE_IFACE: {
                    "UUID": GLib.Variant("s", HID_SERVICE_UUID),
                    "Primary": GLib.Variant("b", True),
                    "Characteristics": GLib.Variant("ao", [char0_path, char1_path, char2_path, char3_path]),
                },
            },
            char0_path: {
                GATT_CHAR_IFACE: {
                    "UUID": GLib.Variant("s", HID_INFO_UUID),
                    "Service": GLib.Variant("o", service_path),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                },
            },
            char1_path: {
                GATT_CHAR_IFACE: {
                    "UUID": GLib.Variant("s", REPORT_MAP_UUID),
                    "Service": GLib.Variant("o", service_path),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                },
            },
            char2_path: {
                GATT_CHAR_IFACE: {
                    "UUID": GLib.Variant("s", HID_CONTROL_POINT_UUID),
                    "Service": GLib.Variant("o", service_path),
                    "Flags": GLib.Variant("as", ["write-without-response"]),
                    "Descriptors": GLib.Variant("ao", []),
                },
            },
            char3_path: {
                GATT_CHAR_IFACE: {
                    "UUID": GLib.Variant("s", REPORT_UUID),
                    "Service": GLib.Variant("o", service_path),
                    "Flags": GLib.Variant("as", ["read", "notify"]),
                    "Descriptors": GLib.Variant("ao", [desc0_path]),
                },
            },
            desc0_path: {
                GATT_DESC_IFACE: {
                    "UUID": GLib.Variant("s", REPORT_REFERENCE_UUID),
                    "Characteristic": GLib.Variant("o", char3_path),
                    "Flags": GLib.Variant("as", ["read"]),
                },
            },
            dis_service_path: {
                GATT_SERVICE_IFACE: {
                    "UUID": GLib.Variant("s", DEVICE_INFO_SERVICE_UUID),
                    "Primary": GLib.Variant("b", True),
                    "Characteristics": GLib.Variant("ao", [dis_char0_path, dis_char1_path, dis_char2_path]),
                },
            },
            dis_char0_path: {
                GATT_CHAR_IFACE: {
                    "UUID": GLib.Variant("s", MANUFACTURER_NAME_UUID),
                    "Service": GLib.Variant("o", dis_service_path),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                },
            },
            dis_char1_path: {
                GATT_CHAR_IFACE: {
                    "UUID": GLib.Variant("s", MODEL_NUMBER_UUID),
                    "Service": GLib.Variant("o", dis_service_path),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                },
            },
            dis_char2_path: {
                GATT_CHAR_IFACE: {
                    "UUID": GLib.Variant("s", PNP_ID_UUID),
                    "Service": GLib.Variant("o", dis_service_path),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                },
            },
        }
        
        # Add GAP service if registered
        gap_service_path = f"{self.APP_PATH}/service2"
        gap_char0_path = f"{gap_service_path}/char0"
        
        result = dict(result)  # Make mutable copy
        result[gap_service_path] = {
            GATT_SERVICE_IFACE: {
                "UUID": GLib.Variant("s", GAP_SERVICE_UUID),
                "Primary": GLib.Variant("b", True),
                "Characteristics": GLib.Variant("ao", [gap_char0_path]),
            },
        }
        result[gap_char0_path] = {
            GATT_CHAR_IFACE: {
                "UUID": GLib.Variant("s", DEVICE_NAME_UUID),
                "Service": GLib.Variant("o", gap_service_path),
                "Flags": GLib.Variant("as", ["read"]),
                "Descriptors": GLib.Variant("ao", []),
            },
        }
        
        return result

    def _register_service(self) -> None:
        """Register HID Service object."""
        xml = f"""
        <node>
            <interface name="{GATT_SERVICE_IFACE}">
                <property name="UUID" type="s" access="read"/>
                <property name="Primary" type="b" access="read"/>
                <property name="Characteristics" type="ao" access="read"/>
            </interface>
            <interface name="{DBUS_PROPS_IFACE}">
                <method name="Get">
                    <arg type="s" direction="in"/>
                    <arg type="s" direction="in"/>
                    <arg type="v" direction="out"/>
                </method>
                <method name="GetAll">
                    <arg type="s" direction="in"/>
                    <arg type="a{{sv}}" direction="out"/>
                </method>
            </interface>
        </node>
        """
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)
        service_path = f"{self.APP_PATH}/service0"
        
        # Register Properties interface
        reg_id = self.bus.register_object(
            service_path,
            node_info.interfaces[1],  # Properties
            self._handle_service_props,
            None,
            None,
        )
        self._registrations.append(reg_id)

    def _handle_service_props(
        self, connection, sender, path, iface, method, params, invocation
    ) -> None:
        """Handle Properties calls on the service."""
        char0_path = f"{self.APP_PATH}/service0/char0"
        char1_path = f"{self.APP_PATH}/service0/char1"
        char2_path = f"{self.APP_PATH}/service0/char2"
        char3_path = f"{self.APP_PATH}/service0/char3"
        
        props = {
            "UUID": GLib.Variant("s", HID_SERVICE_UUID),
            "Primary": GLib.Variant("b", True),
            "Characteristics": GLib.Variant("ao", [char0_path, char1_path, char2_path, char3_path]),
        }
        
        if method == "Get":
            iface_name, prop_name = params.unpack()
            if prop_name in props:
                invocation.return_value(GLib.Variant("(v)", (props[prop_name],)))
            else:
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.InvalidArgs",
                    f"Unknown property: {prop_name}",
                )
        elif method == "GetAll":
            invocation.return_value(GLib.Variant("(a{sv})", (props,)))
        else:
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.UnknownMethod",
                f"Unknown method: {method}",
            )

    def _register_hid_info_char(self) -> None:
        """Register HID Information characteristic."""
        self._register_read_char(
            f"{self.APP_PATH}/service0/char0",
            HID_INFO_UUID,
            HID_INFO,
            "HID Information",
        )

    def _register_report_map_char(self) -> None:
        """Register Report Map characteristic."""
        self._register_read_char(
            f"{self.APP_PATH}/service0/char1",
            REPORT_MAP_UUID,
            REPORT_MAP,
            "Report Map",
        )

    def _register_hid_control_point_char(self) -> None:
        """Register HID Control Point characteristic (write-without-response)."""
        xml = f"""
        <node>
            <interface name="{GATT_CHAR_IFACE}">
                <method name="WriteValue">
                    <arg type="ay" direction="in"/>
                    <arg type="a{{sv}}" direction="in"/>
                </method>
                <property name="UUID" type="s" access="read"/>
                <property name="Service" type="o" access="read"/>
                <property name="Flags" type="as" access="read"/>
                <property name="Descriptors" type="ao" access="read"/>
            </interface>
            <interface name="{DBUS_PROPS_IFACE}">
                <method name="Get">
                    <arg type="s" direction="in"/>
                    <arg type="s" direction="in"/>
                    <arg type="v" direction="out"/>
                </method>
                <method name="GetAll">
                    <arg type="s" direction="in"/>
                    <arg type="a{{sv}}" direction="out"/>
                </method>
            </interface>
        </node>
        """
        path = f"{self.APP_PATH}/service0/char2"
        service_path = f"{self.APP_PATH}/service0"
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)

        def handler(conn, sender, obj_path, iface, method, params, invoc):
            if iface == GATT_CHAR_IFACE:
                if method == "WriteValue":
                    value, options = params.unpack()
                    if self.verbose:
                        logger.info(f"HID Control Point WriteValue: {bytes(value).hex()}")
                    invoc.return_value(None)
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            elif iface == DBUS_PROPS_IFACE:
                props = {
                    "UUID": GLib.Variant("s", HID_CONTROL_POINT_UUID),
                    "Service": GLib.Variant("o", service_path),
                    "Flags": GLib.Variant("as", ["write-without-response"]),
                    "Descriptors": GLib.Variant("ao", []),
                }
                if method == "Get":
                    _, prop = params.unpack()
                    if prop in props:
                        invoc.return_value(GLib.Variant("(v)", (props[prop],)))
                    else:
                        invoc.return_dbus_error(
                            "org.freedesktop.DBus.Error.InvalidArgs",
                            f"Unknown property: {prop}",
                        )
                elif method == "GetAll":
                    invoc.return_value(GLib.Variant("(a{sv})", (props,)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            else:
                invoc.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownInterface",
                    f"Unknown interface: {iface}",
                )

        reg_id = self.bus.register_object(path, node_info.interfaces[0], handler, None, None)
        self._registrations.append(reg_id)
        reg_id = self.bus.register_object(path, node_info.interfaces[1], handler, None, None)
        self._registrations.append(reg_id)

    def _register_read_char(
        self, path: str, uuid: str, value: bytes, name: str
    ) -> None:
        """Register a read-only characteristic."""
        xml = f"""
        <node>
            <interface name="{GATT_CHAR_IFACE}">
                <method name="ReadValue">
                    <arg type="a{{sv}}" direction="in"/>
                    <arg type="ay" direction="out"/>
                </method>
                <property name="UUID" type="s" access="read"/>
                <property name="Service" type="o" access="read"/>
                <property name="Flags" type="as" access="read"/>
                <property name="Descriptors" type="ao" access="read"/>
            </interface>
            <interface name="{DBUS_PROPS_IFACE}">
                <method name="Get">
                    <arg type="s" direction="in"/>
                    <arg type="s" direction="in"/>
                    <arg type="v" direction="out"/>
                </method>
                <method name="GetAll">
                    <arg type="s" direction="in"/>
                    <arg type="a{{sv}}" direction="out"/>
                </method>
            </interface>
        </node>
        """
        service_path = f"{self.APP_PATH}/service0"
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)

        def handler(conn, sender, obj_path, iface, method, params, invoc):
            if iface == GATT_CHAR_IFACE:
                if method == "ReadValue":
                    if self.verbose:
                        logger.info(f"{name} ReadValue called by {sender}")
                    invoc.return_value(GLib.Variant("(ay)", (value,)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            elif iface == DBUS_PROPS_IFACE:
                props = {
                    "UUID": GLib.Variant("s", uuid),
                    "Service": GLib.Variant("o", service_path),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                }
                if method == "Get":
                    _, prop = params.unpack()
                    if prop in props:
                        invoc.return_value(GLib.Variant("(v)", (props[prop],)))
                    else:
                        invoc.return_dbus_error(
                            "org.freedesktop.DBus.Error.InvalidArgs",
                            f"Unknown property: {prop}",
                        )
                elif method == "GetAll":
                    invoc.return_value(GLib.Variant("(a{sv})", (props,)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            else:
                invoc.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownInterface",
                    f"Unknown interface: {iface}",
                )

        reg_id = self.bus.register_object(path, node_info.interfaces[0], handler, None, None)
        self._registrations.append(reg_id)
        reg_id = self.bus.register_object(path, node_info.interfaces[1], handler, None, None)
        self._registrations.append(reg_id)

    def _register_report_char(self) -> None:
        """Register Report characteristic (read + notify)."""
        xml = f"""
        <node>
            <interface name="{GATT_CHAR_IFACE}">
                <method name="ReadValue">
                    <arg type="a{{sv}}" direction="in"/>
                    <arg type="ay" direction="out"/>
                </method>
                <method name="StartNotify"/>
                <method name="StopNotify"/>
                <property name="UUID" type="s" access="read"/>
                <property name="Service" type="o" access="read"/>
                <property name="Flags" type="as" access="read"/>
                <property name="Descriptors" type="ao" access="read"/>
                <property name="Notifying" type="b" access="read"/>
            </interface>
            <interface name="{DBUS_PROPS_IFACE}">
                <method name="Get">
                    <arg type="s" direction="in"/>
                    <arg type="s" direction="in"/>
                    <arg type="v" direction="out"/>
                </method>
                <method name="GetAll">
                    <arg type="s" direction="in"/>
                    <arg type="a{{sv}}" direction="out"/>
                </method>
            </interface>
        </node>
        """
        path = f"{self.APP_PATH}/service0/char3"
        desc0_path = f"{path}/desc0"
        service_path = f"{self.APP_PATH}/service0"
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)

        def handler(conn, sender, obj_path, iface, method, params, invoc):
            if iface == GATT_CHAR_IFACE:
                if method == "ReadValue":
                    if self.verbose:
                        logger.info(f"Report ReadValue called by {sender}")
                    report = self.get_current_report()
                    invoc.return_value(GLib.Variant("(ay)", (report,)))
                elif method == "StartNotify":
                    if self.verbose:
                        logger.info(f"Report StartNotify called by {sender}")
                    self.start_notify()
                    invoc.return_value(None)
                elif method == "StopNotify":
                    if self.verbose:
                        logger.info(f"Report StopNotify called by {sender}")
                    self.stop_notify()
                    invoc.return_value(None)
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            elif iface == DBUS_PROPS_IFACE:
                props = {
                    "UUID": GLib.Variant("s", REPORT_UUID),
                    "Service": GLib.Variant("o", service_path),
                    "Flags": GLib.Variant("as", ["read", "notify"]),
                    "Descriptors": GLib.Variant("ao", [desc0_path]),
                    "Notifying": GLib.Variant("b", self._notifying),
                }
                if method == "Get":
                    _, prop = params.unpack()
                    if prop in props:
                        invoc.return_value(GLib.Variant("(v)", (props[prop],)))
                    else:
                        invoc.return_dbus_error(
                            "org.freedesktop.DBus.Error.InvalidArgs",
                            f"Unknown property: {prop}",
                        )
                elif method == "GetAll":
                    invoc.return_value(GLib.Variant("(a{sv})", (props,)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            else:
                invoc.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownInterface",
                    f"Unknown interface: {iface}",
                )

        reg_id = self.bus.register_object(path, node_info.interfaces[0], handler, None, None)
        self._registrations.append(reg_id)
        reg_id = self.bus.register_object(path, node_info.interfaces[1], handler, None, None)
        self._registrations.append(reg_id)

    def _register_report_reference_desc(self) -> None:
        """Register Report Reference descriptor (Report ID=0, Type=Input)."""
        xml = f"""
        <node>
            <interface name="{GATT_DESC_IFACE}">
                <method name="ReadValue">
                    <arg type="a{{sv}}" direction="in"/>
                    <arg type="ay" direction="out"/>
                </method>
                <property name="UUID" type="s" access="read"/>
                <property name="Characteristic" type="o" access="read"/>
                <property name="Flags" type="as" access="read"/>
            </interface>
            <interface name="{DBUS_PROPS_IFACE}">
                <method name="Get">
                    <arg type="s" direction="in"/>
                    <arg type="s" direction="in"/>
                    <arg type="v" direction="out"/>
                </method>
                <method name="GetAll">
                    <arg type="s" direction="in"/>
                    <arg type="a{{sv}}" direction="out"/>
                </method>
            </interface>
        </node>
        """
        char_path = f"{self.APP_PATH}/service0/char3"
        path = f"{char_path}/desc0"
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)
        
        # Report Reference: Report ID = 0, Report Type = 1 (Input)
        report_ref_value = bytes([0x00, 0x01])

        def handler(conn, sender, obj_path, iface, method, params, invoc):
            if iface == GATT_DESC_IFACE:
                if method == "ReadValue":
                    if self.verbose:
                        logger.info(f"Report Reference ReadValue called by {sender}")
                    invoc.return_value(GLib.Variant("(ay)", (report_ref_value,)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            elif iface == DBUS_PROPS_IFACE:
                props = {
                    "UUID": GLib.Variant("s", REPORT_REFERENCE_UUID),
                    "Characteristic": GLib.Variant("o", char_path),
                    "Flags": GLib.Variant("as", ["read"]),
                }
                if method == "Get":
                    _, prop = params.unpack()
                    if prop in props:
                        invoc.return_value(GLib.Variant("(v)", (props[prop],)))
                    else:
                        invoc.return_dbus_error(
                            "org.freedesktop.DBus.Error.InvalidArgs",
                            f"Unknown property: {prop}",
                        )
                elif method == "GetAll":
                    invoc.return_value(GLib.Variant("(a{sv})", (props,)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            else:
                invoc.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownInterface",
                    f"Unknown interface: {iface}",
                )

        reg_id = self.bus.register_object(path, node_info.interfaces[0], handler, None, None)
        self._registrations.append(reg_id)
        reg_id = self.bus.register_object(path, node_info.interfaces[1], handler, None, None)
        self._registrations.append(reg_id)

    def _register_device_info_service(self) -> None:
        """Register Device Information Service."""
        xml = f"""
        <node>
            <interface name="{GATT_SERVICE_IFACE}">
                <property name="UUID" type="s" access="read"/>
                <property name="Primary" type="b" access="read"/>
                <property name="Characteristics" type="ao" access="read"/>
            </interface>
            <interface name="{DBUS_PROPS_IFACE}">
                <method name="Get">
                    <arg type="s" direction="in"/>
                    <arg type="s" direction="in"/>
                    <arg type="v" direction="out"/>
                </method>
                <method name="GetAll">
                    <arg type="s" direction="in"/>
                    <arg type="a{{sv}}" direction="out"/>
                </method>
            </interface>
        </node>
        """
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)
        service_path = f"{self.APP_PATH}/service1"
        
        char0_path = f"{service_path}/char0"
        char1_path = f"{service_path}/char1"
        char2_path = f"{service_path}/char2"
        
        def handler(conn, sender, path, iface, method, params, invoc):
            if iface == DBUS_PROPS_IFACE:
                props = {
                    "UUID": GLib.Variant("s", DEVICE_INFO_SERVICE_UUID),
                    "Primary": GLib.Variant("b", True),
                    "Characteristics": GLib.Variant("ao", [char0_path, char1_path, char2_path]),
                }
                if method == "Get":
                    _, prop = params.unpack()
                    if prop in props:
                        invoc.return_value(GLib.Variant("(v)", (props[prop],)))
                    else:
                        invoc.return_dbus_error(
                            "org.freedesktop.DBus.Error.InvalidArgs",
                            f"Unknown property: {prop}",
                        )
                elif method == "GetAll":
                    invoc.return_value(GLib.Variant("(a{sv})", (props,)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            else:
                invoc.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownInterface",
                    f"Unknown interface: {iface}",
                )

        reg_id = self.bus.register_object(service_path, node_info.interfaces[1], handler, None, None)
        self._registrations.append(reg_id)

    def _register_dis_manufacturer_char(self) -> None:
        """Register Device Information Service - Manufacturer Name characteristic."""
        self._register_read_char(
            f"{self.APP_PATH}/service1/char0",
            MANUFACTURER_NAME_UUID,
            MANUFACTURER_NAME,
            "DIS Manufacturer Name",
        )

    def _register_dis_model_char(self) -> None:
        """Register Device Information Service - Model Number characteristic."""
        self._register_read_char(
            f"{self.APP_PATH}/service1/char1",
            MODEL_NUMBER_UUID,
            MODEL_NUMBER,
            "DIS Model Number",
        )

    def _register_dis_pnp_id_char(self) -> None:
        """Register Device Information Service - PnP ID characteristic."""
        self._register_read_char(
            f"{self.APP_PATH}/service1/char2",
            PNP_ID_UUID,
            PNP_ID,
            "DIS PnP ID",
        )

    def _register_gap_service(self) -> None:
        """Register Generic Access Profile (GAP) service."""
        xml = f"""
        <node>
            <interface name="{GATT_SERVICE_IFACE}">
                <property name="UUID" type="s" access="read"/>
                <property name="Primary" type="b" access="read"/>
                <property name="Characteristics" type="ao" access="read"/>
            </interface>
            <interface name="{DBUS_PROPS_IFACE}">
                <method name="Get">
                    <arg type="s" direction="in"/>
                    <arg type="s" direction="in"/>
                    <arg type="v" direction="out"/>
                </method>
                <method name="GetAll">
                    <arg type="s" direction="in"/>
                    <arg type="a{{sv}}" direction="out"/>
                </method>
            </interface>
        </node>
        """
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)
        service_path = f"{self.APP_PATH}/service2"
        
        char0_path = f"{service_path}/char0"
        
        def handler(conn, sender, path, iface, method, params, invoc):
            if iface == DBUS_PROPS_IFACE:
                props = {
                    "UUID": GLib.Variant("s", GAP_SERVICE_UUID),
                    "Primary": GLib.Variant("b", True),
                    "Characteristics": GLib.Variant("ao", [char0_path]),
                }
                if method == "Get":
                    _, prop = params.unpack()
                    if prop in props:
                        invoc.return_value(GLib.Variant("(v)", (props[prop],)))
                    else:
                        invoc.return_dbus_error(
                            "org.freedesktop.DBus.Error.InvalidArgs",
                            f"Unknown property: {prop}",
                        )
                elif method == "GetAll":
                    invoc.return_value(GLib.Variant("(a{sv})", (props,)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.UnknownMethod",
                        f"Unknown method: {method}",
                    )
            else:
                invoc.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownInterface",
                    f"Unknown interface: {iface}",
                )

        reg_id = self.bus.register_object(service_path, node_info.interfaces[1], handler, None, None)
        self._registrations.append(reg_id)

    def _register_gap_device_name_char(self) -> None:
        """Register GAP Device Name characteristic."""
        self._register_read_char(
            f"{self.APP_PATH}/service2/char0",
            DEVICE_NAME_UUID,
            self.device_name.encode('utf-8'),
            "GAP Device Name",
        )

    def start_notify(self) -> None:
        """Start sending notifications."""
        if self._notifying:
            return
        self._notifying = True
        logger.info("Notifications started")
        
        if self._on_notify_start:
            self._on_notify_start()
        
        interval_ms = 1000 // self._report_rate_hz
        self._notify_timeout_id = GLib.timeout_add(interval_ms, self._send_notification)

    def stop_notify(self) -> None:
        """Stop sending notifications."""
        if not self._notifying:
            return
        self._notifying = False
        logger.info("Notifications stopped")
        
        if self._notify_timeout_id is not None:
            GLib.source_remove(self._notify_timeout_id)
            self._notify_timeout_id = None
        
        if self._on_notify_stop:
            self._on_notify_stop()

    def _send_notification(self) -> bool:
        """Send a notification with the current report value."""
        if not self._notifying:
            return False
        
        report = self.get_current_report()
        char_path = f"{self.APP_PATH}/service0/char3"
        
        try:
            self.bus.emit_signal(
                None,
                char_path,
                DBUS_PROPS_IFACE,
                "PropertiesChanged",
                GLib.Variant(
                    "(sa{sv}as)",
                    (
                        GATT_CHAR_IFACE,
                        {"Value": GLib.Variant("ay", report)},
                        [],
                    ),
                ),
            )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
        
        return True  # Continue the timeout

    @property
    def notifying(self) -> bool:
        """Check if notifications are active."""
        return self._notifying
