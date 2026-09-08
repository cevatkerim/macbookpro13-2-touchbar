# Touch ID trial: staged, awaiting reboot

On 2026-09-08, preparation began for
[T1Bridge](https://github.com/standardagents/t1bridge), which reports Touch ID
support on MacBookPro13,2. **Touch ID has not yet been enrolled or verified on
this machine.** The working Touch Bar and camera results elsewhere in this
repository describe the earlier community HID driver.

## Prerequisites checked

- Our regenerated, same-machine FDRData contains one `FSCl` fingerprint
  calibration record. The EFI copy matches the production-proven copy.
  Live sensor association and calibration acceptance remain to be checked.
- The production T1 exposes the eight-interface configuration needed for the
  display, private network and Secure Enclave transport.
- All four T1Bridge modules built against kernel 7.1.9-arch1-2.
- The official repository database and all four package signatures verified
  against the published primary key
  `35B166F78B063B04DE1E3D913E6C4216EB03D371`.

## Staged packages

| Package | Version |
| --- | --- |
| t1bridge | 0.1.4-1 |
| t1bridge-dkms | 0.1.4-1 |
| libfprint-t1bridge | 1.94.100-12 |
| fprintd-t1bridge | 1.94.5-9 |

The signed cohort was installed locally. The only missing distribution
dependency was libgusb, installed through `omarchy pkg add libgusb`. No kernel
upgrade or package database refresh was performed. The third-party repository
has not yet been added to pacman.conf; this is a pinned trial.

The old `macbookpro-t1-touchbar-dkms` package was removed after the new DKMS
installation succeeded, removing its rule that forced USB configuration 1.
The existing HID modules remain loaded for the current session. T1Bridge's
selector is included in the rebuilt boot image and its services are enabled
for the next boot. No live driver switch or USB reset was performed.

Apple firmware, provisioning data, and existing PAM configuration are unchanged.
Boot files, PAM files, the original driver package and firmware were backed up
privately on the system SSD and spare USB before installation. Audio driver
packaging and configuration were not modified.

## Desktop controls

[The unprivileged Omarchy adapter](integrations/t1bridge-desktop-provider.py)
implements T1Bridge's v1 audio/media provider contract. It uses Omarchy's
physical-output resolver, bounded volume values and the existing media actions.
It does not access the fingerprint sensor or authentication state. Status was
tested against the live desktop; physical control tests await the new renderer.

It is installed at `/usr/local/libexec/t1bridge-omarchy-desktop` with this user
service drop-in at `/etc/systemd/user/t1-touchbar.service.d/omarchy-desktop.conf`:

```ini
[Service]
Environment=T1BRIDGE_DESKTOP_PROVIDER=/usr/local/libexec/t1bridge-omarchy-desktop
```

## Next test after reboot

1. Confirm production T1 boot, the selected configuration, DKMS modules and
   `sudo t1bridge status`. Check Touch Bar controls and camera again.
2. Import this machine's data with
   `sudo t1bridge machine-data import --from /boot/EFI/APPLE/EMBEDDEDOS/FDRData`.
   Require successful live sensor association; do not substitute other data or
   delete state on failure.
3. Check the private T1 network and xART service. Before enrollment, permit
   IPv6 TCP 61500 only on the discovered T1 interface from its validated peer
   if the firewall blocks it. No LAN-wide exception is appropriate.
4. As the desktop user, run `fprintd-enroll -f right-index-finger`, then
   `fprintd-verify -f right-index-finger`. Require enrollment completion and an
   actual match before configuring any authentication consumer.
5. PAM integration is a separate step after verification, retaining password
   fallback and testing failure behavior with a root recovery shell open.

The trial requires a reboot because the upstream configuration selector runs
before the USB interfaces bind. Upstream explicitly advises against hot-swapping
the competing T1 stacks. Reboot persistence of our regenerated firmware is
also still unverified; preparation is not proof of a successful next boot.

## Rollback

The original driver package is preserved under
`/var/lib/t1-touchbar/before-touchid/`, with another copy on the spare USB.
If rollback is needed, stop the new user renderer and T1Bridge services,
remove the four trial packages through pacman, then reinstall that original
driver package with `pacman -U`. Check DKMS and boot-image regeneration before
rebooting. Removing T1Bridge must not delete its protected state, the backups,
or the Apple EFI firmware. Restore any later PAM changes and verify password
authentication before removing fingerprint packages.
