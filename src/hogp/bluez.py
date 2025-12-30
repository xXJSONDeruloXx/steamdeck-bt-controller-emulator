"""
BlueZ D-Bus helpers for GATT and advertising operations.

Provides async-friendly wrappers around BlueZ's D-Bus APIs to avoid
deadlocks with GDBus on older glib versions.
"""

import logging
import subprocess
from typing import Optional, Callable, Any, List, Dict

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
            GLib.VariantType("(a{oa{sa{sv}}})"),
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


def get_adapter_index(adapter_name: str = "hci0") -> int:
    """Extract adapter index from adapter name (e.g., 'hci0' -> 0)."""
    if adapter_name.startswith("hci"):
        try:
            return int(adapter_name[3:])
        except ValueError:
            pass
    return 0


def check_static_address_set(adapter_index: int = 0) -> bool:
    """
    Check if a static BLE address is already configured.
    Returns True if a static address is set, False otherwise.
    """
    try:
        result = subprocess.run(
            ["btmgmt", "--index", str(adapter_index), "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Look for "static-addr" in the output
            return "static-addr" in result.stdout.lower()
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Could not check static address status: {e}")
        return False


def set_static_ble_address(
    adapter_index: int = 0,
    address: str = "C2:12:34:56:78:9A",
) -> bool:
    """
    Set a static BLE address for the adapter to prevent identity rotation.
    
    This prevents the device from appearing as a new controller on each connection.
    Requires root/sudo privileges.
    
    Args:
        adapter_index: BlueZ adapter index (0 for hci0, 1 for hci1, etc.)
        address: Static random address (must have bit 1 set in first octet for locally administered)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if already set
        if check_static_address_set(adapter_index):
            logger.info(f"Static BLE address already configured for adapter {adapter_index}")
            return True
        
        logger.info(f"Configuring static BLE address {address} for adapter {adapter_index}")
        
        # Power off adapter
        subprocess.run(
            ["btmgmt", "--index", str(adapter_index), "power", "off"],
            capture_output=True,
            timeout=5,
            check=True,
        )
        
        # Set static address
        result = subprocess.run(
            ["btmgmt", "--index", str(adapter_index), "static-addr", address],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        
        # Power back on
        subprocess.run(
            ["btmgmt", "--index", str(adapter_index), "power", "on"],
            capture_output=True,
            timeout=5,
            check=True,
        )
        
        if "successfully set" in result.stdout.lower() or result.returncode == 0:
            logger.info(f"Successfully set static BLE address: {address}")
            return True
        else:
            logger.warning(f"Static address command completed but may not have succeeded: {result.stdout}")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to set static BLE address (requires sudo): {e}")
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning(f"Could not set static BLE address: {e}")
        return False


def get_connected_devices(bus: Gio.DBusConnection, adapter_path: str) -> List[Dict]:
    """
    Get list of devices currently connected to the adapter.
    
    Returns:
        List of dicts with 'path', 'name', 'address', 'connected' keys
    """
    devices = []
    try:
        result = bus.call_sync(
            BLUEZ_SERVICE,
            "/",
            DBUS_OM_IFACE,
            "GetManagedObjects",
            None,
            GLib.VariantType("(a{oa{sa{sv}}})"),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
        objects = result.get_child_value(0)
        for i in range(objects.n_children()):
            entry = objects.get_child_value(i)
            path = entry.get_child_value(0).get_string()
            
            # Only consider devices under our adapter
            if not path.startswith(adapter_path):
                continue
            
            ifaces = entry.get_child_value(1)
            device_props = None
            
            for j in range(ifaces.n_children()):
                iface_entry = ifaces.get_child_value(j)
                iface_name = iface_entry.get_child_value(0).get_string()
                
                if iface_name == "org.bluez.Device1":
                    device_props = iface_entry.get_child_value(1)
                    break
            
            if device_props:
                props_dict = {}
                for k in range(device_props.n_children()):
                    prop_entry = device_props.get_child_value(k)
                    prop_name = prop_entry.get_child_value(0).get_string()
                    prop_value = prop_entry.get_child_value(1).get_variant()
                    props_dict[prop_name] = prop_value
                
                connected = props_dict.get("Connected", GLib.Variant("b", False)).get_boolean()
                
                if connected:
                    devices.append({
                        "path": path,
                        "name": props_dict.get("Name", GLib.Variant("s", "Unknown")).get_string(),
                        "address": props_dict.get("Address", GLib.Variant("s", "")).get_string(),
                        "connected": connected,
                    })
    except GLib.Error as e:
        logger.error(f"Error getting connected devices: {e}")
    
    return devices


def get_primary_connected_device(bus: Gio.DBusConnection, adapter_path: str) -> Optional[Dict]:
    """
    Get the primary (first) connected device info.
    
    Returns:
        Dict with 'name', 'address' keys or None if no device connected
    """
    devices = get_connected_devices(bus, adapter_path)
    return devices[0] if devices else None
