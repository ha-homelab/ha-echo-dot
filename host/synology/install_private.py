#!/usr/bin/env python3
"""Run the already-authorized pilot installer without exposing Wi-Fi/ESPHome keys."""
import base64
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import time

serial, name = sys.argv[1:]
os.umask(0o077)
root = Path('/private')
wifi = json.loads((root / 'wifi.json').read_text())
assert wifi['ssid'] and wifi['password'], 'Expected a secured Wi-Fi network'
adb = ['adb', '-s', serial]
assert subprocess.check_output(adb + ['get-serialno']).decode().strip() == serial
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
log_path = root / f'echoctl-install-{stamp}.log'
command = ['echoctl', 'install', '--serial', serial, '--name', name,
           '--ssid', wifi['ssid'], '--password', wifi['password'], '--yes', '--reboot']
milestones = {
    'flashing boot': 'Installer is writing the prepared boot image',
    'patching': 'Installer is applying system patches',
    'waiting for device': 'Installer is waiting for the Echo to reconnect',
    'installing echod': 'Installer is installing the EchoLocal service',
    'configuring wi': 'Installer is configuring the saved Wi-Fi network',
    'rebooting': 'Installer is rebooting the Echo',
}
reported = set()
print('Installer started; detailed output is stored in a private log', flush=True)
with log_path.open('xb') as log:
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in process.stdout:
        log.write(line)
        log.flush()
        text = line.decode('utf-8', errors='replace').lower()
        for marker, safe_message in milestones.items():
            if marker in text and marker not in reported:
                print(safe_message, flush=True)
                reported.add(marker)
    code = process.wait()
print(f'Installer exit code: {code}', flush=True)
if code:
    sys.exit(code)

key = subprocess.check_output(adb + ['exec-out', 'cat', '/data/misc/echolocal/psk'], timeout=20).strip()
assert len(base64.b64decode(key, validate=True)) == 32, 'Unexpected ESPHome key format'
(root / 'esphome.psk').write_bytes(key + b'\n')
print('Unique ESPHome key validated and saved privately', flush=True)
# The service can be resident a few seconds before the supplicant socket is ready.
status = {}
for attempt in range(30):
    probe = subprocess.run(adb + ['shell', 'wpa_cli', '-p', '/data/misc/wifi/sockets',
                                  '-i', 'wlan0', 'status'],
                           timeout=20, capture_output=True, text=True)
    status = dict(line.split('=', 1) for line in probe.stdout.splitlines() if '=' in line)
    if probe.returncode == 0 and status.get('wpa_state') == 'COMPLETED':
        break
    time.sleep(2)
assert status.get('wpa_state') == 'COMPLETED', 'Wi-Fi association incomplete'
assert status.get('ssid') == wifi['ssid'], 'Unexpected Wi-Fi network'
address = str(ipaddress.ip_address(status['ip_address']))
sdk = subprocess.check_output(adb + ['shell', 'getprop', 'ro.build.version.sdk'], timeout=20).decode().strip()
service = subprocess.check_output(adb + ['shell', 'getprop', 'echolocal.state'], timeout=20).decode().strip()
assert sdk == '25' and service == 'resident', 'Unexpected SDK or EchoLocal service state'
result = {'serial': serial, 'name': name, 'ip': address, 'ssid': wifi['ssid'],
          'sdk': sdk, 'service': service, 'log_file': str(log_path), 'verified_at': stamp}
(root / 'install-result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
