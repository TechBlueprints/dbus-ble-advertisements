# BLE Advertisement Router Integration

## Overview
We've implemented a pluggable BLE scanner interface that allows both `dbus-victron-orion-tr` and `victron-seelevel-python` services to use the `dbus-ble-advertisements` router service as their primary BLE scanning method, with automatic fallback to Bleak when the router is unavailable.

## Changes Made

### 1. dbus-ble-advertisements Service (main branch)
- Added `RootObject` at `/ble-advertisements` for service presence
  - `GetVersion()`: Returns "1.0.0"
  - `GetStatus()`: Returns "running" or "stale" based on heartbeat
  - `GetHeartbeat()`: Returns last heartbeat timestamp
- Heartbeat updates every 10 minutes
- Status check: healthy if heartbeat < 30 minutes old

### 2. Pluggable BLE Scanner Interface (`ble_scanner.py`)
Created in both projects with three scanner implementations:

#### Base Class: `BLEScanner`
- Abstract interface for all scanner backends
- Standardized callback: `(mac, manufacturer_id, data, rssi, interface, name)`

#### Implementation: `BleakBLEScanner`
- Direct BLE scanning using Bleak library
- Filters by single manufacturer ID
- Captures device name from Bleak's `device.name`
- Adapts Bleak's callback format to our standard

#### Implementation: `DBusAdvertisementScanner`
- Uses `dbus-ble-advertisements` router service
- Checks service health with `GetStatus()`
- Registers interest by creating D-Bus objects at:
  - `/ble-advertisements/{service_name}/mfgr/{id}` for manufacturer IDs
  - `/ble-advertisements/{service_name}/addr/{mac}` for specific MACs
- Listens for `Advertisement` signals on registered paths
- Supports multiple manufacturer IDs

#### Factory: `create_scanner()`
- Automatically selects best available scanner
- Arguments:
  - `advertisement_callback`: User's callback function
  - `service_name`: For D-Bus registration (e.g., "orion-tr")
  - `manufacturer_id`: Single manufacturer ID (deprecated)
  - `manufacturer_ids`: List of manufacturer IDs (preferred)
  - `mac_addresses`: List of MACs to monitor
  - `prefer_dbus`: If True, try D-Bus scanner first (default)
- Tries scanners in order until one is available
- Raises `RuntimeError` if no scanner available

### 3. dbus-victron-orion-tr (ble-advertisements branch)
Changes to `dbus-victron-orion-tr.py`:
- Removed direct Bleak imports
- Added `from ble_scanner import create_scanner, BLEScanner`
- Updated `OrionTRScanner.advertisement_callback()`:
  - New signature: `(mac, manufacturer_id, data, rssi, interface)`
  - Simplified filtering (scanner already filters for Victron ID)
- Updated `scan_continuously()`:
  - Uses `create_scanner()` factory
  - Passes `service_name="orion-tr"`
  - Passes `manufacturer_id=VICTRON_MANUFACTURER_ID` (0x02E1)
  - Passes `mac_addresses=list(self.devices.keys())`
  - Prefers D-Bus scanner

### 4. victron-seelevel-python (ble-advertisements branch)
Changes to `data/dbus-seelevel-service.py`:
- Added `import asyncio`
- Added `from ble_scanner import create_scanner, BLEScanner`
- Removed `btmon_proc` and btmon parsing state
- Added `ble_scanner` attribute
- New `advertisement_callback()`:
  - Signature: `(mac, manufacturer_id, data, rssi, interface)`
  - Filters for both Cypress (305) and SeeLevel (3264)
  - Determines sensor_type_id from manufacturer_id
  - Calls `process_seelevel_data()` directly
- Kept `parse_btmon_line()` for potential future fallback
- New `scan_continuously()` method:
  - Async method using `create_scanner()`
  - Passes `service_name="seelevel"`
  - Passes `manufacturer_ids=[MFG_ID_CYPRESS, MFG_ID_SEELEVEL]`
  - Gets MAC addresses from configured sensors
- Updated `run()` method:
  - Sets up async event loop integrated with GLib
  - Schedules BLE scanner as background task
  - Processes async tasks every 100ms
- Updated `cleanup()`:
  - Removes btmon cleanup
  - Sets `ble_scanner = None`

## Architecture

```
┌─────────────────────────────────┐
│  dbus-ble-advertisements        │
│  (Router Service)               │
│  - Runs btmon                   │
│  - Scans for registrations      │
│  - Emits signals per-app        │
└───────────┬─────────────────────┘
            │ D-Bus
            ├──────────────┬───────────────┐
            │              │               │
┌───────────▼─────────┐ ┌─▼──────────────┐│
│  orion-tr           │ │  seelevel      ││
│  - Registers mfg    │ │  - Registers   ││
│    0x02E1           │ │    mfg 305,    ││
│  - Registers MACs   │ │    3264        ││
│  - Listens for      │ │  - Registers   ││
│    Advertisement    │ │    MACs        ││
│    signals          │ │  - Listens for ││
│                     │ │    signals     ││
└─────────────────────┘ └────────────────┘│
                                          │
        (Fallback to Bleak if router     │
         is unavailable)                 │
                                          │
┌─────────────────────────────────────────▼──┐
│  Bleak                                     │
│  - Direct BLE scanning via BlueZ D-Bus    │
│  - One process per adapter limit          │
└────────────────────────────────────────────┘
```

## Benefits

1. **Single BLE Scanner**: Only `dbus-ble-advertisements` needs to run btmon, reducing system load
2. **Coexistence**: Multiple services can monitor BLE simultaneously without conflicts
3. **Automatic Failover**: Services fall back to Bleak if router unavailable
4. **Centralized Filtering**: Router handles filtering, clients just register interests
5. **Per-Application Signals**: Each service gets its own signal paths, no cross-talk
6. **Health Monitoring**: Router provides `GetStatus()` for monitoring
7. **Event-Driven**: Router detects service registration/deregistration immediately via `NameOwnerChanged`
8. **Deduplication**: Router only emits signals when data changes or after heartbeat interval
9. **Device Names**: Router captures and broadcasts BLE device names when available

## Testing Required

Once the Cerbo is back online:

1. **Test dbus-ble-advertisements router**:
   - Start service
   - Verify `/ble-advertisements` object exists
   - Check `GetStatus()` returns "running"
   - Check `GetHeartbeat()` updates

2. **Test orion-tr integration**:
   - Copy updated code to Cerbo
   - Start service
   - Verify it detects router and uses D-Bus scanner
   - Verify D-Bus registrations appear
   - Verify advertisements are received
   - Test fallback: stop router, verify orion-tr switches to Bleak

3. **Test seelevel integration**:
   - Copy updated code to Cerbo
   - Start service
   - Verify it detects router and uses D-Bus scanner
   - Verify D-Bus registrations for both manufacturer IDs
   - Verify advertisements are received
   - Test fallback: stop router, check error handling

## Files Modified

### dbus-ble-advertisements (main)
- `dbus-ble-advertisements.py`: Added RootObject and heartbeat

### dbus-victron-orion-tr (ble-advertisements branch)
- `ble_scanner.py`: New file - pluggable scanner interface
- `dbus-victron-orion-tr.py`: Updated to use pluggable scanner

### victron-seelevel-python (ble-advertisements branch)
- `data/ble_scanner.py`: New file - pluggable scanner interface
- `data/dbus-seelevel-service.py`: Updated to use pluggable scanner

