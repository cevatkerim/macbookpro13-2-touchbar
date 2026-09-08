# Reproduce the tested T1 activation

This procedure activated the Touch Bar on MacBookPro13,2 with a failed internal
SSD, Omarchy on an external SSD, Linux 7.1.9-arch1-2, and Apple's EmbeddedOS
3.0 build 14Y901. Both provisioning passes finished, FDR replay was byte-identical,
and the owner confirmed production Touch Bar icons and buttons. It remains an
experimental firmware workflow for this exact model/build. Cold-boot persistence
and suspend/resume are separate, unverified tests.

The [driver-only guide](../../driver/README.md) is sufficient when
production EmbeddedOS already boots. Recovery USB `05ac:1281` needs the workflow
below. Restore USB `05ac:8600` with one mux interface is not production activation.

## Prepare

Keep AC power connected and preserve your disk/EFI backups. This procedure does
not restore the host operating system, but phase 11 writes T1 firmware. A backup
of Linux files does not provide a T1 firmware rollback. Never use another Mac's
FDR data, ticket or personalized image. Keep all generated data and logs root
private; only generic source and patches belong in Git.

Clone the five upstream projects at the exact bases in `patches/SOURCES.txt`,
apply each project's patches with `git am`, and build as described in
[implementation.md](implementation.md#build-in-a-local-prefix). Apply the
idevicerestore patches in order: 0003, 0005, 0008, 0009, 0010. Use a local prefix;
do not replace distribution libraries or install a competing usbmuxd service.
The replay code and FDR memory option in 0010 are required for the live result.

Use this layout, setting `T1_WORK` to your actual workspace:

```text
t1-recovery/
  prefix/lib/                  # patched libirecovery and libtatsu
  src/idevicerestore/           # patched source and executable
  src/usbmuxd/                  # patched private daemon
  src/acpi_call/                # optional, patched module for verified FRST
  firmware/usr/standalone/firmware/iBridge1_1Customer.bundle/
```

Download the generic Apple package using the URL and pinned SHA-256 in
`inspect-firmware.py`, verify it before extraction, and inspect its manifest.
Do not execute an Apple installer on Linux. After extraction:

```bash
T1_WORK=/absolute/path/to/t1-recovery
T1_PREFIX="$T1_WORK/prefix"
T1_FW="$T1_WORK/firmware/usr/standalone/firmware/iBridge1_1Customer.bundle/Contents/Resources"
python3 "$T1_WORK/src/idevicerestore/scripts/t1-run.py" inspect \
  "$T1_FW" --prefix "$T1_PREFIX"
```

The compiled test suite must pass. Inspection checks identity and component
presence; Apple secure boot validates signatures on hardware. Signing and FDR
provisioning require access to Apple's services and send this T1's identifiers.
The tool keeps raw logs private and prints fixed status messages.

## Provisioning passes

The following block runs in a root Bash shell (`sudo -i`), with the three paths
above set again in that shell. It uses the tested private-daemon arrangement.
Stop any competing system usbmuxd and disconnect unrelated Apple devices first.
Each attempt directory must be new; never overwrite a failed attempt's evidence.

```bash
umask 077
T1_PRIVATE=/var/lib/t1-touchbar/private
install -d -m 0700 "$T1_PRIVATE"

run_pass() (
  set -e
  attempt="$1"
  input="${2:-}"
  mkdir -m 0700 "$attempt"
  mkdir -m 0700 "$attempt/mux-config"
  export LD_LIBRARY_PATH="$T1_PREFIX/lib"
  export USBMUXD_T1_RECOVERY=1
  export USBMUXD_SOCKET_ADDRESS="UNIX:$attempt/mux.sock"
  unset LD_PRELOAD
  "$T1_WORK/src/usbmuxd/src/usbmuxd" -f -p \
    -C "$attempt/mux-config" -S "$attempt/mux.sock" -P NONE \
    >"$attempt/mux.private.log" 2>&1 &
  mux_pid=$!
  trap 'kill "$mux_pid" 2>/dev/null || true; wait "$mux_pid" 2>/dev/null || true' EXIT
  for i in {1..50}; do
    kill -0 "$mux_pid"
    [[ -S "$attempt/mux.sock" ]] && break
    sleep 0.1
  done
  [[ -S "$attempt/mux.sock" ]]
  chmod 0600 "$attempt/mux.sock"
  args=()
  [[ -z "$input" ]] || args+=(--fdr-input "$input")
  python3 "$T1_WORK/src/idevicerestore/scripts/t1-run.py" provision \
    "$T1_FW" --prefix "$T1_PREFIX" --private "$attempt" "${args[@]}"
)

run_pass "$T1_PRIVATE/pass-a"
```

Require exit zero and `phase 11 finished`. On our successful passes the data
requests were NORData, RootTicket, FDRTrustData, FDRMemoryCommit, FUDData,
FDRMemoryCommit. Unknown requests or nonzero final status stop the transaction.
FDRMemoryStorePath selects memory storage; without it this T1 failed with status
52 because no system partition was mounted. FDRData is saved atomically as a
binary plist before acknowledgement. Do not print its contents.

Wait at least ten seconds after successful completion, then return only the T1
to recovery. Our machine's independently inspected ACPI table defines
`\_SB.PCI0.XHC1.RHUB.ASOC.FRST`. The patched acpi_call module built for the running
kernel executed it successfully while the host stayed up. Confirm the method in
your own ACPI table before using the same path; do not substitute `SOCW(1)`.

With that verification complete, in the root shell:

```bash
sleep 10
insmod "$T1_WORK/src/acpi_call/acpi_call.ko"
printf '%s' '\_SB.PCI0.XHC1.RHUB.ASOC.FRST' > /proc/acpi/call
tr -cd '[:print:]' < /proc/acpi/call
rmmod acpi_call
```

Require result `0x0` and recovery USB `05ac:1281` before continuing. The launcher
selects the physical T1's ECID internally, and the pass-B input must match it.

```bash
run_pass "$T1_PRIVATE/pass-b" "$T1_PRIVATE/pass-a"
cmp -s "$T1_PRIVATE/pass-a/FDRData" "$T1_PRIVATE/pass-b/FDRData"
```

Require both commands to succeed. The tool only marks the captured pair complete
after successful final status, FDR commits and matching replay. Back up the
complete `preflight.plist`, `device.plist` and `FDRData` privately on separate
storage now. The image and ticket must stay together; do not obtain a new ticket
for production replay.

## Boot production and test the driver

Install the [tested DKMS package](../../driver/README.md), then load:

```bash
modprobe apple_ibridge skip_acpi_power=1
modprobe apple_touchbar
```

After another minimum ten-second wait, stop the private mux daemon (the function
above already does this), use the verified T1-only FRST again, and wait for
`05ac:1281`. Do not upload iBEC for this production phase.

Use a new replay directory containing only the completed pair and provenance:

```bash
mkdir -m 0700 "$T1_PRIVATE/phase14"
cp "$T1_PRIVATE/pass-b/"{preflight.plist,device.plist,FDRData} "$T1_PRIVATE/phase14/"
chmod 0600 "$T1_PRIVATE/phase14/"*
python3 "$T1_WORK/src/idevicerestore/scripts/t1-run.py" replay \
  "$T1_FW" --prefix "$T1_PREFIX" --private "$T1_PRIVATE/phase14"
```

The tool validates the complete saved pair, saves auto-boot=false, uploads the
bare concatenation of four personalized IMG4 components (OSRamdisk, KernelCache,
DeviceTree, SEP), sets boot-args=rd=md0, and issues blind memboot with bRequest=1.
The standalone ticket transaction is conditional on IBFL bit 1, following Apple's
native controller. On our 0x3d device that bit was clear; forcing `ticket` produced
PIPE, even with a delay. The successful image still contains and validates the
exact original ticket in every component.

Observe production USB for at least 30 seconds and check actual driver ownership.
Our configuration 1 exposed four interfaces, including two physical HIDs; those
bound to apple-ibridge-hid and created two virtual 1d6b:0301 Touch Bar devices
bound to apple-touchbar. Check icons and a button physically. USB ID or dispatch
exit zero alone is insufficient. Keep the image off EFI if these checks fail.

## Stage the proven firmware for later boots

Use the actual mounted EFI partition, preserving its existing EmbeddedOS files
privately before changing anything. Our external SSD ESP is mounted at `/boot`;
other installations may use `/boot/efi`. In the root shell, set `T1_ESP` to that
mount's `EFI/APPLE/EMBEDDEDOS` directory. Only after the exact pair above boots and
its Touch Bar works, stage the three files through temporary names:

```bash
export T1_WORK T1_PRIVATE
export T1_ESP=/boot/EFI/APPLE/EMBEDDEDOS
python3 - <<'PY'
import os, plistlib
from pathlib import Path
src = Path(os.environ['T1_PRIVATE'])/'phase14'
dst = Path(os.environ['T1_ESP'])
pair = plistlib.loads((src/'preflight.plist').read_bytes())
assert pair['RestoreFinished'] is True and pair['FDRReplayed'] is True
version = Path(os.environ['T1_WORK'])/'firmware/usr/standalone/firmware/iBridge1_1Customer.bundle/Contents/version.plist'
files = {'combined.memboot': pair['Image'], 'FDRData': (src/'FDRData').read_bytes(),
         'version.plist': version.read_bytes()}
dst.mkdir(parents=True, exist_ok=True)
for name, data in files.items():
    tmp = dst/('.'+name+'.new')
    with tmp.open('xb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, dst/name)
    assert (dst/name).read_bytes() == data
PY
sync -f "$T1_ESP"
```

The private source files stay mode 0600. FAT's visible permissions come from its
mount options; this machine uses fmask/dmask 0077. Never commit these files.
Keep the completed pair on Linux storage and its separate backup even after EFI
staging. Do not automatically reboot to finish installation. At a later planned
reboot, check whether production firmware and the Touch Bar return. External-SSD
EFI discovery with a failed internal SSD is not established by our live test.

If Linux starts with T1 in recovery, the same completed pair can be copied into
a fresh private replay directory and replayed again; this is the manual fallback
to test before designing any boot service. Do not repeat provisioning or fetch a
new ticket merely because the host rebooted. No automatic firmware boot service
is installed by this repository. Restore prior EFI files from the private backup
if later troubleshooting requires undoing EFI staging.
