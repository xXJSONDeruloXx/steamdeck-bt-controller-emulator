heres a bunch of python we have tested so far with varying levels of success, this is latest:

(130)(deck@steamdeck Desktop)$ cat *.py
#!/usr/bin/env python3
from gi.repository import Gio, GLib

BLUEZ   = "org.bluez"
ADAPTER = "/org/bluez/hci0"

APP_PATH     = "/com/steamdeck/hogp"
SERVICE_PATH = APP_PATH + "/service0"

INFO_PATH   = SERVICE_PATH + "/char0"          # 2A4A
MAP_PATH    = SERVICE_PATH + "/char1"          # 2A4B
CTRL_PATH   = SERVICE_PATH + "/char2"          # 2A4C
REPORT_PATH = SERVICE_PATH + "/char3"          # 2A4D
RR_DESC     = REPORT_PATH + "/desc0"           # 2908

HID_UUID               = "00001812-0000-1000-8000-00805f9b34fb"
HID_INFORMATION_UUID   = "00002a4a-0000-1000-8000-00805f9b34fb"
REPORT_MAP_UUID        = "00002a4b-0000-1000-8000-00805f9b34fb"
HID_CONTROL_POINT_UUID = "00002a4c-0000-1000-8000-00805f9b34fb"
REPORT_UUID            = "00002a4d-0000-1000-8000-00805f9b34fb"
REPORT_REF_UUID        = "00002908-0000-1000-8000-00805f9b34fb"

# Same report map you had: 16 buttons + 4 axes (int16)
REPORT_MAP = bytes([
    0x05, 0x01, 0x09, 0x05, 0xA1, 0x01,
    0x05, 0x09, 0x19, 0x01, 0x29, 0x10,
    0x15, 0x00, 0x25, 0x01, 0x75, 0x01,
    0x95, 0x10, 0x81, 0x02,
    0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x09, 0x33, 0x09, 0x34,
    0x16, 0x01, 0x80, 0x26, 0xFF, 0x7F,
    0x75, 0x10, 0x95, 0x04, 0x81, 0x02,
    0xC0
])

# HID Information: bcdHID=0x0111, country=0, flags=0x03
HID_INFO = bytes([0x11, 0x01, 0x00, 0x03])

# Report Reference descriptor: [ReportID, ReportType]
REPORT_ID   = 0x01
REPORT_TYPE = 0x01  # Input
REPORT_REF  = bytes([REPORT_ID, REPORT_TYPE])

report_value = bytearray(10)  # 2 bytes buttons + 8 bytes axes
notify_enabled = False
notify_source_id = None

OBJMGR_XML = """
<node>
  <interface name="org.freedesktop.DBus.ObjectManager">
    <method name="GetManagedObjects">
      <arg type="a{oa{sa{sv}}}" direction="out"/>
    </method>
  </interface>
</node>
"""

SERVICE_XML = """
<node>
  <interface name="org.bluez.GattService1">
    <property name="UUID" type="s" access="read"/>
    <property name="Primary" type="b" access="read"/>
    <property name="Includes" type="ao" access="read"/>
  </interface>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{sv}" direction="out"/>
    </method>
  </interface>
</node>
"""

CHAR_XML = """
<node>
  <interface name="org.bluez.GattCharacteristic1">
    <method name="ReadValue">
      <arg type="a{sv}" direction="in"/>
      <arg type="ay" direction="out"/>
    </method>
    <method name="WriteValue">
      <arg type="ay" direction="in"/>
      <arg type="a{sv}" direction="in"/>
    </method>
    <method name="StartNotify"/>
    <method name="StopNotify"/>
    <property name="UUID" type="s" access="read"/>
    <property name="Service" type="o" access="read"/>
    <property name="Flags" type="as" access="read"/>
    <property name="Descriptors" type="ao" access="read"/>
  </interface>

  <interface name="org.freedesktop.DBus.Properties">
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{sv}" direction="out"/>
    </method>
    <method name="Get">
      <arg type="s" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
  </interface>
</node>
"""

DESC_XML = """
<node>
  <interface name="org.bluez.GattDescriptor1">
    <method name="ReadValue">
      <arg type="a{sv}" direction="in"/>
      <arg type="ay" direction="out"/>
    </method>
    <property name="UUID" type="s" access="read"/>
    <property name="Characteristic" type="o" access="read"/>
    <property name="Flags" type="as" access="read"/>
  </interface>

  <interface name="org.freedesktop.DBus.Properties">
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{sv}" direction="out"/>
    </method>
    <method name="Get">
      <arg type="s" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
  </interface>
</node>
"""

