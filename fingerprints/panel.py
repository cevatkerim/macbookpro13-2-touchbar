#!/usr/bin/env python3
"""Small GTK panel for the existing T1Bridge/fprintd service (GPL-2.0)."""
import os
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk
from reader import DBusTransport, FINGERS, Reader


class Fingerprints(Adw.Application):
    def __init__(self):
        super().__init__(application_id="me.kerim.T1Fingerprints",
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        self.reader = Reader(DBusTransport(), self.update)
        self.closing = False
        self.window = Adw.ApplicationWindow(application=self, title="Fingerprints",
                                             default_width=480, default_height=590)
        self.window.connect("close-request", self.close_requested)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Refresh reader")
        self.refresh_button.connect("clicked", lambda *_: self.reader.refresh())
        header.pack_end(self.refresh_button)
        toolbar.add_top_bar(header)
        self.window.set_content(toolbar)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        toolbar.set_content(scroll)
        clamp = Adw.Clamp(maximum_size=500)
        scroll.set_child(clamp)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                       margin_start=24, margin_end=24, margin_top=12, margin_bottom=24)
        clamp.set_child(body)
        body.append(Gtk.Image(file=str(Path(__file__).with_name("fingerprint.svg")), pixel_size=48))
        title = Gtk.Label(label="Touch ID")
        title.add_css_class("title-1")
        body.append(title)
        body.append(Gtk.Label(label="Manage your fingerprints on this Mac.\nSave up to three fingers.",
                              justify=Gtk.Justification.CENTER, wrap=True))
        self.group = Adw.PreferencesGroup(title="Saved fingers")
        body.append(self.group)
        self.rows = []
        self.controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.available = []
        self.choice = Gtk.DropDown()
        self.choice.set_tooltip_text("Finger to enroll")
        self.controls.append(self.choice)
        self.add_button = Gtk.Button(label="Add fingerprint")
        self.add_button.add_css_class("suggested-action")
        self.add_button.connect("clicked", self.enroll)
        self.controls.append(self.add_button)
        body.append(self.controls)
        self.status = Gtk.Label(wrap=True, selectable=True, xalign=0)
        self.status.set_lines(-1)
        body.append(self.status)
        self.spinner = Gtk.Spinner()
        body.append(self.spinner)
        self.cancel_button = Gtk.Button(label="Cancel")
        self.cancel_button.connect("clicked", lambda *_: self.reader.cancel())
        body.append(self.cancel_button)
        note = Gtk.Label(label="Fingerprints stay with the existing Touch ID service.\nYour password remains available.",
                         wrap=True, justify=Gtk.Justification.CENTER)
        note.add_css_class("dim-label")
        body.append(note)
        self.update()
        self.window.present()
        self.reader.refresh()

    def update(self):
        reader = self.reader
        ready = reader.phase == "ready"
        busy = reader.phase not in ("ready", "offline")
        self.status.set_label(reader.message)
        self.spinner.set_spinning(busy)
        self.spinner.set_visible(busy)
        self.refresh_button.set_sensitive(not busy)
        self.cancel_button.set_visible(reader.phase in ("claiming", "starting", "active")
                                       and reader.operation != "Delete")
        self.cancel_button.set_sensitive(not reader.cancelled and not self.closing)
        self.controls.set_sensitive(ready and len(reader.fingers) < 3)
        self.group.set_sensitive(ready)
        if not busy:
            selected = self.choice.get_selected()
            old = self.available[selected] if selected < len(self.available) else None
            for row in self.rows:
                self.group.remove(row)
            self.rows = []
            for finger in reader.fingers:
                row = Adw.ActionRow(title=FINGERS.get(finger, finger))
                verify = Gtk.Button(label="Verify", valign=Gtk.Align.CENTER)
                verify.connect("clicked", lambda _, f=finger: reader.start("Verify", f))
                row.add_suffix(verify)
                remove = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Remove this finger",
                                    valign=Gtk.Align.CENTER)
                remove.connect("clicked", lambda _, f=finger: self.confirm_remove(f))
                row.add_suffix(remove)
                self.group.add(row)
                self.rows.append(row)
            if not reader.fingers:
                row = Adw.ActionRow(title="No saved fingers" if ready else "Reader unavailable")
                self.group.add(row)
                self.rows.append(row)
            self.available = [f for f in FINGERS if f not in reader.fingers]
            self.choice.set_model(Gtk.StringList.new([FINGERS[f] for f in self.available]))
            if old in self.available:
                self.choice.set_selected(self.available.index(old))
        if self.closing and not busy:
            self.reader.transport.close()
            self.window.destroy()
            self.quit()

    def enroll(self, *_):
        index = self.choice.get_selected()
        if index < len(self.available):
            self.reader.start("Enroll", self.available[index])

    def confirm_remove(self, finger):
        dialog = Adw.AlertDialog(heading=f"Remove {FINGERS[finger].lower()}?",
                                 body="You will need to enroll this finger again to use it for authentication.")
        if len(self.reader.fingers) == 1:
            dialog.set_body("This is your last saved finger. You can continue using your password and enroll again later.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", lambda _, response: self.reader.start("Delete", finger)
                       if response == "remove" else None)
        dialog.present(self.window)

    def close_requested(self, *_):
        self.closing = True
        if self.reader.phase in ("claiming", "starting", "active", "stopping", "releasing"):
            self.reader.cancel()
            self.update()
            return True
        self.reader.transport.close()
        self.quit()
        return False


if __name__ == "__main__":
    if os.geteuid() == 0:
        sys.exit("Open Fingerprints as your desktop user, without sudo.")
    sys.exit(Fingerprints().run(sys.argv))
