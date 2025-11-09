#!/usr/bin/env python3
"""
Test script to manually register for BLE advertisements and print received signals.
"""

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import sys

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

class TestRegistration(dbus.service.Object):
    """Registration object for testing"""
    pass

# Store registrations globally so they don't get garbage collected
registrations = []

def advertisement_callback(mac, mfg_id, data, rssi, interface, name):
    """Callback for Advertisement signals"""
    data_hex = ''.join(f'{b:02x}' for b in data)
    name_str = f" name='{name}'" if name else ""
    print(f"[{interface}] {mac}{name_str} mfg={mfg_id:#06x} ({mfg_id}) rssi={rssi:4d} len={len(data):3d} data={data_hex[:40]}{'...' if len(data_hex) > 40 else ''}")

def register_manufacturer(service_name, mfg_id):
    """Register for a manufacturer ID"""
    path = f'/ble_advertisements/{service_name}/mfgr/{mfg_id}'
    try:
        bus_name = dbus.service.BusName(f'com.victronenergy.{service_name}', bus)
        reg = TestRegistration(bus_name, path)
        registrations.append(reg)
        
        # Subscribe to signals on the same path
        bus.add_signal_receiver(
            advertisement_callback,
            signal_name='Advertisement',
            dbus_interface='com.victronenergy.ble.Advertisements',
            path=path
        )
        
        print(f"✓ Registered: {path}")
        print(f"  Listening for signals on: {path}")
        return True
    except Exception as e:
        print(f"✗ Failed to register {path}: {e}")
        return False

def register_mac(service_name, mac):
    """Register for a specific MAC address"""
    mac_no_colons = mac.replace(':', '').upper()
    path = f'/ble_advertisements/{service_name}/addr/{mac_no_colons}'
    try:
        bus_name = dbus.service.BusName(f'com.victronenergy.{service_name}', bus)
        reg = TestRegistration(bus_name, path)
        registrations.append(reg)
        
        # Subscribe to signals on the same path
        bus.add_signal_receiver(
            advertisement_callback,
            signal_name='Advertisement',
            dbus_interface='com.victronenergy.ble.Advertisements',
            path=path
        )
        
        print(f"✓ Registered: {path}")
        print(f"  Listening for signals on: {path}")
        return True
    except Exception as e:
        print(f"✗ Failed to register {path}: {e}")
        return False

def main():
    print("BLE Advertisement Test Client")
    print("=" * 60)
    
    # Register for manufacturers
    print("\nRegistering for manufacturer IDs...")
    register_manufacturer('test', 737)    # Victron (0x02E1)
    register_manufacturer('test', 305)    # Cypress (SeeLevel BTP3)
    register_manufacturer('test', 3264)   # SeeLevel BTP7
    
    print("\n" + "=" * 60)
    print("Waiting for advertisements... (Ctrl+C to exit)")
    print("=" * 60 + "\n")
    
    # Run main loop
    try:
        mainloop = GLib.MainLoop()
        mainloop.run()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)

if __name__ == '__main__':
    main()

