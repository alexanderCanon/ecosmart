# EcoSmart offline Wi-Fi onboarding (Raspberry Pi 4)

## Behavior

- NetworkManager keeps the Wi-Fi profiles you have already saved and automatically reconnects to them on boot.
- If wlan0 has no active connection approximately 95 seconds after boot, a systemd timer starts `EcoSmart-Setup` (WPA2) on `10.42.0.1/24`.
- Connect your phone to `EcoSmart-Setup` and visit **http://10.42.0.1:8080**.
- Select a cached nearby SSID (when available) or enter an SSID manually, and supply its WPA2 password.
- The portal briefly disconnects the AP to join the requested network. On failure it attempts to restore the AP.
- The portal listens **only** on `10.42.0.1`, not on Ethernet or Tailscale. Ethernet profiles are never modified.

## Deployment (from laptop with Tailscale)

```bash
ansible-playbook -i ansible/inventory.ini ansible/wifi-setup.yml \
  --private-key ~/.ssh/id_ed25519 \
  --ssh-extra-args='-o IdentitiesOnly=yes' \
  --ask-become-pass
```

Ansible prompts for a unique WPA2 password (8-63 chars). **Never commit the password to Git.** During the first test, keep Ethernet plugged in for recovery.

## Constraints and warnings

- One Wi-Fi radio cannot reliably serve as both a station and an AP concurrently. Switching to another network temporarily drops the setup AP.
- Cached SSIDs can be stale; manually entering the SSID always remains available. This first version supports WPA2-Personal networks; captive portals, open networks, and WPA-Enterprise require additional work.
- The password is transferred over HTTP **within the WPA2-protected AP**. Only share the AP password with trusted people. This is a provisioning interface, not a public service.
- Automatic recovery is best-effort and should be tested with a deliberately incorrect Wi-Fi password **while Ethernet remains connected** before relying on headless operation.
- NetworkManager shared IPv4 mode requires DHCP support (`dnsmasq-base`). Some networks and radio/firmware combinations may need further adjustments.
- If the hotspot is not visible after reboot, recover using Ethernet + SSH/Tailscale; inspect `journalctl -u ecosmart-wifi-fallback.service -u ecosmart-wifi-portal.service`.
- To disable automatic fallback without removing saved connections: `sudo systemctl disable --now ecosmart-wifi-fallback.timer`. To disable the portal: `sudo systemctl disable --now ecosmart-wifi-portal.service`.
