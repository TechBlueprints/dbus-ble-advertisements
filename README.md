# dbus-ble-advertisements

BLE Advertisement Router for Venus OS

Monitors BLE advertisements via `btmon` and distributes them via D-Bus signals to multiple consumers.

## Overview

This service provides a centralized BLE advertisement router that:
- Monitors BLE advertisements using `btmon` (Bluetooth monitor)
- Filters based on manufacturer IDs and MAC addresses registered via D-Bus
- Only broadcasts updates when data changes (or every 10 minutes as heartbeat)
- Emits D-Bus signals for matching advertisements
- Allows multiple services to consume BLE data without scanner conflicts

**Registration**: Clients register filters by creating D-Bus objects at:
- `/ble-advertisements/{service_name}/mfgr/{id}` - for manufacturer ID filtering
- `/ble-advertisements/{service_name}/addr/{mac}` - for MAC address filtering

**Signals**: The router emits `Advertisement` signals on those same exact paths (per-application).

**Multi-client support**: Multiple services can independently register for the same manufacturer/MAC. Each gets its own signal path.

**Note**: This service only handles BLE advertisements (broadcast data).
It does not support GATT connections or two-way communication.

## Architecture

```
btmon → dbus-ble-advertisements → D-Bus Signals
                                  ├─> orion-tr
                                  ├─> seelevel
                                  └─> other services
```

## Why This Approach?

Multiple BLE scanners (using `bleak` or similar libraries) cannot coexist on Venus OS - BlueZ only allows one active scanner at a time. By using `btmon` to passively monitor HCI traffic, this router service allows unlimited consumers to receive BLE advertisements without conflicts.

## Installation

```bash
# Create directory on Cerbo
ssh root@cerbo 'mkdir -p /data/apps/dbus-ble-advertisements'

# Copy files to Cerbo
scp -r dbus-ble-advertisements.py service root@cerbo:/data/apps/dbus-ble-advertisements/

# Make scripts executable
ssh root@cerbo 'chmod +x /data/apps/dbus-ble-advertisements/dbus-ble-advertisements.py /data/apps/dbus-ble-advertisements/service/run /data/apps/dbus-ble-advertisements/service/log/run'

# Link service (will auto-start)
ssh root@cerbo 'ln -sf /data/apps/dbus-ble-advertisements/service /service/dbus-ble-advertisements'

# Verify running
ssh root@cerbo 'svstat /service/dbus-ble-advertisements'
```

## D-Bus Interface

### Service Names

The router registers two D-Bus service names:

1. **`com.victronenergy.switch.ble_router`** (Primary)
   - Main service for device registration and UI integration
   - **Use this for service availability checks**
   - Appears in Venus OS device list

2. **`com.victronenergy.ble`**
   - Used for UI device publishing (Bluetooth Sensors page)
   - Only exists if dbus-ble-sensors is running
   - Not reliable for availability checks

**⚠️ Important**: Always check for `com.victronenergy.switch.ble_router` when verifying the router is available.

### Paths
- **Main**: `/ble_advertisements`
- **Registration**: `/ble_advertisements/{service_name}/mfgr/{id}` or `/ble_advertisements/{service_name}/addr/{mac}`

### Signal
```
Advertisement(string mac, uint16 manufacturer_id, array of bytes data, int16 rssi, string interface, string name)
```

Emitted when a BLE advertisement matching configured filters is received.

**Parameters:**
- `mac`: MAC address (format: "AA:BB:CC:DD:EE:FF")
- `manufacturer_id`: BLE manufacturer ID (e.g., 0x02E1 for Victron)
- `data`: Raw advertisement data bytes
- `rssi`: Signal strength in dBm
- `interface`: HCI interface name (e.g., "hci0")
- `name`: Device name (empty string if unknown/not broadcast)

## Client Registration

Clients register their filter requirements by creating D-Bus objects at specific paths.

### Register for Manufacturer ID

To receive all advertisements from a specific manufacturer:

```python
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# Register for Victron Energy (0x02E1 = 737 decimal)
class VictronRegistration(dbus.service.Object):
    def __init__(self, bus):
        dbus.service.Object.__init__(
            self,
            dbus.service.BusName('com.victronenergy.orion-tr', bus),
            '/ble-advertisements/orion-tr/mfgr/737'
        )

registration = VictronRegistration(bus)
```

### Register for Specific MAC Address

To receive advertisements from a specific device only:

```python
# Register for specific MAC (remove colons from MAC in path)
class DeviceRegistration(dbus.service.Object):
    def __init__(self, bus):
        dbus.service.Object.__init__(
            self,
            dbus.service.BusName('com.victronenergy.orion-tr', bus),
            '/ble-advertisements/orion-tr/addr/EFC1119DA391'
        )

registration = DeviceRegistration(bus)
```

### Complete Example

```python
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

# Register for Victron devices
class VictronFilter(dbus.service.Object):
    def __init__(self, bus):
        bus_name = dbus.service.BusName('com.victronenergy.orion-tr', bus)
        dbus.service.Object.__init__(self, bus_name, '/ble-advertisements/orion-tr/mfgr/737')

# Create registration
filter_reg = VictronFilter(bus)

# Subscribe to advertisements on the SAME path as registration
def advertisement_callback(mac, mfg_id, data, rssi, interface, name):
    print(f"Received from {mac} ({name}): mfg={mfg_id:#06x} len={len(data)} rssi={rssi} if={interface}")
    # Process data...

bus.add_signal_receiver(
    advertisement_callback,
    signal_name='Advertisement',
    dbus_interface='com.victronenergy.ble.Advertisements',
    path='/ble-advertisements/orion-tr/mfgr/737'  # Same path as registration!
)

# Run main loop
mainloop = GLib.MainLoop()
mainloop.run()
```

### Registration Notes

- **Path format**: `/ble-advertisements/{your_service_name}/mfgr/{decimal_id}` or `/ble-advertisements/{your_service_name}/addr/{MAC_NO_COLONS}`
- **Signal path**: Signals are emitted on the same path as your registration (per-application, not shared)
- **Multiple registrations**: A service can create multiple registration objects for different manufacturers/MACs
- **Multi-client support**: Multiple services can register for the same manufacturer/MAC - each gets signals on their own path
- **Auto-discovery**: The router scans for registrations at startup and when services appear/disappear (event-driven)
- **No cleanup needed**: When your service exits, D-Bus automatically removes the objects and router cleans up emitters
- **Signal parameters**: `Advertisement(mac, manufacturer_id, data, rssi, interface)` - includes which HCI interface saw it
- **Deduplication**: Only data changes trigger signals (RSSI and interface changes alone don't trigger duplicates)

### Filter Logic

- If only manufacturer IDs registered: broadcasts all matching advertisements
- If both manufacturer ID and MAC registered: broadcasts only if BOTH match
- If only MACs registered: broadcasts only those specific devices

## Service Management

```bash
# Start
svc -u /service/dbus-ble-advertisements

# Stop
svc -d /service/dbus-ble-advertisements

# Restart
svc -t /service/dbus-ble-advertisements

# Status
svstat /service/dbus-ble-advertisements

# View logs
tail -f /var/log/dbus-ble-advertisements/current
```

## License

Apache License 2.0 - See LICENSE file

Copyright 2025 Clint Goudie-Nice
