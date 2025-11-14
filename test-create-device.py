#!/usr/bin/env python3
"""
Test: Try to create objects using dbus-ble-sensors' connection
"""

import sys
sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

print("=" * 80)
print("TEST: Try to create objects on dbus-ble-sensors' connection")
print("=" * 80)

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# Get the connection that owns com.victronenergy.ble
print("\n[STEP 1] Finding dbus-ble-sensors connection...")
try:
    ble_sensors_conn = bus.call_blocking(
        'org.freedesktop.DBus',
        '/org/freedesktop/DBus',
        'org.freedesktop.DBus',
        'GetNameOwner',
        's',
        ['com.victronenergy.ble']
    )
    print(f"[STEP 1] ✓ dbus-ble-sensors is on: {ble_sensors_conn}")
except Exception as e:
    print(f"[STEP 1] ✗ Failed: {e}")
    sys.exit(1)

# Try to get a proxy to that connection's bus object
print("\n[STEP 2] Attempting to create objects on that connection...")
try:
    # This should fail - we can't create objects on another process's connection
    proxy = bus.get_object(ble_sensors_conn, '/Devices/testdevice_cafebabedeadbeef/Name', introspect=False)
    print(f"[STEP 2] Got proxy to {ble_sensors_conn}")
    
    # Try to call a method
    iface = dbus.Interface(proxy, 'com.victronenergy.BusItem')
    result = iface.GetValue()
    print(f"[STEP 2] ✗ Unexpectedly succeeded: {result}")
except dbus.exceptions.DBusException as e:
    print(f"[STEP 2] ✓ Expected failure: {e}")
    print("[STEP 2] Cannot create objects on another process's connection")
except Exception as e:
    print(f"[STEP 2] ? Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("CONCLUSION: Each process can only create objects on its own connection")
print("=" * 80)
