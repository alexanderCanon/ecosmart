#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Execute as root: sudo bash scripts/install-raspap.sh" >&2
  exit 1
fi

echo "EcoSmart: switching from experimental Wi-Fi setup to official RaspAP"
echo "Keep Ethernet connected throughout this installation."
echo "This changes Wi-Fi services and web-server configuration."
read -r -p "Type INSTALL to continue: " confirmation
[ "$confirmation" = "INSTALL" ] || { echo "Cancelled."; exit 1; }

echo "Disabling experimental EcoSmart Wi-Fi services..."
systemctl disable --now ecosmart-wifi-fallback.timer 2>/dev/null || true
systemctl stop ecosmart-wifi-fallback.service 2>/dev/null || true
systemctl disable --now ecosmart-wifi-portal.service 2>/dev/null || true
if nmcli -t -f NAME connection show | grep -Fxq 'EcoSmart-Setup'; then
  nmcli connection delete 'EcoSmart-Setup'
fi

echo "Installing RaspAP using the official quick installer..."
curl -fsSL https://install.raspap.com -o /tmp/ecosmart-raspap-install.sh
bash /tmp/ecosmart-raspap-install.sh --yes
echo "Installer finished. Follow any installer prompts for reboot or configuration."
echo "Before disconnecting Ethernet, test RaspAP from your phone."
