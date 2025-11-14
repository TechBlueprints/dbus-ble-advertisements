#!/usr/bin/env python3
"""
Test: Claim com.victronenergy.ble and create devices
"""

import sys
import os
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')
from vedbus import VeDbusService

print("Test: Creating com.victronenergy.ble service with devices...")

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

try:
    # Now WE claim the com.victronenergy.ble name
    service = VeDbusService('com.victronenergy.ble', bus, register=False)
    
    # Add our test device
    service.add_path('/Devices/test_integration_master/Name', 'BLE Integrations Scanning')
    service.add_path('/Devices/test_integration_master/Enabled', 0)
    
    # Add a discovered device
    service.add_path('/Devices/integration_oriontr_02e1/Name', 'Orion-TR (0x02E1)')
    service.add_path('/Devices/integration_oriontr_02e1/Enabled', 0)
    
    # Now register to claim the name
    service.register()
    
    print("✓ Successfully claimed com.victronenergy.ble")
    print("✓ Created devices:")
    print("  - /Devices/test_integration_master/Name = 'BLE Integrations Scanning'")
    print("  - /Devices/test_integration_master/Enabled = 0")
    print("  - /Devices/integration_oriontr_02e1/Name = 'Orion-TR (0x02E1)'")
    print("  - /Devices/integration_oriontr_02e1/Enabled = 0")
    
    # Verify
    test_obj = bus.get_object('com.victronenergy.ble', '/Devices/test_integration_master/Name')
    test_iface = dbus.Interface(test_obj, 'com.victronenergy.BusItem')
    value = test_iface.GetValue()
    print(f"\n✓ Verified: Name = '{value}'")
    
    print("\nKeeping service running for 30 seconds...")
    print("Check the UI at: Settings → Integrations → Bluetooth Sensors")
    
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
    sys.exit(1)

