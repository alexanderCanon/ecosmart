#!/usr/bin/env python3
"""Apply Wi-Fi profile and restore EcoSmart-Setup when joining fails."""
import json
import os
import subprocess
import time
import uuid

REQUEST_FILE = "/run/ecosmart-wifi-request"

def nm(*args, timeout=55, check=True):
    return subprocess.run(["nmcli", *args], timeout=timeout, check=check,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    # Let the HTTP response reach the phone before switching wireless modes.
    time.sleep(3)
    with open(REQUEST_FILE, encoding="utf-8") as handle:
        request = json.load(handle)
    os.unlink(REQUEST_FILE)

    profile_uuid = str(uuid.uuid4())
    path = "/etc/NetworkManager/system-connections/ecosmart-" + profile_uuid + ".nmconnection"
    ssid = request["ssid"]
    password = request["password"]
    # NetworkManager keyfile values must not contain line breaks.
    if any(c in ssid + password for c in "\n\r") or not (8 <= len(password) <= 63):
        return
    # Safe keyfile escaping for backslashes and semicolons in the SSID.
    safe_ssid = ssid.replace("\\", "\\\\").replace(";", "\\;")
    safe_password = password.replace("\\", "\\\\").replace(";", "\\;")
    profile = ("[connection]\n"
               "id=EcoSmart-WiFi-" + profile_uuid + "\n"
               "uuid=" + profile_uuid + "\n"
               "type=wifi\n"
               "interface-name=wlan0\n"
               "autoconnect=true\n"
               "[wifi]\n"
               "mode=infrastructure\n"
               "ssid=" + safe_ssid + "\n"
               "[wifi-security]\n"
               "key-mgmt=wpa-psk\n"
               "psk=" + safe_password + "\n"
               "[ipv4]\nmethod=auto\n"
               "[ipv6]\nmethod=auto\n")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            out.write(profile)
        nm("connection", "down", "EcoSmart-Setup", timeout=15, check=False)
        nm("connection", "load", path)
        nm("connection", "up", "uuid", profile_uuid, "ifname", "wlan0", timeout=60)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        nm("connection", "down", "uuid", profile_uuid, timeout=10, check=False)
        nm("connection", "delete", "uuid", profile_uuid, timeout=10, check=False)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        nm("connection", "up", "EcoSmart-Setup", "ifname", "wlan0", timeout=30, check=False)

if __name__ == "__main__":
    main()
