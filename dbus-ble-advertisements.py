#!/usr/bin/env python3
# Copyright 2025 Clint Goudie-Nice
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
BLE Advertisement Router for Venus OS

Monitors BLE advertisements via btmon and broadcasts them via D-Bus signals.
Only emits updates when data changes or 10 minutes have elapsed.
Filters based on manufacturer IDs, product IDs, and MAC addresses registered via D-Bus.

Clients register by creating D-Bus objects at:
  /ble_advertisements/{service_name}/mfgr/{id}                      - all devices from manufacturer
  /ble_advertisements/{service_name}/mfgr/{id}/pid/{product_id}     - specific product ID
  /ble_advertisements/{service_name}/mfgr/{id}/pid_range/{min}_{max} - range of product IDs
  /ble_advertisements/{service_name}/addr/{mac}                     - specific MAC address

The router emits Advertisement signals on those same paths (per-application).
Each service gets its own signal path matching its registration.
"""

import re
import subprocess
import sys
import time
import logging
import signal
import os
from typing import Dict, Set, Tuple, Optional

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

HEARTBEAT_INTERVAL = 600  # 10 minutes
REGISTRATION_SCAN_INTERVAL = 30  # Scan for new registrations every 30 seconds
# Device enabled states are stored in D-Bus settings at:
# /Settings/Devices/bleadvertisements/Device_{mac_sanitized}/Enabled


class AdvertisementEmitter(dbus.service.Object):
    """D-Bus object that emits signals for a specific manufacturer or MAC"""
    
    @dbus.service.signal(dbus_interface='com.victronenergy.switch.bleadvertisements',
                         signature='sqaynss')
    def Advertisement(self, mac, manufacturer_id, data, rssi, interface, name):
        """Signal emitted when a matching BLE advertisement is received
        
        Args:
            mac: MAC address (string)
            manufacturer_id: Manufacturer ID (uint16)
            data: Advertisement data (byte array)
            rssi: Signal strength (int16)
            interface: HCI interface (string)
            name: Device name (string, empty if unknown)
        """
        pass


class RootObject(dbus.service.Object):
    """Root D-Bus object to provide service presence and introspection"""
    
    def __init__(self, bus_name):
        dbus.service.Object.__init__(self, bus_name, '/ble_advertisements')
        self.heartbeat = time.time()
    
    @dbus.service.method(dbus_interface='com.victronenergy.switch.bleadvertisements',
                         in_signature='', out_signature='s')
    def GetVersion(self):
        """Return service version"""
        return "1.0.0"
    
    @dbus.service.method(dbus_interface='com.victronenergy.switch.bleadvertisements',
                         in_signature='', out_signature='s')
    def GetStatus(self):
        """Return service status based on heartbeat"""
        time_since_heartbeat = time.time() - self.heartbeat
        if time_since_heartbeat < 1800:  # 30 minutes
            return "running"
        else:
            return "stale"
    
    @dbus.service.method(dbus_interface='com.victronenergy.switch.bleadvertisements',
                         in_signature='', out_signature='d')
    def GetHeartbeat(self):
        """Return last heartbeat timestamp"""
        return self.heartbeat
    
    def update_heartbeat(self):
        """Update heartbeat timestamp"""
        self.heartbeat = time.time()


class SettingsObject(dbus.service.Object):
    """D-Bus object for UI settings - implements VeDbusItem pattern"""
    
    def __init__(self, bus_name, path, initial_value=0):
        dbus.service.Object.__init__(self, bus_name, path)
        self._value = initial_value
        self._path = path
        logging.info(f"SettingsObject created at {path} with initial value: {initial_value}")
    
    @dbus.service.method(dbus_interface='com.victronenergy.BusItem',
                         in_signature='', out_signature='v')
    def GetValue(self):
        """Return current value"""
        logging.info(f"GetValue called on {self._path}, returning: {self._value}")
        return self._value
    
    @dbus.service.method(dbus_interface='com.victronenergy.BusItem',
                         in_signature='v', out_signature='i')
    def SetValue(self, value):
        """Set value - returns 0 on success"""
        old_value = self._value
        self._value = int(value)
        logging.info(f"SetValue called on {self._path}, changed from {old_value} to {self._value}")
        self.PropertiesChanged({'Value': self._value})
        return 0
    
    @dbus.service.method(dbus_interface='com.victronenergy.BusItem',
                         in_signature='', out_signature='s')
    def GetText(self):
        """Return text representation"""
        logging.info(f"GetText called on {self._path}, returning: {str(self._value)}")
        return str(self._value)
    
    @dbus.service.signal(dbus_interface='com.victronenergy.BusItem',
                         signature='a{sv}')
    def PropertiesChanged(self, changes):
        """Signal emitted when value changes"""
        pass


class UIDevice(dbus.service.Object):
    """
    D-Bus object representing a device in the UI
    
    Published on com.victronenergy.ble service so it appears in the
    Bluetooth Sensors UI alongside Mopeka/Ruuvi devices.
    """
    
    def __init__(self, bus, device_id: str, device_name: str, enabled: bool = False):
        """
        Create a UI device entry
        
        Args:
            bus: D-Bus connection
            device_id: Unique device identifier (e.g., 'ble_integrations_master' or 'integration_oriontr_02e1')
            device_name: Display name for the device
            enabled: Initial enabled state
        """
        self.device_id = device_id
        self.device_name = device_name
        self._enabled = enabled
        
        # We need to get the bus name for com.victronenergy.ble
        # Note: This might fail if dbus-ble-sensors isn't running
        try:
            # We don't own this bus name, we just publish objects on it
            # The bus name is owned by dbus-ble-sensors
            proxy = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
            dbus_iface = dbus.Interface(proxy, 'org.freedesktop.DBus')
            
            if 'com.victronenergy.ble' not in dbus_iface.ListNames():
                logging.error("com.victronenergy.ble service not found - cannot publish UI devices")
                raise RuntimeError("com.victronenergy.ble service not available")
            
            # Create object paths for Name and Enabled
            name_path = f"/Devices/{device_id}/Name"
            enabled_path = f"/Devices/{device_id}/Enabled"
            
            # Initialize D-Bus objects
            # Note: We can't use BusName here since we don't own the name
            # We'll use the bus directly and create objects that others can see
            dbus.service.Object.__init__(self, bus, name_path)
            
            logging.info(f"Created UI device: {device_name} at /Devices/{device_id}")
            
        except Exception as e:
            logging.error(f"Failed to create UI device {device_id}: {e}")
            raise


class BLEAdvertisementRouter:
    """
    BLE Advertisement Router Service
    
    Monitors BLE advertisements and broadcasts them via D-Bus signals.
    Clients register by creating objects at /ble_advertisements/{service}/mfgr/{id} or /ble_advertisements/{service}/addr/{mac}
    Signals are emitted on those same exact paths (per-application, not shared).
    """
    
    def __init__(self, bus):
        self.bus = bus
        
        # Migrate settings from old service name if needed
        self._migrate_settings()
        
        # Create a BusName for the emitters to use (with .switch prefix for GUI recognition)
        self.bus_name = dbus.service.BusName('com.victronenergy.switch.bleadvertisements', bus)
        
        # Create root object to provide GetVersion, GetStatus, GetHeartbeat methods
        self.root_obj = RootObject(self.bus_name)
        
        # Import VeDbusService for creating a proper Venus OS device
        sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext', 'velib_python'))
        from vedbus import VeDbusService
        from settingsdevice import SettingsDevice
        
        # Create as a device with switchable outputs so it appears in the device list
        self.dbusservice = VeDbusService('com.victronenergy.switch.bleadvertisements', bus, register=False)
        
        # Add mandatory paths for Venus OS device
        self.dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self.dbusservice.add_path('/Mgmt/ProcessVersion', '1.0.0')
        self.dbusservice.add_path('/Mgmt/Connection', 'BLE Advertisements')
        self.dbusservice.add_path('/DeviceInstance', 110)
        self.dbusservice.add_path('/ProductId', 0xFFFF)
        self.dbusservice.add_path('/ProductName', 'BLE Advertisements')
        self.dbusservice.add_path('/CustomName', 'BLE Advertisements')
        self.dbusservice.add_path('/FirmwareVersion', '1.0.0')
        self.dbusservice.add_path('/HardwareVersion', None)
        self.dbusservice.add_path('/Connected', 1)
        self.dbusservice.add_path('/State', 0x100)  # Required for GUI device list visibility
        
        # Add switch-specific paths (required for switch devices)
        
        # Create a single switchable output for new device discovery toggle.
        # Use relay_discovery identifier for clarity. For this master toggle we
        # follow the same pattern as other simple switch devices (SeeLevel,
        # SmartShunt): Status stays 0 (OK) regardless of On/Off, only State
        # reflects the on/off value. Using Status=0x09 for an "active alarm"
        # style state is appropriate for threshold relays, but *not* for the
        # master discovery toggle, and it appears to confuse the GUI.
        output_path = '/SwitchableOutput/relay_discovery'
        self.dbusservice.add_path(f'{output_path}/Name', '* BLE Advertisements New Device Discovery')
        self.dbusservice.add_path(f'{output_path}/Type', 1)  # 1 = toggle (at output level for GUI rendering)
        self.dbusservice.add_path(f'{output_path}/State', 0, writeable=True,
                                   onchangecallback=self._on_discovery_changed)
        # Keep Status at 0 (OK) for the discovery switch, just like SeeLevel.
        # The GUI uses /State to determine the toggle position.
        self.dbusservice.add_path(f'{output_path}/Status', 0x00)
        self.dbusservice.add_path(f'{output_path}/Current', 0)  # Required for switches to appear in GUI
        
        # Add settings paths (under /Settings/)
        self.dbusservice.add_path(f'{output_path}/Settings/CustomName', '', writeable=True)
        self.dbusservice.add_path(f'{output_path}/Settings/Type', 1, writeable=True)  # 1 = toggle
        self.dbusservice.add_path(f'{output_path}/Settings/ValidTypes', 2)  # Bitmask: bit 1 set = toggle (0b10 = 2)
        self.dbusservice.add_path(f'{output_path}/Settings/Function', 2, writeable=True)  # 2 = Manual
        self.dbusservice.add_path(f'{output_path}/Settings/ValidFunctions', 4)  # Bitmask: bit 2 set = Manual (0b100 = 4)
        self.dbusservice.add_path(f'{output_path}/Settings/Group', '', writeable=True)
        self.dbusservice.add_path(f'{output_path}/Settings/ShowUIControl', 1, writeable=True)  # 1 = visible in switches pane by default
        self.dbusservice.add_path(f'{output_path}/Settings/PowerOnState', 1)  # 1 = restore previous state on boot
        
        # Runtime cache of discovered devices for fast lookup in hot path
        # Key: MAC without colons (e.g., "efc1119da391"), Value: bool (enabled for routing)
        self.discovered_devices: Dict[str, bool] = {}
        
        # Register device in settings (for GUI device list) - DO THIS BEFORE REGISTERING SERVICE
        settings = {
            "ClassAndVrmInstance": [
                "/Settings/Devices/bleadvertisements/ClassAndVrmInstance",
                "switch:110",
                0,
                0,
            ],
            "DiscoveryEnabled": [
                "/Settings/Devices/bleadvertisements/DiscoveryEnabled",
                1,  # Default: ON
                0,
                1,
            ],
        }
        self._settings = SettingsDevice(
            bus,
            settings,
            eventCallback=self._on_settings_changed,
            timeout=10
        )
        
        # Register the service EARLY with minimal paths (just discovery switch)
        # Then add discovered devices after registration
        self.dbusservice.register()
        
        logging.info("Registered BLE Advertisements on D-Bus")
        
        # Now restore discovery state from settings AFTER registering
        discovery_state = self._settings['DiscoveryEnabled']
        self.dbusservice['/SwitchableOutput/relay_discovery/State'] = discovery_state
        # Do not change Status here – leave it at 0 (OK) to match other
        # simple switch implementations. Only State reflects on/off.
        if discovery_state:
            logging.info("Discovery enabled from saved settings")
        
        # Note: Device switches are created dynamically as BLE advertisements arrive.
        # Enabled/disabled state per device is stored in D-Bus settings and loaded
        # when each device is first seen.
        
        logging.info("BLE Advertisements initialization complete")
        
        # TODO: Re-implement old service names as a migration path if needed
        # for advertisement signal routing to client services
        # For now, we're only implementing the UI control via the switch device
        
        # Filters: manufacturer IDs, product IDs, and MAC addresses we care about
        # Key: mfg_id or MAC, Value: set of full registration paths
        self.mfg_registrations: Dict[int, Set[str]] = {}  # mfg_id -> {'/ble_advertisements/orion_tr/mfgr/737', ...}
        self.mac_registrations: Dict[str, Set[str]] = {}  # MAC -> {'/ble_advertisements/orion_tr/addr/EFC...', ...}
        
        # Product ID filters (more specific than manufacturer-only)
        # Key: (mfg_id, product_id), Value: set of full registration paths
        self.pid_registrations: Dict[Tuple[int, int], Set[str]] = {}  # (mfg_id, pid) -> {paths}
        # Key: (mfg_id, min_pid, max_pid), Value: set of full registration paths
        self.pid_range_registrations: Dict[Tuple[int, int, int], Set[str]] = {}  # (mfg_id, min, max) -> {paths}
        
        # Signal emitters for each registered path
        # Key: full path (e.g., '/ble_advertisements/orion_tr/mfgr/737'), Value: AdvertisementEmitter
        self.emitters: Dict[str, AdvertisementEmitter] = {}
        
        # Tracking for deduplication
        # Key: (mac, mfg_id), Value: (data_bytes, timestamp)
        self.last_advertisement: Dict[Tuple[str, int], Tuple[bytes, float]] = {}
        
        # Device name tracking
        # Key: MAC address, Value: device name (or empty string if unknown)
        self.device_names: Dict[str, str] = {}
        
        # btmon parsing state
        self.current_mac = None
        self.current_name = None
        self.current_mfg_id = None
        self.current_rssi = None
        self.current_interface = None
        self.btmon_proc = None
        
        # Pending services for asynchronous registration scan
        self._pending_scan_services: list[str] = []
        
        # Do initial full scan for registrations AFTER main loop starts (non-blocking)
        # DISABLED: We don't need to scan! Just emit to paths when we get matching advertisements.
        # The registration paths are defined by the pattern: /ble_advertisements/{service}/mfgr/{id} or /ble_advertisements/{service}/addr/{mac}
        # We'll emit signals to ALL possible paths for a given advertisement and let D-Bus handle delivery.
        logging.info("Router ready - will emit signals to matching registration paths as advertisements arrive")
        
        # Subscribe to D-Bus NameOwnerChanged signals to detect when services appear/disappear
        self.bus.add_signal_receiver(
            self._on_name_owner_changed,
            signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus',
            path='/org/freedesktop/DBus'
        )
        
        # Update heartbeat every 10 minutes
        GLib.timeout_add_seconds(600, self._update_heartbeat)
    
    def _migrate_settings(self):
        """Migrate settings from old service name to new name"""
        old_paths = [
            "/Settings/Devices/ble_router/ClassAndVrmInstance",
            "/Settings/Devices/ble_router/DiscoveryEnabled",
            "/Settings/Devices/ble_advertisements/ClassAndVrmInstance",
            "/Settings/Devices/ble_advertisements/DiscoveryEnabled",
        ]
        new_paths = [
            "/Settings/Devices/bleadvertisements/ClassAndVrmInstance",
            "/Settings/Devices/bleadvertisements/DiscoveryEnabled",
            "/Settings/Devices/bleadvertisements/ClassAndVrmInstance",
            "/Settings/Devices/bleadvertisements/DiscoveryEnabled",
        ]
        
        for old_path, new_path in zip(old_paths, new_paths):
            try:
                # Check if old settings exist
                settings_obj = self.bus.get_object('com.victronenergy.settings', old_path)
                settings_iface = dbus.Interface(settings_obj, 'com.victronenergy.BusItem')
                old_value = settings_iface.GetValue()
                
                if old_value is not None:
                    logging.info(f"Migrating settings from {old_path} to {new_path}: {old_value}")
                    
                    # Set the new path with the old value
                    try:
                        new_obj = self.bus.get_object('com.victronenergy.settings', new_path)
                        new_iface = dbus.Interface(new_obj, 'com.victronenergy.BusItem')
                        new_iface.SetValue(old_value)
                        logging.info(f"Successfully migrated settings to {new_path}")
                    except Exception as e:
                        logging.info(f"New settings path doesn't exist yet (will be created): {e}")
                    
                    # Delete the old path
                    try:
                        settings_obj.Delete()
                        logging.info(f"Deleted old settings path: {old_path}")
                    except Exception as e:
                        logging.warning(f"Could not delete old settings path {old_path}: {e}")
                        
            except dbus.exceptions.DBusException:
                # Old settings don't exist - this is fine (fresh install or already migrated)
                logging.debug(f"No old settings to migrate from {old_path}")
            except Exception as e:
                logging.warning(f"Error during settings migration from {old_path}: {e}")
    
    def _on_relay_state_changed(self, path: str, value: int):
        """Callback when a discovered device relay state changes."""
        # Extract relay_id from path like "/SwitchableOutput/relay_efc1119da391/State"
        path_parts = path.split('/')
        if len(path_parts) < 3 or not path_parts[2].startswith('relay_'):
            return True
        
        relay_id = path_parts[2].replace('relay_', '')
        enabled = (value == 1)
        
        # If a switch is turned OFF while discovery is enabled, clear the cache
        # This allows the device to be re-discovered if it appears again
        if not enabled:
            discovery_enabled = self.dbusservice['/SwitchableOutput/relay_discovery/State'] == 1
            if discovery_enabled:
                self.discovered_devices.clear()
                logging.debug("Cleared device cache (switch disabled while discovery enabled)")
        
        # Status is always 0 (OK) - State indicates on/off
        self.dbusservice[f'/SwitchableOutput/relay_{relay_id}/Status'] = 0
        
        # Log the change
        name_path = f'/SwitchableOutput/relay_{relay_id}/Name'
        device_name = self.dbusservice[name_path] if name_path in self.dbusservice else relay_id
        logging.info(f"Device '{device_name}' routing: {'enabled' if enabled else 'disabled'}")
        return True
    
    def _on_settings_changed(self, setting, old_value, new_value):
        """Callback when a setting changes in com.victronenergy.settings"""
        logging.debug(f"Setting changed: {setting} = {new_value}")
        # Settings are already updated by SettingsDevice, no action needed
    
    def _on_discovery_changed(self, path, value):
        """Callback when new device discovery toggle (SwitchableOutput/relay_discovery/State) changes"""
        # Handle both string and integer values from D-Bus
        enabled = (int(value) == 1) if isinstance(value, (int, str)) else bool(value)
        logging.info(f"New device discovery changed to: {enabled}")
        
        # Clear the cache on any discovery toggle - it will repopulate naturally
        self.discovered_devices.clear()
        logging.debug("Cleared device cache (discovery toggled)")
        
        # Save to persistent settings
        self._settings['DiscoveryEnabled'] = value
        
        # Keep Status at 0 (OK) for the discovery switch; only State should
        # indicate whether discovery is enabled. Other devices may use 0x09
        # to indicate an "active" state, but using 0x09 here is not required
        # for GUI visibility and may in fact prevent the card from showing.
        
        # Iterate over actual D-Bus paths (source of truth), not the dictionary cache
        # Find all relay State paths
        relay_paths = [p for p in self.dbusservice._dbusobjects.keys() 
                       if p.startswith('/SwitchableOutput/relay_') and p.endswith('/State')
                       and 'relay_discovery' not in p]
        
        if enabled:
            # Discovery enabled: show all device toggles
            logging.info("Discovery enabled - showing all device switches")
            for state_path in relay_paths:
                relay_part = state_path.split('/')[2]  # e.g., "relay_efc1119da391"
                output_path = f'/SwitchableOutput/{relay_part}'
                show_path = f'{output_path}/Settings/ShowUIControl'
                name_path = f'{output_path}/Name'
                
                if show_path in self.dbusservice:
                    self.dbusservice[show_path] = 1
                    name = self.dbusservice[name_path] if name_path in self.dbusservice else relay_part
                    logging.info(f"Made {name} visible in switches pane")
        else:
            # Discovery disabled: remove disabled devices, hide enabled ones
            logging.info("Discovery disabled - removing disabled devices, hiding enabled ones")
            relays_to_remove = []
            
            for state_path in relay_paths:
                relay_part = state_path.split('/')[2]  # e.g., "relay_efc1119da391"
                relay_id = relay_part.replace('relay_', '')
                output_path = f'/SwitchableOutput/{relay_part}'
                name_path = f'{output_path}/Name'
                name = self.dbusservice[name_path] if name_path in self.dbusservice else relay_id
                
                # Get current state from D-Bus
                state = self.dbusservice[state_path]
                device_enabled = (state == 1)
                
                if not device_enabled:
                    # Device is disabled: mark for removal
                    relays_to_remove.append((relay_id, name))
                else:
                    # Device is enabled: just hide it
                    show_path = f'{output_path}/Settings/ShowUIControl'
                    if show_path in self.dbusservice:
                        self.dbusservice[show_path] = 0
                        logging.info(f"Hidden enabled device {name} from switches pane")
            
            # Remove disabled devices - delete their D-Bus paths directly
            for relay_id, name in relays_to_remove:
                logging.info(f"Removing disabled device {name}")
                self._delete_relay_paths(relay_id)
        
        return True  # Accept the change
    
    
    def _update_device_name_if_exists(self, mac: str, name: str):
        """Update the toggle name for a device if it's already been discovered.
        
        Only updates if discovery mode is enabled - no need to update names when not discovering.
        """
        # Skip if discovery is disabled - no need to update UI elements
        discovery_enabled = self.dbusservice['/SwitchableOutput/relay_discovery/State'] == 1
        if not discovery_enabled:
            return
        
        relay_id = mac.replace(':', '').lower()
        name_path = f'/SwitchableOutput/relay_{relay_id}/Name'
        
        # Only update if the switch exists on D-Bus
        if name_path in self.dbusservice:
            new_name = f"{name} ({mac})"
            self.dbusservice[name_path] = new_name
            logging.info(f"Updated device name: {new_name}")
    
    def _get_service_names_for_mac(self, mac: str) -> list:
        """Get list of service names that are registered for this MAC address"""
        services = set()
        if mac in self.mac_registrations:
            for path in self.mac_registrations[mac]:
                # Path format: /ble_advertisements/{service_name}/addr/{mac}
                parts = path.split('/')
                if len(parts) >= 3:
                    service_name = parts[2]  # Extract service name
                    services.add(service_name)
        return sorted(list(services))
    
    def _add_discovered_device(self, mac: str, name: str):
        """
        Create a new switchable output for a discovered device.
        
        Only called if:
        1. A client service has registered interest in this device
        2. Discovery is enabled
        3. Device doesn't already have a switch
        
        New devices are enabled by default.
        
        Uses context manager to emit ItemsChanged signal so GUI picks up new switches.
        """
        # MAC without colons as relay identifier
        relay_id = mac.replace(':', '').lower()  # e.g., "efc1119da391"
        output_path = f'/SwitchableOutput/relay_{relay_id}'
        
        # Only add if discovery is enabled and device doesn't already exist
        discovery_enabled = self.dbusservice['/SwitchableOutput/relay_discovery/State']
        if discovery_enabled == 0:
            return
        
        # Check cache first (fast), then D-Bus (authoritative)
        if relay_id in self.discovered_devices:
            return
        if f'{output_path}/State' in self.dbusservice:
            # Switch exists on D-Bus but not in cache - add to cache
            state = self.dbusservice[f'{output_path}/State']
            self.discovered_devices[relay_id] = (state == 1)
            return
        
        # Create new D-Bus paths for this device - enabled by default
        # Use context manager to emit ItemsChanged signal when done
        with self.dbusservice as ctx:
            ctx.add_path(f'{output_path}/Name', name)
            ctx.add_path(f'{output_path}/Type', 1)  # 1 = toggle
            ctx.add_path(f'{output_path}/State', 1, writeable=True,
                         onchangecallback=self._on_relay_state_changed)
            ctx.add_path(f'{output_path}/Status', 0)  # 0 = OK
            ctx.add_path(f'{output_path}/Current', 0)
            ctx.add_path(f'{output_path}/Settings/CustomName', '', writeable=True)
            ctx.add_path(f'{output_path}/Settings/Type', 1, writeable=True)
            ctx.add_path(f'{output_path}/Settings/ValidTypes', 2)
            ctx.add_path(f'{output_path}/Settings/Function', 2, writeable=True)
            ctx.add_path(f'{output_path}/Settings/ValidFunctions', 4)
            ctx.add_path(f'{output_path}/Settings/Group', '', writeable=True)
            ctx.add_path(f'{output_path}/Settings/ShowUIControl', 1, writeable=True)
            ctx.add_path(f'{output_path}/Settings/PowerOnState', 1)
        
        # Track in runtime cache (enabled by default)
        # Safety valve: clear cache if it grows too large
        if len(self.discovered_devices) > 1000:
            self.discovered_devices.clear()
            logging.warning("Cleared device cache (exceeded 1000 entries)")
        self.discovered_devices[relay_id] = True
        
        logging.info(f"Created switch for: {name} at {output_path}")
    
    def _delete_relay_paths(self, relay_id: str):
        """Delete all D-Bus paths for a relay switch.
        
        Uses context manager to emit ItemsChanged signal so GUI updates.
        
        Args:
            relay_id: MAC without colons (e.g., "efc1119da391")
        """
        output_path = f'/SwitchableOutput/relay_{relay_id}'
        
        # Use context manager to emit ItemsChanged signal when done
        with self.dbusservice as ctx:
            ctx.del_tree(output_path)
    
    def _on_device_state_changed(self, device_id: str, path: str, value: int):
        """DEPRECATED - now using _on_relay_state_changed"""
        # This method is kept for backwards compatibility but should not be called
        logging.warning("_on_device_state_changed called but is deprecated")
        return True
    
    # _scan_existing_services was used in an earlier synchronous bootstrap
    # implementation. It has been superseded by _schedule_initial_scan /
    # _scan_next_service, which perform the same work incrementally via
    # GLib.idle_add to avoid blocking the D-Bus mainloop. The old
    # implementation is removed to prevent accidental reintroduction of
    # blocking behavior.

    def _schedule_initial_scan(self):
        """Schedule a non-blocking initial registration scan.
        
        Instead of scanning all services synchronously (which can block the
        D-Bus mainloop and cause GUI timeouts), we collect the list of
        candidate services once and then process them incrementally via
        GLib.idle_add.
        """
        try:
            bus_obj = self.bus.get_object('org.freedesktop.DBus', '/')
            bus_iface = dbus.Interface(bus_obj, 'org.freedesktop.DBus')
            service_names = bus_iface.ListNames()
            
            # Only scan services that could have BLE advertisement registrations
            # Known client services that register for BLE advertisements:
            # - com.victronenergy.switch.seelevel (SeeLevel tanks)
            # - com.victronenergy.orion_tr (Orion TR DC-DC)
            # Skip all others to avoid blocking introspection timeouts
            likely_clients = [
                'com.victronenergy.switch.seelevel',
                'com.victronenergy.orion_tr',
            ]
            self._pending_scan_services = [
                s for s in service_names
                if isinstance(s, str)
                and s in likely_clients
            ]
            logging.info(
                f"Queued {len(self._pending_scan_services)} services for async registration scan"
            )
            
            if self._pending_scan_services:
                # Use timeout_add with 100ms delay instead of idle_add
                # to ensure the scan runs even if btmon output is consuming idle cycles
                GLib.timeout_add(100, self._scan_next_service)
        except Exception as e:
            logging.error(f"Error scheduling initial scan: {e}", exc_info=True)

    def _scan_next_service(self):
        """Idle callback to process the next queued service for registrations.
        
        Schedules itself again if there's more work to do.
        """
        if not self._pending_scan_services:
            logging.info(
                f"Async registration scan complete - mfgr={len(self.mfg_registrations)}, "
                f"mac={len(self.mac_registrations)}, pid={len(self.pid_registrations)}, "
                f"pid_range={len(self.pid_range_registrations)}"
            )
            return False  # Don't reschedule
        
        service_name = self._pending_scan_services.pop(0)
        logging.info(
            f"Async scan: checking {service_name} ({len(self._pending_scan_services)} remaining)"
        )
        # Use a short timeout to further reduce risk of blocking the mainloop.
        try:
            self._check_service_registrations(service_name, timeout=1.0)
        except Exception as e:
            logging.debug("Async scan: error checking %s: %s", service_name, e)
        
        # Schedule the next service scan via timeout_add (100ms delay)
        if self._pending_scan_services:
            GLib.timeout_add(100, self._scan_next_service)
        else:
            logging.info(
                f"Async registration scan complete - mfgr={len(self.mfg_registrations)}, "
                f"mac={len(self.mac_registrations)}, pid={len(self.pid_registrations)}, "
                f"pid_range={len(self.pid_range_registrations)}"
            )
        
        return False  # Don't reschedule automatically
    
    def _update_heartbeat(self):
        """Periodic callback to update heartbeat timestamp"""
        # TODO: Re-implement heartbeat for advertisement service monitoring
        logging.debug("Heartbeat updated")
        return True  # Keep the timer running
    
    def _on_name_owner_changed(self, name, old_owner, new_owner):
        """
        D-Bus signal handler for service appearing/disappearing.
        When a service appears, check if it has registration paths.
        When it disappears, remove its registrations.
        """
        # Skip unique names (starting with :)
        if name.startswith(':'):
            return
        
        # Service appeared - check for registrations (non-blocking single service check)
        if new_owner and not old_owner:
            self._check_service_registrations(name)
        
        # Service disappeared - remove any cached emitters and registrations
        elif old_owner and not new_owner:
            self._remove_service_registrations(name)
    
    def _check_service_registrations(self, service_name, timeout: float = 2.0):
        """Check a single service for BLE registration paths.
        
        timeout: maximum time (seconds) to wait for D-Bus introspection. Kept
        reasonably small when called from asynchronous scans to avoid blocking
        the mainloop for too long.
        """
        try:
            # Only check if this looks like a client service (not system services)
            if not service_name.startswith('com.victronenergy.'):
                return
            
            logging.debug(f"  Introspecting {service_name}...")
            obj = self.bus.get_object(service_name, '/')
            intro = dbus.Interface(obj, 'org.freedesktop.DBus.Introspectable')
            
            # Add timeout to avoid hanging on unresponsive services
            xml = intro.Introspect(timeout=timeout)
            
            # Quick check: does this service have /ble_advertisements paths?
            if 'ble_advertisements' in xml:
                logging.info(f"  ✓ Service {service_name} has ble_advertisements, parsing...")
                # Parse just this service's registrations
                self._parse_registrations(service_name, '/', xml)
                self._update_emitters()
                # Clear device cache when registrations change
                self.discovered_devices.clear()
                logging.debug("Cleared device cache (new registration)")
            else:
                logging.debug(f"  - Service {service_name} has no ble_advertisements")
        except dbus.exceptions.DBusException as e:
            if 'Timeout' in str(e):
                logging.warning(f"  ! Service {service_name} introspection timeout (skipping)")
            else:
                logging.debug(f"  - Could not check {service_name}: {e}")
        except Exception as e:
            logging.debug(f"  - Could not check {service_name}: {e}")
    
    def _remove_service_registrations(self, service_name):
        """Remove all registrations and emitters for a service that disappeared"""
        # Remove from manufacturer registrations
        for mfg_id, paths in list(self.mfg_registrations.items()):
            paths_to_remove = {p for p in paths if service_name in p}
            if paths_to_remove:
                paths.difference_update(paths_to_remove)
                if not paths:
                    del self.mfg_registrations[mfg_id]
        
        # Remove from MAC registrations
        for mac, paths in list(self.mac_registrations.items()):
            paths_to_remove = {p for p in paths if service_name in p}
            if paths_to_remove:
                paths.difference_update(paths_to_remove)
                if not paths:
                    del self.mac_registrations[mac]
        
        # Remove from product ID registrations
        for key, paths in list(self.pid_registrations.items()):
            paths_to_remove = {p for p in paths if service_name in p}
            if paths_to_remove:
                paths.difference_update(paths_to_remove)
                if not paths:
                    del self.pid_registrations[key]
        
        # Remove from product ID range registrations
        for key, paths in list(self.pid_range_registrations.items()):
            paths_to_remove = {p for p in paths if service_name in p}
            if paths_to_remove:
                paths.difference_update(paths_to_remove)
                if not paths:
                    del self.pid_range_registrations[key]
        
        # Remove emitters
        paths_to_remove = [path for path in self.emitters.keys() if service_name in path]
        if paths_to_remove:
            logging.info(f"Service {service_name} disappeared, removing {len(paths_to_remove)} registration(s)")
            for path in paths_to_remove:
                try:
                    self.emitters[path].remove_from_connection()
                    del self.emitters[path]
                except:
                    pass
            # Clear device cache when registrations change
            self.discovered_devices.clear()
            logging.debug("Cleared device cache (registration removed)")
    
    def _update_emitters(self):
        """Create or remove emitters based on registered filters"""
        # Collect all registration paths that should have emitters
        active_paths = set()
        
        for paths in self.mfg_registrations.values():
            active_paths.update(paths)
        
        for paths in self.mac_registrations.values():
            active_paths.update(paths)
        
        for paths in self.pid_registrations.values():
            active_paths.update(paths)
        
        for paths in self.pid_range_registrations.values():
            active_paths.update(paths)
        
        logging.info(f"_update_emitters: {len(active_paths)} active paths, {len(self.emitters)} existing emitters")
        
        # Create emitters for new paths
        for path in active_paths:
            if path not in self.emitters:
                try:
                    self.emitters[path] = AdvertisementEmitter(self.bus_name, path)
                    logging.info(f"Created emitter for {path}")
                except Exception as e:
                    logging.error(f"Failed to create emitter for {path}: {e}", exc_info=True)
        
        # Remove emitters for paths that are no longer registered
        for path in list(self.emitters.keys()):
            if path not in active_paths:
                try:
                    self.emitters[path].remove_from_connection()
                    del self.emitters[path]
                    logging.info(f"Removed emitter for {path} (registration removed)")
                except Exception as e:
                    logging.error(f"Failed to remove emitter {path}: {e}")
    
    def _parse_registrations(self, service_name: str, path: str, xml: str):
        """Recursively parse introspection XML to find registration paths"""
        # Simple XML parsing - look for paths matching our registration pattern
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(xml)
            
            # Registration path patterns (flat, no nesting):
            # - /ble_advertisements/{service}/mfgr/{mfgr_id} - all devices from manufacturer
            # - /ble_advertisements/{service}/mfgr_product/{mfgr_id}_{product_id} - specific product
            # - /ble_advertisements/{service}/mfgr_product_range/{mfgr_id}_{low_pid}_{high_pid} - product range
            # - /ble_advertisements/{service}/addr/{mac} - specific MAC address
            
            if '/ble_advertisements/' in path:
                # Product range: /mfgr_product_range/{mfgr_id}_{low_pid}_{high_pid}
                if '/mfgr_product_range/' in path:
                    match = re.search(r'/mfgr_product_range/(\d+)_(\d+)_(\d+)$', path)
                    if match:
                        mfg_id = int(match.group(1))
                        min_pid = int(match.group(2))
                        max_pid = int(match.group(3))
                        key = (mfg_id, min_pid, max_pid)
                        if key not in self.pid_range_registrations:
                            self.pid_range_registrations[key] = set()
                        self.pid_range_registrations[key].add(path)
                        logging.info(f"Registered mfgr_product_range {path} from {service_name} (mfg={mfg_id}, pid={min_pid}-{max_pid})")
                
                # Specific product: /mfgr_product/{mfgr_id}_{product_id}
                elif '/mfgr_product/' in path:
                    match = re.search(r'/mfgr_product/(\d+)_(\d+)$', path)
                    if match:
                        mfg_id = int(match.group(1))
                        pid = int(match.group(2))
                        key = (mfg_id, pid)
                        if key not in self.pid_registrations:
                            self.pid_registrations[key] = set()
                        self.pid_registrations[key].add(path)
                        logging.info(f"Registered mfgr_product {path} from {service_name} (mfg={mfg_id}, pid={pid})")
                
                # Manufacturer only: /mfgr/{mfgr_id}
                elif '/mfgr/' in path:
                    match = re.search(r'/mfgr/(\d+)$', path)
                    if match:
                        mfg_id = int(match.group(1))
                        if mfg_id not in self.mfg_registrations:
                            self.mfg_registrations[mfg_id] = set()
                        self.mfg_registrations[mfg_id].add(path)
                        logging.info(f"Registered mfgr {path} from {service_name} (mfg={mfg_id})")
                
                # MAC address: /addr/{mac}
                elif '/addr/' in path:
                    # Extract MAC from path
                    # e.g., /ble_advertisements/orion_tr/addr/ef_c1_11_9d_a3_91 or /addr/EFC1119DA391
                    parts = path.split('/addr/')
                    if len(parts) == 2:
                        mac_part = parts[1]
                        # Remove underscores first (some services use them instead of colons)
                        mac_part = mac_part.replace('_', '')
                        # Convert to standard format with colons
                        if ':' not in mac_part and len(mac_part) == 12:
                            mac = ':'.join([mac_part[i:i+2] for i in range(0, 12, 2)])
                        else:
                            mac = mac_part
                        mac = mac.upper()
                        if mac not in self.mac_registrations:
                            self.mac_registrations[mac] = set()
                        self.mac_registrations[mac].add(path)
                        logging.debug(f"Registered {path} from {service_name} (MAC: {mac})")
            
            # Recursively check child nodes
            for node in root.findall('node'):
                child_name = node.get('name')
                if child_name:
                    child_path = f"{path}/{child_name}".replace('//', '/')
                    try:
                        obj = self.bus.get_object(service_name, child_path)
                        intro = dbus.Interface(obj, 'org.freedesktop.DBus.Introspectable')
                        child_xml = intro.Introspect()
                        self._parse_registrations(service_name, child_path, child_xml)
                    except:
                        pass
        
        except Exception as e:
            logging.debug(f"Error parsing XML for {service_name}{path}: {e}")
    
    def _extract_product_id(self, data: bytes) -> Optional[int]:
        """Extract product ID from Victron BLE advertisement data.
        
        For Victron devices (mfg_id 0x02E1), the product ID is at bytes 2-3 (little-endian).
        Returns None if data is too short or extraction fails.
        """
        if len(data) >= 4:
            try:
                import struct
                return struct.unpack("<H", data[2:4])[0]
            except:
                pass
        return None
    
    def _has_registration_for_advertisement(self, mac: str, mfg_id: int, product_id: Optional[int] = None) -> bool:
        """Check if any service has registered interest in this advertisement.
        
        Returns True if:
        - Anyone registered for this specific MAC address, OR
        - Anyone registered for this manufacturer ID (without product filter), OR
        - Anyone registered for this specific (mfg_id, product_id) combo, OR
        - Anyone registered for a (mfg_id, min, max) range that includes product_id
        """
        # Check MAC registrations first (most specific)
        if mac in self.mac_registrations:
            return True
        
        # Check product ID registrations (if we have a product ID)
        if product_id is not None:
            # Check specific product ID registrations
            if (mfg_id, product_id) in self.pid_registrations:
                return True
            
            # Check product ID range registrations
            for (reg_mfg, min_pid, max_pid), paths in self.pid_range_registrations.items():
                if reg_mfg == mfg_id and min_pid <= product_id <= max_pid:
                    return True
        
        # Check manufacturer-only registrations (least specific)
        if mfg_id in self.mfg_registrations:
            return True
        
        return False
    
    def should_process_advertisement(self, mac: str, mfg_id: int) -> bool:
        """Check if this advertisement matches our filters (basic check without product ID)"""
        # Check if anyone registered for this manufacturer ID
        if mfg_id in self.mfg_registrations:
            return True
        
        # Check if anyone registered for this specific MAC
        if mac in self.mac_registrations:
            return True
        
        # Check if there are any product ID or range registrations for this manufacturer
        for (reg_mfg, pid) in self.pid_registrations.keys():
            if reg_mfg == mfg_id:
                return True
        
        for (reg_mfg, min_pid, max_pid) in self.pid_range_registrations.keys():
            if reg_mfg == mfg_id:
                return True
        
        return False
    
    def should_emit_update(self, mac: str, mfg_id: int, data: bytes) -> bool:
        """
        Check if we should emit this advertisement update.
        Returns True if data changed OR 10+ minutes elapsed.
        """
        key = (mac, mfg_id)
        now = time.time()
        
        if key not in self.last_advertisement:
            # First time seeing this device
            self.last_advertisement[key] = (data, now)
            return True
        
        last_data, last_time = self.last_advertisement[key]
        
        # Check if data changed
        if data != last_data:
            self.last_advertisement[key] = (data, now)
            return True
        
        # Check if heartbeat interval elapsed
        if now - last_time >= HEARTBEAT_INTERVAL:
            self.last_advertisement[key] = (data, now)
            return True
        
        return False
    
    @dbus.service.signal(dbus_interface='com.victronenergy.switch.bleadvertisements',
                         signature='sqayn')
    def Advertisement(self, mac, manufacturer_id, data, rssi):
        """
        D-Bus signal emitted when a matching BLE advertisement is received.
        
        Args:
            mac: MAC address (string, format "AA:BB:CC:DD:EE:FF")
            manufacturer_id: Manufacturer ID (uint16)
            data: Advertisement data (array of bytes)
            rssi: Signal strength (int16)
        """
        pass  # Signal is emitted by decorator
    
    def parse_btmon_line(self, line: str):
        """Parse btmon output line by line"""
        line = line.strip()
        
        # Match HCI interface (e.g., "@ MGMT Event: Device Found (0x0012) plen 30 {0001} [hci0]")
        # or "< HCI Command: LE Set Scan Enable (0x08|0x000c) plen 2 [hci0]"
        hci_match = re.search(r'\[hci(\d+)\]', line)
        if hci_match:
            self.current_interface = f"hci{hci_match.group(1)}"
        
        # Match MAC address - support both "Address:" and "LE Address:"
        mac_match = re.search(r'(?:LE )?Address: ([0-9A-F:]{17})', line)
        if mac_match:
            self.current_mac = mac_match.group(1)
            self.current_name = None  # Reset name for new device
            self.current_mfg_id = None
            self.current_rssi = None
            # Keep current_interface from previous line
            return
        
        # Match device name (appears as "Name: Device Name" or "Name (complete): Device Name")
        name_match = re.search(r'Name(?: \(complete\))?: (.+)', line)
        if name_match and self.current_mac:
            self.current_name = name_match.group(1).strip()
            # Update device name cache
            self.device_names[self.current_mac] = self.current_name
            # Update the toggle name if this device is already discovered
            self._update_device_name_if_exists(self.current_mac, self.current_name)
            return
        
        # Match RSSI
        rssi_match = re.search(r'RSSI: (-?\d+)', line)
        if rssi_match:
            self.current_rssi = int(rssi_match.group(1))
            return
        
        # Match Company (manufacturer ID)
        company_match = re.search(r'Company: .* \((\d+)\)', line)
        if company_match:
            self.current_mfg_id = int(company_match.group(1))
            return
        
        # Match manufacturer data
        if self.current_mac and self.current_mfg_id is not None:
            data_match = re.search(r'Data: ([0-9a-f]+)', line)
            if data_match:
                hex_data = data_match.group(1)
                self.process_advertisement(
                    self.current_mac,
                    self.current_mfg_id,
                    hex_data,
                    self.current_rssi or 0,
                    self.current_interface or 'hci0'
                )
                # Reset state after processing
                self.current_mac = None
                self.current_mfg_id = None
                self.current_rssi = None
                self.current_interface = None
    
    def process_advertisement(self, mac: str, mfg_id: int, hex_data: str, rssi: int, interface: str):
        """Process a complete BLE advertisement"""
        # Convert hex string to bytes first (needed to extract product ID)
        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            logging.warning(f"Invalid hex data from {mac}: {hex_data}")
            return
        
        # Extract product ID from the advertisement data (for Victron devices)
        product_id = self._extract_product_id(data)
        
        # Step 1: Check if anything is registered to receive these notifications
        # This now includes product ID filtering
        has_registration = self._has_registration_for_advertisement(mac, mfg_id, product_id)
        if not has_registration:
            return  # No one cares about this advertisement
        
        # Check if we should emit this update (deduplication)
        if not self.should_emit_update(mac, mfg_id, data):
            return
        
        # Step 2: Check if device is in our cache (fast path)
        relay_id = mac.replace(':', '').lower()  # e.g., "efc1119da391"
        
        if relay_id in self.discovered_devices:
            # Device is in cache - check if enabled
            if self.discovered_devices[relay_id]:
                # Enabled -> route the advertisement
                self._emit_advertisement(mac, mfg_id, data, rssi, interface)
            # else: disabled in cache -> don't route
            return
        
        # Step 3: Not in cache - check if discovery is enabled AND there's a registration
        discovery_enabled = self.dbusservice['/SwitchableOutput/relay_discovery/State'] == 1
        if discovery_enabled and has_registration:
            # Create an enabled switch for this MAC
            device_name = self.device_names.get(mac, "")
            
            # Format: "Name (MAC)" or just MAC if no name yet
            if device_name:
                display_name = f"{device_name} ({mac})"
            else:
                display_name = mac
            
            self._add_discovered_device(mac, display_name)
            # Route the advertisement
            self._emit_advertisement(mac, mfg_id, data, rssi, interface)
        # else: discovery disabled or no registration -> don't create switch
    
    def _emit_advertisement(self, mac: str, mfg_id: int, data: bytes, rssi: int, interface: str):
        """Emit D-Bus signals for an advertisement to all matching registration paths"""
        try:
            # Get device name from cache (or empty string if unknown)
            device_name = self.device_names.get(mac, "")
            
            # Extract product ID for filtering
            product_id = self._extract_product_id(data)
            
            # Convert data to dbus types
            data_array = dbus.Array(data, signature='y')
            mac_dbus = dbus.String(mac)
            mfg_id_dbus = dbus.UInt16(mfg_id)
            rssi_dbus = dbus.Int16(rssi)
            interface_dbus = dbus.String(interface)
            name_dbus = dbus.String(device_name)
            
            emitted_count = 0
            
            # Emit on all paths registered for this manufacturer ID (no product filter)
            if mfg_id in self.mfg_registrations:
                for path in self.mfg_registrations[mfg_id]:
                    if path in self.emitters:
                        self.emitters[path].Advertisement(mac_dbus, mfg_id_dbus, data_array, rssi_dbus, interface_dbus, name_dbus)
                        emitted_count += 1
            
            # Emit on paths registered for specific product ID
            if product_id is not None:
                key = (mfg_id, product_id)
                if key in self.pid_registrations:
                    for path in self.pid_registrations[key]:
                        if path in self.emitters:
                            self.emitters[path].Advertisement(mac_dbus, mfg_id_dbus, data_array, rssi_dbus, interface_dbus, name_dbus)
                            emitted_count += 1
                
                # Emit on paths registered for product ID ranges
                for (reg_mfg, min_pid, max_pid), paths in self.pid_range_registrations.items():
                    if reg_mfg == mfg_id and min_pid <= product_id <= max_pid:
                        for path in paths:
                            if path in self.emitters:
                                self.emitters[path].Advertisement(mac_dbus, mfg_id_dbus, data_array, rssi_dbus, interface_dbus, name_dbus)
                                emitted_count += 1
            
            # Emit on all paths registered for this specific MAC
            if mac in self.mac_registrations:
                for path in self.mac_registrations[mac]:
                    if path in self.emitters:
                        self.emitters[path].Advertisement(mac_dbus, mfg_id_dbus, data_array, rssi_dbus, interface_dbus, name_dbus)
                        emitted_count += 1
                    else:
                        if not hasattr(self, '_missing_emitter_logged'):
                            self._missing_emitter_logged = set()
                        if path not in self._missing_emitter_logged:
                            self._missing_emitter_logged.add(path)
                            logging.warning(f"No emitter for registered path: {path}")
            
            if emitted_count > 0:
                name_str = f" name='{device_name}'" if device_name else ""
                pid_str = f" pid={product_id:#06x}" if product_id is not None else ""
                logging.info(f"Broadcast: {mac}{name_str} mfg={mfg_id:#06x}{pid_str} len={len(data)} rssi={rssi} if={interface} → {emitted_count} path(s)")
        except Exception as e:
            logging.error(f"Failed to emit signal for {mac}: {e}")
    
    def process_btmon_output(self, source, condition):
        """GLib callback for btmon output"""
        if condition == GLib.IO_HUP:
            logging.error("btmon process ended unexpectedly")
            return False
        
        try:
            line = source.readline()
            if line:
                self.parse_btmon_line(line)
        except Exception as e:
            logging.error(f"Error processing btmon line: {e}")
        
        return True
    
    def cleanup(self, signum=None, frame=None):
        """Cleanup on exit"""
        logging.info("Shutting down...")
        
        # Stop btmon
        if self.btmon_proc:
            try:
                self.btmon_proc.terminate()
                self.btmon_proc.wait(timeout=1)
            except:
                try:
                    self.btmon_proc.kill()
                except:
                    pass
        
        sys.exit(0)
    
    def run(self):
        """Start the router service"""
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        # Start btmon - mirror seelevel's working approach
        try:
            self.btmon_proc = subprocess.Popen(
                ['btmon'],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                universal_newlines=True,
                bufsize=1
            )
            logging.info("Started btmon")
        except Exception as e:
            logging.error(f"Failed to start btmon: {e}")
            return 1
        
        # Add GLib watch for btmon output - mirror seelevel's working approach
        GLib.io_add_watch(
            self.btmon_proc.stdout,
            GLib.IO_IN | GLib.IO_HUP,
            self.process_btmon_output
        )
        logging.info("btmon output handler registered")
        
        # Kick off an asynchronous initial registration scan. We schedule it via
        # GLib.idle_add so that we only ever inspect one service per idle loop,
        # avoiding long blocking periods that could cause D-Bus timeouts for
        # other clients (notably the GUI asking for GetItems on this service).
        self._schedule_initial_scan()
        
        mainloop = GLib.MainLoop()
        logging.info("Router service running...")
        
        try:
            mainloop.run()
        except KeyboardInterrupt:
            self.cleanup()
        
        return 0


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s'
    )
    
    logging.info("BLE Advertisement Router v1.0.0")
    
    # Initialize D-Bus
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    
    # Create and run router
    router = BLEAdvertisementRouter(bus)
    sys.exit(router.run())


if __name__ == '__main__':
    main()

