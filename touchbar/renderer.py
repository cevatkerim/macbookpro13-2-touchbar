#!/usr/bin/env python3
"""Omarchy Touch Bar: sliders and desktop controls over T1Bridge IPC (GPL-2.0)."""
import argparse
import json
import os
from pathlib import Path
import select
import signal
import sys
import time

from drawing import render
from layout import Layout
from protocol import Hardware
from preferences import Preferences


def overlay_state():
    path = Path('/run/t1bridge/touch-id-state.json')
    try:
        info = path.stat()
        if info.st_uid != 0 or info.st_size > 1024:
            return None
        record = json.loads(path.read_text())
        version = record.get('version')
        fields = {'version','pid','state'} | ({'progress'} if version == 2 else set())
        if set(record) != fields or version not in (1,2) or type(record['pid']) is not int or record['pid'] <= 0:
            return None
        if not Path('/proc',str(record['pid'])).exists():
            return None
        names = {'enrollment':'Touch ID · Follow enrollment instructions',
                 'authenticate':'Touch ID · Touch the sensor', 'approve':'Touch ID · Approve request',
                 'retry':'Touch ID · Lift your finger and try again', 'success':'Touch ID · Matched'}
        if version == 2 and (record['state'] != 'enrollment' or type(record['progress']) is not int or not 0 <= record['progress'] <= 100):
            return None
        return names.get(record['state'])
    except (OSError, ValueError, TypeError, KeyError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', type=Path, help='Write a PNG without connecting to hardware')
    parser.add_argument('--page', choices=['home','volume','brightness','keyboard','workspaces','fn'], default='home')
    parser.add_argument('--test-seconds', type=float, help='End the live renderer after this many seconds')
    args = parser.parse_args()
    layout = Layout()
    preferences = Preferences()
    settings_error = None
    try:
        layout.configure(preferences.load())
    except (OSError, ValueError) as error:
        settings_error = str(error)
        print("Using default Touch Bar settings: " + settings_error, file=sys.stderr)
    if args.preview:
        layout.page = args.page
        layout.fn = args.page == 'fn'
        layout.state.update(volume=42,brightness=65,keyboard=30,workspace=2,locked=False)
        render(layout).write_to_png(str(args.preview))
        return 0
    if os.geteuid() == 0:
        parser.error('Run as the desktop user, without sudo.')
    from desktop import Desktop
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    hardware, desktop = None, None
    try:
        hardware = Hardware()
        desktop = Desktop()
        print('Omarchy Touch Bar connected; default renderer resumes on exit.', flush=True)
        start = time.monotonic()
        next_status = 0
        last_draw = 0
        last_level = 0
        last_pixels = None
        queued_levels = {}
        local_levels_until = {}
        dirty = True
        while running and (args.test_seconds is None or time.monotonic()-start < args.test_seconds):
            now = time.monotonic()
            if now >= next_status:
                if layout.contact is None and not layout.blocked:
                    try:
                        settings = preferences.load()
                        if settings != layout.settings:
                            layout.configure(settings)
                            dirty = True
                        settings_error = None
                    except (OSError, ValueError) as error:
                        if str(error) != settings_error:
                            settings_error = str(error)
                            print('Keeping the last valid Touch Bar settings: ' + settings_error, file=sys.stderr)
                overlay = overlay_state()
                if overlay != layout.overlay:
                    layout.change_context(fn=layout.fn, overlay=overlay)
                    queued_levels.clear()
                    dirty = True
                with desktop.condition:
                    values = dict(desktop.state)
                    error, desktop.error = desktop.error, None
                if error:
                    print(error, file=sys.stderr, flush=True)
                for name,value in values.items():
                    if now >= local_levels_until.get(name,0) and layout.state.get(name) != value:
                        if name == 'locked':
                            layout.blocked = layout.blocked or layout.contact is not None
                            layout.contact, layout.pressed = None, None
                            layout.page = 'home'
                            queued_levels.clear()
                        layout.state[name] = value
                        dirty = True
                if not hardware.features & 8: layout.state['brightness'] = None
                if not hardware.features & 16: layout.state['keyboard'] = None
                next_status = now + 0.15
            ready, _, _ = select.select([hardware.sock],[],[],0.02)
            if ready:
                for _ in range(64):
                    try:
                        event = hardware.dispatch()
                    except BlockingIOError:
                        break
                    if event is None:
                        continue
                    fn, contacts = event
                    if fn != layout.fn:
                        layout.change_context(fn=fn, overlay=layout.overlay)
                        queued_levels.clear()
                    scaled = [(identity,x*2170/hardware.width,y*60/hardware.height) for identity,x,y in contacts]
                    for action in layout.handle(scaled):
                        if action[0] == 'level':
                            _, name,value = action
                            queued_levels[name] = value
                            layout.state[name] = value
                            local_levels_until[name] = now + 2
                            if name == 'volume': layout.state['muted'] = False
                        else:
                            name = action[1]
                            if name == 'esc': hardware.tap(1)
                            elif name.startswith('key:'):
                                number = int(name.split(':')[1])
                                hardware.tap(58+number if number <= 10 else 76+number)
                            elif name == 'cancel-auth': hardware.send(7)
                            elif name.startswith('workspace:'):
                                number = int(name.split(':')[1])
                                desktop.submit('workspace',number)
                                layout.state['workspace'] = number
                                local_levels_until['workspace'] = now + 1
                            else: desktop.submit(name)
                    dirty = True
            if queued_levels and now-last_level >= 0.08 and not layout.overlay:
                for name,value in queued_levels.items():
                    if name == 'volume': desktop.submit('volume',value)
                    else:
                        hardware.brightness(name,value)
                        desktop.submit('osd-'+name)
                queued_levels.clear()
                last_level = now
            if dirty and not hardware.busy and now-last_draw >= 1/30:
                surface = render(layout,hardware.width,hardware.height)
                pixels = bytes(surface.get_data())
                if pixels != last_pixels:
                    hardware.submit(pixels)
                    last_pixels = pixels
                dirty = False
                last_draw = now
            hardware.check_timeout()
        return 0
    finally:
        if desktop: desktop.close()
        if hardware: hardware.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, TimeoutError) as error:
        print('Omarchy Touch Bar stopped: '+str(error),file=sys.stderr,flush=True)
        sys.exit(1)
