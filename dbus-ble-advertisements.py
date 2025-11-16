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
Filters based on manufacturer IDs and MAC addresses registered via D-Bus.

Clients register by creating D-Bus objects at:
  /ble_advertisements/{service_name}/mfgr/{id}    - for manufacturer ID filtering
  /ble_advertisements/{service_name}/addr/{mac}   - for MAC address filtering

The router emits Advertisement signals on those same paths (per-application).
Each service gets its own signal path matching its registration.
"""

import re
import subprocess
import sys
import time
import logging
import signal
import json
import os
from typing import Dict, Set, Tuple, Optional

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

HEARTBEAT_INTERVAL = 600  # 10 minutes
REGISTRATION_SCAN_INTERVAL = 30  # Scan for new registrations every 30 seconds
DEVICES_CONFIG_FILE = "/data/apps/dbus-ble-advertisements/devices.json"


class AdvertisementEmitter(dbus.service.Object):
    """D-Bus object that emits signals for a specific manufacturer or MAC"""
    
    @dbus.service.signal(dbus_interface='com.techblueprints.ble.Advertisements',
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
    
    @dbus.service.method(dbus_interface='com.techblueprints.ble.Advertisements',
                         in_signature='', out_signature='s')
    def GetVersion(self):
        """Return service version"""
        return "1.0.0"
    
    @dbus.service.method(dbus_interface='com.techblueprints.ble.Advertisements',
                         in_signature='', out_signature='s')
    def GetStatus(self):
        """Return service status based on heartbeat"""
        time_since_heartbeat = time.time() - self.heartbeat
        if time_since_heartbeat < 1800:  # 30 minutes
            return "running"
        else:
            return "stale"
    
    @dbus.service.method(dbus_interface='com.techblueprints.ble.Advertisements',
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
        
        # Create a BusName for the emitters to use
        self.bus_name = dbus.service.BusName('com.victronenergy.switch.ble.advertisements', bus)
        
        # Create root object to provide GetVersion, GetStatus, GetHeartbeat methods
        self.root_obj = RootObject(self.bus_name)
        
        # Import VeDbusService for creating a proper Venus OS device
        sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext', 'velib_python'))
        from vedbus import VeDbusService
        from settingsdevice import SettingsDevice
        
        # Create as a switch device so it appears in the device list with settings
        self.dbusservice = VeDbusService('com.victronenergy.switch.ble.advertisements', bus, register=False)
        
        # Add mandatory paths for Venus OS device
        self.dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self.dbusservice.add_path('/Mgmt/ProcessVersion', '1.0.0')
        self.dbusservice.add_path('/Mgmt/Connection', 'BLE Router')
        self.dbusservice.add_path('/DeviceInstance', 50)
        self.dbusservice.add_path('/ProductId', 0xFFFF)
        self.dbusservice.add_path('/ProductName', 'BLE Advertisement Router')
        self.dbusservice.add_path('/CustomName', 'BLE Router')
        self.dbusservice.add_path('/FirmwareVersion', '1.0.0')
        self.dbusservice.add_path('/HardwareVersion', None)
        self.dbusservice.add_path('/Connected', 1)
        
        # Add switch-specific paths (required for switch devices)
        self.dbusservice.add_path('/State', 0x100)  # 0x100 = Connected (module-level state)
        
        # Create a single switchable output for new device discovery toggle
        # Use relay_1 identifier - matching RemoteGPIO and GX IO Extender relay pattern
        output_path = '/SwitchableOutput/relay_1'
        self.dbusservice.add_path(f'{output_path}/Name', '* BLE Router New Device Discovery')
        self.dbusservice.add_path(f'{output_path}/Type', 1)  # 1 = toggle (at output level for GUI rendering)
        self.dbusservice.add_path(f'{output_path}/State', 0, writeable=True,
                                   onchangecallback=self._on_discovery_changed)
        self.dbusservice.add_path(f'{output_path}/Status', 0x00)  # 0x00 = Off, 0x09 = On
        
        # Add settings paths (under /Settings/)
        self.dbusservice.add_path(f'{output_path}/Settings/CustomName', '', writeable=True)
        self.dbusservice.add_path(f'{output_path}/Settings/Type', 1, writeable=True)  # 1 = toggle
        self.dbusservice.add_path(f'{output_path}/Settings/ValidTypes', 2)  # Bitmask: bit 1 set = toggle (0b10 = 2)
        self.dbusservice.add_path(f'{output_path}/Settings/Function', 2, writeable=True)  # 2 = Manual
        self.dbusservice.add_path(f'{output_path}/Settings/ValidFunctions', 4)  # Bitmask: bit 2 set = Manual (0b100 = 4)
        self.dbusservice.add_path(f'{output_path}/Settings/Group', '', writeable=True)
        self.dbusservice.add_path(f'{output_path}/Settings/ShowUIControl', 1, writeable=True)  # 1 = visible in switches pane by default
        
        # Register the service after ALL paths are added
        # Note: We'll create switchable outputs dynamically as devices are discovered
        self.dbusservice.register()
        
        # Track discovered devices that should appear as switchable outputs
        # Note: /SwitchableOutput is a container path, not a leaf - it's created implicitly by its children
        # Key: device_id (sanitized MAC or "mfgr_{id}"), Value: device info
        self.discovered_devices: Dict[str, dict] = {}
        
        # Register device in settings (for GUI device list)
        settings = {
            "ClassAndVrmInstance": [
                "/Settings/Devices/ble_advertisements/ClassAndVrmInstance",
                "switch:50",
                0,
                0,
            ],
            "DiscoveryEnabled": [
                "/Settings/Devices/ble_advertisements/DiscoveryEnabled",
                0,  # Default: OFF
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
        
        # Restore discovery state from settings
        discovery_state = self._settings['DiscoveryEnabled']
        self.dbusservice['/SwitchableOutput/relay_1/State'] = discovery_state
        self.dbusservice['/SwitchableOutput/relay_1/Status'] = 0x09 if discovery_state else 0x00
        if discovery_state:
            logging.info("Discovery enabled from saved settings")
        
        # Restore previously discovered devices from persistent storage
        self._load_discovered_devices()
        
        logging.info("Created BLE Router device service as switch device")
        
        # TODO: Re-implement com.victronenergy.ble.advertisements as a separate service
        # for advertisement signal routing to client services
        # For now, we're only implementing the UI control via the switch device
        
        # Filters: manufacturer IDs and MAC addresses we care about
        # Key: mfg_id or MAC, Value: set of full registration paths
        self.mfg_registrations: Dict[int, Set[str]] = {}  # mfg_id -> {'/ble_advertisements/orion_tr/mfgr/737', ...}
        self.mac_registrations: Dict[str, Set[str]] = {}  # MAC -> {'/ble_advertisements/orion_tr/addr/EFC...', ...}
        
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
    
    def _on_relay_state_changed(self, path: str, value: int):
        """Callback when a discovered device relay state changes"""
        # Extract relay_id from path like "/SwitchableOutput/relay_efc1119da391/State"
        # The relay_id is the MAC address without colons
        path_parts = path.split('/')
        if len(path_parts) < 3 or not path_parts[2].startswith('relay_'):
            logging.warning(f"Unexpected path format in _on_relay_state_changed: {path}")
            return True
        
        relay_id = path_parts[2].replace('relay_', '')  # e.g., "efc1119da391"
        
        # Find which device_id is mapped to this relay_id
        for device_id, device_info in self.discovered_devices.items():
            if device_info.get('relay_id') == relay_id:
                device_info['enabled'] = (value == 1)
                device_name = device_info['name']
                logging.info(f"Device '{device_name}' routing changed to: {'enabled' if value == 1 else 'disabled'}")
                
                # Update Status to match State (0x00 = off, 0x09 = on)
                self.dbusservice[f'/SwitchableOutput/relay_{relay_id}/Status'] = 0x09 if value == 1 else 0x00
                
                # If device is disabled, immediately hide it from the UI
                if value == 0:
                    self.dbusservice[f'/SwitchableOutput/relay_{relay_id}/Settings/ShowUIControl'] = 0
                    logging.info(f"Hidden '{device_name}' from switches pane (disabled)")
                
                # Persist the change
                self._save_discovered_devices()
                return True
        
        logging.warning(f"State change for relay_{relay_id} but no device mapped to it")
        return True  # Accept the change anyway
    
    def _on_settings_changed(self, setting, old_value, new_value):
        """Callback when a setting changes in com.victronenergy.settings"""
        logging.debug(f"Setting changed: {setting} = {new_value}")
        # Settings are already updated by SettingsDevice, no action needed
    
    def _on_discovery_changed(self, path, value):
        """Callback when new device discovery toggle (SwitchableOutput/relay_1/State) changes"""
        enabled = (value == 1)
        logging.info(f"New device discovery changed to: {enabled}")
        
        # Save to persistent settings
        self._settings['DiscoveryEnabled'] = value
        
        # Update Status to match State (0x00 = Off, 0x09 = On per Venus documentation)
        self.dbusservice['/SwitchableOutput/relay_1/Status'] = 0x09 if enabled else 0x00
        
        if enabled:
            # Discovery enabled: only show device toggles that are still enabled
            logging.info("Discovery enabled - showing enabled device switches")
            self.dbusservice['/SwitchableOutput/relay_1/Settings/ShowUIControl'] = 1
            
            # Only make enabled device toggles visible
            for device_id, device_info in self.discovered_devices.items():
                relay_id = device_info['relay_id']
                output_path = f'/SwitchableOutput/relay_{relay_id}'
                
                # Only show if device is enabled
                if device_info.get('enabled', True):
                    self.dbusservice[f'{output_path}/Settings/ShowUIControl'] = 1
                    logging.info(f"Made {device_info['name']} visible in switches pane")
                else:
                    logging.info(f"Keeping {device_info['name']} hidden (disabled)")
        else:
            # Discovery disabled: hide all device toggles
            logging.info("Discovery disabled - hiding all device switches")
            self.dbusservice['/SwitchableOutput/relay_1/Settings/ShowUIControl'] = 0
            
            # Hide all discovered device toggles
            for device_id, device_info in self.discovered_devices.items():
                relay_id = device_info['relay_id']
                output_path = f'/SwitchableOutput/relay_{relay_id}'
                self.dbusservice[f'{output_path}/Settings/ShowUIControl'] = 0
                logging.info(f"Hidden {device_info['name']} from switches pane")
        
        return True  # Accept the change
    
    def _save_discovered_devices(self):
        """Save discovered devices to persistent storage"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(DEVICES_CONFIG_FILE), exist_ok=True)
            
            # Save device info
            with open(DEVICES_CONFIG_FILE, 'w') as f:
                json.dump(self.discovered_devices, f, indent=2)
            
            logging.debug(f"Saved {len(self.discovered_devices)} discovered devices to {DEVICES_CONFIG_FILE}")
        except Exception as e:
            logging.error(f"Failed to save discovered devices: {e}")
    
    def _load_discovered_devices(self):
        """Load discovered devices from persistent storage and restore their slots"""
        try:
            if not os.path.exists(DEVICES_CONFIG_FILE):
                logging.info("No saved devices found")
                return
            
            with open(DEVICES_CONFIG_FILE, 'r') as f:
                saved_devices = json.load(f)
            
            if not saved_devices:
                logging.info("No devices to restore")
                return
            
            logging.info(f"Restoring {len(saved_devices)} discovered devices from persistent storage...")
            
            for device_id, device_info in saved_devices.items():
                relay_id = device_info['relay_id']
                name = device_info['name']
                enabled = device_info.get('enabled', True)
                
                # Recreate the D-Bus paths for this device
                output_path = f'/SwitchableOutput/relay_{relay_id}'
                self.dbusservice.add_path(f'{output_path}/Name', name)
                self.dbusservice.add_path(f'{output_path}/Type', 1)
                self.dbusservice.add_path(f'{output_path}/State', 1 if enabled else 0, writeable=True,
                                           onchangecallback=self._on_relay_state_changed)
                self.dbusservice.add_path(f'{output_path}/Status', 0x09 if enabled else 0x00)
                self.dbusservice.add_path(f'{output_path}/Settings/CustomName', '', writeable=True)
                self.dbusservice.add_path(f'{output_path}/Settings/Type', 1, writeable=True)
                self.dbusservice.add_path(f'{output_path}/Settings/ValidTypes', 2)
                self.dbusservice.add_path(f'{output_path}/Settings/Function', 2, writeable=True)
                self.dbusservice.add_path(f'{output_path}/Settings/ValidFunctions', 4)
                self.dbusservice.add_path(f'{output_path}/Settings/Group', '', writeable=True)
                
                # Only show if discovery is enabled
                discovery_enabled = self.dbusservice['/SwitchableOutput/relay_1/State']
                self.dbusservice.add_path(f'{output_path}/Settings/ShowUIControl', 1 if discovery_enabled else 0, writeable=True)
                
                # Restore to in-memory tracking
                self.discovered_devices[device_id] = device_info
                
                logging.info(f"Restored device: {name} at {output_path} (enabled={enabled})")
            
            logging.info(f"Device restoration complete - {len(saved_devices)} devices restored")
        except Exception as e:
            logging.error(f"Failed to load discovered devices: {e}", exc_info=True)
    
    def _update_device_name_if_exists(self, mac: str, name: str):
        """Update the toggle name for a device if it's already been discovered
        
        Only updates if discovery mode is enabled - no need to update names when not discovering.
        """
        # Skip if discovery is disabled - no need to update UI elements
        discovery_enabled = self.dbusservice['/SwitchableOutput/relay_1/State'] == 1
        if not discovery_enabled:
            return
        
        device_id = f"mac_{mac.replace(':', '').lower()}"
        if device_id in self.discovered_devices:
            device_info = self.discovered_devices[device_id]
            relay_id = device_info['relay_id']
            output_path = f'/SwitchableOutput/relay_{relay_id}'
            
            # Format: "Name (MAC)" - much more readable than just MAC
            new_name = f"{name} ({mac})"
            
            # Update the D-Bus path
            self.dbusservice[f'{output_path}/Name'] = new_name
            
            # Update in-memory cache
            device_info['name'] = new_name
            
            # Persist the change
            self._save_discovered_devices()
            
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
    
    def _add_discovered_device(self, device_id: str, name: str, device_type: str):
        """
        Create a new switchable output for a discovered device.
        
        Only adds if discovery is enabled and device doesn't already exist.
        Defaults: State=1 (enabled), ShowUIControl=1 (visible)
        
        Args:
            device_id: Sanitized identifier (e.g., "mac_abc123" or "mfgr_737")
            name: Human-readable name (e.g., "Orion TR (EF:C2:7B:38:54:60)" or "Mfgr 0x2E1")
            device_type: "mac" or "mfgr"
        """
        # Only add if discovery is enabled and device doesn't already exist
        discovery_enabled = self.dbusservice['/SwitchableOutput/relay_1/State']
        if discovery_enabled == 0 or device_id in self.discovered_devices:
            return
        
        # Use MAC address (without colons) as relay identifier
        # device_id format is "mac_abc123", so we can use it directly after "mac_"
        relay_id = device_id.replace('mac_', '')  # e.g., "efc1119da391"
        output_path = f'/SwitchableOutput/relay_{relay_id}'
        
        # Create new D-Bus paths for this device
        self.dbusservice.add_path(f'{output_path}/Name', name)
        self.dbusservice.add_path(f'{output_path}/Type', 1)  # 1 = toggle
        self.dbusservice.add_path(f'{output_path}/State', 1, writeable=True,
                                   onchangecallback=self._on_relay_state_changed)  # Enabled by default
        self.dbusservice.add_path(f'{output_path}/Status', 0x09)  # On
        self.dbusservice.add_path(f'{output_path}/Settings/CustomName', '', writeable=True)
        self.dbusservice.add_path(f'{output_path}/Settings/Type', 1, writeable=True)
        self.dbusservice.add_path(f'{output_path}/Settings/ValidTypes', 2)
        self.dbusservice.add_path(f'{output_path}/Settings/Function', 2, writeable=True)
        self.dbusservice.add_path(f'{output_path}/Settings/ValidFunctions', 4)
        self.dbusservice.add_path(f'{output_path}/Settings/Group', '', writeable=True)
        self.dbusservice.add_path(f'{output_path}/Settings/ShowUIControl', 1, writeable=True)  # Visible
        
        # Store device info
        self.discovered_devices[device_id] = {
            'relay_id': relay_id,  # Store the relay identifier
            'name': name,
            'type': device_type,
            'enabled': True  # Track if routing is enabled for this device
        }
        
        logging.info(f"Added discovered device: {name} (ID: {device_id}) at {output_path} - enabled and visible")
        
        # Persist to disk
        self._save_discovered_devices()
    
    def _remove_discovered_device(self, device_id: str):
        """Hide a discovered device's switchable output slot"""
        if device_id not in self.discovered_devices:
            return
        
        device_info = self.discovered_devices[device_id]
        relay_id = device_info['relay_id']
        output_path = f'/SwitchableOutput/relay_{relay_id}'
        
        # Hide the slot but keep it allocated
        self.dbusservice[f'{output_path}/Settings/ShowUIControl'] = 0
        self.dbusservice[f'{output_path}/State'] = 0
        self.dbusservice[f'{output_path}/Status'] = 0x00
        
        logging.info(f"Hid device {device_info['name']} from switches pane")
        del self.discovered_devices[device_id]
    
    def _on_device_state_changed(self, device_id: str, path: str, value: int):
        """DEPRECATED - now using _on_relay_state_changed"""
        # This method is kept for backwards compatibility but should not be called
        logging.warning("_on_device_state_changed called but is deprecated")
        return True
    
    def _scan_existing_services(self):
        """Scan all existing D-Bus services for BLE registrations (called once at startup)"""
        logging.info("=== INITIAL SERVICE SCAN STARTING ===")
        logging.info(f"_scan_existing_services called at {time.time()}")
        try:
            logging.info("Scanning existing D-Bus services for BLE registrations...")
            bus_obj = self.bus.get_object('org.freedesktop.DBus', '/')
            bus_iface = dbus.Interface(bus_obj, 'org.freedesktop.DBus')
            service_names = bus_iface.ListNames()
            
            # Check all com.victronenergy.* services (no hardcoded filter)
            # Any service can register by creating /ble_advertisements/{service}/mfgr/{id} paths
            victron_services = [s for s in service_names 
                                if isinstance(s, str) and 
                                s.startswith('com.victronenergy.') and 
                                not s.startswith(':')]
            
            logging.info(f"Found {len(victron_services)} Victron services to check: {victron_services}")
            
            checked = 0
            for service_name in victron_services:
                checked += 1
                logging.info(f"[{checked}/{len(victron_services)}] Checking {service_name}...")
                self._check_service_registrations(service_name)
            
            logging.info(f"Initial scan complete - found {len(self.mfg_registrations)} mfgr registrations, {len(self.mac_registrations)} MAC registrations")
            if self.mfg_registrations:
                logging.info(f"Manufacturer IDs registered: {list(self.mfg_registrations.keys())}")
            if self.mac_registrations:
                logging.info(f"MAC addresses registered: {list(self.mac_registrations.keys())}")
        except Exception as e:
            logging.error(f"Error scanning existing services: {e}", exc_info=True)
        
        logging.info("=== INITIAL SERVICE SCAN COMPLETE - btmon processing should resume ===")
        return False  # Don't repeat this idle callback
    
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
    
    def _check_service_registrations(self, service_name):
        """Check a single service for BLE registration paths (fast, non-blocking)"""
        try:
            # Only check if this looks like a client service (not system services)
            if not service_name.startswith('com.victronenergy.'):
                return
            
            logging.debug(f"  Introspecting {service_name}...")
            obj = self.bus.get_object(service_name, '/')
            intro = dbus.Interface(obj, 'org.freedesktop.DBus.Introspectable')
            
            # Add timeout to avoid hanging on unresponsive services
            xml = intro.Introspect(timeout=2.0)
            
            # Quick check: does this service have /ble_advertisements paths?
            if 'ble_advertisements' in xml:
                logging.info(f"  ✓ Service {service_name} has ble_advertisements, parsing...")
                # Parse just this service's registrations
                self._parse_registrations(service_name, '/', xml)
                self._update_emitters()
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
    
    def scan_registrations(self):
        """Scan D-Bus for registration objects and update filters"""
        logging.info("Starting registration scan...")
        old_mfg_count = len(self.mfg_registrations)
        old_mac_count = len(self.mac_registrations)
        
        self.mfg_registrations.clear()
        self.mac_registrations.clear()
        
        try:
            # Get D-Bus object manager
            obj = self.bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
            iface = dbus.Interface(obj, 'org.freedesktop.DBus')
            
            # Get all service names
            names = iface.ListNames()
            
            # Only scan com.victronenergy.* services (skip system services to avoid blocking)
            victron_services = [n for n in names if n.startswith('com.victronenergy.') and not n.startswith(':')]
            logging.info(f"Scanning {len(victron_services)} Victron services for registrations...")
            
            # Look for registration paths in Victron services only
            scanned_count = 0
            for name in victron_services:
                try:
                    # Check if service has registration paths
                    obj = self.bus.get_object(name, '/')
                    
                    # Introspect to find paths
                    intro = dbus.Interface(obj, 'org.freedesktop.DBus.Introspectable')
                    xml = intro.Introspect()
                    
                    # Parse for registration paths
                    self._parse_registrations(name, '/', xml)
                    scanned_count += 1
                    
                except dbus.exceptions.DBusException:
                    # Service doesn't support introspection or path doesn't exist
                    continue
                except Exception as e:
                    logging.debug(f"Error scanning {name}: {e}")
                    continue
        
        except Exception as e:
            logging.error(f"Error scanning registrations: {e}")
        
        # Create emitters for newly registered filters
        self._update_emitters()
        
        logging.info(f"Registration scan completed: scanned {scanned_count} services")
        
        # Log changes
        if len(self.mfg_registrations) != old_mfg_count or len(self.mac_registrations) != old_mac_count:
            logging.info(f"Updated filters: {len(self.mfg_registrations)} manufacturer ID(s), {len(self.mac_registrations)} MAC(s)")
            if self.mfg_registrations:
                for mfg_id, paths in self.mfg_registrations.items():
                    logging.info(f"  Manufacturer {mfg_id}: {len(paths)} registration(s)")
            if self.mac_registrations:
                for mac, paths in self.mac_registrations.items():
                    logging.info(f"  MAC {mac}: {len(paths)} registration(s)")
        
        return True  # Continue periodic scanning
    
    def _update_emitters(self):
        """Create or remove emitters based on registered filters"""
        # Collect all registration paths that should have emitters
        active_paths = set()
        
        for paths in self.mfg_registrations.values():
            active_paths.update(paths)
        
        for paths in self.mac_registrations.values():
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
            
            # Check current path for pattern: /ble_advertisements/{service}/mfgr/{id}
            # or /ble_advertisements/{service}/addr/{mac}
            if '/ble_advertisements/' in path and '/mfgr/' in path:
                # Extract manufacturer ID from path
                # e.g., /ble_advertisements/orion_tr/mfgr/737 -> 737
                parts = path.split('/mfgr/')
                if len(parts) == 2:
                    mfg_id = int(parts[1])
                    if mfg_id not in self.mfg_registrations:
                        self.mfg_registrations[mfg_id] = set()
                    self.mfg_registrations[mfg_id].add(path)
                    logging.debug(f"Registered {path} from {service_name}")
            
            elif '/ble_advertisements/' in path and '/addr/' in path:
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
    
    def should_process_advertisement(self, mac: str, mfg_id: int) -> bool:
        """Check if this advertisement matches our filters"""
        # Check if anyone registered for this manufacturer ID
        if mfg_id in self.mfg_registrations:
            return True
        
        # Check if anyone registered for this specific MAC
        if mac in self.mac_registrations:
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
    
    @dbus.service.signal(dbus_interface='com.techblueprints.ble.Advertisements',
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
        # Step 1: Check if anything is registered to receive these notifications
        # (either for this specific MAC or this manufacturer ID)
        has_registration = (mac in self.mac_registrations) or (mfg_id in self.mfg_registrations)
        if not has_registration:
            return  # No one cares about this advertisement
        
        # Convert hex string to bytes
        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            logging.warning(f"Invalid hex data from {mac}: {hex_data}")
            return
        
        # Check if we should emit this update (deduplication)
        if not self.should_emit_update(mac, mfg_id, data):
            return
        
        # Step 2: Check if there is an existing enabled relay switch for this MAC
        device_id = f"mac_{mac.replace(':', '').lower()}"
        device_exists = device_id in self.discovered_devices
        device_enabled = device_exists and self.discovered_devices[device_id]['enabled']
        
        # Debug logging for first few advertisements
        if not hasattr(self, '_debug_count'):
            self._debug_count = {}
        if mac not in self._debug_count:
            self._debug_count[mac] = 0
        if self._debug_count[mac] < 2:
            self._debug_count[mac] += 1
            logging.info(f"DEBUG: {mac} - exists={device_exists}, enabled={device_enabled}, has_reg={has_registration}")
        
        if device_enabled:
            # Step 3a: Device exists and is enabled -> route it
            self._emit_advertisement(mac, mfg_id, data, rssi, interface)
            return
        
        if not device_exists:
            # Step 3b: Device doesn't exist -> check if discovery is enabled
            discovery_enabled = self.dbusservice['/SwitchableOutput/relay_1/State'] == 1
            if discovery_enabled:
                # Create an enabled switch for this MAC and then route it
                device_name = self.device_names.get(mac, "")
                
                # Format: "Name (MAC)" or "service1, service2: MAC" if no name yet
                if device_name:
                    display_name = f"{device_name} ({mac})"
                else:
                    # No Bluetooth name yet - show which services are listening for this MAC
                    service_names = self._get_service_names_for_mac(mac)
                    if service_names:
                        services_str = ", ".join(service_names)
                        display_name = f"{services_str}: {mac}"
                        logging.info(f"Creating device with service name prefix: {display_name}")
                    else:
                        display_name = mac
                        logging.info(f"Creating device with MAC only (no services registered): {display_name}")
                
                self._add_discovered_device(device_id, display_name, "mac")
                # Route the advertisement
                self._emit_advertisement(mac, mfg_id, data, rssi, interface)
            # else: discovery disabled, device doesn't exist -> return (do nothing)
        # else: device exists but is disabled -> return (do nothing)
    
    def _emit_advertisement(self, mac: str, mfg_id: int, data: bytes, rssi: int, interface: str):
        """Emit D-Bus signals for an advertisement to all matching registration paths"""
        try:
            # Get device name from cache (or empty string if unknown)
            device_name = self.device_names.get(mac, "")
            
            # Convert data to dbus types
            data_array = dbus.Array(data, signature='y')
            mac_dbus = dbus.String(mac)
            mfg_id_dbus = dbus.UInt16(mfg_id)
            rssi_dbus = dbus.Int16(rssi)
            interface_dbus = dbus.String(interface)
            name_dbus = dbus.String(device_name)
            
            emitted_count = 0
            
            # Emit on all paths registered for this manufacturer ID
            if mfg_id in self.mfg_registrations:
                for path in self.mfg_registrations[mfg_id]:
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
                logging.info(f"Broadcast: {mac}{name_str} mfg={mfg_id:#06x} len={len(data)} rssi={rssi} if={interface} → {emitted_count} path(s)")
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
        
        # Do initial service scan NOW (before main loop starts)
        # This is synchronous but should be fast with the optimized scan
        logging.info("Running initial service scan...")
        self._scan_existing_services()
        
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