def props_get_all(reply_iface, mapping):
    if reply_iface in mapping:
        return GLib.Variant("(a{sv})", (mapping[reply_iface],))
    return GLib.Variant("(a{sv})", ({},))

def props_get_one(req_iface, prop, mapping, inv):
    if req_iface in mapping and prop in mapping[req_iface]:
        inv.return_value(GLib.Variant("(v)", (mapping[req_iface][prop],)))
    else:
        inv.return_dbus_error("org.bluez.Error.InvalidArguments", "No such property")

def emit_char_props_changed(conn, path, iface_name, changed: dict):
    conn.emit_signal(
        None,
        path,
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        GLib.Variant("(sa{sv}as)", (iface_name, changed, [])),
    )

def notify_tick(conn):
    global report_value, notify_enabled
    if not notify_enabled:
        return True
    report_value[0] ^= 0x01  # toggle button 1
    changed = {"Value": GLib.Variant("ay", bytes(report_value))}
    emit_char_props_changed(conn, REPORT_PATH, "org.bluez.GattCharacteristic1", changed)
    return True
    report_value[0] ^= 0x01
    changed = {"Value": GLib.Variant("ay", bytes(report_value))}
    emit_char_props_changed(conn, REPORT_PATH, "org.bluez.GattCharacteristic1", changed)
    return True

def handle_objmgr(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    if iface == "org.freedesktop.DBus.ObjectManager" and method == "GetManagedObjects":
        managed = {
            SERVICE_PATH: {
                "org.bluez.GattService1": {
                    "UUID": GLib.Variant("s", HID_UUID),
                    "Primary": GLib.Variant("b", True),
                    "Includes": GLib.Variant("ao", []),
                }
            },
            INFO_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": GLib.Variant("s", HID_INFORMATION_UUID),
                    "Service": GLib.Variant("o", SERVICE_PATH),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                }
            },
            MAP_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": GLib.Variant("s", REPORT_MAP_UUID),
                    "Service": GLib.Variant("o", SERVICE_PATH),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                }
            },
            CTRL_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": GLib.Variant("s", HID_CONTROL_POINT_UUID),
                    "Service": GLib.Variant("o", SERVICE_PATH),
                    "Flags": GLib.Variant("as", ["write-without-response"]),
                    "Descriptors": GLib.Variant("ao", []),
                }
            },
            REPORT_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": GLib.Variant("s", REPORT_UUID),
                    "Service": GLib.Variant("o", SERVICE_PATH),
                    "Flags": GLib.Variant("as", ["read", "notify"]),
                    "Descriptors": GLib.Variant("ao", [RR_DESC]),
                }
            },
            RR_DESC: {
                "org.bluez.GattDescriptor1": {
                    "UUID": GLib.Variant("s", REPORT_REF_UUID),
                    "Characteristic": GLib.Variant("o", REPORT_PATH),
                    "Flags": GLib.Variant("as", ["read"]),
                }
            },
        }
        inv.return_value(GLib.Variant("(a{oa{sa{sv}}})", (managed,)))
        return
    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")

