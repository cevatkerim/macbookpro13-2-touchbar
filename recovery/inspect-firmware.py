#!/usr/bin/env python3
"""Inspect the pinned generic Apple package locally; never access a device.

PBZX framing follows NiklasRosenstein/pbzx d697bbf (GPL-3.0-or-later).
This inspection helper is also GPL-3.0-or-later.
"""
import hashlib
import lzma
from pathlib import Path, PurePosixPath
import plistlib
import struct
import subprocess

root = Path(__file__).resolve().parent
pkg = root / 'download/EmbeddedOSFirmware.pkg'
expected = '0c97ab746ec635b34b1bdea4e4722cd0173443e2ba6ede54cc6af3b5e220d230'
if hashlib.sha256(pkg.read_bytes()).hexdigest() != expected:
    raise SystemExit('Unexpected package checksum')
payload = subprocess.check_output(['bsdtar', '-xOf', str(pkg), 'Payload'])
if payload[:4] != b'pbzx':
    raise SystemExit('Unexpected payload format')
flags = struct.unpack_from('>Q', payload, 4)[0]
offset = 12
size = 0
archive = root / 'download/Payload.cpio'
with archive.open('wb') as out:
    while flags & (1 << 24):
        flags, length = struct.unpack_from('>QQ', payload, offset)
        offset += 16
        chunk = payload[offset:offset + length]
        if len(chunk) != length or length > 64 * 1024 * 1024:
            raise SystemExit('Invalid chunk length')
        offset += length
        data = chunk if length == 1 << 24 else lzma.decompress(chunk, memlimit=128 * 1024 * 1024)
        size += len(data)
        if len(data) > 64 * 1024 * 1024 or size > 512 * 1024 * 1024:
            raise SystemExit('Unexpected uncompressed size')
        out.write(data)
if offset != len(payload):
    raise SystemExit('Unexpected trailing data')
names = subprocess.check_output(['bsdtar', '-tf', str(archive)], text=True).splitlines()
dest = root / 'firmware-manifests'
dest.mkdir(exist_ok=True)
for filename in ('version.plist', 'BuildManifest.plist', 'Restore.plist'):
    matches = [n for n in names if PurePosixPath(n).name == filename]
    if len(matches) != 1:
        raise SystemExit('Missing or ambiguous ' + filename)
    raw = subprocess.check_output(['bsdtar', '-xOf', str(archive), matches[0]])
    data = plistlib.loads(raw)
    (dest / filename).write_bytes(raw)
    print(filename + ': valid plist')
    for key in ('ProductVersion', 'ProductBuildVersion', 'CFBundleShortVersionString'):
        if key in data:
            print('  ' + key + ': ' + str(data[key]))
    for ident in data.get('BuildIdentities', []):
        info = ident.get('Info', {})
        print('  identity:', info.get('DeviceClass'), 'chip:', ident.get('ApChipID'),
              'board:', ident.get('ApBoardID'), 'variant:', info.get('Variant'))
print('Firmware files for x619:', sum('x619' in n for n in names))
print('DMG files:', sum(n.endswith('.dmg') for n in names))
