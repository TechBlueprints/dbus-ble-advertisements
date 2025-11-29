# Developer Guide: Using dbus-ble-advertisements

This guide shows you how to build a Venus OS service that uses the `dbus-ble-advertisements` router for BLE scanning.

## Table of Contents
1. [Why This Service Exists](#why-this-service-exists)
2. [Overview](#overview)
3. [Prerequisites](#prerequisites)
4. [Step 1: Check if Router is Available](#step-1-check-if-router-is-available)
5. [Step 2: Set Up D-Bus Connection](#step-2-set-up-dbus-connection)
6. [Step 3: Register Your Interests](#step-3-register-your-interests)
7. [Step 4: Subscribe to Advertisement Signals](#step-4-subscribe-to-advertisement-signals)
8. [Step 5: Process Advertisements](#step-5-process-advertisements)
9. [Complete Example](#complete-example)
10. [Best Practices](#best-practices)
11. [Troubleshooting](#troubleshooting)

---

## Why This Service Exists

### The Problem

On Venus OS (and most Linux systems using BlueZ), **only one process can actively scan for BLE devices at a time**. When multiple services try to scan simultaneously, you get errors like:

```
org.bluez.Error.InProgress: Operation already in progress
```

This creates serious problems:
- 🚫 Can't run multiple BLE services simultaneously
- 🚫 Services conflict and fail to discover devices
- 🚫 Must choose which service gets BLE access
- 🚫 Adding new BLE features breaks existing ones

### Example Scenario

Imagine you have:
1. **Victron Orion-TR service** - needs to monitor DC-DC converters
2. **SeeLevel tank sensor service** - needs to monitor tank levels
3. **Future battery monitor** - needs to monitor battery BMS

**Without the router:**
```
Service 1 starts scanning → ✅ Works
Service 2 starts scanning → ❌ Error: Operation already in progress
Service 3 starts scanning → ❌ Error: Operation already in progress
```

Only one service works. The others fail.

**With the router:**
```
Router starts btmon → Monitors ALL BLE traffic
Service 1 registers → ✅ Gets its advertisements via D-Bus
Service 2 registers → ✅ Gets its advertisements via D-Bus  
Service 3 registers → ✅ Gets its advertisements via D-Bus
```

All services work simultaneously!

### The Solution

The `dbus-ble-advertisements` router:
1. **Runs ONE passive monitor** (`btmon`) that captures ALL BLE advertisements
2. **Services register their interests** via D-Bus (no scanning needed)
3. **Router filters and distributes** advertisements to interested services
4. **No conflicts** - btmon is passive and doesn't interfere with anything

### Why btmon?

Unlike active BLE scanning (Bleak, BlueZ D-Bus API), `btmon` is **passive**:
- ✅ Doesn't take control of the Bluetooth adapter
- ✅ Multiple processes can read HCI data simultaneously
- ✅ Zero conflicts with other BLE operations
- ✅ Sees ALL advertisements from ALL adapters (hci0, hci1, etc.)

---

## Overview

The `dbus-ble-advertisements` router provides centralized BLE scanning for Venus OS. Instead of each service running its own BLE scanner, services register their interests with the router and receive advertisement data via D-Bus signals.

**Benefits:**
- ✅ No conflicts between multiple BLE services
- ✅ Single `btmon` process for entire system
- ✅ Automatic filtering by manufacturer ID or MAC address
- ✅ Efficient deduplication (signals only on data change or 10-minute heartbeat)

---

## Prerequisites

```python
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
```

Your service needs:
- Python 3 with `python-dbus` and `python-gi`
- The `dbus-ble-advertisements` router installed and running
- Root access (for D-Bus system bus)

---

## Step 1: Check if Router is Available

Before starting your service, verify the router is installed and healthy:

```python
import dbus
from dbus.mainloop.glib import DBusGMainLoop
import logging

logger = logging.getLogger(__name__)

def check_router_available():
    """Check if dbus-ble-advertisements router is available and healthy"""
    try:
        # Initialize D-Bus main loop
        DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()
        
        # Check if service is registered on D-Bus
        proxy = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        dbus_iface = dbus.Interface(proxy, 'org.freedesktop.DBus')
        
        if 'com.victronenergy.switch.bleadvertisements' not in dbus_iface.ListNames():
            logger.error("dbus-ble-advertisements service not found on D-Bus")
            return False
        
        # Check service health by calling GetVersion
        service = bus.get_object('com.victronenergy.switch.bleadvertisements', '/ble_advertisements')
        iface = dbus.Interface(service, 'com.victronenergy.switch.bleadvertisements')
        version = iface.GetVersion()
        
        logger.info(f"dbus-ble-advertisements service found (version: {version})")
        return True
        
    except Exception as e:
        logger.error(f"Router check failed: {e}")
        return False

# Example usage
if not check_router_available():
    print("ERROR: dbus-ble-advertisements not available!")
    print("Install from: https://github.com/TechBlueprints/dbus-ble-advertisements")
    exit(1)
```

---

## Step 2: Set Up D-Bus Connection

Initialize your D-Bus connection and GLib main loop:

```python
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

class MyBLEService:
    def __init__(self):
        # Set up D-Bus main loop (safe to call multiple times)
        DBusGMainLoop(set_as_default=True)
        
        # Connect to system bus
        self.bus = dbus.SystemBus()
        
        # Your service name (used for D-Bus registration paths)
        self.service_name = "my_service"  # Use underscores, not hyphens!
        
        # Will hold D-Bus object references
        self.registration_objects = []
```

**Important:** Service names in D-Bus paths must use underscores, not hyphens. If your service is called "my-cool-service", use "my_cool_service" for D-Bus registration.

---

## Step 3: Register Your Interests

Tell the router what BLE advertisements you're interested in by creating D-Bus objects at specific paths.

### Option A: Register by Manufacturer ID

Use this if you want all advertisements from a specific manufacturer (e.g., all Victron devices):

```python
def register_manufacturer_id(self, manufacturer_id):
    """
    Register interest in a manufacturer ID
    
    Args:
        manufacturer_id: uint16 manufacturer ID (e.g., 0x02E1 for Victron)
    """
    # Create D-Bus path: /ble_advertisements/{service}/mfgr/{id}
    path = f"/ble_advertisements/{self.service_name}/mfgr/{manufacturer_id}"
    
    # Create a D-Bus object at this path
    obj = dbus.service.Object(self.bus, path)
    self.registration_objects.append(obj)
    
    print(f"Registered interest in manufacturer ID: 0x{manufacturer_id:04X} at {path}")

# Example: Register for Victron devices (0x02E1)
service = MyBLEService()
service.register_manufacturer_id(0x02E1)
```

### Option B: Register by MAC Address

Use this if you only want advertisements from specific devices:

```python
def register_mac_address(self, mac_address):
    """
    Register interest in a specific MAC address
    
    Args:
        mac_address: MAC address string (e.g., "F0:9D:2E:E9:A9:11")
    """
    # Convert MAC to D-Bus-safe format (replace : with _)
    mac_safe = mac_address.upper().replace(':', '_')
    
    # Create D-Bus path: /ble_advertisements/{service}/addr/{mac}
    path = f"/ble_advertisements/{self.service_name}/addr/{mac_safe}"
    
    # Create a D-Bus object at this path
    obj = dbus.service.Object(self.bus, path)
    self.registration_objects.append(obj)
    
    print(f"Registered interest in MAC: {mac_address} at {path}")

# Example: Register for specific device
service = MyBLEService()
service.register_mac_address("F0:9D:2E:E9:A9:11")
```

### Register Multiple Interests

You can register for multiple manufacturer IDs and/or MAC addresses:

```python
# Register for multiple manufacturer IDs
for mfg_id in [0x02E1, 0x0131, 0x0CC0]:  # Victron, Cypress, SeeLevel
    service.register_manufacturer_id(mfg_id)

# Register for multiple specific devices
for mac in ["F0:9D:2E:E9:A9:11", "EC:3B:5F:AC:52:EF"]:
    service.register_mac_address(mac)
```

---

## Step 4: Subscribe to Advertisement Signals

Once registered, listen for `Advertisement` signals from the router:

```python
def subscribe_to_advertisements(self):
    """Subscribe to Advertisement signals from the router"""
    
    # Subscribe to signals on ALL paths under our service
    self.bus.add_signal_receiver(
        self.advertisement_callback,           # Your callback function
        signal_name='Advertisement',            # Signal name
        dbus_interface='com.victronenergy.switch.bleadvertisements',  # Interface
        path_keyword='path'                     # Include path in callback
    )
    
    print("Subscribed to Advertisement signals")

def advertisement_callback(self, mac, manufacturer_id, data, rssi, interface, name, path=None):
    """
    Called when a matching BLE advertisement is received
    
    Args:
        mac: MAC address (string, e.g., "F0:9D:2E:E9:A9:11")
        manufacturer_id: Manufacturer ID (uint16, e.g., 737 for Victron)
        data: Advertisement data (dbus.Array of bytes)
        rssi: Signal strength (int16, typically negative)
        interface: Bluetooth adapter (string, e.g., "hci0")
        name: Device name if available (string, may be empty)
        path: D-Bus path the signal was emitted on (string, e.g., "/ble_advertisements/my_service/mfgr/737")
    """
    # Convert dbus.Array to bytes
    data_bytes = bytes(data)
    
    print(f"Advertisement received:")
    print(f"  MAC: {mac}")
    print(f"  Manufacturer ID: 0x{manufacturer_id:04X}")
    print(f"  Data: {data_bytes.hex()}")
    print(f"  RSSI: {rssi} dBm")
    print(f"  Interface: {interface}")
    print(f"  Name: {name}")
    print(f"  Path: {path}")
    
    # Process the advertisement data here
    # ...

# Example: Set up subscription
service = MyBLEService()
service.register_manufacturer_id(0x02E1)
service.subscribe_to_advertisements()
```

**Signal Signature:** `sqaynss`
- `s`: string (MAC address)
- `q`: uint16 (manufacturer ID)
- `ay`: array of bytes (data)
- `n`: int16 (RSSI)
- `s`: string (interface)
- `s`: string (name)

---

## Step 5: Process Advertisements

Now implement your business logic to process the advertisement data:

```python
def advertisement_callback(self, mac, manufacturer_id, data, rssi, interface, name, path=None):
    """Process received advertisement"""
    data_bytes = bytes(data)
    
    # Example: Parse Victron Instant Readout advertisement
    if manufacturer_id == 0x02E1 and len(data_bytes) >= 1:
        record_type = data_bytes[0]
        
        if record_type == 0x10:  # Instant readout
            # Parse the data according to Victron protocol
            # (This is just an example - actual parsing depends on your device)
            print(f"Victron device {name} ({mac}): Instant readout data")
            
            # Update your D-Bus service, database, etc.
            self.update_device(mac, data_bytes)
    
    # Example: Parse SeeLevel tank sensor
    elif manufacturer_id == 0x0131 and len(data_bytes) >= 14:
        # Parse SeeLevel BTP3 protocol
        sensor_num = data_bytes[3]
        reading = data_bytes[4:7].decode('ascii', errors='ignore').strip()
        print(f"SeeLevel sensor {sensor_num}: {reading}%")
```

---

## Complete Example

Here's a complete working example that monitors Victron devices:

```python
#!/usr/bin/env python3
"""
Example service using dbus-ble-advertisements router
Monitors Victron Orion-TR Smart DC-DC converters
"""

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VICTRON_MANUFACTURER_ID = 0x02E1

class VictronMonitor:
    def __init__(self):
        # Initialize D-Bus
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.service_name = "victron_monitor"
        self.registration_objects = []
        self.devices = {}  # Track discovered devices
        
    def check_router(self):
        """Verify router is available"""
        try:
            proxy = self.bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
            dbus_iface = dbus.Interface(proxy, 'org.freedesktop.DBus')
            
            if 'com.victronenergy.switch.bleadvertisements' not in dbus_iface.ListNames():
                return False
            
            service = self.bus.get_object('com.victronenergy.switch.bleadvertisements', '/ble_advertisements')
            iface = dbus.Interface(service, 'com.victronenergy.switch.bleadvertisements')
            version = iface.GetVersion()
            logger.info(f"Found dbus-ble-advertisements version {version}")
            return True
            
        except Exception as e:
            logger.error(f"Router check failed: {e}")
            return False
    
    def register_interest(self):
        """Register interest in Victron advertisements"""
        # Register for Victron manufacturer ID
        path = f"/ble_advertisements/{self.service_name}/mfgr/{VICTRON_MANUFACTURER_ID}"
        obj = dbus.service.Object(self.bus, path)
        self.registration_objects.append(obj)
        logger.info(f"Registered for Victron devices at {path}")
    
    def subscribe(self):
        """Subscribe to advertisement signals"""
        self.bus.add_signal_receiver(
            self.on_advertisement,
            signal_name='Advertisement',
            dbus_interface='com.victronenergy.switch.bleadvertisements',
            path_keyword='path'
        )
        logger.info("Subscribed to Advertisement signals")
    
    def on_advertisement(self, mac, manufacturer_id, data, rssi, interface, name, path=None):
        """Handle received advertisement"""
        data_bytes = bytes(data)
        
        # Track device
        if mac not in self.devices:
            self.devices[mac] = {'name': name, 'count': 0}
            logger.info(f"Discovered new device: {name} ({mac})")
        
        self.devices[mac]['count'] += 1
        
        # Log every 10th advertisement to avoid spam
        if self.devices[mac]['count'] % 10 == 0:
            logger.info(f"{name} ({mac}): "
                       f"mfg=0x{manufacturer_id:04X} "
                       f"len={len(data_bytes)} "
                       f"rssi={rssi} "
                       f"if={interface}")
    
    def run(self):
        """Main run loop"""
        if not self.check_router():
            logger.error("dbus-ble-advertisements not available!")
            logger.error("Install from: https://github.com/TechBlueprints/dbus-ble-advertisements")
            return 1
        
        self.register_interest()
        self.subscribe()
        
        logger.info("Service running, press Ctrl+C to exit...")
        
        # Run GLib main loop
        mainloop = GLib.MainLoop()
        try:
            mainloop.run()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        
        return 0

if __name__ == '__main__':
    monitor = VictronMonitor()
    sys.exit(monitor.run())
```

**To run this example:**
```bash
chmod +x victron_monitor.py
python3 victron_monitor.py
```

---

## Best Practices

### 1. Service Names
- Use underscores in service names for D-Bus paths: `my_service`, not `my-service`
- Keep names short but descriptive
- Use lowercase

### 2. Registration
- Register interests during service initialization
- Keep `registration_objects` list to prevent garbage collection
- Register for specific MACs when you know them (more efficient)
- Use manufacturer ID when you want all devices from a vendor

### 3. Signal Handling
- Always convert `dbus.Array` to `bytes`: `data_bytes = bytes(data)`
- Check data length before parsing: `if len(data_bytes) >= 14:`
- Handle empty device names: `name or "Unknown"`
- Process signals quickly (offload heavy work to separate thread/process)

### 4. Error Handling
```python
def on_advertisement(self, mac, manufacturer_id, data, rssi, interface, name, path=None):
    try:
        data_bytes = bytes(data)
        # Your processing here
    except Exception as e:
        logger.error(f"Error processing advertisement from {mac}: {e}")
```

### 5. Deduplication Awareness
The router only emits signals when:
- Advertisement data changes, OR
- 10 minutes have elapsed since last emission (heartbeat)

Don't implement your own deduplication - the router does it for you!

### 6. Testing
Always check router availability before starting:
```python
if not self.check_router():
    logger.error("Router not available!")
    sys.exit(1)
```

---

## Troubleshooting

### Router Not Found
**Problem:** `dbus-ble-advertisements service not found on D-Bus`

**Solutions:**
1. Check if router is installed: `ls -la /data/apps/dbus-ble-advertisements/`
2. Check if router is running: `svstat /service/dbus-ble-advertisements`
3. Check router logs: `tail -f /var/log/dbus-ble-advertisements/current`
4. Restart router: `svc -t /service/dbus-ble-advertisements`

### GetVersion Fails
**Problem:** `Method "GetVersion" ... doesn't exist`

**Solutions:**
1. Check you're using correct path: `/ble_advertisements` (not `/`)
2. Check correct interface: `com.victronenergy.switch.bleadvertisements`
3. Update router to latest version

### No Advertisements Received
**Problem:** Signal callback never called

**Solutions:**
1. Verify registration paths are correct
2. Check D-Bus object isn't garbage collected (keep reference in list)
3. Verify GLib main loop is running: `mainloop.run()`
4. Check router is receiving advertisements: `tail -f /var/log/dbus-ble-advertisements/current`
5. Verify your device is actually advertising (check with `btmon` directly)

### Wrong Data Format
**Problem:** `data` parameter has unexpected format

**Solution:** Always convert to bytes:
```python
data_bytes = bytes(data)  # Convert dbus.Array to bytes
```

### Registration Path Errors
**Problem:** D-Bus path creation fails

**Solutions:**
1. Use underscores in service name: `my_service` not `my-service`
2. Use uppercase and underscores in MACs: `FF_00_AA_BB_CC_DD`
3. Format manufacturer IDs as integers: `0x02E1` → `737`

---

## Additional Resources

- **Router Source Code:** https://github.com/TechBlueprints/dbus-ble-advertisements
- **Example Implementation (Orion-TR):** https://github.com/TechBlueprints/dbus-victron-orion-tr
- **Example Implementation (SeeLevel):** https://github.com/TechBlueprints/victron-seelevel-python
- **D-Bus Python Tutorial:** https://dbus.freedesktop.org/doc/dbus-python/
- **BLE Advertising Basics:** https://www.bluetooth.com/specifications/specs/core-specification/

---

## Summary

1. ✅ Check router is available with `GetVersion()`
2. ✅ Register interests by creating D-Bus objects at specific paths
3. ✅ Subscribe to `Advertisement` signals
4. ✅ Process advertisements in your callback
5. ✅ Run GLib main loop

That's it! The router handles all the complex BLE scanning, filtering, and deduplication for you.

