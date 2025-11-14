#!/usr/bin/env python3
"""
Test: Create device objects at /Devices paths (no service name claim)
Just like how orion-tr creates /ble_advertisements/orion_tr paths
"""

import sys
sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

print("Creating device objects at /Devices paths...")

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# Create VeDbusItem-style objects
class DeviceProperty(dbus.service.Object):
    def __init__(self, bus, path, value):
        dbus.service.Object.__init__(self, bus, path)
        self._value = value
        print(f"  Created: {path} = {value}")
        
    @dbus.service.method('com.victronenergy.BusItem', out_signature='v')
    def GetValue(self):
        return self._value
        
    @dbus.service.method('com.victronenergy.BusItem', in_signature='v', out_signature='i')
    def SetValue(self, value):
        print(f"  SetValue called: {self._value} -> {value}")
        self._value = value
        return 0
        
    @dbus.service.method('com.victronenergy.BusItem', out_signature='v')
    def GetText(self):
        return str(self._value)

try:
    # Create device objects just like orion-tr creates registration objects
    name_obj = DeviceProperty(bus, '/Devices/integration_test_master/Name', 'BLE Integrations Scanning')
    enabled_obj = DeviceProperty(bus, '/Devices/integration_test_master/Enabled', 0)
    
    print("\n✓ Objects created!")
    print("\nNow check if they appear:")
    print("  dbus-send --system --print-reply --dest=com.victronenergy.ble /Devices org.freedesktop.DBus.Introspectable.Introspect")
    print("\nKeeping alive for 60 seconds...")
    
    def timeout():
        print("\nTimeout - exiting")
        mainloop.quit()
        return False
    
    GLib.timeout_add_seconds(60, timeout)
    mainloop = GLib.MainLoop()
    mainloop.run()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

