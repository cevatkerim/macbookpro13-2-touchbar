# Touch ID on Omarchy

On 2026-09-08, [T1Bridge](https://github.com/standardagents/t1bridge) enrolled a
right index finger on this MacBookPro13,2 and a fresh verification returned
`verify-match`. The new Touch Bar controls and Omarchy volume/brightness OSD
were confirmed by the owner. This uses the T1Bridge stack in place of the
earlier community HID driver; do not install both stacks together.

## Prerequisites checked

- Our regenerated, same-machine FDRData contains one `FSCl` fingerprint
  calibration record. The EFI copy matches the production-proven copy.
  Its equivalent XML serialization passed the upstream validator and the
  normal importer's live sensor association check.
- The production T1 exposes the eight-interface configuration needed for the
  display, private network and Secure Enclave transport.
- All four T1Bridge modules built against kernel 7.1.9-arch1-2.
- The official repository database and all four package signatures verified
  against the published primary key
  `35B166F78B063B04DE1E3D913E6C4216EB03D371`.

## Installed packages

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
T1Bridge's selector is included in the rebuilt boot image. After reboot and
saved-image firmware startup, configuration 2 exposes eight interfaces and the
new display, private network and biometric services are running.

Apple firmware and the original provisioning data are unchanged.
Boot files, PAM files, the original driver package and firmware were backed up
privately on the system SSD and spare USB before installation. Audio driver
packaging and configuration were not modified.

## Desktop controls

[The unprivileged Omarchy adapter](integrations/t1bridge-desktop-provider.py)
implements T1Bridge's v1 audio/media provider contract. It uses Omarchy's
physical-output resolver, bounded volume values and the existing media actions.
It does not access the fingerprint sensor or authentication state. It calls
Omarchy's OSD for volume, mute, display brightness and keyboard brightness.
The owner confirmed working controls and restored volume/brightness indicators.

It is installed at `/usr/local/libexec/t1bridge-omarchy-desktop` with this user
service drop-in at `/etc/systemd/user/t1-touchbar.service.d/omarchy-desktop.conf`:

```ini
[Service]
Environment=T1BRIDGE_DESKTOP_PROVIDER=/usr/local/libexec/t1bridge-omarchy-desktop
```

## Calibration import and enrollment

1. Confirm production T1 boot and `sudo t1bridge status` before enrollment.
2. Import matching machine data using the normal T1Bridge importer. Our recovery
   tool produced a binary plist that T1Bridge rejected with `invalid binary
   plist trailer`. Python's plist reader accepted it. Re-encoding that dictionary
   as XML preserved every signed record byte, passed the unmodified upstream
   validator offline, and passed the live importer. The original FDRData and EFI
   files were retained. The compatible copy is private; no payloads were
   published. An encoding rejection does not justify weakening sensor matching.
3. Check the private T1 network and xART service. Before enrollment, permit
   IPv6 TCP 61500 only on the discovered T1 interface from its validated peer
   if the firewall blocks it. No LAN-wide exception is appropriate.
4. As the desktop user, run `fprintd-enroll -f right-index-finger`, then
   `fprintd-verify -f right-index-finger`. Require enrollment completion and an
   actual match before configuring any authentication consumer.
5. Require `enroll-completed`, the expected finger in `fprintd-list`, and then
   `verify-match`. The first attempt here failed during device-keybag preparation;
   one retry with redacted logging succeeded. The first failure's precise cause
   is unconfirmed. No keybag or biometric state was erased to retry.

## Authentication integration

The [Fingerprints panel](fingerprints/README.md) provides enrollment management
through the existing service. Its launcher and Omarchy menu entry persist across
reboot. It does not change the authentication setup described below.

The sudo and polkit trial adds the existing faillock precheck, Omarchy's
closed-lid gate and `pam_fprintd.so maxtries=3 timeout=10`, preserving the
original password and account includes. The lock screen uses its separate
`omarchy-lock-fingerprint` PAM stack; `omarchy-lock-password` and `system-auth`
remain byte-identical to their originals. The stock setup wizard was not run
because it would try to install the distribution fingerprint packages over
the matched T1Bridge pair.

The trial used a privileged recovery process limited to restoring these three
PAM files, with rollback on disconnect or timeout. Sudo and graphical
authorization succeeded, and both accepted passwords with fprintd temporarily
masked. The owner also confirmed lock-screen password fallback in that state.
The owner then confirmed fingerprint lock-screen unlock. The verified PAM
configuration was retained and the recovery process closed. The runtime fprintd
mask was removed before the fingerprint unlock test.

## Firmware startup after reboot

For the later failure after repeated lock-screen scan timeouts, see the
[experimental keybag relay recovery patch](integrations/keybag-relay/README.md).
Its installation and validation status are recorded there.

The first reboot returned T1 to recovery (`05ac:1281`). Staging the firmware
under the external SSD's Apple EFI path was insufficient on this machine.
Replaying the same completed production pair from Linux booted the T1 again;
the new stack then selected configuration 2 and the owner confirmed controls.

[boot-saved-t1.py](recovery/boot-saved-t1.py) and
[t1-saved-firmware.service](recovery/t1-saved-firmware.service) now provide this
saved-image startup automatically. The helper checks the model, recovery device
identity, completed provisioning flags and original verified image hash. It
attempts at most one replay per host boot, keeps logs private, and does nothing
when the expected production configuration is already running. It does not
sign, provision, reset the USB device, switch a running configuration, or enroll.

The installed executable and its two local shared libraries are root-owned under
`/usr/local/libexec/t1-firmware`; firmware resources stay under the private state
directory. The service cannot access the network or user home. It is enabled
and its already-running-device path passed. On the next reboot, the saved-image
startup and keybag services both completed successfully, and the owner reported
working hardware and Touch ID. The custom renderer initially fell back to stock
because its socket was not ready; its subsequent
[startup readiness fix](touchbar/README.md) has a separate pending reboot test.
A user service retry drop-in also restarts a failed launcher.

The private-link UFW exception is restricted to the observed T1 interface,
verified USB driver/device identity and expected link-local peer, TCP 61500.
If interface naming changes, rediscover the T1 and update that host-specific
rule rather than opening the port on other networks. Suspend/resume is untested.

## Rollback

The original driver package is preserved under
`/var/lib/t1-touchbar/before-touchid/`, with another copy on the spare USB.
If rollback is needed, stop the new user renderer and T1Bridge services,
remove the four trial packages through pacman, then reinstall that original
driver package with `pacman -U`. Check DKMS and boot-image regeneration before
rebooting. Removing T1Bridge must not delete its protected state, the backups,
or the Apple EFI firmware. Restore any later PAM changes and verify password
authentication before removing fingerprint packages.
