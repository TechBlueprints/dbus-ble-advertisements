#!/usr/bin/env python3
"""
Install script to augment PageSettingsBleSensors.qml with BLE integrations support
Supports both GUI v1 (old) and GUI v2 (new)
"""

import sys
import os
import re

# Support both gui (v1) and gui-v2
GUI_PATHS = [
    {
        "original": "/opt/victronenergy/gui/qml/PageSettingsBleSensors.qml",
        "overlay_dir": "/data/apps/overlay-fs/data/gui/upper/qml",
        "name": "GUI v1",
        "version": 1
    },
    {
        "original": "/opt/victronenergy/gui-v2/Victron/VenusOS/pages/settings/PageSettingsBleSensors.qml",
        "overlay_dir": "/data/apps/overlay-fs/data/gui-v2/upper/Victron/VenusOS/pages/settings",
        "name": "GUI v2",
        "version": 2
    }
]

def read_original_qml(path):
    """Read the original QML file"""
    if not os.path.exists(path):
        return None
    
    with open(path, 'r') as f:
        return f.read()

def augment_qml_v1(content):
    """Augment the QML v1 with BLE integrations support"""
    
    # 1. Add property for our service
    property_addition = '''	property string bleIntegrationsService: "dbus/com.techblueprints.ble_advertisements"
	property string bleIntegrationsSetting: "dbus/com.victronenergy.settings/Settings/BleIntegrations/MasterScanEnabled"
'''
    
    # Insert after the serviceSetting property
    content = content.replace(
        'property string serviceSetting: "dbus/com.victronenergy.settings/Settings/Services/BleSensors"',
        'property string serviceSetting: "dbus/com.victronenergy.settings/Settings/Services/BleSensors"\n' + property_addition
    )
    
    # 2. Add integrationSensors model to combine both services
    integration_sensors = '''
	property VeQItemSortTableModel integrationSensors: VeQItemSortTableModel {
		model: VeQItemTableModel {
			uids: [Utils.path(bleIntegrationsService, "/Devices")]
			flags: VeQItemTableModel.AddChildren |
				   VeQItemTableModel.AddNonLeaves |
				   VeQItemTableModel.DontAddItem
		}
		dynamicSortFilter: true
		filterFlags: VeQItemSortTableModel.FilterOffline
	}
'''
    
    # Insert after the interfaces model
    content = re.sub(
        r'(property VeQItemSortTableModel interfaces:.*?\n\t\})',
        r'\1' + integration_sensors,
        content,
        flags=re.DOTALL
    )
    
    # 3. Add BLE Integrations Scanning switch after Continuous scanning
    ble_integrations_switch = '''
			MbSwitch {
				id: bleIntegrationsScan
				name: qsTr("BLE Integrations Scanning")
				bind: bleIntegrationsSetting
				show: enable.checked
			}

			MbItemText {
				text: qsTr("When enabled, discovered integration devices (from services like dbus-ble-advertisements) will appear below. Enable individual devices to route their BLE events.")
				wrapMode: Text.WordWrap
				show: bleIntegrationsScan.checked
			}
'''
    
    # Insert after the continuous scanning warning text
    content = re.sub(
        r'(MbItemText \{[^}]*Continuous scanning may interfere with Wi-Fi operation[^}]*\})',
        r'\1\n' + ble_integrations_switch,
        content,
        flags=re.DOTALL
    )
    
    # 4. Augment the device list to include integration sensors
    original_delegate = r'''		DelegateModel \{
			model: VeQItemSortTableModel \{
				model: VeQItemChildModel \{
					model: sensors
					childId: "Name"
				\}
				dynamicSortFilter: true
				filterFlags: VeQItemSortTableModel\.FilterInvalid
			\}

			delegate: MbSwitch \{
				name: model\.item\.value
				bind: \[model\.item\.itemParent\(\)\.uid, "/Enabled"\]
			\}
		\}'''
    
    augmented_delegate = '''		// Original sensors from com.victronenergy.ble
		DelegateModel {
			model: VeQItemSortTableModel {
				model: VeQItemChildModel {
					model: sensors
					childId: "Name"
				}
				dynamicSortFilter: true
				filterFlags: VeQItemSortTableModel.FilterInvalid
			}

			delegate: MbSwitch {
				name: model.item.value
				bind: [model.item.itemParent().uid, "/Enabled"]
			}
		}

		// Integration sensors from com.techblueprints.ble_advertisements
		DelegateModel {
			model: VeQItemSortTableModel {
				model: VeQItemChildModel {
					model: integrationSensors
					childId: "Name"
				}
				dynamicSortFilter: true
				filterFlags: VeQItemSortTableModel.FilterInvalid
			}

			delegate: MbSwitch {
				name: model.item.value
				bind: [model.item.itemParent().uid, "/Enabled"]
			}
		}'''
    
    content = re.sub(
        original_delegate,
        augmented_delegate,
        content,
        flags=re.DOTALL
    )
    
    return content

