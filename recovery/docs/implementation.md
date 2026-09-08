# Experimental T1 EmbeddedOS support (Linux only)

This is a new implementation based on the public runbook, **not** the author's
unpublished patch. **Both provisioning passes and production boot succeeded; the owner
confirmed Touch Bar icons and buttons**:
https://gist.github.com/tigercosmos/ecbfe1fc20b7303c1808d3ab74af1f5b

Scope is deliberately restricted to x619ap, chip 0x8002, board 0x12, Image4-capable
T1 recovery USB 05ac:1281, EmbeddedOS 3.0 build 14Y901. This branch was built on
Omarchy/Arch, Linux 7.1.9, gcc 16.2.1. It does not implement Touch Bar HID drivers.

## Implementation

`t1.c` is an independent entry point selected before the generic restore logic.
`t1_policy.c` contains the offline-testable policy, private storage, bounded DER
parser, and phase-14 command sequence. Ordinary invocation retains upstream
behavior; any `IDEVICERESTORE_T1_` variable routes into validation and cannot fall
through to a generic restore. **Do not copy the gist's shell commands unchanged.**
This implementation uses the explicit modes below and rejects legacy research
variables. Its image/ticket interface intentionally uses a single binary-plist
bundle to prevent mixing separate files from different personalization requests.

Implemented:

- Preflight requests an Apple ticket and constructs/validates the image locally.
  It exits before iBEC upload and writes only an incomplete preflight-only.plist;
  replay rejects this file. It does not start restored or require usbmuxd.
- T1 signing uses the accompanying libtatsu verified-HTTPS API, restricted to
  https://gs.apple.com/TSS/controller?action=2 with certificate/hostname checking,
  no redirects or HTTP fallback, bounded timeouts, and failure on transport errors.
  The tool includes Apple's public Root CA for this connection only. The CA was
  downloaded over normally verified HTTPS from Apple's PKI link and its DER
  SHA-256 checked: b0b1730ecbc7ff4505142c49f1295e6eda6bcaed7e2c68c5be91b5a11001f024.
  No system-wide certificate trust change or disabled verification is required.

- Identity/build restriction and explicit ECID selection; validate the physical
  recovery device and restored HardwareInfo against the selected chip/board/ECID.
- Phase 11 bypasses OS/filesystem extraction and generic partition restore options.
  Options set ApBootstrapOnly=false, PersonalizedDuringPreflight=true,
  FlashNOR=true, ShouldRestoreSystemImage=false, CreateFilesystemPartitions=false,
  UpdateBaseband=false, FDRMemoryStorePath="FDRData". The latter selects memory
  storage on EmbeddedOS; the host saves inside its private dirfd. SystemImage,
  RootToInstall and BootImageTagOverride are absent.
- Only NORData, RootTicket, FDRTrustData, FDRMemoryCommit and FUDData accepted.
  Unsupported messages, asynchronous requests and alternate data ports stop the
  session. No filesystem or baseband request reaches a generic handler.
- FDR commit writes a binary plist atomically before acknowledging the request;
  input FDR is added as FDRMemoryStoreData in the RootTicket reply. Input directory
  must contain provenance from the same ECID. Replay output is compared using
  binary serialization. Different ordering may cause a conservative rejection.
- The initial TSS response is retained through iBEC, restored and preflight
  capture; no second signing request is made after iBEC. The four personalized IMG4 objects are concatenated in the order
  OSRamdisk, KernelCache, DeviceTree, SEP with no padding or 2GMI header.
- Every saved object's DER structure/tag and embedded ticket are checked. The
  bundle is atomically saved before phase 11; it is marked complete only after
  successful final status, FDR commit, and (for pass B) matching FDR replay.
- Phase 14 requires a completed pass-B bundle, matching ECID, and a minimum
  ten-second wait. It never requests a new ticket or uploads iBEC. It sends
  auto-boot=false and saveenv, then the saved image, boot-args=rd=md0 and memboot
  with USB bRequest=1. A separate saved-ticket upload/ticket command is included
  only when the connected bootloader requests it through IBFL bit 1. Embedded
  tickets are checked in all four image components regardless of that bit.
