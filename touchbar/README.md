# Omarchy Touch Bar

An unprivileged replacement renderer for T1Bridge, with native touch sliders and
shortcuts to Omarchy. It uses T1Bridge's existing hardware service and the same
`omarchy` font glyph (`U+E900`) as the menu-bar launcher. No Apple firmware,
kernel driver, fingerprint enrollment or PAM configuration is changed.

## Settings panel

Open **Omarchy Touch Bar** from the application launcher or **Setup → Touch Bar**
in the Omarchy menu. The panel provides:

- A **Custom Touch Bar** switch to enable custom controls or return to the
  previous/stock renderer. The panel stays available in either mode.
- Show/hide switches and ordering arrows for **Workspace switcher**,
  **Screenshot** and **Notifications**.
- Show/hide switches for **Media controls** and **Keyboard brightness**.
- A header restart button to recover the selected controls if needed.

Icon changes save immediately to `~/.config/t1bridge/omarchy-touchbar.json`
(honoring `XDG_CONFIG_HOME`) and apply without restarting the renderer. Changes
made while custom controls are disabled are retained for the next enable.
Escape, the Omarchy launcher, volume and display brightness remain available;
Fn still opens the function-key row. Enabling/disabling restarts only the user
renderer service. The Touch Bar itself has no Default/exit button.

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
`T1BRIDGE_DESKTOP_PROVIDER` environment setting. The renderer needs Pycairo; the panel also needs GTK4/libadwaita:

```sh
omarchy pkg add python python-cairo python-gobject gtk4 libadwaita
python3 touchbar/install.py
```

Run the installer as your normal desktop user, **without sudo**. It copies the
renderer, settings panel and launchers into `~/.local/share/omarchy-touchbar`, selects
that launcher through `~/.config/t1bridge/renderer` (honoring `XDG_CONFIG_HOME`),
and restarts only the existing user renderer service. An earlier selection is
saved as `renderer.before-omarchy-touchbar`; a conflicting backup is never
overwritten. The root hardware/authentication services continue running.

The installer adds an application entry, an Omarchy menu item and a small
floating-window rule. Changed user menu/Hyprland files are backed up alongside
the originals. Nothing under `/usr/share/omarchy` is edited. Validate desktop
integration after installing:

```sh
hyprctl reload
hyprctl configerrors
omarchy menu refresh
```

Use `--no-menu --no-window-rule` on other desktops or when managing those
integrations yourself. A conflicting custom menu item is not overwritten.

The selection persists across logins and reboot, provided T1 firmware and its
existing services start successfully. [This machine's automatic firmware
startup still needs its separate reboot test](../touchid.md#firmware-startup-after-reboot).
After updating the repository, rerun the installer to update installed files.

The application launcher now opens settings. Use its **Custom Touch Bar** switch
to choose the renderer, or its restart button to restart the current selection.
The equivalent restart command is:

```sh
systemctl --user restart t1-touchbar.service
```

To persistently disable this renderer and restore the previous selection:

```sh
python3 touchbar/install.py --disable
```

The installed settings panel remains available for re-enabling. An unrelated renderer
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
installed custom renderer then started successfully. Twenty-three automated tests
cover touch transitions, slider clamping, context changes, function keys,
workspace selection, packet validation, cancellation races, lock gating,
preference validation, shortcut ordering/visibility and renderer selection
round trips. The owner confirmed that the controls work and subsequently
confirmed the settings panel's switching and customization behavior. A live
framebuffer capture exposed overlapping brightness/keyboard labels; measuring
text width fixed the spacing, and the slider track was shortened to about 575
native pixels. Suspend/resume and reboot behavior are not established by these
live tests.

The workspace page contains workspaces 1–10. The panel customizes the supported
shortcut set; app-specific layouts and arbitrary new actions are not implemented.
Settings accept only known control IDs and booleans, with no command strings.
Malformed settings keep the last valid running layout; on startup the renderer
uses defaults. Layout changes wait until a touch gesture finishes.
