"""Bounded, unprivileged desktop actions and status polling off the render loop."""
from collections import deque
import json
import os
from pathlib import Path
import subprocess
import threading
import time


class Desktop:
    def __init__(self):
        self.condition = threading.Condition()
        self.queue = deque(maxlen=12)
        self.latest = {}
        self.state = {}
        self.error = None
        self.closed = False
        self.screenshot = None
        self.provider = os.environ.get('T1BRIDGE_DESKTOP_PROVIDER', '/usr/local/libexec/t1bridge-omarchy-desktop')
        if not Path(self.provider).is_absolute() or not os.access(self.provider, os.X_OK):
            raise ValueError('The Omarchy desktop provider is not installed')
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    @staticmethod
    def run(args, timeout=1):
        env = dict(os.environ, LC_ALL='C.UTF-8')
        return subprocess.check_output(args, timeout=timeout, text=True, stderr=subprocess.DEVNULL, env=env)

    def submit(self, action, value=None):
        with self.condition:
            if action in ('volume','osd-brightness','osd-keyboard'):
                self.latest[action] = value
            elif len(self.queue) < self.queue.maxlen:
                self.queue.append((action,value))
            self.condition.notify()

    def status(self):
        values = {}
        try:
            values['locked'] = self.run(['omarchy-shell','lock','isLocked']).strip() != 'false'
        except (OSError, subprocess.SubprocessError):
            values['locked'] = True
        try:
            fields = self.run([self.provider,'v1','status']).split()
            if len(fields) == 5 and fields[:2] == ['T1BRIDGE-DESKTOP','1']:
                values['volume'] = int(fields[3]) if fields[3].isdigit() else None
                values['muted'] = fields[4] == '1'
        except (OSError, ValueError, subprocess.SubprocessError):
            values['volume'] = None
        for name, directory, pattern in [('brightness','/sys/class/backlight','*'), ('keyboard','/sys/class/leds','*kbd_backlight*')]:
            try:
                devices = list(Path(directory).glob(pattern))
                if len(devices) != 1: raise ValueError('Ambiguous brightness device')
                value = int((devices[0]/'brightness').read_text())
                maximum = int((devices[0]/'max_brightness').read_text())
                values[name] = round(value*100/maximum) if maximum > 0 and 0 <= value <= maximum else None
            except (OSError, ValueError):
                values[name] = None
        try:
            active = json.loads(self.run(['hyprctl','activeworkspace','-j']))
            if type(active.get('id')) is int and 1 <= active['id'] <= 999:
                values['workspace'] = active['id']
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        with self.condition:
            self.state.update(values)

    def execute(self, action, value):
        if action in ('launcher','notifications','workspace','screenshot'):
            if self.run(['omarchy-shell','lock','isLocked']).strip() != 'false':
                return
        fixed = {
            'launcher': ['omarchy','menu','toggle'],
            'notifications': ['omarchy-shell','notifications','showHistory'],
            'previous': [self.provider,'v1','media-previous'],
            'play': [self.provider,'v1','media-play-pause'],
            'next': [self.provider,'v1','media-next'],
            'mute': [self.provider,'v1','toggle-mute'],
            'osd-brightness': [self.provider,'v1','show-display-brightness'],
            'osd-keyboard': [self.provider,'v1','show-keyboard-backlight'],
        }
        if action == 'volume' and type(value) is int and 0 <= value <= 100:
            self.run([self.provider,'v1','set-volume',str(value)])
        elif action == 'workspace' and type(value) is int and 1 <= value <= 10:
            self.run(['hyprctl','dispatch',f'hl.dsp.focus({{ workspace = "{value}" }})'])
        elif action == 'screenshot':
            if self.screenshot is None or self.screenshot.poll() is not None:
                self.screenshot = subprocess.Popen(['omarchy','capture','screenshot'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        elif action in fixed:
            self.run(fixed[action])

    def worker(self):
        next_poll = 0
        while not self.closed:
            if time.monotonic() >= next_poll:
                self.status()
                next_poll = time.monotonic()+1.5
            with self.condition:
                if self.queue:
                    job = self.queue.popleft()
                elif self.latest:
                    name = next(iter(self.latest))
                    job = (name,self.latest.pop(name))
                else:
                    self.condition.wait(0.15)
                    continue
            try:
                self.execute(*job)
            except (OSError, ValueError, subprocess.SubprocessError):
                with self.condition:
                    self.error = 'Desktop action failed; check Omarchy is running.'

    def close(self):
        self.closed = True
        with self.condition:
            self.queue.clear()
            self.latest.clear()
            self.condition.notify()
