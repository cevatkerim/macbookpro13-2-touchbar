# Fingerprints panel

A small GTK4/libadwaita panel for the working T1Bridge Touch ID service. Open
**Fingerprints** from the application launcher or **Setup → Security →
Fingerprints** in Omarchy. Choose an unused finger and click **Add fingerprint**;
follow the touch/lift instructions until it reports that the fingerprint is
saved. Use **Verify** to check a saved finger. The trash button asks for
confirmation before removing only that finger.

T1Bridge supports up to three fingers for one Linux owner. Enrollment labels
describe the finger you choose; the panel cannot tell which anatomical finger
you actually touched. Accepted scans are counted without pretending that the
service's reported enrollment-stage count is a reliable percentage.

## Install and keep it installed

First complete the [T1Bridge setup](../touchid.md) and confirm that
`fprintd-list "$USER"` and `fprintd-verify` work. This panel does not install a
driver, provision T1, or enable fingerprint login. Keep the matched
`fprintd-t1bridge` / `libfprint-t1bridge` packages.

On Omarchy, install any missing UI dependencies:

```sh
omarchy pkg add python-gobject gtk4 libadwaita
```

From this repository, as the normal desktop user:

```sh
python3 fingerprints/install.py
hyprctl reload
hyprctl configerrors
omarchy menu refresh
~/.local/bin/t1-fingerprints
```

The installer copies the application into `~/.local/share/t1-fingerprints`,
adds a launcher in `~/.local/bin` and a `.desktop` entry in
`~/.local/share/applications`. It adds marked blocks to the user's Omarchy menu
extension and Hyprland Lua config, backing up changed config files alongside
their originals. The window rule opens a centered 480×640 floating panel.
These user files survive reboot and Omarchy package updates. No autostart
service is needed. Re-run the installer after updating this repository.

The menu override replaces the stock fingerprint package-install wizard. It
also overrides its USB-only hardware detection, which misses T1Bridge's
network-backed reader. Nothing under `/usr/share/omarchy` is modified.
If a custom fingerprint action already exists, the installer stops rather
than overwrite it. Use `--no-menu` and merge the action manually. For other
desktops or older Hyprland configurations, use `--no-menu --no-window-rule`.
The Lua rule follows the current [Hyprland window-rule documentation](https://wiki.hypr.land/Configuring/Basics/Window-Rules/).

## Ownership, cancellation and privacy

The panel calls the installed fprintd system D-Bus API with an empty username,
meaning the current caller. It runs without root and uses the service's
existing Polkit checks. There are no other-user or delete-all controls and no
PAM edits. It does not read raw samples, protected enrollment files, firmware,
keybags or calibration data, and does not save fingerprint data or logs.

Each operation claims the reader, stops capture when finished/cancelled, and
releases it. Cancellation waits for a pending Claim/Start reply before cleanup.
Closing during capture also cancels and releases. A dedicated D-Bus connection
is dropped on errors, including timeouts, so a late reply cannot leave this
client owning the reader. If another login/enrollment prompt owns it, finish
that prompt and use Refresh. Cancelling a removal is possible in its
confirmation dialog; once confirmed, the service performs the deletion.

Password login remains available. A verification inside this panel is only a
sensor check; it does not grant privileges or independently validate PAM login.

## Validation

```sh
python3 -m unittest discover -s fingerprints -v
desktop-file-validate ~/.local/share/applications/me.kerim.T1Fingerprints.desktop
```

The 11 tests cover cancellation during pending Claim/Start, terminal signals
arriving before Start replies, connection cleanup after errors, retries,
enrollment limits, single-finger deletion, repeat installation and preservation
of user configuration during uninstall. Live listing and the rendered panel
were checked on this MacBookPro13,2. Two live verification/cancellation cycles
completed Start → Stop → Release, retaining the existing enrollment. The desktop
entry passed validation and Hyprland reported no config errors.

The owner subsequently confirmed that the panel works nicely. Individual live
add/remove results were not separately recorded; the existing saved finger was
not deleted for automated tests.

## Remove the panel

```sh
python3 fingerprints/install.py --uninstall
hyprctl reload
hyprctl configerrors
omarchy menu refresh
```

This removes the panel and its managed config blocks, preserving fingerprints,
T1Bridge packages and authentication configuration. The stock Omarchy
fingerprint menu behavior returns; avoid its package-install wizard while using
the matched T1Bridge packages. Config backups are retained. Python may leave a
harmless `__pycache__` in the application's data directory.
