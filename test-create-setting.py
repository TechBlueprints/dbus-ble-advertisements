#!/usr/bin/env python3
"""
Test script to create the BLE Integrations master switch setting
"""

import sys
sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from vedbus import VeDbusService

print("Creating BLE Integrations master switch setting...")

DBusGMainLoop(set_as_default=True)

# Create a dummy service just to register the setting
service = VeDbusService("com.techblueprints.ble_advertisements", bus=dbus.SystemBus())

# Add the setting with default value 0, min 0, max 1
service.add_path('/Settings/MasterScanEnabled', value=0, writeable=True,
                 onchangecallback=lambda path, value: print(f"Setting changed to: {value}"))

print("✓ Setting created at com.techblueprints.ble_advertisements/Settings/MasterScanEnabled")
print("  Current value: 0 (disabled)")
print("\nKeeping service alive for 5 minutes...")
print("Check the GUI now - the 'BLE Integrations Scanning' switch should appear!")
print("\nPress Ctrl+C to stop")

try:
    mainloop = GLib.MainLoop()
    GLib.timeout_add_seconds(300, lambda: mainloop.quit() or False)
    mainloop.run()
except KeyboardInterrupt:
    print("\nStopped")

print("Done")

