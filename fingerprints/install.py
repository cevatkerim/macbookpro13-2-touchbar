#!/usr/bin/env python3
"""Install the panel for the current desktop user; never changes PAM/packages."""
import argparse
import datetime
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

START = "  // BEGIN t1-fingerprints (managed by fingerprints/install.py)"
END = "  // END t1-fingerprints"


def desktop_quote(value):
    # Desktop Entry Exec escaping, followed by the key-value string escaping.
    for character in ('\\', '"', '`', '$'):
        value = value.replace(character, '\\' + character)
    return '"' + value.replace('\\', '\\\\') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--no-menu", action="store_true", help="Leave the Omarchy menu unchanged")
    parser.add_argument("--no-window-rule", action="store_true", help="Leave Hyprland configuration unchanged")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Run as the desktop user, without sudo.")
    home = Path.home()
    target = home / ".local/share/t1-fingerprints"
    launcher = home / ".local/bin/t1-fingerprints"
    desktop = home / ".local/share/applications/me.kerim.T1Fingerprints.desktop"
    menu = home / ".config/omarchy/extensions/omarchy-menu.jsonc"
    old = menu.read_text() if menu.exists() else "{\n}\n"
    updated = old
    if not args.no_menu:
        updated = re.sub(r"\n" + re.escape(START) + r"\n.*?" + re.escape(END) + r"\n", "", old, flags=re.S)
        if not args.uninstall:
            if re.search(r'^\s*"setup\.security\.fingerprint"\s*:', updated, re.M):
                parser.error("A custom fingerprint menu action already exists. Use --no-menu and merge it manually.")
            import json
            action = shlex.quote(str(launcher))
            entry = json.dumps({"label": "Fingerprints", "action": action, "when": "true",
                                "description": "Add, verify or remove a Touch ID fingerprint"})
            block = f'\n{START}\n  "setup.security.fingerprint": {entry},\n{END}\n'
            if not updated.lstrip().startswith("{"):
                parser.error("Unexpected menu format. Use --no-menu and merge the action manually.")
            position = updated.index("{") + 1
            updated = updated[:position] + block + updated[position:]
    if args.uninstall:
        for path in (launcher, desktop, target / "panel.py", target / "reader.py", target / "fingerprint.svg"):
            path.unlink(missing_ok=True)
    else:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        target.mkdir(parents=True, exist_ok=True)
        for name in ("panel.py", "reader.py", "fingerprint.svg"):
            shutil.copyfile(Path(__file__).resolve().parent / name, target / name)
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text("#!/bin/sh\nexec /usr/bin/python3 " + shlex.quote(str(target / "panel.py")) + ' "$@"\n')
        launcher.chmod(0o755)
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text("[Desktop Entry]\nType=Application\nName=Fingerprints\n"
                           "Comment=Manage Touch ID fingerprints\n"
                           "Exec=/usr/bin/python3 " + desktop_quote(str(target / "panel.py")) + "\n"
                           "Icon=" + str(target / "fingerprint.svg") + "\nTerminal=false\nCategories=Settings;Security;\n"
                           "StartupNotify=true\nStartupWMClass=me.kerim.T1Fingerprints\n")
    if updated != old:
        menu.parent.mkdir(parents=True, exist_ok=True)
        if menu.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            shutil.copy2(menu, menu.with_name(menu.name + ".bak." + stamp))
        menu.write_text(updated)
    hypr = home / ".config/hypr/hyprland.lua"
    if not args.no_window_rule and hypr.exists():
        old_hypr = hypr.read_text()
        rule = ('\n-- BEGIN t1-fingerprints\n'
                'o.window("^me[.]kerim[.]T1Fingerprints$", { float = true, center = true, size = { 480, 640 }, fullscreen = false })\n'
                '-- END t1-fingerprints\n')
        new_hypr = re.sub(r'\n-- BEGIN t1-fingerprints\n.*?-- END t1-fingerprints\n', '', old_hypr, flags=re.S)
        if not args.uninstall:
            new_hypr += rule
        if new_hypr != old_hypr:
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            shutil.copy2(hypr, hypr.with_name(hypr.name + ".bak." + stamp))
            hypr.write_text(new_hypr)
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(desktop.parent)], check=True)
    print("Fingerprints removed." if args.uninstall else "Installed. Open Fingerprints in the launcher or Setup → Security → Fingerprints.")


if __name__ == "__main__":
    main()
