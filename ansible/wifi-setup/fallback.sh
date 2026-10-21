#!/bin/sh
set -eu

# Never interfere with Ethernet. Only examine wlan0.
if ! nmcli -t -f DEVICE,TYPE device status | grep -q '^wlan0:wifi; then
  exit 0
fi

# Give NetworkManager time to auto-connect saved Wi-Fi profiles after boot.
uptime_seconds=$(cut -d. -f1 /proc/uptime | cut -d' ' -f1)
if [ "$uptime_seconds" -lt 90 ]; then
  exit 0
fi

active=$(nmcli -g GENERAL.CONNECTION device show wlan0 2>/dev/null || true)
if [ "$active" != "" ] && [ "$active" != "--" ]; then
  exit 0
fi

# Cache any available SSIDs before entering AP mode, where scanning can fail.
nmcli device wifi list ifname wlan0 --rescan yes >/dev/null 2>&1 || true
nmcli connection up EcoSmart-Setup ifname wlan0
; then
  exit 0
fi

# Give NetworkManager time to auto-connect saved Wi-Fi profiles after boot.
uptime_seconds=$(cut -d. -f1 /proc/uptime | cut -d' ' -f1)
if [ "$uptime_seconds" -lt 90 ]; then
  exit 0
fi

active=$(nmcli -g GENERAL.CONNECTION device show wlan0 2>/dev/null || true)
if [ "$active" != "" ] && [ "$active" != "--" ]; then
  exit 0
fi

# Cache any available SSIDs before entering AP mode, where scanning can fail.
nmcli device wifi list ifname wlan0 --rescan yes >/dev/null 2>&1 || true
nmcli connection up EcoSmart-Setup ifname wlan0