- T1 commands check the actual USB control-transfer length. The upstream helper
  discards that result; it is not used for T1 command dispatch. A disconnect
  during a boot command can therefore conservatively be reported as failure.
- Live modes require root and a pre-existing root-owned mode-0700 directory.
  Private files use mode 0600, exclusive creation/atomic replacement, no symlink
  traversal, no special files or hardlinks. Raw stdout/stderr go into a private
  log; only fixed status messages and whitelisted request names reach the console.
  A fresh directory is required for each provision attempt. Replay log is also
  exclusive: an existing log blocks accidental repeat dispatch.

## Remaining protocol uncertainties

Apple's MobileDevice framework saves FDRMemoryStoreData and acknowledges the
commit with an empty dictionary. The restore executable selects Memory storage
when FDRMemoryStorePath is present. The implementation follows these behaviors,
accepting one nonempty dictionary at the request root or under Arguments. It
also accepts the earlier inferred FDRMemoryStore spelling. Ambiguous, empty or
wrongly typed stores stop the transaction and are saved privately for review.
Both live passes completed, and the pass-B FDR output was byte-identical to
pass A. These results validate the observed exchange for this device/build.

The separate restore boot now succeeds. It keeps the bootstrap signing ticket,
uploads RestoreRamDisk then issues ramdisk without intermediate queries, sends
RestoreDeviceTree/devicetree and RestoreKernelCache/bootx. There is no separate
RestoreSEP/rsepfirmware command in this path, matching Apple's native sequence.
RestoreSEP remains available to the firmware provisioning handler.

A T1-specific opener checks QueryType and HardwareInfo once and retains the
connection. Generic discovery closes it with Goodbye, after which this device
refused new restored connections. The retained connection reached StartRestore,
NORData, RootTicket and FDRTrustData. The installed libimobiledevice 1.4.0 reverse
proxy reached Apple's FDR trust service, which returned HTTP 200. The first run
then failed at FDR recovery with status 52 because it selected local disk storage;
FDRMemoryStorePath corrected that failure. Pass A and pass B then completed,
including both observed FDRMemoryCommit requests per pass.

The generic restore helpers used for NOR/FUD still have upstream behavior and
parsers. These patches do not claim a security audit of the whole toolchain.
Offline tests establish specific host-side checks, not firmware safety or success.
Do not infer a successful boot from a zero phase-14 dispatch exit status.

## Build in a local prefix

Build the accompanying libirecovery, libtatsu and usbmuxd patches first. The new
libtatsu API is required to link idevicerestore. Do not install
this experimental stack into /usr or replace the system usbmuxd service.
Dependencies on Arch are already available in this development environment:
autoconf, automake, libtool, pkgconf, libusb, libimobiledevice-glue, libplist,
libtatsu, libimobiledevice, libusbmuxd, libzip, curl and zlib.

```sh
T1_WORK=/absolute/path/to/t1-recovery
T1_PREFIX="$T1_WORK/prefix"
export PKG_CONFIG_PATH="$T1_PREFIX/lib/pkgconfig"
export LD_LIBRARY_PATH="$T1_PREFIX/lib"
# In patched libirecovery:
./autogen.sh --prefix="$T1_PREFIX" --without-udev
make -j4 && make install
# In patched libtatsu:
./autogen.sh --prefix="$T1_PREFIX"
make -j4 && make install
sh tests/test_secure_transport.sh
# In patched usbmuxd (build only, use src/usbmuxd directly):
./autogen.sh --prefix="$T1_PREFIX" --without-systemd
make -j4
# In patched idevicerestore:
./autogen.sh --prefix="$T1_PREFIX"
make -j4
python3 tests/test_t1.py
```

The tests compile the actual C policy with UndefinedBehaviorSanitizer and strict
warnings. Synthetic fixtures exercise identity checks, excluded restore options,
request restrictions, exact replay ordering, each simulated transport failure,
wrong/incomplete pairs, mismatched tickets/tags, truncated DER, private file
permissions, unsafe file types and FDR persistence/rejection. A linked preflight
harness has no firmware-upload implementations and checks signing failure plus
incomplete output that replay rejects. The libtatsu mock-transport test checks
HTTPS settings, rejected endpoints, unsupported security options and rejection of
a partial success response after a certificate error. No test opens USB,
contacts Apple, starts usbmuxd, changes drivers, or writes firmware.

