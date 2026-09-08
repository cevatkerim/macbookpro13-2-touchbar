import json
import subprocess
import unittest
from unittest.mock import patch

from desktop import Desktop


class SessionEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.desktop = object.__new__(Desktop)
        self.desktop.environment = {'PATH': '/usr/bin', 'LC_ALL': 'C.UTF-8'}

    def test_session_import_after_startup_recovers_desktop_commands(self):
        imported = {'OMARCHY_PATH': '/synthetic/omarchy', 'PATH': '/synthetic/bin:/usr/bin',
                    'WAYLAND_DISPLAY': 'wayland-7', 'HYPRLAND_INSTANCE_SIGNATURE': 'synthetic-session'}
        with patch.object(self.desktop, 'run', side_effect=['{}', json.dumps(imported)]):
            self.desktop.refresh_environment()
            self.assertNotIn('OMARCHY_PATH', self.desktop.environment)
            self.desktop.refresh_environment()
        with patch('desktop.subprocess.check_output', return_value='false\n') as run:
            self.assertEqual(self.desktop.run(['omarchy-shell', 'lock', 'isLocked']), 'false\n')
            self.assertEqual(run.call_args.kwargs['env'], dict(imported, LC_ALL='C.UTF-8'))

    def test_unrelated_environment_cannot_replace_user_or_loader_settings(self):
        imported = {'OMARCHY_PATH': '/synthetic/omarchy', 'HOME': '/other',
                    'LD_PRELOAD': '/synthetic/library', 'LC_ALL': 'invalid'}
        with patch.object(self.desktop, 'run', return_value=json.dumps(imported)):
            self.desktop.refresh_environment()
        self.assertEqual(self.desktop.environment,
                         {'PATH': '/usr/bin', 'LC_ALL': 'C.UTF-8', 'OMARCHY_PATH': '/synthetic/omarchy'})

    def test_unavailable_or_malformed_manager_preserves_last_environment(self):
        previous = self.desktop.environment.copy()
        for response in ('not JSON', '[]', '{"PATH": 42}', '{"PATH": "bad\\u0000path"}'):
            with self.subTest(response=response), patch.object(self.desktop, 'run', return_value=response):
                self.desktop.refresh_environment()
                self.assertEqual(self.desktop.environment, previous)
        with patch.object(self.desktop, 'run', side_effect=subprocess.TimeoutExpired('systemctl', 1)):
            self.desktop.refresh_environment()
        self.assertEqual(self.desktop.environment, previous)