def handle_service_props(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    if iface == "org.freedesktop.DBus.Properties" and method == "GetAll":
        (req_iface,) = params
        mapping = {
            "org.bluez.GattService1": {
                "UUID": GLib.Variant("s", HID_UUID),
                "Primary": GLib.Variant("b", True),
                "Includes": GLib.Variant("ao", []),
            }
        }
        inv.return_value(props_get_all(req_iface, mapping))
        return
    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")

def handle_char(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    global notify_enabled, notify_source_id

    if obj_path == INFO_PATH:
        uuid, flags, descriptors = HID_INFORMATION_UUID, ["read"], []
    elif obj_path == MAP_PATH:
        uuid, flags, descriptors = REPORT_MAP_UUID, ["read"], []
    elif obj_path == CTRL_PATH:
        uuid, flags, descriptors = HID_CONTROL_POINT_UUID, ["write-without-response"], []
    elif obj_path == REPORT_PATH:
        uuid, flags, descriptors = REPORT_UUID, ["read", "notify"], [RR_DESC]
    else:
        inv.return_dbus_error("org.bluez.Error.InvalidArguments", "Unknown characteristic path")
        return

    mapping = {
        "org.bluez.GattCharacteristic1": {
            "UUID": GLib.Variant("s", uuid),
            "Service": GLib.Variant("o", SERVICE_PATH),
            "Flags": GLib.Variant("as", flags),
            "Descriptors": GLib.Variant("ao", descriptors),
        }
    }

    if iface == "org.freedesktop.DBus.Properties":
        if method == "GetAll":
            (req_iface,) = params
            inv.return_value(props_get_all(req_iface, mapping))
            return
        if method == "Get":
            (req_iface, prop) = params
            props_get_one(req_iface, prop, mapping, inv)
            return

    if iface == "org.bluez.GattCharacteristic1":
        if method == "ReadValue":
            if obj_path == INFO_PATH:
                inv.return_value(GLib.Variant("(ay)", (HID_INFO,)))
                return
            if obj_path == MAP_PATH:
                inv.return_value(GLib.Variant("(ay)", (REPORT_MAP,)))
                return
            if obj_path == REPORT_PATH:
                inv.return_value(GLib.Variant("(ay)", (bytes(report_value),)))
                return
            inv.return_dbus_error("org.bluez.Error.NotPermitted", "Not readable")
            return

        if method == "WriteValue":
            if obj_path == CTRL_PATH:
                inv.return_value(None)
                return
            inv.return_dbus_error("org.bluez.Error.NotPermitted", "Not writable")
            return

        if method == "StartNotify":
            if obj_path != REPORT_PATH:
                inv.return_dbus_error("org.bluez.Error.NotSupported", "Notify not supported here")
                return
            if not notify_enabled:
                notify_enabled = True
                notify_source_id = GLib.timeout_add(500, notify_tick, conn)
                emit_char_props_changed(
                    conn, REPORT_PATH, "org.bluez.GattCharacteristic1",
                    {"Notifying": GLib.Variant("b", True)}
                )
            inv.return_value(None)
            return

        if method == "StopNotify":
            if obj_path != REPORT_PATH:
                inv.return_dbus_error("org.bluez.Error.NotSupported", "Notify not supported here")
                return
            if notify_enabled:
                notify_enabled = False
                if notify_source_id is not None:
                    GLib.source_remove(notify_source_id)
                    notify_source_id = None
                emit_char_props_changed(
                    conn, REPORT_PATH, "org.bluez.GattCharacteristic1",
                    {"Notifying": GLib.Variant("b", False)}
                )
            inv.return_value(None)
            return

    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")

def handle_desc(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    if obj_path != RR_DESC:
        inv.return_dbus_error("org.bluez.Error.InvalidArguments", "Unknown descriptor path")
        return

    mapping = {
        "org.bluez.GattDescriptor1": {
            "UUID": GLib.Variant("s", REPORT_REF_UUID),
            "Characteristic": GLib.Variant("o", REPORT_PATH),
            "Flags": GLib.Variant("as", ["read"]),
        }
    }

    if iface == "org.freedesktop.DBus.Properties":
        if method == "GetAll":
            (req_iface,) = params
            inv.return_value(props_get_all(req_iface, mapping))
            return
        if method == "Get":
            (req_iface, prop) = params
            props_get_one(req_iface, prop, mapping, inv)
            return

    if iface == "org.bluez.GattDescriptor1" and method == "ReadValue":
        inv.return_value(GLib.Variant("(ay)", (REPORT_REF,)))
        return

    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")

def main():
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    loop = GLib.MainLoop()

    objmgr_node = Gio.DBusNodeInfo.new_for_xml(OBJMGR_XML)
    bus.register_object(APP_PATH, objmgr_node.interfaces[0], handle_objmgr, None, None)

    service_node = Gio.DBusNodeInfo.new_for_xml(SERVICE_XML)
    bus.register_object(SERVICE_PATH, service_node.interfaces[0], None, None, None)
    bus.register_object(SERVICE_PATH, service_node.interfaces[1], handle_service_props, None, None)

    char_node = Gio.DBusNodeInfo.new_for_xml(CHAR_XML)
    for path in (INFO_PATH, MAP_PATH, CTRL_PATH, REPORT_PATH):
        for ifaceinfo in char_node.interfaces:
            bus.register_object(path, ifaceinfo, handle_char, None, None)

    desc_node = Gio.DBusNodeInfo.new_for_xml(DESC_XML)
    for ifaceinfo in desc_node.interfaces:
        bus.register_object(RR_DESC, ifaceinfo, handle_desc, None, None)

    mngr = Gio.DBusProxy.new_sync(
        bus, Gio.DBusProxyFlags.NONE, None, BLUEZ, ADAPTER, "org.bluez.GattManager1", None
    )

    def on_registered(proxy, res, _):
        try:
            proxy.call_finish(res)
            print("RegisterApplication OK. HoG up. Ctrl+C to stop.")
        except Exception as e:
            print(f"RegisterApplication FAILED: {e}")
            loop.quit()

    # async call avoids hard-deadlock/timeout stalls in the client
    mngr.call(
        "RegisterApplication",
        GLib.Variant("(oa{sv})", (APP_PATH, {})),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
        on_registered,
        None,
    )

    loop.run()

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
from gi.repository import Gio, GLib

BLUEZ   = "org.bluez"
ADAPTER = "/org/bluez/hci0"

ADV_PATH = "/com/steamdeck/hogp/adv0"

APP_PATH     = "/com/steamdeck/hogp"
SERVICE_PATH = APP_PATH + "/service0"

INFO_PATH   = SERVICE_PATH + "/char0"          # 2A4A
MAP_PATH    = SERVICE_PATH + "/char1"          # 2A4B
CTRL_PATH   = SERVICE_PATH + "/char2"          # 2A4C
REPORT_PATH = SERVICE_PATH + "/char3"          # 2A4D
RR_DESC     = REPORT_PATH + "/desc0"           # 2908

HID_UUID               = "00001812-0000-1000-8000-00805f9b34fb"
HID_INFORMATION_UUID   = "00002a4a-0000-1000-8000-00805f9b34fb"
REPORT_MAP_UUID        = "00002a4b-0000-1000-8000-00805f9b34fb"
HID_CONTROL_POINT_UUID = "00002a4c-0000-1000-8000-00805f9b34fb"
REPORT_UUID            = "00002a4d-0000-1000-8000-00805f9b34fb"
REPORT_REF_UUID        = "00002908-0000-1000-8000-00805f9b34fb"

# Same report map you had: 16 buttons + 4 axes (int16)
REPORT_MAP = bytes([
    0x05, 0x01, 0x09, 0x05, 0xA1, 0x01,
    0x05, 0x09, 0x19, 0x01, 0x29, 0x10,
    0x15, 0x00, 0x25, 0x01, 0x75, 0x01,
    0x95, 0x10, 0x81, 0x02,
    0x05, 0x01, 0x09, 0x30, 0x09, 0x31, 0x09, 0x33, 0x09, 0x34,
    0x16, 0x01, 0x80, 0x26, 0xFF, 0x7F,
    0x75, 0x10, 0x95, 0x04, 0x81, 0x02,
    0xC0
])

# HID Information: bcdHID=0x0111, country=0, flags=0x03
HID_INFO = bytes([0x11, 0x01, 0x00, 0x03])

# Report Reference descriptor: [ReportID, ReportType]
REPORT_ID   = 0x01
REPORT_TYPE = 0x01  # Input
REPORT_REF  = bytes([REPORT_ID, REPORT_TYPE])

report_value = bytearray(10)  # 2 bytes buttons + 8 bytes axes
notify_enabled = False
notify_source_id = None

OBJMGR_XML = """
<node>
  <interface name="org.freedesktop.DBus.ObjectManager">
    <method name="GetManagedObjects">
      <arg type="a{oa{sa{sv}}}" direction="out"/>
    </method>
  </interface>
</node>
"""

SERVICE_XML = """
<node>
  <interface name="org.bluez.GattService1">
    <property name="UUID" type="s" access="read"/>
    <property name="Primary" type="b" access="read"/>
    <property name="Includes" type="ao" access="read"/>
  </interface>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{sv}" direction="out"/>
    </method>
  </interface>
</node>
"""

CHAR_XML = """
<node>
  <interface name="org.bluez.GattCharacteristic1">
    <method name="ReadValue">
      <arg type="a{sv}" direction="in"/>
      <arg type="ay" direction="out"/>
    </method>
    <method name="WriteValue">
      <arg type="ay" direction="in"/>
      <arg type="a{sv}" direction="in"/>
    </method>
    <method name="StartNotify"/>
    <method name="StopNotify"/>
    <property name="UUID" type="s" access="read"/>
    <property name="Service" type="o" access="read"/>
    <property name="Flags" type="as" access="read"/>
    <property name="Descriptors" type="ao" access="read"/>
  </interface>

  <interface name="org.freedesktop.DBus.Properties">
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{sv}" direction="out"/>
    </method>
    <method name="Get">
      <arg type="s" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
  </interface>
</node>
"""

DESC_XML = """
<node>
  <interface name="org.bluez.GattDescriptor1">
    <method name="ReadValue">
      <arg type="a{sv}" direction="in"/>
      <arg type="ay" direction="out"/>
    </method>
    <property name="UUID" type="s" access="read"/>
    <property name="Characteristic" type="o" access="read"/>
    <property name="Flags" type="as" access="read"/>
  </interface>

  <interface name="org.freedesktop.DBus.Properties">
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{sv}" direction="out"/>
    </method>
    <method name="Get">
      <arg type="s" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
  </interface>
</node>
"""

def props_get_all(reply_iface, mapping):
    if reply_iface in mapping:
        return GLib.Variant("(a{sv})", (mapping[reply_iface],))
    return GLib.Variant("(a{sv})", ({},))

def props_get_one(req_iface, prop, mapping, inv):
    if req_iface in mapping and prop in mapping[req_iface]:
        inv.return_value(GLib.Variant("(v)", (mapping[req_iface][prop],)))
    else:
        inv.return_dbus_error("org.bluez.Error.InvalidArguments", "No such property")

def emit_char_props_changed(conn, path, iface_name, changed: dict):
    conn.emit_signal(
        None,
        path,
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        GLib.Variant("(sa{sv}as)", (iface_name, changed, [])),
    )

def notify_tick(conn):
    global report_value, notify_enabled
    if not notify_enabled:
        return True
    report_value[0] ^= 0x01  # toggle button 1
    changed = {"Value": GLib.Variant("ay", bytes(report_value))}
    emit_char_props_changed(conn, REPORT_PATH, "org.bluez.GattCharacteristic1", changed)
    return True
    report_value[0] ^= 0x01
    changed = {"Value": GLib.Variant("ay", bytes(report_value))}
    emit_char_props_changed(conn, REPORT_PATH, "org.bluez.GattCharacteristic1", changed)
    return True

def handle_objmgr(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    if iface == "org.freedesktop.DBus.ObjectManager" and method == "GetManagedObjects":
        managed = {
            SERVICE_PATH: {
                "org.bluez.GattService1": {
                    "UUID": GLib.Variant("s", HID_UUID),
                    "Primary": GLib.Variant("b", True),
                    "Includes": GLib.Variant("ao", []),
                }
            },
            INFO_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": GLib.Variant("s", HID_INFORMATION_UUID),
                    "Service": GLib.Variant("o", SERVICE_PATH),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                }
            },
            MAP_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": GLib.Variant("s", REPORT_MAP_UUID),
                    "Service": GLib.Variant("o", SERVICE_PATH),
                    "Flags": GLib.Variant("as", ["read"]),
                    "Descriptors": GLib.Variant("ao", []),
                }
            },
            CTRL_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": GLib.Variant("s", HID_CONTROL_POINT_UUID),
                    "Service": GLib.Variant("o", SERVICE_PATH),
                    "Flags": GLib.Variant("as", ["write-without-response"]),
                    "Descriptors": GLib.Variant("ao", []),
                }
            },
            REPORT_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": GLib.Variant("s", REPORT_UUID),
                    "Service": GLib.Variant("o", SERVICE_PATH),
                    "Flags": GLib.Variant("as", ["read", "notify"]),
                    "Descriptors": GLib.Variant("ao", [RR_DESC]),
                }
            },
            RR_DESC: {
                "org.bluez.GattDescriptor1": {
                    "UUID": GLib.Variant("s", REPORT_REF_UUID),
                    "Characteristic": GLib.Variant("o", REPORT_PATH),
                    "Flags": GLib.Variant("as", ["read"]),
                }
            },
        }
        inv.return_value(GLib.Variant("(a{oa{sa{sv}}})", (managed,)))
        return
    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")

