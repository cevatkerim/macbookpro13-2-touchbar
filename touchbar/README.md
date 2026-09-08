# Omarchy Touch Bar

An unprivileged replacement renderer for T1Bridge, with native touch sliders and
shortcuts to Omarchy. It uses T1Bridge's existing hardware service and the same
`omarchy` font glyph (`U+E900`) as the menu-bar launcher. No Apple firmware,
kernel driver, fingerprint enrollment or PAM configuration is changed.

## Controls

| Control | Action |
| --- | --- |
| Escape | Sends Escape |
| Omarchy icon | Opens/closes the Omarchy menu, including application launchers |
| Workspace grid | Opens buttons for workspaces 1–10; the current workspace is highlighted |
| Camera | Opens Omarchy's interactive screenshot picker |
| Bell | Opens notification history |
| Previous / play-pause / next | Uses Omarchy's media controls |
| Speaker | Opens the volume slider; Mute/Unmute is available beside it |
| Sun | Opens the display brightness slider, with a 1% minimum |
| Keyboard | Opens the keyboard-backlight slider |
| Back | Returns from sliders or workspace selection |
| Default | Exits this renderer; T1Bridge starts its stock buttons |
| Hold the physical Fn key | Shows Escape and F1–F12; release restores the previous page |

Sliders change only when you touch their track, not when you open them. One
contact owns a gesture; drags across ordinary buttons and multi-finger touches
do not accidentally activate shortcuts. The renderer coalesces slider updates
and keeps desktop subprocesses off the rendering loop. Desktop levels refresh
when changed elsewhere. Missing level controls show a dash.

Touch ID prompts temporarily replace the normal controls, with a Cancel button
routed through T1Bridge's existing typed cancellation request. This display is
cosmetic; matching and authorization remain entirely with the existing broker.
Launcher, workspace, notification and screenshot actions check Omarchy's lock
state immediately before execution and are unavailable if that check fails.

## Install

First confirm the stock T1Bridge Touch Bar works and install the
[Omarchy desktop provider](../touchid.md#desktop-controls). This renderer expects
that provider at `/usr/local/libexec/t1bridge-omarchy-desktop`, or via the existing
`T1BRIDGE_DESKTOP_PROVIDER` environment setting. It needs Python and Pycairo:

```sh
omarchy pkg add python python-cairo
python3 touchbar/install.py
```

Run the installer as your normal desktop user, **without sudo**. It copies the
five Python files and launcher into `~/.local/share/omarchy-touchbar`, selects
that launcher through `~/.config/t1bridge/renderer` (honoring `XDG_CONFIG_HOME`),
and restarts only the existing user renderer service. An earlier selection is
saved as `renderer.before-omarchy-touchbar`; a conflicting backup is never
overwritten. The root hardware/authentication services continue running.

The selection persists across logins and reboot, provided T1 firmware and its
existing services start successfully. [This machine's automatic firmware
startup still needs its separate reboot test](../touchid.md#firmware-startup-after-reboot).
After updating the repository, rerun the installer to update installed files.

To return after tapping Default, open **Omarchy Touch Bar** from the application
launcher. The installer adds this shortcut. From a terminal, the equivalent is:

```sh
systemctl --user restart t1-touchbar.service
```

To persistently disable this renderer and restore the previous selection:

```sh
python3 touchbar/install.py --disable
```

The installed files remain available for re-enabling. An unrelated renderer
selected later is left untouched. `--no-restart` edits selection without
restarting the service. T1Bridge automatically falls back to its built-in
renderer if this program cannot start or exits. Do not run two renderers against
the hardware socket simultaneously.

## Development and validation

```sh
python3 -m unittest discover -s touchbar -v
python3 touchbar/renderer.py --preview /tmp/touchbar-home.png
python3 touchbar/renderer.py --preview /tmp/touchbar-volume.png --page volume
```

Preview generation never connects to hardware. It uses synthetic levels and
installed fonts. The interface follows the installed T1Bridge
[renderer and hardware contracts](https://github.com/standardagents/t1bridge/blob/main/docs/interfaces.md).
Frame size is negotiated, frames use sealed shared-memory buffers, and the
client waits for buffer release before writing the next frame. Both the socket
file and connected peer must be root-owned. The UI only requests bounded keys,
brightness percentages and Touch ID cancellation through that interface.
Desktop commands are fixed argument arrays, run as the user, with no shell
interpolation or arbitrary-command configuration.

On this MacBookPro13,2, the first 12-second live trial negotiated the display,
submitted frames, exited successfully and restarted the stock renderer. The
installed custom renderer then started successfully. Fourteen automated tests
cover touch transitions, slider clamping, context changes, function keys,
workspace selection, packet validation, cancellation races and lock gating. The owner confirmed that the controls work. A live framebuffer capture
then exposed overlapping brightness/keyboard labels; measuring text width fixed
the spacing, and the slider track was shortened to about 575 native pixels. Suspend/resume and reboot behavior
are not established by the short live trial.

This first version has a fixed layout and workspace page. App-specific layouts
and a visual layout editor are possible follow-up work, not implemented here.
