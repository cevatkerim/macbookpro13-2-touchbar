import errno
import unittest
from unittest.mock import patch

from protocol import connect_when_ready


class StartupTests(unittest.TestCase):
    def test_missing_then_refused_socket_eventually_connects(self):
        hardware = object()
        with patch('protocol.Hardware', side_effect=[
            FileNotFoundError(errno.ENOENT, 'Not ready'),
            ConnectionRefusedError(errno.ECONNREFUSED, 'Not listening'), hardware,
        ]) as connect, patch('protocol.time.sleep') as sleep:
            self.assertIs(connect_when_ready(lambda: True), hardware)
        self.assertEqual(connect.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_unavailable_hardware_eventually_allows_fallback(self):
        with patch('protocol.Hardware', side_effect=FileNotFoundError(errno.ENOENT, 'Not ready')) as connect, \
             patch('protocol.time.monotonic', side_effect=[0, 0, 120]), \
             patch('protocol.time.sleep'):
            with self.assertRaises(FileNotFoundError):
                connect_when_ready(lambda: True)
        self.assertEqual(connect.call_count, 2)

    def test_stop_during_wait_does_not_open_another_connection(self):
        running = iter([True, False])
        with patch('protocol.Hardware', side_effect=FileNotFoundError(errno.ENOENT, 'Not ready')) as connect, \
             patch('protocol.time.sleep'):
            self.assertIsNone(connect_when_ready(lambda: next(running)))
        self.assertEqual(connect.call_count, 1)

    def test_trust_permissions_and_protocol_errors_are_not_retried(self):
        for error in (PermissionError(errno.EACCES, 'Denied'),
                      ValueError('Untrusted hardware peer'),
                      ValueError('Hardware negotiation failed'), TimeoutError('Timed out')):
            with self.subTest(error=error), patch('protocol.Hardware', side_effect=error) as connect, \
                 patch('protocol.time.sleep') as sleep:
                with self.assertRaises(type(error)):
                    connect_when_ready(lambda: True)
                connect.assert_called_once()
                sleep.assert_not_called()