def handle_service_props(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    if iface == "org.freedesktop.DBus.Properties" and method == "GetAll":
        (req_iface,) = params
        mapping = {
            "org.bluez.GattService1": {
                "UUID": GLib.Variant("s", HID_UUID),
                "Primary": GLib.Variant("b", True),
                "Includes": GLib.Variant("ao", []),
            }
        }
        inv.return_value(props_get_all(req_iface, mapping))
        return
    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")

def handle_char(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    global notify_enabled, notify_source_id

    if obj_path == INFO_PATH:
        uuid, flags, descriptors = HID_INFORMATION_UUID, ["read"], []
    elif obj_path == MAP_PATH:
        uuid, flags, descriptors = REPORT_MAP_UUID, ["read"], []
    elif obj_path == CTRL_PATH:
        uuid, flags, descriptors = HID_CONTROL_POINT_UUID, ["write-without-response"], []
    elif obj_path == REPORT_PATH:
        uuid, flags, descriptors = REPORT_UUID, ["read", "notify"], [RR_DESC]
    else:
        inv.return_dbus_error("org.bluez.Error.InvalidArguments", "Unknown characteristic path")
        return

    mapping = {
        "org.bluez.GattCharacteristic1": {
            "UUID": GLib.Variant("s", uuid),
            "Service": GLib.Variant("o", SERVICE_PATH),
            "Flags": GLib.Variant("as", flags),
            "Descriptors": GLib.Variant("ao", descriptors),
        }
    }

    if iface == "org.freedesktop.DBus.Properties":
        if method == "GetAll":
            (req_iface,) = params
            inv.return_value(props_get_all(req_iface, mapping))
            return
        if method == "Get":
            (req_iface, prop) = params
            props_get_one(req_iface, prop, mapping, inv)
            return
        if method == "Set":
            # BlueZ may try to Set() some properties; accept and ignore.
            inv.return_value(None)
            return


    if iface == "org.bluez.GattCharacteristic1":
        if method == "ReadValue":
            if obj_path == INFO_PATH:
                inv.return_value(GLib.Variant("(ay)", (HID_INFO,)))
                return
            if obj_path == MAP_PATH:
                inv.return_value(GLib.Variant("(ay)", (REPORT_MAP,)))
                return
            if obj_path == REPORT_PATH:
                inv.return_value(GLib.Variant("(ay)", (bytes(report_value),)))
                return
            inv.return_dbus_error("org.bluez.Error.NotPermitted", "Not readable")
            return

        if method == "WriteValue":
            if obj_path == CTRL_PATH:
                inv.return_value(None)
                return
            inv.return_dbus_error("org.bluez.Error.NotPermitted", "Not writable")
            return

        if method == "StartNotify":
            if obj_path != REPORT_PATH:
                inv.return_dbus_error("org.bluez.Error.NotSupported", "Notify not supported here")
                return
            if not notify_enabled:
                notify_enabled = True
                notify_source_id = GLib.timeout_add(500, notify_tick, conn)
                emit_char_props_changed(
                    conn, REPORT_PATH, "org.bluez.GattCharacteristic1",
                    {"Notifying": GLib.Variant("b", True)}
                )
            inv.return_value(None)
            return

        if method == "StopNotify":
            if obj_path != REPORT_PATH:
                inv.return_dbus_error("org.bluez.Error.NotSupported", "Notify not supported here")
                return
            if notify_enabled:
                notify_enabled = False
                if notify_source_id is not None:
                    GLib.source_remove(notify_source_id)
                    notify_source_id = None
                emit_char_props_changed(
                    conn, REPORT_PATH, "org.bluez.GattCharacteristic1",
                    {"Notifying": GLib.Variant("b", False)}
                )
            inv.return_value(None)
            return

    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")

def handle_desc(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    if obj_path != RR_DESC:
        inv.return_dbus_error("org.bluez.Error.InvalidArguments", "Unknown descriptor path")
        return

    mapping = {
        "org.bluez.GattDescriptor1": {
            "UUID": GLib.Variant("s", REPORT_REF_UUID),
            "Characteristic": GLib.Variant("o", REPORT_PATH),
            "Flags": GLib.Variant("as", ["read"]),
        }
    }

    if iface == "org.freedesktop.DBus.Properties":
        if method == "GetAll":
            (req_iface,) = params
            inv.return_value(props_get_all(req_iface, mapping))
            return
        if method == "Get":
            (req_iface, prop) = params
            props_get_one(req_iface, prop, mapping, inv)
            return

    if iface == "org.bluez.GattDescriptor1" and method == "ReadValue":
        inv.return_value(GLib.Variant("(ay)", (REPORT_REF,)))
        return

    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")


ADV_XML = """
<node>
  <interface name="org.bluez.LEAdvertisement1">
    <method name="Release"/>
    <property name="Type" type="s" access="read"/>
    <property name="ServiceUUIDs" type="as" access="read"/>
    <property name="LocalName" type="s" access="read"/>
    <property name="Discoverable" type="b" access="read"/>
    <property name="Includes" type="as" access="read"/>
  </interface>

  <interface name="org.freedesktop.DBus.Properties">
    <method name="GetAll">
      <arg type="s" direction="in"/>
      <arg type="a{sv}" direction="out"/>
    </method>
    <method name="Get">
      <arg type="s" direction="in"/>
      <arg type="s" direction="in"/>
      <arg type="v" direction="out"/>
    </method>
  </interface>
</node>
"""

def handle_adv(conn, sender, obj_path, iface, method, params, inv, user_data=None):
    mapping = {
        "org.bluez.LEAdvertisement1": {
            "Type": GLib.Variant("s", "peripheral"),
            "ServiceUUIDs": GLib.Variant("as", [HID_UUID]),
            "LocalName": GLib.Variant("s", "SteamDeckHoG"),
            "Discoverable": GLib.Variant("b", True),
            "Includes": GLib.Variant("as", ["tx-power"]),
        }
    }

    if iface == "org.freedesktop.DBus.Properties":
        if method == "GetAll":
            (req_iface,) = params
            inv.return_value(props_get_all(req_iface, mapping))
            return
        if method == "Get":
            (req_iface, prop) = params
            props_get_one(req_iface, prop, mapping, inv)
            return

    if iface == "org.bluez.LEAdvertisement1" and method == "Release":
        inv.return_value(None)
        return

    inv.return_dbus_error("org.bluez.Error.NotSupported", "Not supported")

def main():
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    loop = GLib.MainLoop()

    adv_node = Gio.DBusNodeInfo.new_for_xml(ADV_XML)
    for ifaceinfo in adv_node.interfaces:
        bus.register_object(ADV_PATH, ifaceinfo, handle_adv, None, None)

    objmgr_node = Gio.DBusNodeInfo.new_for_xml(OBJMGR_XML)
    bus.register_object(APP_PATH, objmgr_node.interfaces[0], handle_objmgr, None, None)

    service_node = Gio.DBusNodeInfo.new_for_xml(SERVICE_XML)
    bus.register_object(SERVICE_PATH, service_node.interfaces[0], None, None, None)
    bus.register_object(SERVICE_PATH, service_node.interfaces[1], handle_service_props, None, None)

    char_node = Gio.DBusNodeInfo.new_for_xml(CHAR_XML)
    for path in (INFO_PATH, MAP_PATH, CTRL_PATH, REPORT_PATH):
        for ifaceinfo in char_node.interfaces:
            bus.register_object(path, ifaceinfo, handle_char, None, None)

    desc_node = Gio.DBusNodeInfo.new_for_xml(DESC_XML)
    for ifaceinfo in desc_node.interfaces:
        bus.register_object(RR_DESC, ifaceinfo, handle_desc, None, None)

    mngr = Gio.DBusProxy.new_sync(
        bus, Gio.DBusProxyFlags.NONE, None, BLUEZ, ADAPTER, "org.bluez.GattManager1", None
    )

    def on_registered(proxy, res, _):
        try:
            proxy.call_finish(res)
            print("RegisterApplication OK. HoG up. Ctrl+C to stop.")
            # Register LE advertisement so central devices (e.g. Mac) can discover us
            try:
                advm = Gio.DBusProxy.new_sync(
                    bus, Gio.DBusProxyFlags.NONE, None, BLUEZ, ADAPTER, "org.bluez.LEAdvertisingManager1", None
                )
                advm.call(
                    "RegisterAdvertisement",
                    GLib.Variant("(oa{sv})", (ADV_PATH, {})),
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None,
                    None,
                    None,
                )
                print("RegisterAdvertisement OK. Advertising as SteamDeckHoG.")
            except Exception as e:
                print(f"RegisterAdvertisement FAILED: {e}")
        except Exception as e:
            print(f"RegisterApplication FAILED: {e}")
            loop.quit()

    # async call avoids hard-deadlock/timeout stalls in the client
    mngr.call(
        "RegisterApplication",
        GLib.Variant("(oa{sv})", (APP_PATH, {})),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
        on_registered,
        None,
    )

    loop.run()

if __name__ == "__main__":
    main()
(deck@steamdeck Desktop)$ 
