# Experimental T1 Touch Bar recovery

**Touch Bar activated on hardware; icons and buttons confirmed by the owner.** These independently written
patches implement a restricted x619ap EmbeddedOS recovery workflow based on
[this experimental report](https://gist.github.com/tigercosmos/ecbfe1fc20b7303c1808d3ab74af1f5b).
They are not the report author's unpublished patches. The [separate audio fix](https://github.com/cevatkerim/macbookpro13-2-audio)
does not depend on this work.

The tested MacBookPro13,2 has a failed internal SSD and runs Omarchy from an
external SSD. T1 started in recovery USB 05ac:1281, CPID 0x8002, BDID 0x12. It now
boots EmbeddedOS 3.0/14Y901 in production mode with Touch Bar HID interfaces.
See the **[activation procedure](docs/activation.md)** and
**[driver installation guide](../driver/README.md)**.

## Files and validation

- `patches/`: Git-format patches for libirecovery, usbmuxd, idevicerestore,
  libtatsu and acpi_call.
- `patches/SOURCES.txt`: exact upstream bases, local commits and patch hashes.
- [Implementation and build instructions](docs/implementation.md): supported
  modes, tests, private logging and unresolved protocol details.
- `inspect-firmware.py`: local generic-package inspection helper; does not access
  the T1. Download the Apple package to `download/EmbeddedOSFirmware.pkg` first,
  using the URL in its source report. The helper verifies the pinned checksum.

Apply each patch to its corresponding upstream repository at its listed base
using `git am`. For idevicerestore apply 0003, 0005, 0008, 0009, then 0010 in order. For
libtatsu apply 0004 then 0007. The other patches have independent upstream bases;
acpi_call comes from nix-community. Build and
install patched libirecovery and libtatsu into the local prefix before compiling
idevicerestore. Build usbmuxd without replacing the system service. The optional
acpi_call module is separate and is not needed for preflight on a T1 already in
recovery. See the build instructions for details.

The idevicerestore patches include the source, 31 offline tests, documentation and
`scripts/t1-run.py` launcher. The libtatsu patch includes an offline test that mocks
network transfers and checks certificate/hostname verification, HTTPS-only
routing, rejected endpoints and failure handling.

The patched userspace projects and optional acpi_call module compiled on
Omarchy/Arch Linux 7.1.9 with gcc 16.2.1. All 31 idevicerestore offline tests and
the libtatsu mock-transport test passed, with UndefinedBehaviorSanitizer. Earlier
compiler static analysis passed for the initial T1 C modules. The compiled
inspection mode accepted the checksum-verified Apple firmware. Patches were
checked against their exact bases.

## Live result and persistence limits

The live preflight succeeded on 2026-09-08: Apple issued the connected T1 a ticket
and local personalized image validation passed. Two host-side issues were fixed:
the launcher now prefixes hexadecimal ECIDs with `0x`, and the signing tool uses
Apple's official public Root CA for this connection. Certificate and hostname
verification stay enabled. The CA is independently sourced from
[Apple PKI](https://www.apple.com/certificateauthority/); system trust is unchanged.

On 2026-09-08 both provisioning passes finished successfully. Pass B replayed
byte-identical FDR data from pass A. The exact saved pass-B image then booted in
production mode; 35 of 35 one-second USB samples remained 05ac:8600 with four
interfaces. Two physical HIDs bound to apple-ibridge-hid, two virtual Touch Bar
HIDs bound to apple-touchbar, and webcam device nodes appeared. The owner
confirmed visible icons and working buttons. A subsequent webcam test decoded
90 frames at 1280×720 and 30 fps with built-in uvcvideo; see
[camera verification](../camera.md). Fn layout remains unverified.

Patch 0010 corrects bootstrap timing/flags, preserves the original ticket through
iBEC, uses the separate restore-ramdisk/device-tree/kernel boot path, and keeps
one verified restored connection open through provisioning. Generic discovery
sends Goodbye when closing its connection; this device then refused reconnects.
FDRMemoryStorePath selects the required in-memory store. Production replay sends
a standalone ticket only if IBFL bit 1 requests it; this device instead uses the
verified tickets embedded in the four IMG4 components. Apple native code and
live trials support these changes. Earlier failed trials are recorded in the
implementation notes.

The driver was installed through DKMS, module-loading and udev configuration were
installed, and Omarchy's unified kernel image rebuilt successfully. The exact
live-proven combined.memboot, FDRData and version.plist were staged and read-back
verified under /boot/EFI/APPLE/EMBEDDEDOS on the external SSD. The completed
activation pair and FDR data were also backed up privately on the spare USB.

T1-only ASOC.FRST resets succeeded without rebooting the Intel host. The private
mux daemon is stopped. No host reboot was initiated. **Cold-boot persistence from
the external SSD remains unverified**, especially with the internal SSD failed.
EFI staging and automatic driver loading are installed; their presence alone
does not establish that this Mac's firmware will load EmbeddedOS after power-off.

A verified private live file backup is on the separate USB, with two files
reported changed during reading. This is not a bootable rescue drive or full disk
clone. It does not recreate the missing T1 provisioning identity or establish a
firmware rollback.

Offline examination of Apple's MobileDevice framework identified the one-second
bootstrap delay, IBFL bit-0 check, and FDR memory-commit acknowledgement. New
harnesses test the actual bootstrap controller and retention of the verified
restored connection, using simulated transport only. The implementation notes
record the evidence, earlier failures and remaining limits.

The live fix is confirmed. Suspend/resume and cold-boot persistence still need
separate tests; do not claim those outcomes from the successful live activation.

Do not commit Apple firmware, personalized images, signing tickets, device
identifiers, FDRData, private logs or disk backups. Patch authorship uses the
email explicitly supplied by the repository owner. Upstream source and patches
retain their respective LGPL/GPL terms; the inspection helper is GPL-3.0-or-later.
