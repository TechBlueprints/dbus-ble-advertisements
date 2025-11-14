#!/usr/bin/env python3
"""
Test: Just create objects at /Devices paths and see what happens
"""

import sys
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

print("Test: Creating device objects without claiming bus name...")

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# VeDbusItem-compatible class
class VeDbusItem(dbus.service.Object):
    def __init__(self, bus, path, value):
        dbus.service.Object.__init__(self, bus, path)
        self._value = value
        
    @dbus.service.method('com.victronenergy.BusItem', out_signature='v')
    def GetValue(self):
        return self._value
        
    @dbus.service.method('com.victronenergy.BusItem', in_signature='v', out_signature='i')
    def SetValue(self, value):
        old = self._value
        self._value = value
        print(f"Value changed: {old} -> {value}")
        return 0
        
    @dbus.service.method('com.victronenergy.BusItem', out_signature='v')
    def GetText(self):
        return str(self._value)

try:
    # Just create the objects - don't claim any name
    print("Creating objects...")
    name1 = VeDbusItem(bus, '/com/victronenergy/ble/Devices/test_integration_master/Name', 'BLE Integrations Scanning')
    enabled1 = VeDbusItem(bus, '/com/victronenergy/ble/Devices/test_integration_master/Enabled', 0)
    
    print("✓ Created:")
    print("  - /com/victronenergy/ble/Devices/test_integration_master/Name")
    print("  - /com/victronenergy/ble/Devices/test_integration_master/Enabled")
    
    print("\nTrying to access via our connection name...")
    # Get our unique connection name
    my_name = bus.get_unique_name()
    print(f"Our connection name: {my_name}")
    
    test_obj = bus.get_object(my_name, '/com/victronenergy/ble/Devices/test_integration_master/Name')
    test_iface = dbus.Interface(test_obj, 'com.victronenergy.BusItem')
    value = test_iface.GetValue()
    print(f"✓ Can read via {my_name}: '{value}'")
    
    print("\nKeeping alive for 30 seconds to test...")
    
    def timeout():
        print("\nTest complete")
        mainloop.quit()
        return False
    
    GLib.timeout_add_seconds(30, timeout)
    mainloop = GLib.MainLoop()
    mainloop.run()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

