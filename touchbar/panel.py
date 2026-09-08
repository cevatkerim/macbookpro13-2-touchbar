#!/usr/bin/env python3
"""GTK settings for the custom Omarchy Touch Bar."""
from copy import deepcopy
import os
import subprocess
import sys
import threading

import gi
gi.require_version('Gtk','4.0')
gi.require_version('Adw','1')
from gi.repository import Adw, Gio, GLib, Gtk
from preferences import DEFAULTS, SHORTCUTS, Preferences, Selection


class TouchBarSettings(Adw.Application):
    def __init__(self):
        super().__init__(application_id='me.kerim.OmarchyTouchBar',flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.window = None
        self.busy = False
        self.syncing = False
        self.closing = False
        self.preferences = Preferences()
        self.selection = Selection()

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        initial_error = None
        try:
            self.settings = self.preferences.load()
        except (OSError,ValueError) as error:
            self.settings = deepcopy(DEFAULTS)
            initial_error = str(error)
        self.window = Adw.ApplicationWindow(application=self,title='Touch Bar',default_width=520,default_height=690)
        self.window.connect('close-request',self.close_requested)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.restart_button = Gtk.Button(icon_name='view-refresh-symbolic',tooltip_text='Restart Touch Bar controls')
        self.restart_button.connect('clicked',lambda *_: self.apply_selection(self.selection.enabled))
        header.pack_end(self.restart_button)
        toolbar.add_top_bar(header)
        self.window.set_content(toolbar)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        toolbar.set_content(scroll)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20,
                       margin_top=12,margin_bottom=24,margin_start=24,margin_end=24)
        clamp = Adw.Clamp(maximum_size=560)
        clamp.set_child(body)
        scroll.set_child(clamp)
        body.append(Gtk.Image(icon_name='input-keyboard-symbolic',pixel_size=42))
        title = Gtk.Label(label='Your Touch Bar')
        title.add_css_class('title-1')
        body.append(title)
        selection_group = Adw.PreferencesGroup()
        self.enable_row = Adw.SwitchRow(title='Custom Touch Bar',subtitle='Sliders and Omarchy shortcuts')
        self.enable_row.set_active(self.selection.enabled)
        self.enable_row.connect('notify::active',self.enable_changed)
        selection_group.add(self.enable_row)
        body.append(selection_group)
        self.shortcuts_group = Adw.PreferencesGroup(title='Shortcuts',description='Show the icons you use and choose their order.')
        body.append(self.shortcuts_group)
        self.shortcut_rows = []
        self.build_shortcuts()
        others = Adw.PreferencesGroup(title='Other controls')
        for key,title,subtitle in [('media','Media controls','Previous, play/pause and next'),
                                   ('keyboard','Keyboard brightness','Show the keyboard-backlight slider')]:
            row = Adw.SwitchRow(title=title,subtitle=subtitle)
            row.set_active(self.settings[key])
            row.connect('notify::active',self.other_changed,key)
            others.add(row)
        body.append(others)
        note = Gtk.Label(label='Escape, the Omarchy menu, volume and display brightness\nremain available. Hold Fn for function keys.',
                         wrap=True,justify=Gtk.Justification.CENTER)
        note.add_css_class('dim-label')
        body.append(note)
        self.status = Gtk.Label(wrap=True,xalign=0)
        self.status.add_css_class('dim-label')
        self.status.set_label(initial_error or self.selection_message())
        body.append(self.status)
        self.window.present()

    def selection_message(self):
        return 'Custom layout selected. Icon changes apply immediately.' if self.selection.enabled else 'Standard layout selected. Your custom icon choices are saved.'

    def build_shortcuts(self):
        for row in self.shortcut_rows:
            self.shortcuts_group.remove(row)
        self.shortcut_rows = []
        for index,item in enumerate(self.settings['shortcuts']):
            key = item['id']
            row = Adw.ActionRow(title=SHORTCUTS[key])
            for direction,icon,label in [(-1,'go-up-symbolic','Move earlier'),(1,'go-down-symbolic','Move later')]:
                button = Gtk.Button(icon_name=icon,tooltip_text=label,valign=Gtk.Align.CENTER)
                button.set_sensitive(0 <= index+direction < len(self.settings['shortcuts']))
                button.connect('clicked',self.move_shortcut,key,direction)
                row.add_suffix(button)
            toggle = Gtk.Switch(active=item['visible'],valign=Gtk.Align.CENTER,tooltip_text='Show '+SHORTCUTS[key].lower())
            toggle.connect('notify::active',self.shortcut_changed,key)
            row.add_suffix(toggle)
            row.set_activatable_widget(toggle)
            self.shortcuts_group.add(row)
            self.shortcut_rows.append(row)

    def save(self):
        try:
            self.preferences.save(self.settings)
            self.status.set_label('Saved. Changes appear on the custom Touch Bar immediately.')
        except (OSError,ValueError) as error:
            self.status.set_label('Could not save settings: '+str(error))

    def shortcut_changed(self, toggle, _, key):
        for item in self.settings['shortcuts']:
            if item['id'] == key:
                item['visible'] = toggle.get_active()
        self.save()

    def move_shortcut(self, _, key, direction):
        items = self.settings['shortcuts']
        index = next(i for i,item in enumerate(items) if item['id']==key)
        other = index+direction
        if 0 <= other < len(items):
            items[index],items[other] = items[other],items[index]
            self.save()
            self.build_shortcuts()

    def other_changed(self, row, _, key):
        self.settings[key] = row.get_active()
        self.save()

    def enable_changed(self, row, _):
        if not self.syncing:
            self.apply_selection(row.get_active())

    def apply_selection(self, enabled):
        if self.busy:
            return
        self.busy = True
        previous = self.selection.enabled
        self.enable_row.set_sensitive(False)
        self.restart_button.set_sensitive(False)
        self.status.set_label('Switching Touch Bar controls…')
        def work():
            error = None
            try:
                self.selection.set_enabled(enabled)
                subprocess.run(['systemctl','--user','restart','t1-touchbar.service'],
                               check=True,timeout=15,capture_output=True)
            except (OSError,ValueError,subprocess.SubprocessError) as exc:
                error = 'Could not switch the Touch Bar: '+str(exc)
                try:
                    self.selection.set_enabled(previous)
                    subprocess.run(['systemctl','--user','restart','t1-touchbar.service'],
                                   check=True,timeout=15,capture_output=True)
                except (OSError,ValueError,subprocess.SubprocessError):
                    error += ' Use Restart controls to retry.'
            GLib.idle_add(self.selection_finished,error)
        threading.Thread(target=work,daemon=False).start()

    def selection_finished(self, error):
        self.busy = False
        self.syncing = True
        self.enable_row.set_active(self.selection.enabled)
        self.syncing = False
        self.enable_row.set_sensitive(True)
        self.restart_button.set_sensitive(True)
        self.status.set_label(error or self.selection_message())
        if self.closing:
            self.window.destroy()
            self.quit()
        return False

    def close_requested(self, *_):
        if self.busy:
            self.closing = True
            return True
        self.quit()
        return False


if __name__=='__main__':
    if os.geteuid()==0:
        sys.exit('Open Touch Bar settings as your desktop user, without sudo.')
    sys.exit(TouchBarSettings().run(sys.argv))