## Offline inspection

Download the generic package directly from Apple and verify the SHA-256 before
extracting. The existing local inspect-firmware.py helper records the exact URL
and digest. This branch's inspection mode checks the manifest identity and the
presence of required components, **not** the cryptographic authenticity of every
extracted file. Apple's secure boot remains responsible for accepting signatures.

```sh
IDEVICERESTORE_T1_MODE=inspect \
  src/idevicerestore /path/to/iBridge1_1Customer.bundle/Contents/Resources
```

This mode needs neither root nor a connected T1. It must succeed before any live
attempt. It does not create the generic restore log.

## Live-mode interface for a supervised experiment

These are expert development interfaces. The successful sequence is documented
in [activation.md](activation.md); the earlier diagnostics below are historical.
Use the local launcher in the patch bundle to supply the ECID internally rather
than pasting it into public terminal output. Never share private logs or artifacts.

Environment controls (all other IDEVICERESTORE variables are rejected):

- `IDEVICERESTORE_T1_MODE`: inspect, preflight, ibec-probe, boot-probe,
  captured-boot-probe, memboot-probe, provision, provision-running, or replay.
  provision-running is a direct-binary diagnostic mode for a captured private
  pair; normal activation uses provision without closing the restored connection.
- `IDEVICERESTORE_T1_PRIVATE`: existing absolute root-owned mode-0700 directory.
- `IDEVICERESTORE_T1_FDR_INPUT_DIR`: optional previous successful pass-A directory,
  containing FDRData and device.plist; only used in provision mode (pass B).

Preflight first: create a new root-owned 0700 directory on private local storage
and run the launcher as root (using pkexec on this development machine):

```sh
pkexec install -d -m 0700 /var/lib/t1-touchbar/private/preflight-001
pkexec python3 scripts/t1-run.py preflight \
  /path/to/iBridge1_1Customer.bundle/Contents/Resources \
  --prefix "$T1_PREFIX" --private /var/lib/t1-touchbar/private/preflight-001
```

This sends the connected T1's unique chip identifier, boot nonces and firmware
metadata to Apple's signing service. It does not send home files or upload
firmware. Get the machine owner's approval for that disclosure before running.
A successful preflight checks signing and local image construction only; it does
not validate FDR provisioning or promise firmware rollback. A signing rejection
must be resolved before proceeding; never bypass it or substitute another T1's
artifacts. Use a fresh directory for each attempt so existing logs are preserved.

Pass A: provision into a new private directory, without input FDR. Pass B:
provision into another new directory, using pass A as the input. Replay: use the
pass-B directory and no FDR input variable. Each live invocation requires `-i`
with this T1's ECID; debug, custom signing servers, erase, keep-personalized, ignore
errors and other generic restore flags are rejected. The executable creates no
host disk targets and accepts no block-device restore destination.

Before pass A/B, a reviewed private usbmuxd instance must own the selected mux socket with
`USBMUXD_T1_RECOVERY=1`; the system instance must not compete. The patch changes
only the opt-in libusb device-class filter; product-ID and mux-interface checks
remain. The tested setup used an isolated root-private UNIX socket, passed as
`-S /private/path/mux.sock` to usbmuxd and
`USBMUXD_SOCKET_ADDRESS=UNIX:/private/path/mux.sock` to the launcher. Its config,
PID handling and logs were isolated too; no system daemon was installed or
replaced. The daemon was stopped after the attempt. This broader discovery applies to Apple's matching product IDs, so detach
unrelated Apple devices during a future experiment.

Between successful passes and before replay, wait at least ten seconds. Any
necessary T1 reset is a separate operation: only verified ASOC.FRST, never SOCW(1).
The tool deliberately performs no ACPI reset, reboot, service stop/start, driver
installation, EFI staging, or automatic retry. Stop the private mux daemon before
phase 14. After dispatch, observe stable 05ac:8600 and test display/input/webcam.
Only then consider staging the exact image on EFI. Persistence on an external SSD
with failed internal storage remains unverified even in the original report.

