#!/bin/bash
# Install Telegram Watch Tower as systemd service

SERVICE_FILE="/home/ubuntu/financial_orchestrator/telegram_watchtower/telegram-watchtower.service"
SYSTEMD_DIR="/etc/systemd/system"

echo "=== Telegram Watch Tower Service Installer ==="

if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    echo "Usage: sudo $0"
    exit 1
fi

echo "Copying service file..."
cp "$SERVICE_FILE" "$SYSTEMD_DIR/telegram-watchtower.service"

echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling service..."
systemctl enable telegram-watchtower

echo "Starting service..."
systemctl start telegram-watchtower

echo ""
echo "=== Service Commands ==="
echo "  Start:   sudo systemctl start telegram-watchtower"
echo "  Stop:    sudo systemctl stop telegram-watchtower"
echo "  Restart: sudo systemctl restart telegram-watchtower"
echo "  Status:  sudo systemctl status telegram-watchtower"
echo "  Logs:    sudo journalctl -u telegram-watchtower -f"
echo ""
echo "Service installed successfully!"
