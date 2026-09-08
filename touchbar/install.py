#!/usr/bin/env python3
"""Install/select the unprivileged Omarchy renderer; keep previous selection."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

FILES = ('renderer.py','protocol.py','layout.py','drawing.py','desktop.py')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disable',action='store_true',help='Restore the prior renderer selection')
    parser.add_argument('--no-restart',action='store_true')
    args=parser.parse_args()
    if os.geteuid()==0:
        parser.error('Run as the desktop user, without sudo.')
    home=Path.home()
    config=Path(os.environ.get('XDG_CONFIG_HOME') or home/'.config')/'t1bridge'
    if not config.is_absolute():
        parser.error('XDG_CONFIG_HOME must be absolute.')
    directory=home/'.local/share/omarchy-touchbar'
    launcher=directory/'launch'
    selection=config/'renderer'
    backup=config/'renderer.before-omarchy-touchbar'
    owned=selection.is_symlink() and selection.resolve()==launcher.resolve()
    if args.disable:
        if owned:
            selection.unlink()
            if backup.exists() or backup.is_symlink():
                backup.rename(selection)
        elif selection.exists() or selection.is_symlink():
            parser.error('Another renderer is selected; leaving it untouched.')
    else:
        import cairo
        if not Path('/usr/lib/t1bridge/t1-touchbar').is_file():
            parser.error('Install and verify T1Bridge first.')
        if not os.access('/usr/local/libexec/t1bridge-omarchy-desktop',os.X_OK):
            parser.error('Install the documented Omarchy desktop provider first.')
        if not owned and (selection.exists() or selection.is_symlink()):
            if backup.exists() or backup.is_symlink():
                parser.error('A previous-renderer backup already exists; refusing to overwrite it.')
            selection.rename(backup)
        directory.mkdir(parents=True,exist_ok=True)
        for name in FILES:
            shutil.copyfile(Path(__file__).resolve().parent/name,directory/name)
        import shlex
        launcher.write_text('#!/bin/sh\nexec /usr/bin/python3 '+shlex.quote(str(directory/'renderer.py'))+'\n')
        launcher.chmod(0o755)
        config.mkdir(parents=True,exist_ok=True)
        if not owned:
            selection.symlink_to(launcher)
    if not args.no_restart:
        subprocess.run(['systemctl','--user','restart','t1-touchbar.service'],check=True)
    print('Previous renderer restored.' if args.disable else 'Omarchy Touch Bar selected. Tap Default to fall back; restart the user service to return.')


if __name__=='__main__':
    main()
