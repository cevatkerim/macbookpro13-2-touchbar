# MacBookPro13,2 Touch Bar on Omarchy

**Working Touch Bar icons and buttons, confirmed by the owner on 2026-09-08.**
The test machine has a failed internal SSD and runs Omarchy from an external SSD.
Its T1 was in recovery. Both provisioning passes and production boot succeeded;
the driver and firmware files are installed for later boots. **Cold-boot
persistence and suspend/resume remain unverified.**

Audio is maintained separately in
[macbookpro13-2-audio](https://github.com/cevatkerim/macbookpro13-2-audio).
This repository contains only the T1 activation work, its tests and documentation,
and an Arch/DKMS package definition for the existing community Touch Bar driver.

## Start here

- [Driver installation and removal](driver/README.md): use this when production
  EmbeddedOS already boots. Includes automatic loading and kernel updates.
- [FaceTime camera verification](camera.md): built-in UVC support, tested capture
  settings and OBS setup after T1 activation.
- [Touch ID trial](touchid.md): T1Bridge packages staged for reboot; enrollment
  and the new driver stack are not yet verified on this machine.
- [Full activation procedure](recovery/docs/activation.md): the tested recovery,
  FDR creation/replay, production boot, verification and EFI staging sequence.
- [Results and limitations](recovery/README.md): live evidence and persistence status.
- [Implementation and investigation](recovery/docs/implementation.md): code details,
  local builds, offline tests, historical failures and their corrections.
- [Pinned source revisions and patch hashes](recovery/patches/SOURCES.txt).

## What was written

The firmware is Apple's original, signed EmbeddedOS 3.0 build 14Y901. It was not
rewritten or patched. Apple's signing service issued tickets for this physical
T1, and the T1's restore firmware generated its own FDR provisioning data.
Secure boot was not bypassed: the device accepted properly signed Apple images.

The new work is a restricted Linux host-side activation path in idevicerestore,
with model/build checks, private artifact storage, ticket/image validation,
FDR memory commits and replay, plus 31 offline tests. Supporting patches add the
T1 device entry, private USB discovery, verified HTTPS signing and a null-result
fix for acpi_call. Native Apple code and live trials informed the protocol fixes.

The kernel driver is the existing
[AJ-dev-i60/t1-touchbar fork](https://github.com/AJ-dev-i60/t1-touchbar/tree/20d65c7b0fe6d05ea9734f869b27384a62de5109),
pinned and packaged for Omarchy/Arch. Its implementation was not written from
scratch. Its ACPI power-call skip is explicitly enabled.

## Tested result

| Item | Result |
| --- | --- |
| Machine | MacBookPro13,2; T1 x619ap, CPID 0x8002, BDID 0x12 |
| OS / kernel | Omarchy 4.0.2; 7.1.9-arch1-2 |
| Firmware | Apple EmbeddedOS 3.0, build 14Y901 |
| Provisioning | Both passes completed; replayed FDR data byte-identical |
| Production USB | 35/35 one-second samples at 05ac:8600, four interfaces |
| HID binding | Two physical iBridge HIDs and two virtual Touch Bar HIDs bound |
| Display / buttons | Owner confirmed icons and working buttons |
| Webcam | 720p/30 capture passed with built-in uvcvideo; owner confirmed OBS works |
| Driver persistence | apple-ib-drv/0.1 installed through DKMS; boot image rebuilt |
| Firmware persistence | Proven files staged on external SSD EFI and verified |
| Cold boot / suspend | Not tested |

A restore ramdisk also exposes 05ac:8600, with one mux interface. That USB ID
alone does not establish production boot or a working Touch Bar. No host reboot
was initiated during the successful activation.

## Private files and licenses

Never publish Apple firmware, personalized images, tickets, FDRData, unique device
identifiers, recovery photographs or raw logs. They are not included here. The
completed activation data is stored privately on the machine and backed up on
separate storage; another Mac's files cannot substitute for it.

Repository scripts/documentation use GPL-2.0 unless a file states otherwise.
The inspection helper is GPL-3.0-or-later; patches retain their source projects'
LGPL/GPL terms. The driver is GPL-2.0. Apple firmware is downloaded separately
from Apple and is not redistributed in this repository.