def augment_qml_v2(content):
    """Augment the QML v2 with BLE integrations support"""
    
    # 1. Add property for our integration service (after bleServiceUid)
    integration_property = '''
	readonly property string bleIntegrationsServiceUid: "dbus/com.techblueprints.ble_advertisements"
'''
    
    content = re.sub(
        r'(readonly property string bleServiceUid:.*?\n)',
        r'\1' + integration_property,
        content
    )
    
    # 2. Add integrationSensors model (after interfaces model)
    integration_sensors = '''
	VeQItemSortTableModel {
		id: integrationSensors
		model: VeQItemTableModel {
			uids: [ root.bleIntegrationsServiceUid + "/Devices" ]
			flags: VeQItemTableModel.AddChildren | VeQItemTableModel.AddNonLeaves | VeQItemTableModel.DontAddItem
		}
		dynamicSortFilter: true
		filterFlags: VeQItemSortTableModel.FilterOffline
	}
'''
    
    # Insert after interfaces model closing brace
    content = re.sub(
        r'(VeQItemSortTableModel \{\s+id: interfaces.*?filterFlags: VeQItemSortTableModel\.FilterOffline\s+\})',
        r'\1\n' + integration_sensors,
        content,
        flags=re.DOTALL
    )
    
    # 3. Add BLE Integrations Scanning switch (after contScan PrimaryListLabel)
    ble_integrations_switch = '''
			ListSwitch {
				id: bleIntegrationsScan
				//% "BLE Integrations Scanning"
				text: qsTrId("settings_ble_integrations_scanning")
				dataItem.uid: root.bleIntegrationsServiceUid + "/Settings/MasterScanEnabled"
				preferredVisible: enable.checked
			}

			PrimaryListLabel {
				//% "When enabled, discovered integration devices (from services like dbus-ble-advertisements) will appear below. Enable individual devices to route their BLE events."
				text: qsTrId("settings_ble_integrations_scanning_help")
				preferredVisible: bleIntegrationsScan.checked
			}
'''
    
    content = re.sub(
        r'(PrimaryListLabel \{[^}]*text: qsTrId\("settings_continuous_scan_may_interfere"\)[^}]*\})',
        r'\1\n' + ble_integrations_switch,
        content
    )
    
    # 4. Add integration sensors repeater (after the original sensorRepeater closing)
    integration_repeater = '''
			SettingsColumn {
				width: parent ? parent.width : 0
				preferredVisible: integrationRepeater.count > 0

				Repeater {
					id: integrationRepeater
					model: VeQItemSortTableModel {
						model: VeQItemChildModel {
							model: integrationSensors
							childId: "Name"
						}
						dynamicSortFilter: true
						filterFlags: VeQItemSortTableModel.FilterInvalid
					}

					delegate: ListSwitch {
						text: model.item.value
						dataItem.uid: model.item.itemParent().uid + "/Enabled"
					}
				}
			}
'''
    
    # Insert after the sensorRepeater SettingsColumn
    content = re.sub(
        r'(SettingsColumn \{[^}]*Repeater \{\s+id: sensorRepeater.*?\}\s+\})',
        r'\1\n' + integration_repeater,
        content,
        flags=re.DOTALL
    )
    
    return content

def main():
    print("=" * 80)
    print("BLE Advertisements UI Overlay Installer")
    print("=" * 80)
    
    success_count = 0
    
    for gui_path in GUI_PATHS:
        print(f"\n--- Processing {gui_path['name']} ---")
        
        # Read original
        print(f"[1/4] Reading original QML from {gui_path['original']}")
        original_content = read_original_qml(gui_path['original'])
        
        if original_content is None:
            print(f"      ⚠ File not found, skipping {gui_path['name']}")
            continue
            
        print(f"      Original file size: {len(original_content)} bytes")
        
        # Augment based on version
        print(f"\n[2/4] Augmenting QML with BLE integrations support (version {gui_path['version']})")
        if gui_path['version'] == 1:
            augmented_content = augment_qml_v1(original_content)
        else:
            augmented_content = augment_qml_v2(original_content)
        print(f"      Augmented file size: {len(augmented_content)} bytes")
        
        if len(augmented_content) == len(original_content):
            print(f"      ⚠ WARNING: No changes were made (regex patterns may not have matched)")
        
        # Create overlay directory
        overlay_dir = gui_path['overlay_dir']
        overlay_qml = os.path.join(overlay_dir, "PageSettingsBleSensors.qml")
        
        print(f"\n[3/4] Creating overlay directory: {overlay_dir}")
        os.makedirs(overlay_dir, exist_ok=True)
        
        # Write overlay
        print(f"\n[4/4] Writing overlay to {overlay_qml}")
        with open(overlay_qml, 'w') as f:
            f.write(augmented_content)
        
        print(f"      ✓ {gui_path['name']} overlay installed successfully!")
        success_count += 1
    
    if success_count == 0:
        print("\n" + "=" * 80)
        print("✗ No GUI installations found!")
        print("=" * 80)
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print(f"✓ UI overlay installed successfully for {success_count} GUI version(s)!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Add overlay entries to /data/apps/overlay-fs/overlay-fs.conf:")
    if success_count > 0:
        print("     /opt/victronenergy/gui dbus-ble-advertisements")
        print("     /opt/victronenergy/gui-v2 dbus-ble-advertisements")
    print("2. Run /data/apps/overlay-fs/enable.sh to activate the overlay")
    print("3. Restart the GUI: killall venus-gui-v2 && svc -t /service/start-gui")
    print()

if __name__ == "__main__":
    main()
