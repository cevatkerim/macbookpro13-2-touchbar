from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from layout import Layout
from preferences import DEFAULTS, Preferences, Selection, validate


class PreferencesTests(unittest.TestCase):
    def test_unknown_actions_duplicate_ids_and_non_booleans_are_rejected(self):
        for change in ('unknown','duplicate','boolean'):
            value=deepcopy(DEFAULTS)
            if change=='unknown': value['shortcuts'][0]['id']='run-command'
            if change=='duplicate': value['shortcuts'][0]['id']=value['shortcuts'][1]['id']
            if change=='boolean': value['media']='false'
            with self.assertRaises(ValueError): validate(value)

    def test_save_round_trip_preserves_order_and_visibility(self):
        with tempfile.TemporaryDirectory() as temporary:
            preferences=Preferences(Path(temporary))
            value=preferences.load()
            value['shortcuts'].reverse()
            value['shortcuts'][0]['visible']=False
            preferences.save(value)
            self.assertEqual(preferences.load(),value)
            self.assertEqual(preferences.path.stat().st_mode & 0o777,0o600)
            self.assertEqual(list(Path(temporary).glob('.touchbar-*')),[])

    def test_hide_and_reorder_shortcuts_preserves_essential_controls(self):
        layout=Layout()
        layout.state['locked']=False
        settings=deepcopy(DEFAULTS)
        settings['shortcuts'].reverse()
        settings['shortcuts'][1]['visible']=False
        settings['media']=False
        settings['keyboard']=False
        layout.configure(settings)
        self.assertEqual([i.action for i in layout.items()],
                         ['esc','launcher','notifications','workspaces','volume','brightness'])

    def test_default_button_is_absent_from_all_pages(self):
        layout=Layout()
        for locked in (True,False):
            layout.state['locked']=locked
            for page in ('home','volume','brightness','keyboard','workspaces'):
                layout.page=page
                self.assertNotIn('stock',[i.action for i in layout.items()])

    def test_hiding_open_workspace_page_returns_home(self):
        layout=Layout()
        layout.page='workspaces'
        settings=deepcopy(DEFAULTS)
        settings['shortcuts'][0]['visible']=False
        layout.configure(settings)
        self.assertEqual(layout.page,'home')

    def test_reconfiguring_during_touch_cancels_old_target(self):
        layout=Layout()
        layout.state['locked']=False
        item=next(i for i in layout.items() if i.action=='launcher')
        layout.handle([(0,item.x+10,30)])
        layout.configure(DEFAULTS)
        self.assertEqual(layout.handle([]),[])


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name)
        self.launcher=self.base/'launch'
        self.launcher.write_text('#!/bin/sh\nexit 0\n')
        self.launcher.chmod(0o755)
        self.selection=Selection(self.base/'config',self.launcher)

    def test_enable_disable_round_trip_from_stock(self):
        self.selection.set_enabled(True)
        self.selection.set_enabled(True)
        self.assertTrue(self.selection.enabled)
        self.selection.set_enabled(False)
        self.selection.set_enabled(False)
        self.assertFalse(self.selection.path.exists())
        self.assertTrue(self.launcher.exists())

    def test_previous_renderer_is_preserved_and_restored(self):
        self.selection.directory.mkdir()
        self.selection.path.write_text('previous renderer')
        self.selection.set_enabled(True)
        self.assertEqual(self.selection.backup.read_text(),'previous renderer')
        self.selection.set_enabled(False)
        self.assertEqual(self.selection.path.read_text(),'previous renderer')
        self.assertFalse(self.selection.backup.exists())

    def test_conflicting_backup_is_never_overwritten(self):
        self.selection.directory.mkdir()
        self.selection.path.write_text('other renderer')
        self.selection.backup.write_text('saved renderer')
        with self.assertRaises(ValueError): self.selection.set_enabled(True)
        self.assertEqual(self.selection.path.read_text(),'other renderer')
        self.assertEqual(self.selection.backup.read_text(),'saved renderer')


if __name__=='__main__':
    unittest.main()
