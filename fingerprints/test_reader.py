"""Exercise ownership races without touching any saved fingerprints."""
import unittest
from reader import Reader

FINGER = "right-index-finger"
NEW = "right-middle-finger"


class Transport:
    def __init__(self):
        self.calls = []
        self.closed = False

    def call(self, method, argument, callback):
        self.calls.append((method, argument, callback))

    def close(self):
        self.closed = True

    def reply(self, method, value=(), error=None):
        name, argument, callback = self.calls.pop(0)
        assert name == method, (name, method)
        callback(value, error)
        return argument


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.bus = Transport()
        self.reader = Reader(self.bus, lambda: None)
        self.reader.phase = "ready"
        self.reader.fingers = [FINGER]

    def finish_release(self):
        self.bus.reply("Release")
        self.assertEqual(self.bus.reply("ListEnrolledFingers", ([FINGER],)), "")
        self.assertEqual(self.reader.phase, "ready")
        self.assertEqual(self.bus.calls, [])

    def test_cancel_pending_claim_never_starts_enrollment(self):
        self.reader.start("Enroll", NEW)
        self.reader.cancel()
        self.assertEqual(self.bus.reply("Claim"), "")
        self.finish_release()

    def test_cancel_pending_start_stops_before_release(self):
        self.reader.start("Verify", FINGER)
        self.bus.reply("Claim")
        self.reader.cancel()
        self.bus.reply("VerifyStart")
        self.bus.reply("VerifyStop")
        self.finish_release()

    def test_terminal_signal_before_start_reply_is_not_lost(self):
        self.reader.start("Verify", FINGER)
        self.bus.reply("Claim")
        self.reader.signal("VerifyStatus", ("verify-match", True))
        self.bus.reply("VerifyStart")
        self.bus.reply("VerifyStop")
        self.finish_release()
        self.assertEqual(self.reader.message, "Fingerprint matched.")

    def test_stop_error_drops_connection_to_release_claim(self):
        self.reader.start("Verify", FINGER)
        self.bus.reply("Claim")
        self.bus.reply("VerifyStart")
        self.reader.cancel()
        self.bus.reply("VerifyStop", error="Timed out")
        self.assertTrue(self.bus.closed)
        self.assertEqual(self.reader.phase, "offline")

    def test_claim_timeout_drops_connection(self):
        self.reader.start("Verify", FINGER)
        self.bus.reply("Claim", error="Timed out")
        self.assertTrue(self.bus.closed)
        self.assertEqual(self.bus.calls, [])

    def test_delete_targets_only_selected_finger(self):
        self.reader.start("Delete", FINGER)
        self.assertEqual(self.bus.reply("Claim"), "")
        self.assertEqual(self.bus.reply("DeleteEnrolledFinger"), FINGER)
        self.finish_release()

    def test_duplicate_full_and_invalid_enrollment_do_nothing(self):
        self.reader.start("Enroll", FINGER)
        self.reader.start("Enroll", "any")
        self.reader.fingers = [FINGER, NEW, "left-thumb"]
        self.reader.start("Enroll", "right-thumb")
        self.assertEqual(self.bus.calls, [])

    def test_retries_keep_capture_active_and_other_signals_are_ignored(self):
        self.reader.start("Enroll", NEW)
        self.bus.reply("Claim")
        self.bus.reply("EnrollStart")
        self.reader.signal("VerifyStatus", ("verify-match", True))
        self.reader.signal("EnrollStatus", ("enroll-stage-passed", False))
        self.assertEqual(self.reader.scans, 1)
        self.assertEqual(self.reader.phase, "active")
        self.assertEqual(self.bus.calls, [])


if __name__ == "__main__":
    unittest.main()
