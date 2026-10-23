#!/usr/bin/env python3
"""
EcoSmart Wi-Fi Onboarding Portal
Checks Wi-Fi internet connectivity on boot. If unavailable, starts an open AP
and captive portal for user setup. Once connected with verified internet,
deactivates the AP and portal.
"""

import html
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

AP_SSID = "EcoSmart-Setup"
AP_IP = "10.42.0.1"
PORT = 80
INTERFACE = "wlan0"

# Global server instance to allow clean shutdown
http_server = None
stop_requested = False


def run_cmd(cmd, timeout=30, check=False):
    """Execute a system command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        logging.warning("Command timed out: %s", " ".join(cmd))
        return -1, "", "Timeout expired"
    except Exception as exc:
        logging.error("Command error (%s): %s", " ".join(cmd), exc)
        return -1, "", str(exc)


def check_wifi_internet(interface=INTERFACE):
    """
    Check if interface is connected to Wi-Fi and can reach the internet.
    Returns True only if Wi-Fi interface has active internet connectivity.
    """
    # 1. Check NetworkManager device state
    rc, state, _ = run_cmd(["nmcli", "-g", "GENERAL.STATE", "device", "show", interface])
    if "100" not in state:
        logging.info("Interface %s is not connected (state: %s)", interface, state)
        return False

    # 2. Check active connection name (must not be our setup AP)
    rc, conn, _ = run_cmd(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", interface])
    if not conn or conn == "--" or conn == AP_SSID:
        logging.info("Interface %s has no valid external connection (conn: %s)", interface, conn)
        return False

    # 3. Test real internet reachability specifically through this interface
    # First attempt: ping public DNS through wlan0
    rc, _, _ = run_cmd(["ping", "-c", "1", "-W", "3", "-I", interface, "1.1.1.1"], timeout=5)
    if rc == 0:
        logging.info("Interface %s confirmed internet access via ping", interface)
        return True

    # Second attempt: HTTP connectivity check via wlan0
    rc, _, _ = run_cmd(
        ["curl", "-s", "-m", "4", "--interface", interface, "http://connectivitycheck.gstatic.com/generate_204"],
        timeout=6,
    )
    if rc == 0:
        logging.info("Interface %s confirmed internet access via curl", interface)
        return True

    logging.info("Interface %s connected to '%s' but lacks internet connectivity", interface, conn)
    return False


def get_nearby_networks(rescan=False):
    """Scan and return a list of unique nearby Wi-Fi networks sorted by signal strength."""
    cmd = ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,BARS", "device", "wifi", "list", "ifname", INTERFACE]
    if rescan:
        cmd.extend(["--rescan", "yes"])
    else:
        cmd.extend(["--rescan", "no"])

    rc, stdout, _ = run_cmd(cmd, timeout=12)
    networks = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 3:
            ssid = parts[0].replace("\\:", ":").strip()
            if not ssid or ssid == "--" or ssid == AP_SSID:
                continue
            try:
                signal_val = int(parts[1])
            except ValueError:
                signal_val = 0
            security = parts[2].strip() or "Abierta"
            if ssid not in networks or signal_val > networks[ssid]["signal"]:
                networks[ssid] = {
                    "ssid": ssid,
                    "signal": signal_val,
                    "security": security,
                    "is_open": ("WPA" not in security and "WEP" not in security),
                }

    return sorted(networks.values(), key=lambda x: x["signal"], reverse=True)[:30]


def ensure_ap_profile():
    """Ensure the open AP connection profile exists in NetworkManager."""
    rc, stdout, _ = run_cmd(["nmcli", "-g", "connection.id", "connection", "show", AP_SSID])
    if rc != 0:
        logging.info("Creating NetworkManager profile '%s' (Open AP)...", AP_SSID)
        run_cmd([
            "nmcli", "connection", "add",
            "type", "wifi",
            "ifname", INTERFACE,
            "con-name", AP_SSID,
            "ssid", AP_SSID,
            "802-11-wireless.mode", "ap",
            "802-11-wireless.band", "bg",
            "802-11-wireless.channel", "6",
            "802-11-wireless.powersave", "2",
            "ipv4.method", "shared",
            "ipv4.addresses", f"{AP_IP}/24",
            "ipv6.method", "disabled",
            "connection.autoconnect", "no",
        ], check=True)
    else:
        # Ensure optimal AP settings (Channel 6, Powersave disabled)
        run_cmd([
            "nmcli", "connection", "modify", AP_SSID,
            "802-11-wireless.channel", "6",
            "802-11-wireless.powersave", "2",
            "802-11-wireless.band", "bg",
            "connection.autoconnect", "no",
        ], check=False)
        # Clear any security keys so it remains open
        run_cmd(["nmcli", "connection", "modify", AP_SSID, "remove", "wifi-sec"], check=False)


def start_ap():
    """Activate the setup AP."""
    logging.info("Activating setup AP '%s'...", AP_SSID)
    # Ensure country code is set so chip transmits at full regulatory power
    country = "GT"
    rc, c_out, _ = run_cmd(["raspi-config", "nonint", "get_wifi_country"])
    if rc == 0 and c_out.strip():
        country = c_out.strip()
    run_cmd(["/sbin/iw", "reg", "set", country], check=False)

    ensure_ap_profile()
    # Cache scan results before switching to AP mode
    get_nearby_networks(rescan=True)
    rc, stdout, stderr = run_cmd(["nmcli", "connection", "up", AP_SSID, "ifname", INTERFACE], timeout=20)
    if rc != 0:
        logging.error("Failed to start AP: %s", stderr)
        return False

    # Disable power management to prevent beacon dropping and low power states
    run_cmd(["/sbin/iwconfig", INTERFACE, "power", "off"], check=False)

    logging.info("Setup AP active on %s at %s (Channel 6, Powersave off)", INTERFACE, AP_IP)
    return True


def stop_ap():
    """Deactivate the setup AP."""
    logging.info("Deactivating setup AP '%s'...", AP_SSID)
    run_cmd(["nmcli", "connection", "down", AP_SSID], timeout=15)


def connect_to_wifi(ssid, password):
    """
    Attempt to connect to a user-provided Wi-Fi network.
    Returns True if successfully connected with internet.
    """
    logging.info("Attempting connection to '%s'...", ssid)
    # 1. Bring down setup AP
    stop_ap()
    time.sleep(2)

    # 2. Attempt connection via NetworkManager
    cmd = ["nmcli", "device", "wifi", "connect", ssid, "ifname", INTERFACE]
    if password:
        cmd.extend(["password", password])

    rc, stdout, stderr = run_cmd(cmd, timeout=35)
    logging.info("nmcli connect result: rc=%d, out=%s, err=%s", rc, stdout, stderr)

    # 3. Wait for DHCP and verify internet connectivity
    for attempt in range(6):
        time.sleep(3)
        if check_wifi_internet(INTERFACE):
            logging.info("Successfully connected to '%s' with confirmed internet access!", ssid)
            return True

    logging.warning("Connection to '%s' failed or lacks internet. Restoring setup AP...", ssid)
    # If connection was created but failed, delete it so it doesn't leave broken profile
    run_cmd(["nmcli", "connection", "delete", "id", ssid], check=False)
    # Restore setup AP so user can re-try
    start_ap()
    return False


HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Configuración Wi-Fi - EcoSmart</title>
  <style>
    :root {
      --primary: #10b981;
      --primary-hover: #059669;
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --border: #334155;
      --input-bg: #0f172a;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 16px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 28px;
      max-width: 440px;
      width: 100%;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      background: rgba(16, 185, 129, 0.15);
      color: var(--primary);
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 12px;
    }
    h1 { font-size: 22px; font-weight: 700; margin-bottom: 8px; }
    p.subtitle { color: var(--text-muted); font-size: 14px; margin-bottom: 24px; line-height: 1.4; }
    label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 6px; color: var(--text); }
    select, input[type="text"], input[type="password"] {
      width: 100%;
      padding: 12px 14px;
      background: var(--input-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-size: 15px;
      margin-bottom: 16px;
      outline: none;
      transition: border-color 0.2s;
    }
    select:focus, input:focus { border-color: var(--primary); }
    .password-wrap { position: relative; margin-bottom: 16px; }
    .password-wrap input { margin-bottom: 0; padding-right: 48px; }
    .toggle-pwd {
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 13px;
    }
    button.btn-submit {
      width: 100%;
      background: var(--primary);
      color: #ffffff;
      border: none;
      border-radius: 8px;
      padding: 14px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
      margin-top: 8px;
    }
    button.btn-submit:hover { background: var(--primary-hover); }
    button.btn-submit:disabled { opacity: 0.6; cursor: not-allowed; }
    .status-box {
      display: none;
      margin-top: 18px;
      padding: 14px;
      border-radius: 8px;
      font-size: 14px;
      text-align: center;
      line-height: 1.4;
    }
    .status-info { background: #1e3a8a; color: #93c5fd; }
    .status-success { background: #064e3b; color: #6ee7b7; }
    .status-error { background: #7f1d1d; color: #fca5a5; }
    .spinner {
      display: inline-block;
      width: 18px;
      height: 18px;
      border: 2px solid rgba(255,255,255,0.3);
      border-radius: 50%;
      border-top-color: #fff;
      animation: spin 0.8s linear infinite;
      vertical-align: middle;
      margin-right: 8px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">EcoSmart Setup</span>
    <h1>Conectar a Wi-Fi</h1>
    <p class="subtitle">Selecciona tu red Wi-Fi o escribe su nombre. Una vez conectada a internet, esta red de configuración se desactivará sola.</p>

    <form id="wifiForm" onsubmit="submitForm(event)">
      <label for="networkSelect">Redes detectadas</label>
      <select id="networkSelect" onchange="onSelectNetwork(this.value)">
        <option value="">-- Selecciona una red --</option>
        __OPTIONS__
      </select>

      <label for="ssid">Nombre de la red (SSID)</label>
      <input type="text" id="ssid" name="ssid" required placeholder="Ej. MiRedHogar" maxlength="64">

      <label for="password">Contraseña Wi-Fi</label>
      <div class="password-wrap">
        <input type="password" id="password" name="password" placeholder="Contraseña de la red" maxlength="64">
        <button type="button" class="toggle-pwd" onclick="togglePassword()">Ver</button>
      </div>

      <button type="submit" id="submitBtn" class="btn-submit">Conectar a internet</button>
    </form>

    <div id="statusBox" class="status-box"></div>
  </div>

  <script>
    function onSelectNetwork(val) {
      if (val) {
        document.getElementById('ssid').value = val;
        document.getElementById('password').focus();
      }
    }

    function togglePassword() {
      const pwd = document.getElementById('password');
      const btn = event.target;
      if (pwd.type === 'password') {
        pwd.type = 'text';
        btn.textContent = 'Ocultar';
      } else {
        pwd.type = 'password';
        btn.textContent = 'Ver';
      }
    }

    function submitForm(e) {
      e.preventDefault();
      const ssid = document.getElementById('ssid').value.trim();
      const password = document.getElementById('password').value;
      const statusBox = document.getElementById('statusBox');
      const submitBtn = document.getElementById('submitBtn');

      if (!ssid) return;

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner"></span> Conectando...';

      statusBox.className = 'status-box status-info';
      statusBox.style.display = 'block';
      statusBox.innerHTML = 'Conectando a <strong>' + escapeHtml(ssid) + '</strong>...<br><small>Espera unos 30 segundos. Si tiene éxito, este panel se apagará y la red EcoSmart-Setup desaparecerá.</small>';

      fetch('/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ ssid: ssid, password: password })
      })
      .then(res => res.json())
      .catch(() => {
        // Fetch error often occurs because AP disconnected when joining target network
      });
    }

    function escapeHtml(text) {
      const div = document.createElement('div');
      div.innerText = text;
      return div.innerHTML;
    }
  </script>
</body>
</html>
"""


class CaptivePortalHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean minimal logging
        logging.info("%s - %s", self.address_string(), format % args)

    def send_redirect(self, location=f"http://{AP_IP}/"):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        host = self.headers.get("Host", "")

        # Captive portal detection endpoints (Android, iOS, Windows)
        captive_endpoints = [
            "/generate_204",
            "/gen_204",
            "/hotspot-detect.html",
            "/canonical.html",
            "/connecttest.txt",
            "/ncsi.txt",
            "/success.txt",
        ]

        if parsed.path in captive_endpoints or (host and not host.startswith(AP_IP)):
            # If request is from an OS captive check or any external domain, redirect to portal root
            self.send_redirect(f"http://{AP_IP}/")
            return

        if parsed.path == "/":
            networks = get_nearby_networks(rescan=False)
            options_html = ""
            for net in networks:
                sec_text = "" if net["is_open"] else " 🔒"
                label = f"{net['ssid']} ({net['signal']}%{sec_text})"
                options_html += f'<option value="{html.escape(net["ssid"], quote=True)}">{html.escape(label)}</option>'

            content = HTML_TEMPLATE.replace("__OPTIONS__", options_html).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
            return

        if parsed.path == "/scan":
            networks = get_nearby_networks(rescan=True)
            body = json.dumps(networks).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # Default fallback
        self.send_redirect(f"http://{AP_IP}/")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/connect":
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            post_data = self.rfile.read(length).decode("utf-8")
            data = parse_qs(post_data)

            ssid = data.get("ssid", [""])[0].strip()
            password = data.get("password", [""])[0]

            if not ssid:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "SSID requerido"}')
                return

            response_body = json.dumps({
                "status": "connecting",
                "message": f"Conectando a {ssid}..."
            }).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

            # Spawn connection worker in background thread so HTTP response is delivered first
            def connection_worker():
                time.sleep(1.5)
                success = connect_to_wifi(ssid, password)
                if success:
                    logging.info("Connection successful! Shutting down setup portal.")
                    global stop_requested, http_server
                    stop_requested = True
                    if http_server:
                        threading.Thread(target=http_server.shutdown).start()

            threading.Thread(target=connection_worker, daemon=True).start()

        except Exception as exc:
            logging.error("Error processing connect request: %s", exc)
            self.send_response(500)
            self.end_headers()


def start_server():
    global http_server
    server_address = ("0.0.0.0", PORT)
    http_server = ThreadingHTTPServer(server_address, CaptivePortalHandler)
    logging.info("Captive portal HTTP server listening on %s:%d", server_address[0], PORT)
    try:
        http_server.serve_forever()
    except Exception as exc:
        logging.info("HTTP server stopping: %s", exc)
    finally:
        http_server.server_close()


def main():
    # Allow 15s initial wait on boot for NetworkManager auto-connect
    logging.info("EcoSmart Wi-Fi onboarding starting. Checking initial status...")
    time.sleep(5)

    if check_wifi_internet(INTERFACE):
        logging.info("Wi-Fi is already connected with internet access. No onboarding needed.")
        sys.exit(0)

    logging.info("No active Wi-Fi internet detected on %s. Starting onboarding AP & portal...", INTERFACE)

    if not start_ap():
        logging.error("Could not start setup AP. Exiting.")
        sys.exit(1)

    # Start captive portal HTTP server
    start_server()

    # If stop_requested and internet is confirmed, cleanup and exit
    if stop_requested:
        logging.info("Setup complete. Deactivating AP and stopping service.")
        stop_ap()
        sys.exit(0)


if __name__ == "__main__":
    main()
