#!/usr/bin/env python3
"""
Simple test - just register and wait for signals
"""

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import sys

print("Initializing D-Bus...", flush=True)
DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

print("Creating registration object...", flush=True)

class TestReg(dbus.service.Object):
    pass

try:
    # Register service name
    print("Requesting bus name com.victronenergy.test...", flush=True)
    bus_name = dbus.service.BusName('com.victronenergy.test', bus)
    
    # Create registration object at path for Victron manufacturer ID (737)
    path = '/ble_advertisements/test/mfgr/737'
    print(f"Creating object at {path}...", flush=True)
    reg = TestReg(bus_name, path)
    
    # Subscribe to signals
    print("Subscribing to Advertisement signals...", flush=True)
    def callback(mac, mfg_id, data, rssi, interface, name):
        data_hex = ''.join(f'{b:02x}' for b in data)
        print(f"[{interface}] {mac} name='{name}' mfg={mfg_id:#06x} rssi={rssi} len={len(data)} data={data_hex[:40]}", flush=True)
    
    bus.add_signal_receiver(
        callback,
        signal_name='Advertisement',
        dbus_interface='com.victronenergy.ble.Advertisements',
        path=path
    )
    
    print(f"✓ Registered and listening on {path}", flush=True)
    print("Waiting for advertisements (Ctrl+C to exit)...", flush=True)
    
    mainloop = GLib.MainLoop()
    mainloop.run()

except KeyboardInterrupt:
    print("\nExiting...", flush=True)
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

