#!/usr/bin/env python3
"""Minimal offline-only Wi-Fi onboarding page. Accessible only on AP address."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from urllib.parse import parse_qs
import os
import secrets
import subprocess
import time

HOST, PORT = "10.42.0.1", 8080
REQUEST_FILE = "/run/ecosmart-wifi-request"
TOKEN = secrets.token_urlsafe(32)

def nearby_networks():
    # Cached scan list only: active scanning while in AP mode is unreliable.
    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list", "ifname", "wlan0", "--rescan", "no"],
        capture_output=True, text=True, timeout=8, check=False,
    )
    return sorted({line.strip().replace("\\:", ":") for line in result.stdout.splitlines() if line.strip()})[:40]

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def page(self, content, code=200):
        raw = ("<!doctype html><html lang='en'><meta name='viewport' content='width=device-width,initial-scale=1'>"
               "<meta charset='utf-8'><title>EcoSmart Wi-Fi</title>"
               "<style>body{font:16px system-ui;max-width:440px;margin:40px auto;padding:0 18px}"
               "label,input,select,button{display:block;width:100%;box-sizing:border-box;margin:12px 0;padding:12px}"
               "button{background:#196f58;color:white;border:0;border-radius:7px}</style>"
               "<h2>EcoSmart Wi-Fi Setup</h2>" + content + "</html>").encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path != "/":
            return self.page("Not found", 404)
        items = "".join("<option value='" + escape(ssid, quote=True) + "'>" + escape(ssid) + "</option>" for ssid in nearby_networks())
        self.page("<p>Choose a cached nearby network, or enter its exact SSID manually.</p>"
                  "<form action='/connect' method='post'>"
                  "<label>Nearby networks<select id='network' onchange=\"if(this.value)document.getElementById('ssid').value=this.value\">"
                  "<option value=''>Select (optional)</option>" + items + "</select></label>"
                  "<label>Wi-Fi name (SSID)<input id='ssid' name='ssid' required maxlength='32'></label>"
                  "<label>Wi-Fi password<input type='password' name='password' maxlength='63'></label>"
                  "<input type='hidden' name='token' value='" + TOKEN + "'>"
                  "<button type='submit'>Connect</button></form>"
                  "<p>Keep this phone near EcoSmart. The setup network will disappear on success.</p>")

    def do_POST(self):
        if self.path != "/connect":
            return self.page("Not found", 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                return self.page("Invalid request", 400)
            data = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            ssid = data.get("ssid", [""])[0].strip()
            password = data.get("password", [""])[0]
            if (data.get("token", [""])[0] != TOKEN or
                not (1 <= len(ssid.encode()) <= 32) or
                "\n" in ssid or "\r" in ssid or
                not (8 <= len(password) <= 63) or
                "\n" in password or "\r" in password):
                return self.page("Invalid SSID, password or request. WPA2 passwords require 8-63 characters.", 400)
            # File-based handoff avoids displaying passwords in a process argument list.
            fd = os.open(REQUEST_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as out:
                import json
                json.dump({"ssid": ssid, "password": password}, out)
            self.page("Connection attempt started. Wait up to one minute. "
                      "If it fails, reconnect to EcoSmart-Setup and try again.")
            subprocess.Popen(["/usr/bin/python3", "/usr/local/sbin/ecosmart-wifi-connect"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except FileExistsError:
            self.page("Another connection attempt is in progress. Try again soon.", 409)
        except Exception:
            self.page("Could not start connection. Try again.", 500)

if __name__ == "__main__":
    while True:
        try:
            server = ThreadingHTTPServer((HOST, PORT), Handler)
            server.serve_forever()
        except OSError:
            # Only listen when 10.42.0.1 exists. Never expose portal on Ethernet/Tailscale.
            time.sleep(5)
