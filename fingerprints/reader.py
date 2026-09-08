"""Own-user fprintd client. No biometric data is read or stored by this panel."""

FINGERS = {
    f"{hand}-{finger}": f"{hand.title()} {label}"
    for hand in ("left", "right")
    for finger, label in (("thumb", "thumb"), ("index-finger", "index finger"),
                          ("middle-finger", "middle finger"), ("ring-finger", "ring finger"),
                          ("little-finger", "little finger"))
}


def error_text(error):
    text = str(error)
    for code, explanation in {
        "AlreadyInUse": "The reader is busy. Finish the other fingerprint prompt and try again.",
        "PermissionDenied": "Authorization was denied. Try again and approve the system prompt.",
        "NoSuchDevice": "Touch ID is unavailable. Check that the Touch Bar is running, then refresh.",
        "NoEnrolledPrints": "No fingerprints are saved yet.",
    }.items():
        if code in text:
            return explanation
    return text


class Reader:
    def __init__(self, transport, changed):
        self.transport, self.changed = transport, changed
        self.phase = "offline"
        self.fingers = []
        self.message = "Connecting to Touch ID…"
        self.operation = None
        self.cancelled = False
        self.terminal = None
        self.scans = 0

    def publish(self, message=None):
        if message is not None:
            self.message = message
        self.changed()

    def refresh(self):
        if self.phase not in ("offline", "ready"):
            return
        self.phase = "loading"
        self.publish("Connecting to Touch ID…")
        self.transport.connect(self.signal, self.disconnected, self.connected)

    def connected(self, error=None):
        if error:
            self.disconnected(error)
        else:
            self.list_fingers()

    def list_fingers(self, message=None):
        self.phase = "loading"
        def listed(value, error):
            if error and "NoEnrolledPrints" not in str(error):
                self.disconnected(error)
                return
            self.fingers = list(value[0]) if not error else []
            self.phase = "ready"
            self.operation = None
            self.publish(message or "Choose a finger to verify, or add a new one.")
        self.transport.call("ListEnrolledFingers", "", listed)

    def start(self, operation, finger):
        if self.phase != "ready" or finger not in FINGERS:
            return
        if operation not in ("Enroll", "Verify", "Delete"):
            return
        if operation == "Enroll" and (finger in self.fingers or len(self.fingers) >= 3):
            return
        if operation != "Enroll" and finger not in self.fingers:
            return
        self.operation, self.finger = operation, finger
        self.cancelled, self.terminal, self.scans = False, None, 0
        self.phase = "claiming"
        self.publish("Requesting access to Touch ID…")
        self.transport.call("Claim", "", self.claimed)

    def claimed(self, value, error):
        if error:
            # Drop our dedicated connection: even a late successful Claim cannot
            # leave this client owning the sensor after a timeout.
            self.disconnected(error)
            return
        if self.cancelled:
            self.release("Cancelled.")
            return
        self.phase = "starting"
        method = "DeleteEnrolledFinger" if self.operation == "Delete" else self.operation + "Start"
        self.publish("Removing selected finger…" if self.operation == "Delete"
                     else f"Touch the sensor with your {FINGERS[self.finger].lower()}.")
        self.transport.call(method, self.finger, self.started)

    def started(self, value, error):
        if error:
            self.disconnected(error)
        elif self.operation == "Delete":
            self.release(f"{FINGERS[self.finger]} removed.")
        else:
            self.phase = "active"
            if self.cancelled:
                self.finish("Cancelled.")
            elif self.terminal:
                self.finish(self.terminal)
            else:
                self.publish()

    def signal(self, name, values):
        if self.phase not in ("starting", "active") or name != self.operation + "Status":
            return
        result, done = values
        messages = {
            "enroll-completed": "Fingerprint saved. Verify it to check the result.",
            "verify-match": "Fingerprint matched.",
            "verify-no-match": "No match. Try again with the selected finger.",
            "enroll-duplicate": "That fingerprint is already saved. Try a different finger.",
            "enroll-data-full": "The reader is full. Remove a saved finger before adding another.",
            "enroll-failed": "Enrollment failed. You can try again.",
        }
        if result.endswith("disconnected"):
            self.disconnected("Touch ID disconnected. Refresh when it is available again.")
            return
        if result == "enroll-stage-passed":
            self.scans += 1
            message = f"Scan {self.scans} accepted. Lift your finger, then touch a slightly different area."
        elif result.endswith("remove-and-retry"):
            message = "Lift your finger, then touch the sensor again."
        elif result.endswith("finger-not-centered"):
            message = "Center your finger on the sensor and try again."
        elif result.endswith(("retry-scan", "too-fast", "swipe-too-short")):
            message = "Rest your finger on the sensor a little longer, then lift it."
        else:
            message = messages.get(result, "The reader reported: " + result)
        self.publish(message)
        if done:
            self.terminal = message
            if self.phase == "active":
                self.finish(message)

    def cancel(self):
        if self.phase not in ("claiming", "starting", "active") or self.operation == "Delete":
            return
        self.cancelled = True
        self.publish("Cancelling…")
        if self.phase == "active":
            self.finish("Cancelled.")

    def finish(self, message):
        self.phase = "stopping"
        self.publish()
        def stopped(value, error):
            if error:
                self.disconnected(error)
            else:
                self.release(message)
        self.transport.call(self.operation + "Stop", None, stopped)

    def release(self, message):
        self.phase = "releasing"
        self.publish()
        def released(value, error):
            if error:
                self.disconnected(error)
            else:
                self.list_fingers(message)
        self.transport.call("Release", None, released)

    def disconnected(self, error):
        self.transport.close()
        self.phase, self.operation = "offline", None
        self.publish(error_text(error))


