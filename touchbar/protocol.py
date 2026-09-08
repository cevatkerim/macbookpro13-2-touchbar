"""Unprivileged client for T1Bridge's documented hardware IPC v1."""
import array
import fcntl
import mmap
import os
from pathlib import Path
import socket
import stat
import struct
import time

HEADER = struct.Struct('<4sHHII')
SOCKET = '/run/t1bridge/touchbar.sock'


def packet(kind, request, payload=b''):
    return HEADER.pack(b'T1HW', 1, kind, len(payload), request) + payload


def decode(data):
    if len(data) < HEADER.size:
        raise ValueError('Truncated hardware message')
    magic, version, kind, size, request = HEADER.unpack_from(data)
    if magic != b'T1HW' or version != 1 or size != len(data) - HEADER.size:
        raise ValueError('Invalid hardware message')
    return kind, request, data[HEADER.size:]


def input_frame(payload, width, height):
    if len(payload) < 12:
        raise ValueError('Truncated input frame')
    timestamp, fn, count, reserved = struct.unpack_from('<QBBH', payload)
    if fn > 1 or count > 10 or reserved or len(payload) != 12 + count * 12:
        raise ValueError('Invalid input frame')
    contacts = []
    ids = set()
    for offset in range(12, len(payload), 12):
        identity, tip, in_range, reserved, x, y = struct.unpack_from('<BBBBII', payload, offset)
        if identity > 15 or identity in ids or tip > 1 or in_range > 1 or reserved or x >= width or y >= height:
            raise ValueError('Invalid touch contact')
        ids.add(identity)
        if tip and in_range:
            contacts.append((identity, x, y))
    return bool(fn), contacts


class Hardware:
    def __init__(self):
        self.sock = None
        self.memory = None
        self.fd = None
        self.request = 0
        self.pending = {}
        self.frame = 0
        self.busy = False
        try:
            self.connect()
        except BaseException:
            self.close()
            raise

    def connect(self):
        metadata = Path(SOCKET).stat()
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != 0:
            raise ValueError('Untrusted hardware socket')
        # Brightness classes are optional; require only supported combinations.
        for features in (0x3f, 0x2f, 0x37, 0x27):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.sock.settimeout(1)
            self.sock.connect(SOCKET)
            _, uid, _ = struct.unpack('3i', self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != 0:
                raise ValueError('Untrusted hardware peer')
            self.send(1, struct.pack('<HHQ', 0, 0, features))
            kind, request, payload = self.receive()
            if kind == 0x8003 and payload == struct.pack('<I', 2):
                self.pending.pop(request, None)
                self.sock.close()
                time.sleep(0.1)
                continue
            if kind != 0x8001 or request not in self.pending or len(payload) != 20:
                raise ValueError('Hardware negotiation failed')
            self.pending.pop(request)
            minor, reserved, self.width, self.height, pixel, buffers = struct.unpack('<HHIIII', payload)
            if minor or reserved or pixel != 1 or not 1 <= buffers <= 3 or not 1 <= self.width <= 8192 or not 1 <= self.height <= 512:
                raise ValueError('Unsupported display format')
            self.features = features
            break
        else:
            raise ValueError('Required renderer features unavailable')
        self.fd = os.memfd_create('omarchy-touchbar-frame', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        size = self.width * self.height * 4
        os.ftruncate(self.fd, size)
        self.memory = mmap.mmap(self.fd, size)
        fcntl.fcntl(self.fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SEAL)
        register = self.send(2, struct.pack('<IIQ', 1, self.width * 4, size), self.fd)
        while True:
            kind, request, payload = self.receive()
            if request == register:
                if kind != 0x8002 or payload:
                    raise ValueError('Frame registration failed')
                self.pending.pop(request)
                break
            if kind != 0x9002:
                raise ValueError('Unexpected registration response')
        self.sock.setblocking(False)

    def send(self, kind, payload=b'', descriptor=None):
        self.request = self.request % 0xffffffff + 1
        if self.request in self.pending or len(self.pending) > 64:
            raise ValueError('Hardware request backlog')
        self.pending[self.request] = (kind, time.monotonic())
        ancillary = [] if descriptor is None else [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [descriptor]))]
        data = packet(kind, self.request, payload)
        if self.sock.sendmsg([data], ancillary) != len(data):
            raise OSError('Short hardware write')
        return self.request

    def receive(self):
        data, ancillary, flags, _ = self.sock.recvmsg(65536, socket.CMSG_SPACE(16))
        if ancillary:
            for level, kind, raw in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    descriptors = array.array('i')
                    descriptors.frombytes(raw[:len(raw) - len(raw) % descriptors.itemsize])
                    for fd in descriptors:
                        os.close(fd)
            raise ValueError('Unexpected hardware descriptors')
        if not data or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise ValueError('Hardware disconnected or truncated packet')
        return decode(data)

    def dispatch(self):
        kind, request, payload = self.receive()
        if kind == 0x9002 and request == 0:
            return input_frame(payload, self.width, self.height)
        if kind == 0x9001 and request == 0 and len(payload) == 12:
            buffer_id, frame_id = struct.unpack('<IQ', payload)
            if not self.busy or buffer_id != 1 or frame_id != self.frame:
                raise ValueError('Unexpected frame release')
            self.busy = False
            return None
        if request not in self.pending:
            raise ValueError('Unknown hardware response')
        operation, _ = self.pending.pop(request)
        # The broker may finish authentication between the visible prompt and
        # a Cancel tap. A denied cancellation is then a normal race.
        if kind == 0x8003 and operation == 7 and payload == struct.pack('<I', 7):
            return None
        if kind != 0x8002 or payload:
            raise ValueError('Hardware rejected an operation')
        return None

    def submit(self, pixels):
        if self.busy:
            return False
        if len(pixels) != len(self.memory):
            raise ValueError('Wrong frame size')
        self.memory[:] = pixels
        self.frame += 1
        self.send(3, struct.pack('<IQI', 1, self.frame, 0))
        self.busy = True
        return True

    def tap(self, code):
        if code not in (1, *range(59, 69), 87, 88):
            raise ValueError('Unsupported key')
        self.send(4, struct.pack('<B3x4H', 1, code, 0, 0, 0))

    def brightness(self, name, value):
        feature, operation = (8, 5) if name == 'brightness' else (16, 6)
        if self.features & feature and type(value) is int and 0 <= value <= 100:
            self.send(operation, bytes([value]))

    def check_timeout(self):
        if any(time.monotonic() - start > 3 for _, start in self.pending.values()):
            raise TimeoutError('Hardware request timed out')

    def close(self):
        if self.sock is not None:
            self.sock.close()
        if self.memory is not None:
            self.memory.close()
        if self.fd is not None:
            os.close(self.fd)
