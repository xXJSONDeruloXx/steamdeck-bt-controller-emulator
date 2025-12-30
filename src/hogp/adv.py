"""
BLE Advertisement implementation for HID-over-GATT profile.

Implements org.bluez.LEAdvertisement1 interface with proper D-Bus
Properties handling (including Set no-op to avoid BlueZ issues).
"""

import logging
from typing import Dict, List, Any, Optional

from gi.repository import Gio, GLib

logger = logging.getLogger(__name__)

LE_ADV_IFACE = "org.bluez.LEAdvertisement1"
DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"

# Standard 16-bit UUID for HID Service
HID_SERVICE_UUID_16 = "1812"


class Advertisement:
    """
    BLE Advertisement for HID-over-GATT peripheral.
    
    Registers at ADV_PATH with:
    - org.bluez.LEAdvertisement1 interface
    - org.freedesktop.DBus.Properties interface (with Set no-op)
    """

    ADV_PATH = "/com/steamdeck/hogp/adv0"

    def __init__(
        self,
        bus: Gio.DBusConnection,
        local_name: str = "SteamDeckHoG",
        verbose: bool = False,
    ):
        self.bus = bus
        self.local_name = local_name
        self.verbose = verbose
        self._registrations: List[int] = []
        
        # Advertisement properties
        self._type = "peripheral"
        self._service_uuids = [HID_SERVICE_UUID_16]
        self._appearance = 0x03C4  # Gamepad appearance
        self._discoverable = True
        self._includes = ["tx-power"]

    def register(self) -> bool:
        """Register advertisement object on D-Bus."""
        try:
            self._register_advertisement()
            self._register_properties()
            logger.info(f"Advertisement object registered at {self.ADV_PATH}")
            return True
        except Exception as e:
            logger.error(f"Failed to register advertisement object: {e}")
            self.unregister()
            return False

    def unregister(self) -> None:
        """Unregister D-Bus objects."""
        for reg_id in self._registrations:
            try:
                self.bus.unregister_object(reg_id)
            except Exception as e:
                logger.debug(f"Error unregistering object {reg_id}: {e}")
        self._registrations.clear()
        logger.info("Advertisement object unregistered")

    def _get_properties(self) -> Dict[str, GLib.Variant]:
        """Get advertisement properties as GLib.Variant dict."""
        return {
            "Type": GLib.Variant("s", self._type),
            "ServiceUUIDs": GLib.Variant("as", self._service_uuids),
            "LocalName": GLib.Variant("s", self.local_name),
            "Appearance": GLib.Variant("q", self._appearance),
            "Discoverable": GLib.Variant("b", self._discoverable),
            "Includes": GLib.Variant("as", self._includes),
        }

    def _register_advertisement(self) -> None:
        """Register LEAdvertisement1 interface."""
        xml = f"""
        <node>
            <interface name="{LE_ADV_IFACE}">
                <method name="Release"/>
                <property name="Type" type="s" access="read"/>
                <property name="ServiceUUIDs" type="as" access="read"/>
                <property name="LocalName" type="s" access="read"/>
                <property name="Appearance" type="q" access="read"/>
                <property name="Discoverable" type="b" access="read"/>
                <property name="Includes" type="as" access="read"/>
            </interface>
        </node>
        """
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)

        def handler(conn, sender, path, iface, method, params, invoc):
            if method == "Release":
                if self.verbose:
                    logger.info("Advertisement Release called")
                invoc.return_value(None)
            else:
                invoc.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod",
                    f"Unknown method: {method}",
                )

        reg_id = self.bus.register_object(
            self.ADV_PATH,
            node_info.interfaces[0],
            handler,
            self._get_property_handler,
            None,
        )
        self._registrations.append(reg_id)

    def _get_property_handler(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
    ) -> Optional[GLib.Variant]:
        """Property getter for LEAdvertisement1."""
        props = self._get_properties()
        return props.get(property_name)

    def _register_properties(self) -> None:
        """Register Properties interface with Get/GetAll/Set handlers."""
        xml = f"""
        <node>
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
                <method name="Set">
                    <arg type="s" direction="in"/>
                    <arg type="s" direction="in"/>
                    <arg type="v" direction="in"/>
                </method>
            </interface>
        </node>
        """
        node_info = Gio.DBusNodeInfo.new_for_xml(xml)

        def handler(conn, sender, path, iface, method, params, invoc):
            if method == "Get":
                iface_name, prop_name = params.unpack()
                props = self._get_properties()
                if prop_name in props:
                    invoc.return_value(GLib.Variant("(v)", (props[prop_name],)))
                else:
                    invoc.return_dbus_error(
                        "org.freedesktop.DBus.Error.InvalidArgs",
                        f"Unknown property: {prop_name}",
                    )
            elif method == "GetAll":
                iface_name = params.unpack()[0]
                props = self._get_properties()
                invoc.return_value(GLib.Variant("(a{sv})", (props,)))
            elif method == "Set":
                # No-op Set handler to avoid BlueZ issues
                # BlueZ may call Set on advertisement properties; we ignore it
                iface_name, prop_name, value = params.unpack()
                if self.verbose:
                    logger.info(f"Advertisement Set called (no-op): {prop_name}")
                invoc.return_value(None)
            else:
                invoc.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod",
                    f"Unknown method: {method}",
                )

        reg_id = self.bus.register_object(
            self.ADV_PATH,
            node_info.interfaces[0],
            handler,
            None,
            None,
        )
        self._registrations.append(reg_id)
