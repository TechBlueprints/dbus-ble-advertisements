#!/usr/bin/env python3
"""
Test script to see if we can publish objects on com.victronenergy.ble
"""

import sys
import os
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

# Add velib to path
sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')
from vedbus import VeDbusService

print("Testing if we can add devices to com.victronenergy.ble service...")

# Initialize D-Bus
DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# Check if com.victronenergy.ble exists
proxy = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
dbus_iface = dbus.Interface(proxy, 'org.freedesktop.DBus')

if 'com.victronenergy.ble' not in dbus_iface.ListNames():
    print("ERROR: com.victronenergy.ble service not found")
    sys.exit(1)

print("✓ com.victronenergy.ble service exists")

# We need to register our objects under the com.victronenergy.ble name
# even though we don't own it
try:
    # The trick is to use the connection object, not create a BusName
    # but still export objects that respond to that name
    
    class VeDbusItemExport(dbus.service.Object):
        """Export a VeDbusItem-compatible object"""
        
        def __init__(self, bus, path, value, conn=None):
            # Don't pass conn if not provided - let Object handle it
            if conn:
                dbus.service.Object.__init__(self, conn, path)
            else:
                dbus.service.Object.__init__(self, bus, path)
            self._value = value
            
        @dbus.service.method('com.victronenergy.BusItem', out_signature='v')
        def GetValue(self):
            return self._value
            
        @dbus.service.method('com.victronenergy.BusItem', in_signature='v', out_signature='i')
        def SetValue(self, value):
            self._value = value
            return 0  # Success
            
        @dbus.service.method('com.victronenergy.BusItem', out_signature='v')
        def GetText(self):
            return str(self._value)
    
    # Create device items directly on the bus (not a BusName)
    name_item = VeDbusItemExport(bus, '/Devices/test_integration/Name', 'Test Integration Device')
    enabled_item = VeDbusItemExport(bus, '/Devices/test_integration/Enabled', 0)
    
    print("✓ Successfully created device objects")
    print("  - /Devices/test_integration/Name")
    print("  - /Devices/test_integration/Enabled")
    
    # Verify we can read it back
    test_name = dbus.Interface(
        bus.get_object('com.victronenergy.ble', '/Devices/test_integration/Name'),
        'com.victronenergy.BusItem'
    ).GetValue()
    
    print(f"✓ Verified: Name = '{test_name}'")
    
    print("\nSuccess! We can add devices to com.victronenergy.ble")
    print("Keeping service running for 10 seconds so you can inspect it...")
    
    def timeout():
        print("\nTest complete - cleaning up")
        mainloop.quit()
        return False
    
    GLib.timeout_add_seconds(10, timeout)
    mainloop = GLib.MainLoop()
    mainloop.run()
    
except Exception as e:
    print(f"✗ Failed to create device: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

