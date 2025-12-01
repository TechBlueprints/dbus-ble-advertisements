#!/bin/bash
#
# Enable script for dbus-ble-advertisements
# This script is run on every boot via rc.local to ensure the service is properly set up
#

# Fix permissions
chmod +x /data/apps/dbus-ble-advertisements/*.py
chmod +x /data/apps/dbus-ble-advertisements/service/run
chmod +x /data/apps/dbus-ble-advertisements/service/log/run

# Create rc.local if it doesn't exist
if [ ! -f /data/rc.local ]; then
    echo "#!/bin/bash" > /data/rc.local
    chmod 755 /data/rc.local
fi

# Add enable script to rc.local (runs on every boot)
RC_ENTRY="bash /data/apps/dbus-ble-advertisements/enable.sh"
grep -qxF "$RC_ENTRY" /data/rc.local || echo "$RC_ENTRY" >> /data/rc.local

# Remove old-style symlink-only entries from rc.local
sed -i '/ln -sf \/data\/apps\/dbus-ble-advertisements\/service \/service\/dbus-ble-advertisements/d' /data/rc.local

# Create symlink to service directory
if [ -L /service/dbus-ble-advertisements ]; then
    rm /service/dbus-ble-advertisements
fi
ln -s /data/apps/dbus-ble-advertisements/service /service/dbus-ble-advertisements

echo "dbus-ble-advertisements enabled"

