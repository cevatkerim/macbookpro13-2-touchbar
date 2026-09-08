import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.menu = self.home / ".config/omarchy/extensions/omarchy-menu.jsonc"
        self.hypr = self.home / ".config/hypr/hyprland.lua"
        self.menu.parent.mkdir(parents=True)
        self.hypr.parent.mkdir(parents=True)
        self.original_menu = '{\n  // Existing preferences\n  "personal": {"label": "My menu"},\n}\n'
        self.original_hypr = '-- Existing settings\nrequire("hypr.monitors")\n'
        self.menu.write_text(self.original_menu)
        self.hypr.write_text(self.original_hypr)

    def run_installer(self, *args):
        with patch.object(Path, "home", return_value=self.home), \
             patch("sys.argv", ["install.py", *args]), \
             patch.object(install.subprocess, "run"), \
             contextlib.redirect_stdout(io.StringIO()):
            install.main()

    def test_reinstall_is_idempotent_and_uninstall_preserves_user_config(self):
        self.run_installer()
        first_menu, first_hypr = self.menu.read_text(), self.hypr.read_text()
        self.run_installer()
        self.assertEqual(self.menu.read_text(), first_menu)
        self.assertEqual(self.hypr.read_text(), first_hypr)
        self.run_installer("--uninstall")
        self.assertEqual(self.menu.read_text(), self.original_menu)
        self.assertEqual(self.hypr.read_text(), self.original_hypr)
        self.assertFalse((self.home / ".local/bin/t1-fingerprints").exists())

    def test_existing_custom_fingerprint_action_is_not_overwritten(self):
        original = '{\n  "setup.security.fingerprint": {"action": "custom"}\n}\n'
        self.menu.write_text(original)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_installer()
        self.assertEqual(self.menu.read_text(), original)
        self.assertFalse((self.home / ".local/bin/t1-fingerprints").exists())

    def test_opt_out_leaves_both_config_files_unchanged(self):
        self.run_installer("--no-menu", "--no-window-rule")
        self.assertEqual(self.menu.read_text(), self.original_menu)
        self.assertEqual(self.hypr.read_text(), self.original_hypr)
        self.assertTrue((self.home / ".local/bin/t1-fingerprints").exists())


if __name__ == "__main__":
    unittest.main()
