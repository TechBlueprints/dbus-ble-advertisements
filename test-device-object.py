#!/usr/bin/env python3
"""
Test: Create a device object with Name and Enabled properties
"""

import sys
sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

print("Creating device object with Name/Enabled properties...")

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# Create a device object that has Name and Enabled as properties
class DeviceObject(dbus.service.Object):
    def __init__(self, bus, path, name, enabled):
        dbus.service.Object.__init__(self, bus, path)
        self.name = name
        self.enabled = enabled
        print(f"  Created device at: {path}")
        print(f"    Name: {name}")
        print(f"    Enabled: {enabled}")
        
    @dbus.service.method('com.victronenergy.BusItem', out_signature='v')
    def GetValue(self):
        # Return dict with properties
        return {'Name': self.name, 'Enabled': self.enabled}
        
    @dbus.service.method('com.victronenergy.BusItem', out_signature='v')
    def GetText(self):
        return str({'Name': self.name, 'Enabled': self.enabled})

try:
    # Create device object
    device = DeviceObject(bus, '/Devices/integration_test_master', 
                         'BLE Integrations Scanning', 0)
    
    print("\n✓ Device object created!")
    print("\nTest with:")
    print("  dbus-send --system --print-reply --dest=com.victronenergy.ble /Devices org.freedesktop.DBus.Introspectable.Introspect")
    print("  dbus -y com.victronenergy.ble /Devices/integration_test_master GetValue")
    print("\nKeeping alive for 60 seconds...")
    
    def timeout():
        print("\nExiting")
        mainloop.quit()
        return False
    
    GLib.timeout_add_seconds(60, timeout)
    mainloop = GLib.MainLoop()
    mainloop.run()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

