"""
BlueZ D-Bus helpers for GATT and advertising operations.

Provides async-friendly wrappers around BlueZ's D-Bus APIs to avoid
deadlocks with GDBus on older glib versions.
"""

import logging
from typing import Optional, Callable, Any

from gi.repository import Gio, GLib

logger = logging.getLogger(__name__)

# BlueZ D-Bus constants
BLUEZ_SERVICE = "org.bluez"
ADAPTER_IFACE = "org.bluez.Adapter1"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADV_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"


def get_system_bus() -> Gio.DBusConnection:
    """Get a connection to the system D-Bus."""
    return Gio.bus_get_sync(Gio.BusType.SYSTEM, None)


def find_adapter_path(bus: Gio.DBusConnection, adapter_name: str = "hci0") -> Optional[str]:
    """
    Find the BlueZ adapter object path for the given adapter name.
    
    Returns the path like /org/bluez/hci0 or None if not found.
    """
    try:
        result = bus.call_sync(
            BLUEZ_SERVICE,
            "/",
            DBUS_OM_IFACE,
            "GetManagedObjects",
            None,
            GLib.VariantType("(a{oa{sa{sv}}}"),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
        objects = result.get_child_value(0)
        for i in range(objects.n_children()):
            entry = objects.get_child_value(i)
            path = entry.get_child_value(0).get_string()
            if path.endswith(f"/{adapter_name}"):
                ifaces = entry.get_child_value(1)
                for j in range(ifaces.n_children()):
                    iface_entry = ifaces.get_child_value(j)
                    iface_name = iface_entry.get_child_value(0).get_string()
                    if iface_name == ADAPTER_IFACE:
                        return path
    except GLib.Error as e:
        logger.error(f"Error finding adapter: {e}")
    return None


def get_adapter_property(bus: Gio.DBusConnection, adapter_path: str, prop_name: str) -> Any:
    """Get a property from the adapter."""
    try:
        result = bus.call_sync(
            BLUEZ_SERVICE,
            adapter_path,
            DBUS_PROPS_IFACE,
            "Get",
            GLib.Variant("(ss)", (ADAPTER_IFACE, prop_name)),
            GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
        return result.get_child_value(0).get_variant()
    except GLib.Error as e:
        logger.error(f"Error getting adapter property {prop_name}: {e}")
        return None


def set_adapter_property(bus: Gio.DBusConnection, adapter_path: str, prop_name: str, value: GLib.Variant) -> bool:
    """Set a property on the adapter."""
    try:
        bus.call_sync(
            BLUEZ_SERVICE,
            adapter_path,
            DBUS_PROPS_IFACE,
            "Set",
            GLib.Variant("(ssv)", (ADAPTER_IFACE, prop_name, value)),
            None,
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
        return True
    except GLib.Error as e:
        logger.error(f"Error setting adapter property {prop_name}: {e}")
        return False


def get_le_advertising_active_instances(bus: Gio.DBusConnection, adapter_path: str) -> int:
    """Get the number of active advertising instances."""
    try:
        result = bus.call_sync(
            BLUEZ_SERVICE,
            adapter_path,
            DBUS_PROPS_IFACE,
            "Get",
            GLib.Variant("(ss)", (LE_ADV_MANAGER_IFACE, "ActiveInstances")),
            GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
        return result.get_child_value(0).get_variant().get_byte()
    except GLib.Error as e:
        logger.error(f"Error getting ActiveInstances: {e}")
        return -1


def register_application_async(
    bus: Gio.DBusConnection,
    adapter_path: str,
    app_path: str,
    callback: Callable[[bool, Optional[str]], None],
) -> None:
    """
    Register a GATT application with BlueZ asynchronously.
    
    The callback receives (success: bool, error_message: Optional[str]).
    """
    def on_done(connection, result, user_data):
        try:
            connection.call_finish(result)
            logger.info(f"GATT application registered at {app_path}")
            callback(True, None)
        except GLib.Error as e:
            logger.error(f"Failed to register GATT application: {e}")
            callback(False, str(e))

    bus.call(
        BLUEZ_SERVICE,
        adapter_path,
        GATT_MANAGER_IFACE,
        "RegisterApplication",
        GLib.Variant("(oa{sv})", (app_path, {})),
        None,
        Gio.DBusCallFlags.NONE,
        30000,  # 30 second timeout
        None,
        on_done,
        None,
    )


def unregister_application_async(
    bus: Gio.DBusConnection,
    adapter_path: str,
    app_path: str,
    callback: Optional[Callable[[bool, Optional[str]], None]] = None,
) -> None:
    """
    Unregister a GATT application from BlueZ asynchronously.
    """
    def on_done(connection, result, user_data):
        try:
            connection.call_finish(result)
            logger.info(f"GATT application unregistered from {app_path}")
            if callback:
                callback(True, None)
        except GLib.Error as e:
            logger.warning(f"Failed to unregister GATT application (may be normal on shutdown): {e}")
            if callback:
                callback(False, str(e))

    bus.call(
        BLUEZ_SERVICE,
        adapter_path,
        GATT_MANAGER_IFACE,
        "UnregisterApplication",
        GLib.Variant("(o)", (app_path,)),
        None,
        Gio.DBusCallFlags.NONE,
        5000,
        None,
        on_done,
        None,
    )


def register_advertisement_async(
    bus: Gio.DBusConnection,
    adapter_path: str,
    adv_path: str,
    callback: Callable[[bool, Optional[str]], None],
) -> None:
    """
    Register an LE advertisement with BlueZ asynchronously.
    """
    def on_done(connection, result, user_data):
        try:
            connection.call_finish(result)
            logger.info(f"Advertisement registered at {adv_path}")
            callback(True, None)
        except GLib.Error as e:
            logger.error(f"Failed to register advertisement: {e}")
            callback(False, str(e))

    bus.call(
        BLUEZ_SERVICE,
        adapter_path,
        LE_ADV_MANAGER_IFACE,
        "RegisterAdvertisement",
        GLib.Variant("(oa{sv})", (adv_path, {})),
        None,
        Gio.DBusCallFlags.NONE,
        30000,
        None,
        on_done,
        None,
    )


def unregister_advertisement_async(
    bus: Gio.DBusConnection,
    adapter_path: str,
    adv_path: str,
    callback: Optional[Callable[[bool, Optional[str]], None]] = None,
) -> None:
    """
    Unregister an LE advertisement from BlueZ asynchronously.
    """
    def on_done(connection, result, user_data):
        try:
            connection.call_finish(result)
            logger.info(f"Advertisement unregistered from {adv_path}")
            if callback:
                callback(True, None)
        except GLib.Error as e:
            logger.warning(f"Failed to unregister advertisement (may be normal on shutdown): {e}")
            if callback:
                callback(False, str(e))

    bus.call(
        BLUEZ_SERVICE,
        adapter_path,
        LE_ADV_MANAGER_IFACE,
        "UnregisterAdvertisement",
        GLib.Variant("(o)", (adv_path,)),
        None,
        Gio.DBusCallFlags.NONE,
        5000,
        None,
        on_done,
        None,
    )


def ensure_adapter_powered_and_discoverable(bus: Gio.DBusConnection, adapter_path: str) -> bool:
    """Ensure the adapter is powered on and set to be discoverable (for pairing)."""
    # Power on
    if not set_adapter_property(bus, adapter_path, "Powered", GLib.Variant("b", True)):
        return False
    # Make discoverable (optional for BLE, but helps)
    set_adapter_property(bus, adapter_path, "Discoverable", GLib.Variant("b", True))
    return True