class DBusTransport:
    """Dedicated bus connection so disconnect reliably relinquishes ownership."""
    BUS = "net.reactivated.Fprint"
    IFACE = BUS + ".Device"

    def __init__(self):
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.connection = None
        self.generation = 0

    def close(self):
        self.generation += 1
        if self.connection:
            self.connection.close(None, None, None)
            self.connection = None

    def connect(self, signal, disconnected, callback):
        self.close()
        generation = self.generation
        Gio = self.Gio
        def opened(source, result):
            try:
                connection = Gio.DBusConnection.new_for_address_finish(result)
            except self.GLib.Error as error:
                if generation == self.generation:
                    callback(error)
                return
            if generation != self.generation:
                connection.close(None, None, None)
                return
            self.connection = connection
            connection.connect("closed", lambda *args: disconnected("Fingerprint service disconnected.")
                               if generation == self.generation else None)
            def discovered(value, error):
                if error:
                    callback(error)
                    return
                self.path = value[0]
                connection.signal_subscribe(self.BUS, self.IFACE, None, self.path, None,
                    Gio.DBusSignalFlags.NONE,
                    lambda c, sender, path, iface, name, args: signal(name, args.unpack())
                    if generation == self.generation else None)
                connection.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus",
                    "NameOwnerChanged", "/org/freedesktop/DBus", self.BUS,
                    Gio.DBusSignalFlags.NONE,
                    lambda c, sender, path, iface, name, args: disconnected("Fingerprint service restarted. Refresh to reconnect.")
                    if generation == self.generation and args.unpack()[1] else None)
                callback()
            self._call("/net/reactivated/Fprint/Manager", self.BUS + ".Manager",
                       "GetDefaultDevice", None, discovered)
        address = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SYSTEM, None)
        Gio.DBusConnection.new_for_address(address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None, opened)

    def call(self, method, argument, callback):
        self._call(self.path, self.IFACE, method, argument, callback)

    def _call(self, path, interface, method, argument, callback):
        generation = self.generation
        def finished(connection, result):
            try:
                value, error = connection.call_finish(result).unpack(), None
            except self.GLib.Error as exc:
                value, error = None, exc
            if generation == self.generation:
                callback(value, error)
        args = None if argument is None else self.GLib.Variant("(s)", (argument,))
        self.connection.call(self.BUS, path, interface, method, args, None,
            self.Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, 30000, None, finished)