## Historical development result (before successful activation)

Patched libirecovery, libtatsu, usbmuxd and idevicerestore compiled locally.
At the earlier checkpoint, all 28 idevicerestore offline tests and the libtatsu mock-transport test passed.
Earlier gcc static analysis with strict warnings passed for the initial T1 C
modules. The compiled inspection mode accepted the checksum-verified Apple
package's x619ap 14Y901 resources. The live preflight passed after correcting the
ECID argument format and supplying Apple's official CA to the signing connection.
One provision attempt loaded iBEC and obtained a fresh ticket, then stopped at
`ramdisk`; its private console reported `Ramdisk image not valid`. The original
restore ramdisk SHA-384 and its digest in the Apple ticket match the manifest.
The precise reason for device rejection remains unresolved; subsequent probes are
recorded below. No restored session, NORData request, FDR generation or phase-14
memboot occurred. The saved pair remains incomplete and cannot be replayed.

The test sent `setenv auto-boot false` and `saveenv` to the T1 before the ramdisk
failure. This is T1 state, distinct from the unchanged Linux boot configuration.
No previous value was captured, so automatic reversal would be a guess. The T1
remains in 05ac:1281 recovery. No personalized image was installed on EFI.

The separate USB was formatted for a private live file backup of home, /etc and
/boot, with partition metadata, the Linux encryption header and package list.
The compressed archives passed integrity/listing checks; two home files changed
while being read. This is not a bootable rescue drive, a complete disk clone or
a T1 firmware backup. Working audio, keyboard/trackpad and boot configuration
were not modified by this checkpoint.

The local ACPI table defines the T1 reset method at
`\_SB.PCI0.XHC1.RHUB.ASOC.FRST`: it toggles EC.SOCR with 15 ms and 600 ms waits,
and has no explicit Return. The accompanying acpi_call patch handles a successful
method with no output object instead of dereferencing NULL. It compiled against
the running kernel; the module was loaded and unloaded successfully without
calling FRST. No reset was performed.
Verification of this table is specific to this machine, not permission to call
the same method on arbitrary models. T1 already enumerates in recovery here, so
no reset is needed for preflight.


## Historical boot probes, 2026-09-08

The owner rebooted Linux and also inspected Sierra Recovery 10.12.6 (16G29) and
Monterey Recovery 12.6 (21G115). Searches under /usr and /System/Library found
AppleEmbeddedOSSupportHost.kext and EmbeddedOSSupportHost.framework, without an
EmbeddedOSInstall service. This is a limited filesystem search, not proof that
all installer resources lack the service. No erase or macOS install was performed.
The working audio DKMS module loaded again after the owner's Linux reboot.

Patch 0009 adds two explicitly selected diagnostic modes. Neither starts a
restored provisioning session, acknowledges FDR, or marks a production pair
complete:

- `boot-probe` tries the existing iBEC and separate restore-component sequence,
  with a checked build-version query after recovery re-enumeration, bounded
  private console capture, IMG4/tag/ticket checks, upload-length comparison and
  transfer delays. It stops before StartRestore even if the boot succeeds.
- `memboot-probe` signs for the currently running recovery device without loading
  iBEC, saves an incomplete preflight-only pair, concatenates personalized
  RestoreRamDisk/RestoreKernelCache/RestoreDeviceTree/RestoreSEP in that order,
  and dispatches `memboot` with bRequest=1 and the fixed restore boot arguments.
  Each component contains the same ticket; no separate raw `ticket` command is
  sent. This is a new experimental hypothesis, not the guide author's confirmed
  phase-11 protocol. Its only success condition is a matching restored service.

Both probes can change T1 boot state and save auto-boot=false. They are not
read-only operations. A successful probe would establish a boot path only, not
working Touch Bar functionality or persistent activation.

Observed results:

1. Checked recovery build-version was iBoot-3406.65.1.2. `boot-stage` was not
   supported. Recovery re-enumeration plus that version is insufficient evidence
   that the uploaded iBEC executed rather than falling back to existing iBoot.
