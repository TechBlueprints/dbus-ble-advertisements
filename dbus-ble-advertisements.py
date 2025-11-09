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
from typing import Dict, Set, Tuple

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

HEARTBEAT_INTERVAL = 600  # 10 minutes
REGISTRATION_SCAN_INTERVAL = 30  # Scan for new registrations every 30 seconds


class AdvertisementEmitter(dbus.service.Object):
    """D-Bus object that emits signals for a specific manufacturer or MAC"""
    
    @dbus.service.signal(dbus_interface='com.victronenergy.ble.Advertisements',
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
    
    @dbus.service.method(dbus_interface='com.victronenergy.ble.Advertisements',
                         in_signature='', out_signature='s')
    def GetVersion(self):
        """Return service version"""
        return "1.0.0"
    
    @dbus.service.method(dbus_interface='com.victronenergy.ble.Advertisements',
                         in_signature='', out_signature='s')
    def GetStatus(self):
        """Return service status based on heartbeat"""
        time_since_heartbeat = time.time() - self.heartbeat
        if time_since_heartbeat < 1800:  # 30 minutes
            return "running"
        else:
            return "stale"
    
    @dbus.service.method(dbus_interface='com.victronenergy.ble.Advertisements',
                         in_signature='', out_signature='d')
    def GetHeartbeat(self):
        """Return last heartbeat timestamp"""
        return self.heartbeat
    
    def update_heartbeat(self):
        """Update heartbeat timestamp"""
        self.heartbeat = time.time()


class BLEAdvertisementRouter:
    """
    BLE Advertisement Router Service
    
    Monitors BLE advertisements and broadcasts them via D-Bus signals.
    Clients register by creating objects at /ble_advertisements/{service}/mfgr/{id} or /ble_advertisements/{service}/addr/{mac}
    Signals are emitted on those same exact paths (per-application, not shared).
    """
    
    def __init__(self, bus):
        self.bus = bus
        self.bus_name = dbus.service.BusName('com.victronenergy.ble.advertisements', bus)
        
        # Create root object for service presence
        self.root_object = RootObject(self.bus_name)
        
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
        
        # Subscribe to D-Bus NameOwnerChanged signals to clear cache when services disappear
        self.bus.add_signal_receiver(
            self._on_name_owner_changed,
            signal_name='NameOwnerChanged',
            dbus_interface='org.freedesktop.DBus',
            path='/org/freedesktop/DBus'
        )
        
        # Update heartbeat every 10 minutes
        GLib.timeout_add_seconds(600, self._update_heartbeat)
        
        logging.info(f"Router initialized")
    
    def _update_heartbeat(self):
        """Periodic callback to update heartbeat timestamp"""
        self.root_object.update_heartbeat()
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
            
            obj = self.bus.get_object(service_name, '/')
            intro = dbus.Interface(obj, 'org.freedesktop.DBus.Introspectable')
            xml = intro.Introspect()
            
            # Quick check: does this service have /ble_advertisements paths?
            if 'ble_advertisements' in xml:
                logging.info(f"Service {service_name} appeared, checking for registrations...")
                # Parse just this service's registrations
                self._parse_registrations(service_name, '/', xml)
                self._update_emitters()
        except Exception as e:
            logging.debug(f"Could not check {service_name}: {e}")
    
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
        
        # Create emitters for new paths
        for path in active_paths:
            if path not in self.emitters:
                self.emitters[path] = AdvertisementEmitter(self.bus_name, path)
                logging.debug(f"Created emitter for {path}")
        
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
                # e.g., /ble_advertisements/orion_tr/addr/EFC1119DA391
                parts = path.split('/addr/')
                if len(parts) == 2:
                    mac_part = parts[1]
                    # Convert to standard format with colons
                    if ':' not in mac_part:
                        mac = ':'.join([mac_part[i:i+2] for i in range(0, 12, 2)])
                    else:
                        mac = mac_part
                    mac = mac.upper()
                    if mac not in self.mac_registrations:
                        self.mac_registrations[mac] = set()
                    self.mac_registrations[mac].add(path)
                    logging.debug(f"Registered {path} from {service_name}")
            
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
    
    @dbus.service.signal(dbus_interface='com.victronenergy.ble.Advertisements',
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
        # Check if this matches our filters
        if not self.should_process_advertisement(mac, mfg_id):
            return
        
        # Convert hex string to bytes
        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            logging.warning(f"Invalid hex data from {mac}: {hex_data}")
            return
        
        # Check if we should emit this update (deduplication without interface/rssi)
        if not self.should_emit_update(mac, mfg_id, data):
            return
        
        # Emit D-Bus signal on all matching registration paths (per-application)
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

