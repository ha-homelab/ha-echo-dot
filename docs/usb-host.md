# USB host: Synology container and native Linux fallback

This guide prepares a host for the [conversion runbook](../research/conversion.md). It does not replace the device checkpoints in that runbook. Hardware scope is described in the [compatibility guide](hardware-compatibility.md).

The completed pilot used an **x86-64 Synology DS620slim, DSM 7.3.2, Linux 4.4.302+ and Docker 24.0.2**, with the Dot connected directly to the NAS. No VM passthrough was involved. Other NAS architectures need separate validation; an ARM or MIPS host cannot run the pinned x86 binaries merely because it runs Linux.

The container receives USB device nodes for **one exact serial on one physical port**. It has no network, no additional capabilities and no access to the host's entire `/dev/bus/usb`. The Echo's later Wi-Fi connection is independent of this host isolation.

## 1. Stage the source and downloads

On your workstation, start in the project directory containing `host/`, `docs/` and `research/`. Download the three pinned artifacts from the [conversion guide](../research/conversion.md#2-pin-and-verify-the-artifacts) into `downloads/`. The XDA attachment may need a browser download. Do not run downloaded code yet.

To copy the host files to a NAS, substitute your own SSH account and hostname in these commands:

```bash
ssh NAS_USER@NAS_HOST 'umask 077; mkdir -p ha-echo-dot-staging/host/synology ha-echo-dot-staging/downloads'
scp -O host/synology/Dockerfile host/synology/usb_proxy.py host/synology/backup_postunlock.py host/synology/install_private.py NAS_USER@NAS_HOST:ha-echo-dot-staging/host/synology/
scp -O downloads/amonet-biscuit-v2.0.0.zip downloads/echolocal_linux_x86_64 downloads/update-kindle-biscuit_puffin-NS6574_user_7623_0013121734532.bin NAS_USER@NAS_HOST:ha-echo-dot-staging/downloads/
```

The pilot NAS rejected the modern SFTP-based `scp` transfer; `-O` selects the legacy SCP protocol that worked there. Hosts with working SFTP may omit it. SSH still protects the transport in either case.

On the NAS, locate the absolute staging path with `cd ~/ha-echo-dot-staging` followed by `pwd -P`. Open an authorized root shell with `sudo -i`, then `bash`. The remaining Synology commands run **on the NAS in that root Bash session**, not on the workstation. Keep this terminal open while using the host adapters.

Set your paths. Replace `HAE_STAGE` with the path just observed. The dedicated root path may be changed, but the proxy helper currently requires its destination to contain `/ha-echo-dot/private/` and end in `/usb-proxy`. The helper also accepts the historical `/ha-echo/private/` host directory for existing installations; renaming the workstation project does not rename a running NAS deployment.

```bash
umask 077
HAE_STAGE='/absolute/path/to/ha-echo-dot-staging'
HAE_ROOT='/volume1/docker/ha-echo-dot'
HAE_PRIVATE="$HAE_ROOT/private/pilot"
HAE_PROXY_DIR="$HAE_ROOT/private/pilot-usb/usb-proxy"
HAE_DOCKER='/usr/local/bin/docker'
HAE_IMAGE='ha-echo-dot-host:0.0.8'
HAE_CONTAINER='ha-echo-dot-usb'

mkdir -p "$HAE_ROOT/host/synology" "$HAE_ROOT/downloads" "$HAE_ROOT/vendor" "$HAE_ROOT/build-context"
mkdir -p "$HAE_PRIVATE/backups" "$HAE_PROXY_DIR"
chmod 0700 "$HAE_ROOT/private" "$HAE_PRIVATE" "$HAE_PRIVATE/backups" "$HAE_ROOT/private/pilot-usb" "$HAE_PROXY_DIR"
install -m 0644 "$HAE_STAGE/host/synology/Dockerfile" "$HAE_ROOT/host/synology/Dockerfile"
for helper in usb_proxy.py backup_postunlock.py install_private.py; do
  install -m 0644 "$HAE_STAGE/host/synology/$helper" "$HAE_ROOT/host/synology/$helper"
done
for artifact in amonet-biscuit-v2.0.0.zip echolocal_linux_x86_64 update-kindle-biscuit_puffin-NS6574_user_7623_0013121734532.bin; do
  install -m 0600 "$HAE_STAGE/downloads/$artifact" "$HAE_ROOT/downloads/$artifact"
done
```

Use a new private device directory and separate proxy directory for every later Dot. Keep `HAE_PROXY_DIR` outside `HAE_PRIVATE`: otherwise the writable `/private` bind would create a second, writable path to the proxy nodes. Do not share credentials, backups or proxy directories across concurrent sessions. Check free space before backing up; leave several GiB per device, with more space for uncompressed images.

## 2. Verify files and build the image

The following expected hashes are fixed values from the pilot, not generated from the files being checked:

```bash
cat > "$HAE_ROOT/downloads/SHA256SUMS" <<'SUMS'
a350601761bc52ef865eba63b7117e6a63315c9541a780bd1f6d6984b7bde396  echolocal_linux_x86_64
98297293701082bc7272efe077f941c56fc7b6e1f27ef6f2e93b6e4c6fc7b62d  amonet-biscuit-v2.0.0.zip
64ab6d2dd85f8093abdd62c275d229c7e9fdd68e4d46892b48bdbd1d100d46d8  update-kindle-biscuit_puffin-NS6574_user_7623_0013121734532.bin
SUMS
(cd "$HAE_ROOT/downloads" && sha256sum -c SHA256SUMS)
```

**Require all three `OK` results before building or extracting.** The [Dockerfile](../host/synology/Dockerfile) expects the binary at the root of its build context. Create a minimal context rather than sending private files to Docker:

```bash
install -m 0644 "$HAE_ROOT/host/synology/Dockerfile" "$HAE_ROOT/build-context/Dockerfile"
install -m 0644 "$HAE_ROOT/downloads/echolocal_linux_x86_64" "$HAE_ROOT/build-context/echolocal_linux_x86_64"
"$HAE_DOCKER" build -t "$HAE_IMAGE" "$HAE_ROOT/build-context"
"$HAE_DOCKER" image inspect "$HAE_IMAGE" --format '{{.Id}}'
```

Building needs package-network access; the later hardware container does not. The Dockerfile pins Debian's base digest and validates EchoLocal's SHA-256, but **APT package versions are not pinned**. These commands reproduce the environment setup, not necessarily the exact image bytes. The pilot image ID was `sha256:16472eaa7d93320b75501c3ec94cf111a9e317264adcfc909033f8d64c2eb85f`; record your own image ID and tool versions.

Extract the verified ZIP in an isolated utility container. It contains a top-level `amonet/` directory, so extract to `vendor/`, not `vendor/amonet/`:

```bash
"$HAE_DOCKER" run --rm -i --network none --cap-drop ALL --read-only \
  --security-opt no-new-privileges:true \
  --mount "type=bind,src=$HAE_ROOT/downloads,dst=/downloads,readonly" \
  --mount "type=bind,src=$HAE_ROOT/vendor,dst=/vendor" \
  "$HAE_IMAGE" python3 - <<'PYZIP'
from pathlib import Path
import stat
import zipfile
root = Path('/vendor').resolve()
assert not (root / 'amonet').exists(), 'Use a fresh extraction directory'
with zipfile.ZipFile('/downloads/amonet-biscuit-v2.0.0.zip') as archive:
    assert archive.testzip() is None, 'ZIP CRC failure'
    for entry in archive.infolist():
        (root / entry.filename).resolve().relative_to(root)
        assert not stat.S_ISLNK(entry.external_attr >> 16), 'Unexpected symlink'
    archive.extractall(root)
PYZIP
chmod 0755 "$HAE_ROOT/vendor/amonet/fastbrick.sh" "$HAE_ROOT/vendor/amonet/bin/fastboot" "$HAE_ROOT/vendor/amonet/bin/fastboot32"
```

Keep the bundled fastboot. The author's brick command uses a modified version; the distribution's fastboot is only a diagnostic dependency here. The vendor working copy is mounted writable because `fastbrick.sh` calls `chmod` on its bundled tools. The original ZIP stays read-only inside the hardware container.

## 3. Identify the USB port and serial

Connect one Dot, then enter stock fastboot as described in the conversion runbook: hold Action while reconnecting power, release on the green ring. A stock Dot need not offer ADB during normal operation. A brief USB appearance followed by disconnect is not, by itself, proof of a bad cable.

On the NAS, inspect USB metadata privately:

```bash
python3 - <<'PYUSB'
from pathlib import Path
for device in sorted(Path('/sys/bus/usb/devices').glob('*')):
    if not (device / 'idVendor').exists():
        continue
    def value(name):
        try:
            return (device / name).read_text().strip()
        except OSError:
            return ''
    print(device.name, value('idVendor') + ':' + value('idProduct'),
          value('product'), value('serial'), value('busnum'), value('devnum'))
PYUSB
```

Identify the newly attached Dot and compare its serial with the device's label/private inventory. Do not choose an existing storage device, accelerator or USB hub. Set these values from that observation:

```bash
ECHO_SERIAL='REPLACE_WITH_EXACT_ECHO_SERIAL'
HAE_USB_PORT='REPLACE_WITH_SYSFS_PORT'
ECHO_NAME='echo-living-room'
OTA_FILE='/downloads/update-kindle-biscuit_puffin-NS6574_user_7623_0013121734532.bin'
```

`HAE_USB_PORT` is a physical sysfs name such as `1-1`, not a transient `/dev/bus/usb/BBB/DDD` address. That example is not a discovery result. Select the final device name before HA pairing.

## 4. Start the serial-pinned proxy and hardware container

The [proxy helper](../host/synology/usb_proxy.py) validates the port's serial, usbfs major/minor, actual character device and a second identity snapshot before publishing a node. It updates that node on re-enumeration and removes it on disconnect. It never modifies the real `/dev` tree. Do not run Python with `-O`: the helper uses assertions for several checks.

Confirm that `HAE_CONTAINER` does not name an existing container you need to retain. Check that no other ADB server/container owns this Echo before starting; two owners can compete for its USB interface. Run one host session through backup and installation, or stop the previous one before replacement.

```bash
"$HAE_DOCKER" ps -a --filter "name=^/${HAE_CONTAINER}$"
python3 "$HAE_ROOT/host/synology/usb_proxy.py" \
  "$HAE_USB_PORT" "$ECHO_SERIAL" "$HAE_PROXY_DIR" \
  > "$HAE_PRIVATE/usb-proxy.log" 2>&1 &
HAE_PROXY_PID=$!
```

Check that the watcher is alive and its private log reports an exposed, verified Echo before creating the container. If identity is absent or different, fix the physical selection; do not broaden the match.

```bash
kill -0 "$HAE_PROXY_PID"
cat "$HAE_PRIVATE/usb-proxy.log"
"$HAE_DOCKER" run -d --name "$HAE_CONTAINER" \
  --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --device-cgroup-rule='c 189:* rw' \
  --env ADB_LIBUSB=0 \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777,size=256m \
  --tmpfs /root/.android:rw,nosuid,nodev,mode=0700,size=16m \
  --mount "type=bind,src=$HAE_PROXY_DIR,dst=/dev/bus/usb,readonly" \
  --mount "type=bind,src=$HAE_PRIVATE,dst=/private" \
  --mount "type=bind,src=$HAE_ROOT/downloads,dst=/downloads,readonly" \
  --mount "type=bind,src=$HAE_ROOT/host/synology,dst=/helpers,readonly" \
  --mount "type=bind,src=$HAE_ROOT/vendor/amonet,dst=/work/amonet" \
  "$HAE_IMAGE" sleep infinity
```

Require a successful container start. Then keep a guard running to stop it if its watcher dies, and arrange cleanup when this root shell exits:

```bash
(
  while kill -0 "$HAE_PROXY_PID" 2>/dev/null; do sleep 1; done
  "$HAE_DOCKER" stop -t 2 "$HAE_CONTAINER" >/dev/null 2>&1 || true
) &
HAE_GUARD_PID=$!

cleanup_usb() {
  "$HAE_DOCKER" rm -f "$HAE_CONTAINER" >/dev/null 2>&1 || true
  kill -TERM "$HAE_PROXY_PID" 2>/dev/null || true
  wait "$HAE_PROXY_PID" 2>/dev/null || true
  kill "$HAE_GUARD_PID" 2>/dev/null || true
  wait "$HAE_GUARD_PID" 2>/dev/null || true
}
trap cleanup_usb EXIT
trap 'exit 130' INT
trap 'exit 143' HUP TERM
```

A read-only bind prevents changing the proxy directory through that mount; it **does not** prevent USB writes through its character devices. Those writes are the purpose of the scoped `rw` cgroup rule. No `m` permission or MKNOD capability is granted. `/sys` can still expose metadata about other USB devices; the isolation claim concerns accessible device nodes, not hidden metadata. The tmpfs mounts provide runtime storage needed by ADB and echoctl despite the read-only root filesystem.

Do not delete/recreate the proxy root directory while mounted. Do not place it on a filesystem mounted `nodev`. The watcher polls every 0.5 seconds: this is a practical serial-pinned tool boundary, not a guarantee against every device-number-reuse race. If the watcher is killed uncleanly, stop the container immediately; restarting the helper clears its old proxy nodes. Never resolve an access failure by adding `--privileged` or mounting all host USB devices. [Docker device rules](https://docs.docker.com/reference/cli/docker/container/run/), [network-none behavior](https://docs.docker.com/engine/network/drivers/none/).

## 5. Define host adapters and check the tools

These functions are defined in the same NAS root Bash session. `adbe` never allocates a TTY, so binary `exec-out` remains safe. Only the interactive unlock script uses `-it`.

```bash
adbe() {
  kill -0 "$HAE_PROXY_PID" 2>/dev/null || return 1
  "$HAE_DOCKER" exec "$HAE_CONTAINER" adb -s "$ECHO_SERIAL" "$@"
}
fbe() {
  kill -0 "$HAE_PROXY_PID" 2>/dev/null || return 1
  "$HAE_DOCKER" exec -w /work/amonet "$HAE_CONTAINER" ./bin/fastboot -s "$ECHO_SERIAL" "$@"
}
run_fastbrick() {
  kill -0 "$HAE_PROXY_PID" 2>/dev/null || return 1
  "$HAE_DOCKER" exec -it -e TERM=xterm -w /work/amonet "$HAE_CONTAINER" bash ./fastbrick.sh
}
backup_echo() {
  HAE_BACKUP_NAME="postunlock-$(date -u +%Y%m%dT%H%M%SZ)"
  printf 'Private backup directory: %s/backups/%s\n' "$HAE_PRIVATE" "$HAE_BACKUP_NAME"
  "$HAE_DOCKER" exec "$HAE_CONTAINER" python3 /helpers/backup_postunlock.py \
    "$ECHO_SERIAL" "/private/backups/$HAE_BACKUP_NAME"
}
install_echo_private() {
  local stamp result
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  "$HAE_DOCKER" exec "$HAE_CONTAINER" python3 /helpers/install_private.py \
    "$ECHO_SERIAL" "$ECHO_NAME" > "$HAE_PRIVATE/install-wrapper-$stamp.log" 2>&1
  result=$?
  printf 'Installer wrapper exit code: %s; details remain in the private directory.\n' "$result"
  return "$result"
}

"$HAE_DOCKER" exec "$HAE_CONTAINER" adb version
"$HAE_DOCKER" exec "$HAE_CONTAINER" echoctl --version
"$HAE_DOCKER" exec "$HAE_CONTAINER" python3 --version
fbe --version
```

The pilot used ADB 1.0.41 / Debian platform-tools 29.0.6, Python 3.11.2, EchoLocal 0.0.8 and bundled fastboot `28.0.0 rc1-eng.chaosm.20190910.064622`. Record the actual rebuilt versions. `ADB_LIBUSB=0` selects the native polling backend in the tested ADB build, which survived the pilot's recovery and Android re-enumerations. [ADB backend option](https://android.googlesource.com/platform/packages/modules/adb/+/refs/tags/android-16.0.0_r4/docs/user/adb.1.md).

If a rebooted Echo disappears from ADB, first check the host watcher, exact serial and newly exposed node. Once the new node is confirmed and no transfer is running, restarting **only this container's ADB server** can force rediscovery:

```bash
"$HAE_DOCKER" exec "$HAE_CONTAINER" adb kill-server
"$HAE_DOCKER" exec "$HAE_CONTAINER" adb start-server
adbe get-state
```

Do not interrupt a raw backup, OTA write or boot-image write to do this. A state of `device` is expected in Android and `recovery` in TWRP; an unexpected serial change is not automatically accepted.

## 6. Prepare private Wi-Fi input

Run this in the NAS root terminal before the EchoLocal stage. It prompts on the terminal, hides the password and refuses to overwrite an existing `wifi.json`. Use a compatible secured network; the wrapper expects both SSID and password. The Wi-Fi implementation supports WPA2 and compatible transition networks, not arbitrary enterprise or WPA3-only provisioning.

```bash
python3 -c '
import getpass, json, os, sys
os.umask(0o077)
ssid = input("Wi-Fi SSID: ")
password = getpass.getpass("Wi-Fi password or 64-digit hexadecimal PSK: ")
assert ssid and password
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as target:
    json.dump({"ssid": ssid, "password": password}, target)
    target.write("\n")
' "$HAE_PRIVATE/wifi.json"
```

Do not paste the password into shell history, source code or a shared transcript. Existing credentials may be recovered separately from a private backup, but this guide does not print or blindly restore the old supplicant configuration.

The install helper captures CLI stdout/stderr because the CLI prints its pairing key and some errors may include credentials. The helper's own final output includes identifying metadata such as IP/SSID/serial; the adapter therefore captures that output too. `/private/esphome.psk`, `install-result.json` and detailed logs remain inside the host's private directory. File modes are 0600 under the private umask. The subprocess still receives Wi-Fi credentials in its argument list; sufficiently privileged local process inspection can see them temporarily.

## 7. Run the conversion, then release USB access

Return to [step 3 of the conversion runbook](../research/conversion.md#3-unlock-the-selected-stock-dot). Its checkpoints control the sequence: identity → unlock → TWRP → unmounted verified backup → two-slot OTA → install → private PSK → HA.

Before a backup, manually inspect `/proc/mounts`, resolve any block-device aliases and unmount **all eMMC-backed filesystems**. The current helper's guard only searches for the literal `/dev/block/mmcblk0` in mount output; it does not prove that every possible alias is unmounted. Keep recovery idle during the raw read. Do not use an unverified, still-growing or `.partial` image as permission to erase data.

After successful pairing and the basic voice test, stop the container **before** stopping its proxy:

```bash
cleanup_usb
trap - EXIT INT HUP TERM
find "$HAE_PROXY_DIR" -type c -print
```

The final command should print no character devices. If unclean termination left a node, keep the container stopped and run the proxy helper once under supervision, then stop it normally; it clears its own nodes. Do not remove or alter real `/dev/bus/usb` entries. The Dot may stay on USB power and use its own Wi-Fi without the container or proxy.

## Native x86-64 Linux fallback

A directly attached x86-64 Linux computer avoids NAS-specific USB handling. This fallback uses the same pinned amonet package, raw-backup helper and conversion checkpoints. The NAS pilot proves the artifacts; this complete native workflow has not been independently repeated.

Install Bash, Python 3, ADB, fastboot, coreutils, unzip and the libraries needed by the bundled fastboot. On Debian/Ubuntu the package preparation is:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends bash python3 python3-serial adb fastboot coreutils unzip ca-certificates
```

Use either configured udev permissions or one dedicated root Bash session. Do not mix competing root/user ADB servers. Disconnect other fastboot targets. If ModemManager interferes with a serial-mode recovery branch, handle that separately; the main route does not require globally disabling it by default.

In that Linux session, define paths and identity from your own observations:

```bash
umask 077
HAE_ROOT='/absolute/path/to/ha-echo-dot'
HAE_PRIVATE="$HAE_ROOT/private/pilot"
ECHO_SERIAL='REPLACE_WITH_EXACT_ECHO_SERIAL'
ECHO_NAME='echo-living-room'
ECHOCTL="$HAE_ROOT/downloads/echolocal_linux_x86_64"
OTA_FILE="$HAE_ROOT/downloads/update-kindle-biscuit_puffin-NS6574_user_7623_0013121734532.bin"
mkdir -p "$HAE_PRIVATE/backups" "$HAE_ROOT/vendor"
chmod 0700 "$HAE_ROOT/private" "$HAE_PRIVATE" "$HAE_PRIVATE/backups"
```

Save the exact `SHA256SUMS` block from section 2 in this host's `downloads/`, then verify all three results. Extract the verified ZIP once to `vendor/`; it supplies `vendor/amonet/`:

```bash
(cd "$HAE_ROOT/downloads" && sha256sum -c SHA256SUMS)
unzip -t "$HAE_ROOT/downloads/amonet-biscuit-v2.0.0.zip"
unzip "$HAE_ROOT/downloads/amonet-biscuit-v2.0.0.zip" -d "$HAE_ROOT/vendor"
chmod 0755 "$ECHOCTL" "$HAE_ROOT/vendor/amonet/fastbrick.sh" "$HAE_ROOT/vendor/amonet/bin/fastboot" "$HAE_ROOT/vendor/amonet/bin/fastboot32"
adb version
"$ECHOCTL" --version
"$HAE_ROOT/vendor/amonet/bin/fastboot" --version
```

Define the conversion adapters. This private installer runner has no live progress output; wait for it to exit and inspect its private log on failure. Unlike the Synology wrapper, it leaves Wi-Fi/service completion checks to the explicit conversion checkpoint.

```bash
adbe() { adb -s "$ECHO_SERIAL" "$@"; }
fbe() { "$HAE_ROOT/vendor/amonet/bin/fastboot" -s "$ECHO_SERIAL" "$@"; }
run_fastbrick() { (cd "$HAE_ROOT/vendor/amonet" && bash ./fastbrick.sh); }
backup_echo() {
  HAE_BACKUP_NAME="postunlock-$(date -u +%Y%m%dT%H%M%SZ)"
  python3 "$HAE_ROOT/host/synology/backup_postunlock.py" \
    "$ECHO_SERIAL" "$HAE_PRIVATE/backups/$HAE_BACKUP_NAME"
}
install_echo_private() {
  python3 - "$HAE_PRIVATE" "$ECHO_SERIAL" "$ECHO_NAME" "$ECHOCTL" <<'PYINSTALL'
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
os.umask(0o077)
root, serial, name, binary = sys.argv[1:]
root = Path(root)
wifi = json.loads((root / 'wifi.json').read_text())
assert wifi['ssid'] and wifi['password']
assert subprocess.check_output(['adb', '-s', serial, 'get-serialno']).decode().strip() == serial
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
with (root / ('echoctl-install-' + stamp + '.log')).open('xb') as log:
    result = subprocess.run([binary, 'install', '--serial', serial, '--name', name,
        '--ssid', wifi['ssid'], '--password', wifi['password'], '--yes', '--reboot'],
        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
print('Installer exit code:', result.returncode)
if result.returncode:
    sys.exit(result.returncode)
key = subprocess.check_output(['adb', '-s', serial, 'exec-out', 'cat',
    '/data/misc/echolocal/psk'], timeout=20).strip()
assert len(base64.b64decode(key, validate=True)) == 32
(root / 'esphome.psk').write_bytes(key + b'\n')
os.chmod(root / 'esphome.psk', 0o600)
print('Pairing key saved privately; continue with the Wi-Fi and service checkpoints.')
PYINSTALL
}
```

Create `wifi.json` with section 6's private prompt in this Linux terminal, then follow the conversion runbook. Never substitute ordinary fastboot for amonet's bundled tool. Windows users should follow the author's Windows entrypoint and choose a binary-safe backup method; these Bash redirections are not a claim about every PowerShell version. macOS is useful after unlock, but is not the verified initial-unlock host here.

## Sanitized pilot evidence and remaining tests

The pilot confirmed the complete no-disassembly route on one Dot 2: TWRP 3.7.0_9-0 with root and unchanged serial; raw eMMC plus both boot-area backups verified by size and SHA-256; two successful inactive-slot OTA passes; independent read-only inspection of both Fire OS system partitions; and EchoLocal 0.0.8 running after its installer reboot.

The original LK build was `a828f29-20210822_210511`; amonet selected its default `fastbrick.img`. Main eMMC size was 3,909,091,328 bytes, with two 4,194,304-byte boot areas. Compressed backup sizes were 1,568,098,663, 203,159 and 20,882 bytes; these sizes are observations, not checksums or expectations for another device. Partial earlier reads were not counted as backups. File staging required `scp -O` because the NAS's SFTP transfer path failed.

The first EchoLocal attempt exceeded its 10-second old-service stop timeout. After `init.svc.ledcontroller` reached `stopped`, an idempotent retry with explicit `--reboot` succeeded without another wipe. `resident` arrived before the Wi-Fi socket, so the helper separately waits for `wpa_cli` readiness. The isolated container survived USB re-enumeration using the native ADB backend. Pairing, a Russian announcement and a user-confirmed spoken command/reply all succeeded; afterward the container and proxy were stopped.

**Still unverified:** a cold power cycle, a full command/false-trigger sample, recovery after HA restart and a 24-hour soak. One basic voice success is not a completed batch-acceptance test. Device identities, network details, keys, raw logs and backup manifests belong in private records, not in this public-facing guide.