2. The personalized restore ramdisk was 25,756,269 bytes, and the device's
   reported filesize matched exactly. The capacity query returned 0x8000000.
   Readiness checks and delays still ended in `Ramdisk image not valid` and USB
   PIPE (-9) on the ramdisk command.
3. An extra zero-length 0x21/1 notification after `go`, taken from upstream's
   generic sequence, returned PIPE. That attempted change was removed.
4. Separate private diagnostics checked the current ticket's device fields and
   nonces, verified its body signature against its embedded certificate key,
   and checked the ramdisk digest. The signature check was not a full certificate
   chain validation. A raw ticket command and an original IM4P ramdisk probe were
   rejected as well; these diagnostic helpers are not part of the public patch.
5. With AC power verified, memboot-probe-001 saved a 36,921,209-byte combined
   restore image, dispatched the boot transaction, and did not find restored
   during its 60-second observation period. T1 remained/reappeared as 05ac:1281.
   The log had no captured explanatory boot-console error. FDRData was absent
   and RestoreFinished remained false. The private mux process exited; its old
   socket pathname alone is not evidence of a running daemon.

All 28 offline tests passed, including malformed/mixed/truncated restore-image
rejection before any command and stopping at each simulated transfer failure.
At that earlier checkpoint, no NOR/FDR provisioning, phase-14 replay, FRST, EFI staging, or Touch Bar driver
installation occurred. The external USB backup remains unchanged. No successful
Touch Bar activation or permanent fix is claimed.

The next investigation requires evidence about the phase-11 boot sequence and
personalization. The public guide's successful patches are unpublished, so the
subsequent investigation below uses Apple's downloadable restore implementation.
A native macOS installation on external
storage is also not a confirmed workaround: a firsthand report from another
A1706 owner with a failed SSD describes repair failing because no internal system
EFI was found, and reports success only after repairing the onboard SSD:
https://superuser.com/questions/1537778/macbook-pro-a1706-bridgeos-and-external-efi
That single report does not prove a software workaround is impossible.

## Historical Apple bootstrap investigation, 2026-09-08

Apple's [iTunes 12.6.2 download](https://support.apple.com/en-us/106381) includes a
MobileDevice framework with recovery-bootstrap symbols. Its download target is
https://updates.cdn-apple.com/2019/cert/041-90437-20191023-5A3ABDC1-2C08-4C6D-BCED-986BF1EF68C4/iTunes.dmg.
The locally examined DMG has SHA-256
`752f9a499048f3172b41a893cb306ab3414de648b95a4bdf84688f549489e2f5`.
The installer was extracted for offline inspection, not executed. Apple binaries
and disassembly are not distributed here.

Independent analysis of the x86_64 framework found that its recovery restore
controller selects iBEC using IBFL bit 0, waits one second after uploading it,
then sends `go` with bRequest=1. A separate ticket upload is conditional on IBFL
bit 1, which is clear on this device. The recovery bulk transfer uses a 0x41/0
initial request and 0x8000-byte chunks. These observations establish individual
steps, not the complete EmbeddedOS activation protocol.

Patch 0010 follows the bootstrap delay and bit-0 check. It skips a redundant iBEC
upload when the bit is already clear and rejects a post-go recovery that still
requests bootstrap. Its new `ibec-probe` mode obtains a fresh ticket and stops
after the bootstrap check; it sends no ramdisk, StartRestore, or saveenv command.
Use the same launcher/private-directory setup as other live modes, selecting
`ibec-probe`. It changes the T1's volatile boot state and requires root.

The live `ibec-probe-001` observed IBFL 0x3d before `go` and 0x3c afterward.
The banner still said `iBoot for x619`, demonstrating that this banner alone
cannot distinguish the bootstrap stages. We did not record earlier attempts'
post-go flags, so the new delay is not proven to explain their failures.

From IBFL 0x3c, `boot-probe-004` uploaded all 25,756,269 restore-ramdisk bytes and
still received PIPE with `Ramdisk image not valid`. `memboot-probe-002` sent the
combined signed restore image and observed no matching restored service within
60 seconds; the device subsequently exposed 05ac:1281 with IBFL 0x3c. The private
console captured no explanatory message for that combined-image attempt.

