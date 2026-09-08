import struct
import unittest
from unittest.mock import patch

from layout import Layout
from protocol import Hardware, decode, input_frame, packet
from desktop import Desktop


class GestureTests(unittest.TestCase):
    def setUp(self):
        self.layout = Layout()
        self.layout.state.update(locked=False,volume=50,brightness=50)

    def item(self, action):
        return next(i for i in self.layout.items() if i.action == action)

    def tap(self, action):
        item = self.item(action)
        self.assertEqual(self.layout.handle([(0,item.x+item.width/2,30)]),[])
        return self.layout.handle([])

    def test_tap_icon_opens_slider_without_changing_level(self):
        self.assertEqual(self.tap('volume'),[])
        self.assertEqual(self.layout.page,'volume')
        self.assertEqual(self.layout.state['volume'],50)

    def test_brightness_slider_clamps_at_one_percent(self):
        self.tap('brightness')
        item = self.item('slider')
        self.assertEqual(self.layout.handle([(0,item.x+1,30)]),[('level','brightness',1)])
        self.assertEqual(self.layout.handle([(0,2160,30)]),[('level','brightness',100)])
        self.assertEqual(self.layout.handle([]),[])

    def test_drag_across_buttons_never_launches(self):
        item = self.item('launcher')
        self.layout.handle([(0,item.x+10,30)])
        self.layout.handle([(0,item.x+100,30)])
        self.assertEqual(self.layout.handle([]),[])

    def test_multitouch_suppresses_action_until_all_fingers_lift(self):
        item = self.item('launcher')
        self.layout.handle([(0,item.x+10,30)])
        self.layout.handle([(0,item.x+10,30),(1,900,30)])
        self.layout.handle([(0,item.x+10,30)])
        self.assertEqual(self.layout.handle([]),[])
        self.assertEqual(self.tap('launcher'),[('action','launcher')])

    def test_auth_overlay_during_touch_suppresses_old_action(self):
        item = self.item('launcher')
        self.layout.handle([(0,item.x+10,30)])
        self.layout.change_context(overlay='Touch ID')
        self.assertEqual(self.layout.handle([]),[])
        self.assertEqual(self.tap('cancel-auth'),[('action','cancel-auth')])

    def test_fn_row_returns_function_key_and_preserves_page(self):
        self.tap('volume')
        self.layout.change_context(fn=True)
        self.assertEqual(self.tap('key:12'),[('action','key:12')])
        self.layout.change_context(fn=False)
        self.assertEqual(self.layout.page,'volume')

    def test_all_workspace_targets_are_available(self):
        self.tap('workspaces')
        for number in range(1,11):
            self.assertEqual(self.tap(f'workspace:{number}'),[('action',f'workspace:{number}')])

    def test_locked_layout_hides_desktop_commands(self):
        self.layout.state['locked'] = True
        self.assertNotIn('launcher',[i.action for i in self.layout.items()])
        self.assertNotIn('screenshot',[i.action for i in self.layout.items()])


class ProtocolTests(unittest.TestCase):
    def test_length_mismatch_rejected(self):
        with self.assertRaises(ValueError): decode(packet(1,1,b'x')+b'x')

    def test_out_of_bounds_and_duplicate_contacts_rejected(self):
        header = struct.pack('<QBBH',123,0,2,0)
        contact = struct.pack('<BBBBII',0,1,1,0,10,10)
        with self.assertRaises(ValueError): input_frame(header+contact*2,2170,60)
        with self.assertRaises(ValueError):
            input_frame(struct.pack('<QBBH',123,0,1,0)+struct.pack('<BBBBII',0,1,1,0,2170,10),2170,60)

    def test_cancel_after_auth_finished_does_not_drop_renderer(self):
        hardware = object.__new__(Hardware)
        hardware.pending = {17:(7,0)}
        with patch.object(hardware,'receive',return_value=(0x8003,17,struct.pack('<I',7))):
            self.assertIsNone(hardware.dispatch())
        self.assertEqual(hardware.pending,{})

    def test_empty_frame_releases_contacts_and_preserves_fn(self):
        self.assertEqual(input_frame(struct.pack('<QBBH',123,1,0,0),2170,60),(True,[]))


class DesktopTests(unittest.TestCase):
    def test_locked_desktop_never_executes_launcher(self):
        desktop = object.__new__(Desktop)
        with patch.object(desktop,'run',return_value='true\n') as run:
            desktop.execute('launcher',None)
            self.assertEqual(run.call_count,1)

    def test_workspace_uses_only_validated_number(self):
        desktop = object.__new__(Desktop)
        desktop.provider = '/synthetic/provider'
        with patch.object(desktop,'run',return_value='false\n') as run:
            desktop.execute('workspace','2; arbitrary')
            self.assertEqual(run.call_count,1)
            desktop.execute('workspace',2)
            self.assertEqual(run.call_args.args[0],['hyprctl','dispatch','hl.dsp.focus({ workspace = "2" })'])


if __name__ == '__main__':
    unittest.main()
