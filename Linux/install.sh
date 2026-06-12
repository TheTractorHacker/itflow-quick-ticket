#!/bin/bash
# ITFlow Quick Ticket - Linux installer
#
# Installs the prebuilt ITFlowQuickTicket binary to /opt/itflow-quick-ticket,
# writes /etc/itflow-quick-ticket/config.json, and registers it as an
# XDG autostart application for all users.
#
# Usage (run as root, e.g. via RMM):
#   ./install.sh <itflow_base_url> <api_key> <client_id> [contact_id] [priority]
#
# Example:
#   ./install.sh https://itflow.foleyit.com XXXXXXXXXXXXXXXX 5 12 Medium
#
# Re-running this script upgrades an existing install: it stops any running
# instance, replaces the binary, and (unless new values are passed) keeps the
# existing config.json.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/itflow-quick-ticket"
CONFIG_DIR="/etc/itflow-quick-ticket"
CONFIG_PATH="$CONFIG_DIR/config.json"
AUTOSTART_DIR="/etc/xdg/autostart"

ITFLOW_BASE_URL="${1:-}"
API_KEY="${2:-}"
CLIENT_ID="${3:-}"
CONTACT_ID="${4:-}"
PRIORITY="${5:-Medium}"

# Stop any running instance so the binary can be replaced cleanly.
pkill -f "$INSTALL_DIR/ITFlowQuickTicket" 2>/dev/null || true

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$AUTOSTART_DIR"

if [ -f "$SCRIPT_DIR/dist/ITFlowQuickTicket" ]; then
    install -m 755 "$SCRIPT_DIR/dist/ITFlowQuickTicket" "$INSTALL_DIR/ITFlowQuickTicket"
elif [ -f "$SCRIPT_DIR/ITFlowQuickTicket" ]; then
    install -m 755 "$SCRIPT_DIR/ITFlowQuickTicket" "$INSTALL_DIR/ITFlowQuickTicket"
else
    echo "ITFlowQuickTicket binary not found next to install.sh (expected ./ITFlowQuickTicket or ./dist/ITFlowQuickTicket)" >&2
    exit 1
fi

mkdir -p "$INSTALL_DIR/assets"
if [ -f "$SCRIPT_DIR/assets/icon.png" ]; then
    install -m 644 "$SCRIPT_DIR/assets/icon.png" "$INSTALL_DIR/assets/icon.png"
fi

install -m 644 "$SCRIPT_DIR/itflow-quick-ticket.desktop" "$AUTOSTART_DIR/itflow-quick-ticket.desktop"

if [ -n "$ITFLOW_BASE_URL" ] && [ -n "$API_KEY" ] && [ -n "$CLIENT_ID" ]; then
    if [ -n "$CONTACT_ID" ]; then
        CONTACT_JSON="$CONTACT_ID"
    else
        CONTACT_JSON="null"
    fi

    cat > "$CONFIG_PATH" <<EOF
{
    "itflow_base_url": "$ITFLOW_BASE_URL",
    "api_key": "$API_KEY",
    "client_id": $CLIENT_ID,
    "contact_id": $CONTACT_JSON,
    "priority": "$PRIORITY"
}
EOF
    chmod 644 "$CONFIG_PATH"
elif [ ! -f "$CONFIG_PATH" ]; then
    echo "No config.json exists and no connection settings were passed." >&2
    echo "Usage: $0 <itflow_base_url> <api_key> <client_id> [contact_id] [priority]" >&2
    exit 1
else
    echo "Keeping existing $CONFIG_PATH"
fi

echo "ITFlow Quick Ticket installed to $INSTALL_DIR"
echo "It will start automatically on next login for all users."

# Launch now for the current graphical session, if any.
if [ -n "${XDG_CURRENT_DESKTOP:-}" ] || [ -n "${DISPLAY:-}" ]; then
    nohup "$INSTALL_DIR/ITFlowQuickTicket" >/dev/null 2>&1 &
    disown || true
    echo "Launched ITFlowQuickTicket"
fi
