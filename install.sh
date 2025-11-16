#!/bin/bash
#
# One-step installer for dbus-ble-advertisements on Venus OS
# 
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/TechBlueprints/dbus-ble-advertisements/main/install.sh | bash
#
# Or:
#   wget -qO- https://raw.githubusercontent.com/TechBlueprints/dbus-ble-advertisements/main/install.sh | bash
#

set -e

REPO_URL="https://github.com/TechBlueprints/dbus-ble-advertisements"
INSTALL_DIR="/data/apps/dbus-ble-advertisements"
SERVICE_LINK="/service/dbus-ble-advertisements"

echo "========================================"
echo "dbus-ble-advertisements installer"
echo "========================================"
echo ""

# Check if running on Venus OS
if [ ! -d "/data/apps" ]; then
    echo "ERROR: /data/apps not found. This script must run on Venus OS."
    exit 1
fi

# Check if git is available
if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is not installed. Please install git first."
    exit 1
fi

# Check if service is already installed
if [ -d "$INSTALL_DIR" ]; then
    echo "Service directory already exists at $INSTALL_DIR"
    
    # Check if it's a git repo
    if [ -d "$INSTALL_DIR/.git" ]; then
        echo "Updating existing installation..."
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard origin/main
        echo "✓ Updated to latest version"
    else
        echo "WARNING: Installation directory exists but is not a git repository."
        echo "Backing up and reinstalling..."
        mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%s)"
        git clone "$REPO_URL" "$INSTALL_DIR"
        echo "✓ Reinstalled (old installation backed up)"
    fi
else
    echo "Installing to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    echo "✓ Cloned repository"
fi

# Make scripts executable
chmod +x "$INSTALL_DIR/dbus-ble-advertisements.py"
chmod +x "$INSTALL_DIR/service/run"
chmod +x "$INSTALL_DIR/service/log/run"
chmod +x "$INSTALL_DIR/install-ui-overlay.py"
echo "✓ Made scripts executable"

# Install UI overlay
echo ""
echo "Installing UI overlay..."
if python3 "$INSTALL_DIR/install-ui-overlay.py"; then
    echo "✓ UI overlay installed"
    
    # Add to overlay-fs config if not already there
    OVERLAY_CONF="/data/apps/overlay-fs/overlay-fs.conf"
    if [ -f "$OVERLAY_CONF" ]; then
        if ! grep -q "/opt/victronenergy/gui dbus-ble-advertisements" "$OVERLAY_CONF"; then
            echo "/opt/victronenergy/gui dbus-ble-advertisements" >> "$OVERLAY_CONF"
            echo "✓ Added GUI v1 to overlay-fs config"
        else
            echo "✓ GUI v1 already in overlay-fs config"
        fi
        
        if ! grep -q "/opt/victronenergy/gui-v2 dbus-ble-advertisements" "$OVERLAY_CONF"; then
            echo "/opt/victronenergy/gui-v2 dbus-ble-advertisements" >> "$OVERLAY_CONF"
            echo "✓ Added GUI v2 to overlay-fs config"
        else
            echo "✓ GUI v2 already in overlay-fs config"
        fi
        
        # Enable the overlay
        if [ -x "/data/apps/overlay-fs/enable.sh" ]; then
            /data/apps/overlay-fs/enable.sh >/dev/null 2>&1
            echo "✓ Overlay enabled"
            GUI_RESTART_NEEDED=true
        fi
    else
        echo "⚠ overlay-fs not found - UI overlay will not be active"
        GUI_RESTART_NEEDED=false
    fi
else
    echo "⚠ UI overlay installation failed (service will still work without UI)"
    GUI_RESTART_NEEDED=false
fi

# Add to rc.local to persist across reboots
RC_LOCAL="/data/rc.local"
RC_ENTRY="bash $INSTALL_DIR/install.sh > $INSTALL_DIR/startup.log 2>&1 &"

if [ ! -f "$RC_LOCAL" ]; then
    echo "Creating /data/rc.local..."
    echo "#!/bin/bash" > "$RC_LOCAL"
    chmod 755 "$RC_LOCAL"
fi

if ! grep -qF "$RC_ENTRY" "$RC_LOCAL"; then
    echo "Adding service to rc.local for persistence across reboots..."
    echo "$RC_ENTRY" >> "$RC_LOCAL"
    echo "✓ Added to rc.local"
else
    echo "✓ Already in rc.local"
fi

# Set up service link if not present
if [ -L "$SERVICE_LINK" ]; then
    echo "Service link already exists"
    
    # Check if service is running
    if svstat "$SERVICE_LINK" 2>/dev/null | grep -q "^$SERVICE_LINK: up"; then
        echo "✓ Service is running"
        RESTART_NEEDED=false
    else
        echo "Service is installed but not running"
        RESTART_NEEDED=true
    fi
else
    echo "Creating service link..."
    ln -s "$INSTALL_DIR/service" "$SERVICE_LINK"
    echo "✓ Service link created"
    RESTART_NEEDED=true
fi

# Start or restart service if needed
if [ "$RESTART_NEEDED" = true ]; then
    echo "Starting service..."
    svc -u "$SERVICE_LINK"
    sleep 2
    
    if svstat "$SERVICE_LINK" 2>/dev/null | grep -q "^$SERVICE_LINK: up"; then
        echo "✓ Service started successfully"
    else
        echo "WARNING: Service may not have started correctly"
        echo "Check logs: tail -f /var/log/dbus-ble-advertisements/current"
    fi
else
    echo "Restarting service to apply updates..."
    svc -t "$SERVICE_LINK"
    sleep 2
    echo "✓ Service restarted"
fi

# Verify service is healthy
echo ""
echo "Verifying installation..."
sleep 2

if dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>/dev/null | grep -q "com.victronenergy.switch.ble_router"; then
    echo "✓ Service registered on D-Bus"
    
    # Try to get version
    VERSION=$(dbus-send --system --print-reply --dest=com.victronenergy.switch.ble_router /ble_advertisements com.techblueprints.BleAdvertisements.GetVersion 2>/dev/null | grep string | awk '{print $2}' | tr -d '"' || echo "unknown")
    echo "✓ Service version: $VERSION"
echo ""
echo "========================================"
echo "Installation successful!"
echo "========================================"
echo ""
if [ "$GUI_RESTART_NEEDED" = true ]; then
    echo "⚠ GUI restart required to see UI changes"
    echo "  Run: svc -t /service/gui"
    echo ""
fi
else
    echo "⚠ Service not yet registered on D-Bus (may still be starting up)"
    echo ""
    echo "========================================"
    echo "Installation complete"
    echo "========================================"
    echo ""
    echo "If service doesn't appear in a few seconds, check logs:"
    echo "  tail -f /var/log/dbus-ble-advertisements/current"
fi

echo ""
echo "Service management commands:"
echo "  svc -u $SERVICE_LINK  # Start"
echo "  svc -d $SERVICE_LINK  # Stop"
echo "  svc -t $SERVICE_LINK  # Restart"
echo "  svstat $SERVICE_LINK           # Status"
echo ""
echo "View logs:"
echo "  tail -f /var/log/dbus-ble-advertisements/current"
echo ""

exit 0

