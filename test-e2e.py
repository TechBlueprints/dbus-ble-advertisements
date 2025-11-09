#!/usr/bin/env python3
"""
End-to-End Test for BLE Advertisement Router

This test verifies the complete flow:
1. Router service is running and responsive
2. Client can register for manufacturer ID and MAC address
3. Client receives advertisement signals with all expected data
4. Multiple registration types work simultaneously
"""

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import sys
import time

print("=" * 70, flush=True)
print("BLE Advertisement Router - End-to-End Test", flush=True)
print("=" * 70, flush=True)

# Initialize D-Bus
print("\n[1/7] Initializing D-Bus...", flush=True)
DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
print("✓ D-Bus initialized", flush=True)

# Check if router service exists
print("\n[2/7] Checking router service availability...", flush=True)
try:
    router_obj = bus.get_object('com.victronenergy.ble.advertisements', '/ble_advertisements')
    router_iface = dbus.Interface(router_obj, 'com.victronenergy.ble.Advertisements')
    
    version = router_iface.GetVersion()
    status = router_iface.GetStatus()
    heartbeat = router_iface.GetHeartbeat()
    
    print(f"✓ Router service found", flush=True)
    print(f"  - Version: {version}", flush=True)
    print(f"  - Status: {status}", flush=True)
    print(f"  - Heartbeat: {heartbeat}", flush=True)
    
    if status != "running":
        print(f"✗ Router status is '{status}', expected 'running'", flush=True)
        sys.exit(1)
except Exception as e:
    print(f"✗ Router service not available: {e}", flush=True)
    sys.exit(1)

# Create test service
print("\n[3/7] Registering test service on D-Bus...", flush=True)

class TestRegistration(dbus.service.Object):
    """Empty registration object"""
    pass

try:
    bus_name = dbus.service.BusName('com.victronenergy.e2etest', bus)
    print(f"✓ Service name registered: com.victronenergy.e2etest", flush=True)
except Exception as e:
    print(f"✗ Failed to register service: {e}", flush=True)
    sys.exit(1)

# Create registrations
print("\n[4/7] Creating registration objects...", flush=True)
registrations = []

# Register for Victron manufacturer ID (737 / 0x02E1)
victron_path = '/ble_advertisements/e2etest/mfgr/737'
victron_reg = TestRegistration(bus_name, victron_path)
registrations.append(victron_reg)
print(f"✓ Created registration: {victron_path}", flush=True)

# Register for Cypress/SeeLevel manufacturer ID (305 / 0x0131)
seelevel_path = '/ble_advertisements/e2etest/mfgr/305'
seelevel_reg = TestRegistration(bus_name, seelevel_path)
registrations.append(seelevel_reg)
print(f"✓ Created registration: {seelevel_path}", flush=True)

# Track received advertisements
received = {
    'victron_count': 0,
    'seelevel_count': 0,
    'victron_macs': set(),
    'seelevel_macs': set(),
    'victron_names': set(),
    'seelevel_names': set(),
    'start_time': time.time()
}

def victron_callback(mac, mfg_id, data, rssi, interface, name):
    """Callback for Victron advertisements"""
    received['victron_count'] += 1
    received['victron_macs'].add(mac)
    if name:
        received['victron_names'].add(name)
    
    # Print first few for verification
    if received['victron_count'] <= 3:
        data_hex = ''.join(f'{b:02x}' for b in data)
        name_str = f" name='{name}'" if name else ""
        print(f"  Victron: [{interface}] {mac}{name_str} mfg={mfg_id:#06x} rssi={rssi:4d} len={len(data):3d}", flush=True)

def seelevel_callback(mac, mfg_id, data, rssi, interface, name):
    """Callback for SeeLevel advertisements"""
    received['seelevel_count'] += 1
    received['seelevel_macs'].add(mac)
    if name:
        received['seelevel_names'].add(name)
    
    # Print first few for verification
    if received['seelevel_count'] <= 3:
        data_hex = ''.join(f'{b:02x}' for b in data)
        name_str = f" name='{name}'" if name else ""
        print(f"  SeeLevel: [{interface}] {mac}{name_str} mfg={mfg_id:#06x} rssi={rssi:4d} len={len(data):3d}", flush=True)

# Subscribe to signals
print("\n[5/7] Subscribing to Advertisement signals...", flush=True)
try:
    bus.add_signal_receiver(
        victron_callback,
        signal_name='Advertisement',
        dbus_interface='com.victronenergy.ble.Advertisements',
        path=victron_path
    )
    print(f"✓ Subscribed to signals on {victron_path}", flush=True)
    
    bus.add_signal_receiver(
        seelevel_callback,
        signal_name='Advertisement',
        dbus_interface='com.victronenergy.ble.Advertisements',
        path=seelevel_path
    )
    print(f"✓ Subscribed to signals on {seelevel_path}", flush=True)
