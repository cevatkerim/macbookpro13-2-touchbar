#!/usr/bin/python3
"""Boot this Mac's previously verified production image when T1 is in recovery.

Installed resources and private state must be root-owned. This never signs,
provisions, resets hardware, switches a running USB configuration, or enrolls.
"""
from pathlib import Path
import hashlib
import os
import plistlib
import re
import shutil
import subprocess
import sys
import time

STATE = Path('/var/lib/t1-touchbar/private')
TOOLS = Path('/usr/local/libexec/t1-firmware')


def device_state():
    found = []
    for device in Path('/sys/bus/usb/devices').iterdir():
        try:
            if (device/'idVendor').read_text().strip() != '05ac':
                continue
            product = (device/'idProduct').read_text().strip()
            if product in ('1281', '8600'):
                found.append((device, product))
        except FileNotFoundError:
            continue
    if len(found) != 1:
        raise ValueError('Expected exactly one T1 device')
    return found[0]


def main():
    if os.geteuid() != 0:
        raise ValueError('Root required')
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MacBookPro13,2':
        raise ValueError('Unsupported model')
    device, product = device_state()
    if product == '8600':
        if (device/'bNumInterfaces').read_text().strip() != '8':
            raise ValueError('T1 present with unexpected configuration; no change made')
        print('T1 already running in the expected production configuration.')
        return
    fields = {key: int(value, 16) for key, value in re.findall(
        r'\b(CPID|BDID|ECID):([0-9A-Fa-f]+)\b', (device/'serial').read_text())}
    if fields.get('CPID') != 0x8002 or fields.get('BDID') != 0x12:
        raise ValueError('Recovery identity rejected')
    source = STATE/'pass-b-001'
    pair = plistlib.loads((source/'preflight.plist').read_bytes())
    marker = plistlib.loads((STATE/'phase14-003/production-verified.plist').read_bytes())
    if (pair.get('RestoreFinished') is not True or pair.get('FDRReplayed') is not True
            or pair.get('ECID') != fields.get('ECID')
            or hashlib.sha256(pair['Image']).digest() != marker['ImageSHA256']):
        raise ValueError('Saved pair does not match the verified production image')
    os.umask(0o077)
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if not re.fullmatch(r'[0-9a-f-]{36}', boot_id):
        raise ValueError('Invalid boot identity')
    attempts = STATE/'automatic-boots'
    attempts.mkdir(mode=0o700, exist_ok=True)
    attempt = attempts/boot_id
    attempt.mkdir(mode=0o700)  # At most one firmware dispatch per host boot.
    for name in ('device.plist', 'preflight.plist', 'FDRData'):
        shutil.copyfile(source/name, attempt/name)
        (attempt/name).chmod(0o600)
    environment = {'PATH': '/usr/bin', 'LANG': 'C',
                   'LD_LIBRARY_PATH': str(TOOLS/'lib'),
                   'IDEVICERESTORE_T1_MODE': 'replay',
                   'IDEVICERESTORE_T1_PRIVATE': str(attempt)}
    with (attempt/'launcher.log').open('xb') as log:
        result = subprocess.run([str(TOOLS/'idevicerestore'), '-i', hex(fields['ECID']),
                                 str(STATE/'firmware-resources')], env=environment,
                                stdout=log, stderr=subprocess.STDOUT, timeout=90)
    if result.returncode:
        raise ValueError('Saved production dispatch failed; see private log')
    for _ in range(45):
        try:
            device, product = device_state()
            if product == '8600' and (device/'bNumInterfaces').read_text().strip() == '8':
                print('Saved Apple firmware booted; production T1 configuration ready.')
                return
        except (ValueError, FileNotFoundError):
            pass
        time.sleep(1)
    raise ValueError('Production T1 did not appear before timeout')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Never include private paths, identifiers, or payloads in the journal.
        print(f'T1 saved-image startup failed ({type(error).__name__}); private state preserved.', file=sys.stderr)
        sys.exit(1)
