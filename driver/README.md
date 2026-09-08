# T1 Touch Bar driver on Omarchy / Arch

The owner confirmed Touch Bar icons and working buttons on MacBookPro13,2,
Omarchy 4.0.2 and Linux 7.1.9-arch1-2 on 2026-09-08. The driver is
[AJ-dev-i60/t1-touchbar](https://github.com/AJ-dev-i60/t1-touchbar/tree/20d65c7b0fe6d05ea9734f869b27384a62de5109),
pinned to commit `20d65c7b0fe6d05ea9734f869b27384a62de5109`.
The PKGBUILD checks the source archive's SHA-256 and packages the GPL driver.
It does not run the upstream Debian/Ubuntu installer.

## Check firmware before installing

A driver needs production EmbeddedOS running on the T1. `05ac:1281` is recovery;
use the [activation procedure](../recovery/docs/activation.md) first.
`05ac:8600` alone is insufficient: the restore ramdisk also uses that ID, with
only one mux interface. Our production configuration 1 has four USB interfaces,
including two physical HID interfaces. A normal production boot exposes the
Touch Bar and webcam to Linux.

Do not run provisioning when the T1 already boots production firmware and only
needs its Linux driver.

## Install permanently

From this repository, as your ordinary user:

```bash
cd driver
makepkg --syncdeps
sudo pacman -U ./macbookpro-t1-touchbar-dkms-0.1.20260908-1-x86_64.pkg.tar.zst
```

Use headers matching your running kernel. This package depends on `linux-headers`
for the standard Arch kernel; other kernels need their corresponding headers and
a package adjustment. DKMS/pacman builds and installs the two modules. On the
tested Omarchy system its hooks also rebuilt the unified kernel image successfully.
Check that these hooks finish successfully.

The package installs:

- `/usr/src/apple-ib-drv-0.1`: pinned source for DKMS rebuilds after kernel updates.
- `/etc/modprobe.d/apple-touchbar.conf`: `skip_acpi_power=1`.
- `/etc/modules-load.d/apple-touchbar.conf`: automatic iBridge driver loading.
- `/etc/udev/rules.d/99-ibridge.rules`: USB configuration 1 and autosuspend disabled
  only for Apple T1 `05ac:8600`.

Load the drivers in the current session when the T1 is ready:

```bash
sudo udevadm control --reload
sudo modprobe apple_ibridge skip_acpi_power=1
sudo modprobe apple_touchbar
cat /sys/module/apple_ibridge/parameters/skip_acpi_power
```

The last command must print `1`. Never set it to `0`: the ASOC.SOCW power method
can freeze this hardware. The pinned source checks this setting at probe,
suspend and resume. Our live test loaded both drivers before production memboot,
so they claimed the new HID interfaces immediately. If a generic HID driver
already owns them, loading a module alone may not transfer ownership; avoid
blind unbind/rebind commands. Check the actual device state first.

If a system usbmuxd rule matches iBridge, make a local override removing only the
T1 `8600` alternative, preserving phone/tablet support. Do not delete unrelated
USB rules or mask usbmuxd indiscriminately. This tested Omarchy installation had
no system usbmuxd rule/service, and its temporary provisioning daemon is stopped.

## Verify

```bash
dkms status -m apple-ib-drv -v 0.1
modinfo -F filename apple_ibridge
modinfo -F filename apple_touchbar
journalctl -k --no-pager -g 'apple-ibridge|apple-touchbar|skip_acpi_power'
```

Expected: DKMS says installed for the current kernel; physical `05ac:8600` HIDs
use `apple-ibridge-hid`; virtual `1d6b:0301` HIDs use `apple-touchbar`. Confirm
visible icons and a button press physically. Our owner confirmed icons/buttons;
the webcam subsequently passed a 90-frame 720p/30 capture test using built-in
uvcvideo. See [camera verification](../camera.md). Fn layout remains unverified.

The temporary live test used `idle_timeout=-1` and `dim_timeout=-1` to keep the
bar visible. The permanent package retains upstream defaults: the display can
sleep after inactivity and wakes on input. Those temporary options last only
until module reload/reboot.

## Firmware persistence and removal

Driver persistence and T1 firmware boot are separate. On the tested Mac, both
provisioning passes and production boot succeeded, and the exact working image,
FDRData and version metadata were installed under `/boot/EFI/APPLE/EMBEDDEDOS`
on the external SSD. Their private source copies and a spare-USB backup were
verified. **Cold-boot persistence with the failed internal SSD is not yet tested.**
Save work before a later reboot; verify the Touch Bar afterward. EFI files alone
do not guarantee this Mac's firmware will discover them on external storage.
The recovery guide explains manual replay using the completed private pair if
Linux starts with the T1 back in recovery.

After kernel updates, inspect DKMS status; compatibility with future kernels is
not guaranteed. Remove the driver package with:

```bash
sudo pacman -R macbookpro-t1-touchbar-dkms
```

Allow removal hooks to complete. The currently loaded modules remain until
unloaded or rebooted. This removes the package's driver configuration, not the
private activation backup or EFI firmware. For a driver-related boot problem,
append `modprobe.blacklist=apple_ibridge,apple_touchbar` temporarily to the Linux
kernel command line in the bootloader.