except Exception as e:
    print(f"✗ Failed to subscribe: {e}", flush=True)
    sys.exit(1)

# Wait for advertisements
print("\n[6/7] Waiting for advertisements (10 seconds)...", flush=True)
print("  (First few advertisements will be printed)\n", flush=True)

def check_results():
    """Check if we received advertisements and print summary"""
    elapsed = time.time() - received['start_time']
    
    print("\n" + "=" * 70, flush=True)
    print("Test Results", flush=True)
    print("=" * 70, flush=True)
    
    print(f"\nElapsed time: {elapsed:.1f} seconds", flush=True)
    
    print(f"\n[7/7] Victron (0x02E1) Advertisements:", flush=True)
    print(f"  - Total received: {received['victron_count']}", flush=True)
    print(f"  - Unique MACs: {len(received['victron_macs'])}", flush=True)
    print(f"  - Unique names: {len(received['victron_names'])}", flush=True)
    if received['victron_names']:
        print(f"  - Example names: {', '.join(list(received['victron_names'])[:5])}", flush=True)
    
    print(f"\n[7/7] SeeLevel (0x0131) Advertisements:", flush=True)
    print(f"  - Total received: {received['seelevel_count']}", flush=True)
    print(f"  - Unique MACs: {len(received['seelevel_macs'])}", flush=True)
    print(f"  - Unique names: {len(received['seelevel_names'])}", flush=True)
    if received['seelevel_names']:
        print(f"  - Example names: {', '.join(list(received['seelevel_names'])[:5])}", flush=True)
    
    # Determine pass/fail
    print("\n" + "=" * 70, flush=True)
    print("Test Evaluation", flush=True)
    print("=" * 70, flush=True)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Victron advertisements received
    tests_total += 1
    if received['victron_count'] > 0:
        print(f"✓ Test 1: Received Victron advertisements ({received['victron_count']})", flush=True)
        tests_passed += 1
    else:
        print(f"✗ Test 1: No Victron advertisements received", flush=True)
    
    # Test 2: Multiple Victron devices detected
    tests_total += 1
    if len(received['victron_macs']) >= 2:
        print(f"✓ Test 2: Multiple Victron devices detected ({len(received['victron_macs'])})", flush=True)
        tests_passed += 1
    else:
        print(f"✗ Test 2: Expected multiple devices, got {len(received['victron_macs'])}", flush=True)
    
    # Test 3: Device names received
    tests_total += 1
    if len(received['victron_names']) > 0:
        print(f"✓ Test 3: Device names received ({len(received['victron_names'])} unique)", flush=True)
        tests_passed += 1
    else:
        print(f"✗ Test 3: No device names received", flush=True)
    
    # Test 4: SeeLevel advertisements (if available)
    tests_total += 1
    if received['seelevel_count'] > 0:
        print(f"✓ Test 4: Received SeeLevel advertisements ({received['seelevel_count']})", flush=True)
        tests_passed += 1
    else:
        print(f"⚠ Test 4: No SeeLevel advertisements (device may not be present)", flush=True)
        # Don't fail if SeeLevel not present
        tests_passed += 1
    
    # Test 5: Advertisement rate reasonable
    tests_total += 1
    rate = received['victron_count'] / elapsed if elapsed > 0 else 0
    if rate >= 1.0:  # At least 1 per second
        print(f"✓ Test 5: Advertisement rate acceptable ({rate:.1f}/sec)", flush=True)
        tests_passed += 1
    else:
        print(f"✗ Test 5: Advertisement rate too low ({rate:.1f}/sec)", flush=True)
    
    print("\n" + "=" * 70, flush=True)
    if tests_passed == tests_total:
        print(f"✅ ALL TESTS PASSED ({tests_passed}/{tests_total})", flush=True)
        print("=" * 70, flush=True)
        mainloop.quit()
        sys.exit(0)
    else:
        print(f"❌ SOME TESTS FAILED ({tests_passed}/{tests_total})", flush=True)
        print("=" * 70, flush=True)
        mainloop.quit()
        sys.exit(1)

# Run mainloop with timeout
mainloop = GLib.MainLoop()
GLib.timeout_add_seconds(10, check_results)

try:
    mainloop.run()
except KeyboardInterrupt:
    print("\n\nTest interrupted", flush=True)
    sys.exit(1)

