#!/usr/bin/env python3
"""
Test: Can we export objects that coexist with dbus-ble-sensors objects?
"""

import sys
sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from vedbus import VeDbusService

print("Testing coexistence with dbus-ble-sensors...")

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# Check dbus-ble-sensors is running
proxy = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
dbus_iface = dbus.Interface(proxy, 'org.freedesktop.DBus')

if 'com.victronenergy.ble' not in dbus_iface.ListNames():
    print("ERROR: dbus-ble-sensors not running")
    sys.exit(1)

print("✓ dbus-ble-sensors is running")

# Check existing devices
print("\nExisting devices before our test:")
existing = bus.get_object('com.victronenergy.ble', '/Devices')
intro = dbus.Interface(existing, 'org.freedesktop.DBus.Introspectable')
xml = intro.Introspect()
import re
existing_devices = re.findall(r'<node name="([^"]+)"', xml)
for dev in existing_devices[:5]:
    print(f"  - {dev}")
if len(existing_devices) > 5:
    print(f"  ... and {len(existing_devices)-5} more")

# Now try to add OUR objects using a different service name
# but at paths that should appear under com.victronenergy.ble
print("\nCreating our own service with device paths...")

try:
    # Create our service with a DIFFERENT name
    our_service = VeDbusService('com.victronenergy.ble.integrations', bus)
    
    # But add paths that LOOK like they're under com.victronenergy.ble
    our_service.add_path('/Devices/integration_test_device/Name', 'Test Integration')
    our_service.add_path('/Devices/integration_test_device/Enabled', 0)
    
    print("✓ Created com.victronenergy.ble.integrations with /Devices paths")
    
    # Can we read it via OUR service name?
    test1 = bus.get_object('com.victronenergy.ble.integrations', '/Devices/integration_test_device/Name')
    val1 = dbus.Interface(test1, 'com.victronenergy.BusItem').GetValue()
    print(f"✓ Via com.victronenergy.ble.integrations: '{val1}'")
    
    # Does it appear when listing com.victronenergy.ble devices?
    print("\nChecking if it appears in com.victronenergy.ble /Devices...")
    existing = bus.get_object('com.victronenergy.ble', '/Devices')
    intro = dbus.Interface(existing, 'org.freedesktop.DBus.Introspectable')
    xml = intro.Introspect()
    devices_now = re.findall(r'<node name="([^"]+)"', xml)
    
    if 'integration_test_device' in devices_now:
        print("✓ YES! Our device appears in com.victronenergy.ble listing!")
    else:
        print("✗ No, our device does NOT appear in com.victronenergy.ble")
        print(f"Devices now: {devices_now[:5]}")
    
    print("\nKeeping alive for 30 seconds for manual testing...")
    
    def timeout():
        mainloop.quit()
        return False
    
    GLib.timeout_add_seconds(30, timeout)
    mainloop = GLib.MainLoop()
    mainloop.run()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