A separate local diagnostic loaded the signed production OSRamdisk from that
attempt's incomplete pair, after checking device identity, embedded ticket and
current AP/SEP nonces. Its 19,502,240-byte upload succeeded, but `ramdisk` again
returned PIPE and `Ramdisk image not valid`. No kernel or boot command followed.
Offline extraction confirms that the production ramdisk is LZFSE-compressed and
contains the Touch Bar services, while the restore ramdisk is an uncompressed
HFS+ image containing `restored_external`. This is not evidence that either image
can be substituted for the other in the activation workflow.

At that bootstrap-only checkpoint, 29 offline tests passed. The new harness invokes the actual C bootstrap
controller with simulated device events/transfers and no linked USB transport.
It verifies delay-before-go, upload/command failures, rejecting unchanged boot
flags, and skipping uploads when bootstrap is already complete. At that point,
provisioning, activation and persistence were unverified, and no EFI image had
been staged. The successful activation below supersedes that status.


### Successful restore bootstrap and first provisioning session

A T1-only FRST followed by ibec-probe-002 saved the initial ticket before iBEC.
The post-iBEC AP nonce remained unchanged. Reusing the original ticket and
removing intermediate ramdisk queries made the ramdisk command succeed. A
captured-boot probe then reached a matching restored service. The reset, ticket
reuse and command changes were combined, so none alone is proven causal.

Pass-a-005 used the corrected full provisioning path and one retained restored
connection. NORData, RootTicket and FDRTrustData were exchanged. The final status
was 52, not success; FDRData was absent and the saved pair remained incomplete.
Apple's FDR trust endpoint responded successfully, but the device selected Local
storage and had no system partition. Offline inspection of the generic restore
executable confirms FDRMemoryStorePath selects Memory and avoids the immediate
missing-system-partition branch in RestoredFDRRecover. The source now sets it.

The additional connection harness rejects a wrong service, chip, board or ECID,
and verifies that a matching connection is retained without Goodbye or a second
open. At that checkpoint, all 30 tests passed with UndefinedBehaviorSanitizer. Apple binaries, private
logs, unique fields and personalized artifacts are not distributed.


## Successful activation and installation, 2026-09-08

Pass-a-006 completed after setting FDRMemoryStorePath="FDRData". Pass-b-001
provided that store in the RootTicket reply, received both FDRMemoryCommit
messages, finished successfully and produced byte-identical FDR output. Both
passed the strict completion checks; the pass-B image/ticket pair is complete.

The first production attempt stopped at a PIPE error on the standalone ticket
command, before OS upload. Adding a one-second delay did not change that result.
Apple's native recovery controller checks IBFL bit 1 before this separate ticket
transaction. The T1 reported 0x3d, so the implementation now omits that transaction
when bit 1 is clear, while retaining all embedded-ticket validation. Phase14-003
then dispatched the exact saved pass-B image successfully and booted production
EmbeddedOS. This is a documented correction to the public runbook's unconditional
ticket sequence. No new TSS request or iBEC upload was used during replay.

All 31 offline tests pass. Replay tests cover both standalone-ticket branches,
wrong embedded tickets and stopping after every failed transfer. Live sampling
recorded 35/35 seconds as 05ac:8600 with four interfaces. Two physical HID devices
bound to apple-ibridge-hid and two virtual 1d6b:0301 devices to apple-touchbar.
The owner confirmed icons and working buttons. Webcam nodes video0/video1 are
present. A subsequent test decoded 90 webcam frames at 1280×720 and 30 fps using
the built-in uvcvideo driver, with exit status 0 and no decoding errors. See
[camera verification](../../camera.md). Fn layout remains unverified.

The driver source is pinned to AJ-dev-i60/t1-touchbar commit
20d65c7b0fe6d05ea9734f869b27384a62de5109. The Arch package installed DKMS
apple-ib-drv/0.1 for 7.1.9-arch1-2 and automatic module/udev configuration,
including skip_acpi_power=1. The boot image rebuilt successfully. The three
live-proven EFI files were staged on the external SSD and compared byte-for-byte.
A private activation backup is on the spare USB. No host reboot was performed;
cold-boot persistence with the failed internal SSD and suspend/resume remain
unverified. See the driver guide and activation procedure for reproduction.
