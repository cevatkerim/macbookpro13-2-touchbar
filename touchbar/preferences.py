"""Validated, atomic preferences shared by the panel and renderer."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

SHORTCUTS = {'workspaces': 'Workspace switcher', 'screenshot': 'Screenshot', 'notifications': 'Notifications'}
DEFAULTS = {'version': 1, 'shortcuts': [{'id': name, 'visible': True} for name in SHORTCUTS],
            'media': True, 'keyboard': True}


def config_directory():
    directory = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')
    if not directory.is_absolute():
        raise ValueError('XDG_CONFIG_HOME must be an absolute path.')
    return directory/'t1bridge'


def validate(value):
    if not isinstance(value,dict) or set(value) != set(DEFAULTS) or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported Touch Bar settings format.')
    shortcuts = value['shortcuts']
    if not isinstance(shortcuts,list) or len(shortcuts) != len(SHORTCUTS):
        raise ValueError('Invalid shortcut list.')
    seen = set()
    for shortcut in shortcuts:
        if not isinstance(shortcut,dict) or set(shortcut) != {'id','visible'}:
            raise ValueError('Invalid shortcut.')
        name = shortcut['id']
        if not isinstance(name,str) or name not in SHORTCUTS or name in seen or type(shortcut['visible']) is not bool:
            raise ValueError('Invalid shortcut name or visibility.')
        seen.add(name)
    if type(value['media']) is not bool or type(value['keyboard']) is not bool:
        raise ValueError('Control visibility must be true or false.')
    return deepcopy(value)


class Preferences:
    def __init__(self, directory=None):
        self.path = (directory if directory is not None else config_directory())/'omarchy-touchbar.json'

    def load(self):
        try:
            if self.path.stat().st_size > 16384:
                raise ValueError('Touch Bar settings are too large.')
            return validate(json.loads(self.path.read_text()))
        except FileNotFoundError:
            return deepcopy(DEFAULTS)

    def save(self, value):
        value = validate(value)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w',dir=self.path.parent,prefix='.touchbar-',delete=False) as out:
                temporary = Path(out.name)
                json.dump(value,out,indent=2)
                out.write('\n')
                out.flush()
                os.fsync(out.fileno())
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


class Selection:
    def __init__(self, directory=None, launcher=None):
        self.directory = directory if directory is not None else config_directory()
        self.launcher = launcher if launcher is not None else Path.home()/'.local/share/omarchy-touchbar/launch'
        self.path = self.directory/'renderer'
        self.backup = self.directory/'renderer.before-omarchy-touchbar'

    @property
    def enabled(self):
        return self.path.is_symlink() and self.path.resolve() == self.launcher.resolve()

    def set_enabled(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Invalid renderer selection.')
        if enabled:
            if not self.launcher.is_file() or not os.access(self.launcher,os.X_OK):
                raise ValueError('Install the custom Touch Bar renderer first.')
            if self.enabled:
                return
            self.directory.mkdir(parents=True,exist_ok=True)
            if self.path.exists() or self.path.is_symlink():
                if self.backup.exists() or self.backup.is_symlink():
                    raise ValueError('A previous renderer backup exists; it will not be overwritten.')
                self.path.rename(self.backup)
            try:
                self.path.symlink_to(self.launcher)
            except OSError:
                if self.backup.exists() or self.backup.is_symlink():
                    self.backup.rename(self.path)
                raise
        elif self.enabled:
            self.path.unlink()
            if self.backup.exists() or self.backup.is_symlink():
                self.backup.rename(self.path)
