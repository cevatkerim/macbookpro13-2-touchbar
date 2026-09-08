#!/usr/bin/python3
"""Unprivileged T1Bridge v1 audio/media adapter for Omarchy 4."""
import os
import re
import subprocess
import sys
import time

DEADLINE = time.monotonic() + 0.45
OMARCHY = '/usr/share/omarchy/bin/'


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL,
                                   timeout=max(0.001, DEADLINE - time.monotonic()))


def sink():
    value = run(OMARCHY + 'omarchy-audio-output-sink').strip()
    if not value or len(value) > 256 or value.startswith('-'):
        raise ValueError('invalid sink')
    return value


def main(args):
    if os.geteuid() == 0 or len(args) < 2 or args[0] != 'v1':
        return 2
    operation, extra = args[1], args[2:]
    if operation == 'set-volume':
        if len(extra) != 1 or not re.fullmatch(r'[0-9]{1,3}', extra[0]):
            return 2
        volume = int(extra[0])
        if volume > 100:
            return 2
        output = sink()
        run('/usr/bin/pactl', 'set-sink-volume', output, f'{volume}%')
        run('/usr/bin/pactl', 'set-sink-mute', output, '0')
        return 0
    if extra:
        return 2
    if operation == 'status':
        capabilities, volume, muted = 0, '-', '-'
        try:
            output = sink()
            state = run('/usr/bin/pactl', 'get-sink-volume', output)
            match = re.search(r'\b([0-9]+)%', state)
            if match is None:
                raise ValueError('invalid volume')
            volume = str(min(100, int(match[1])))
            mute = run('/usr/bin/pactl', 'get-sink-mute', output).strip()
            if mute not in ('Mute: yes', 'Mute: no'):
                raise ValueError('invalid mute state')
            muted = '1' if mute == 'Mute: yes' else '0'
            capabilities |= 1
        except (ValueError, subprocess.SubprocessError, OSError):
            volume, muted = '-', '-'
        try:
            names = run('/usr/bin/busctl', '--user', '--no-pager', '--no-legend', 'list')
            if any(line.startswith('org.mpris.MediaPlayer2.') for line in names.splitlines()):
                capabilities |= 2
        except (subprocess.SubprocessError, OSError):
            pass
        print(f'T1BRIDGE-DESKTOP 1 {capabilities} {volume} {muted}')
        return 0
    if operation == 'toggle-mute':
        run('/usr/bin/pactl', 'set-sink-mute', sink(), 'toggle')
        return 0
    media = {'media-previous': 'previous', 'media-play-pause': 'playPause',
             'media-next': 'next'}
    if operation in media:
        run(OMARCHY + 'omarchy-shell', 'media', media[operation])
        return 0
    return 2


if __name__ == '__main__':
    os.environ['LC_ALL'] = 'C'
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, subprocess.SubprocessError, OSError):
        sys.exit(1)
