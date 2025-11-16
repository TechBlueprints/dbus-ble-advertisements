#!/bin/bash

# Simple reboot script - just recreate the service symlink
# This is called from /data/rc.local on every boot

SERVICE_DIR="/data/apps/dbus-ble-advertisements"

# Recreate service symlink
ln -sf "$SERVICE_DIR/service" /service/dbus-ble-advertisements

exit 0

