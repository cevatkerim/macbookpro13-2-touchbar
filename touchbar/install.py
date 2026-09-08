#!/usr/bin/env python3
"""Install the Touch Bar renderer and its unprivileged settings panel."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from preferences import Selection, config_directory

FILES = ('renderer.py','protocol.py','layout.py','drawing.py','desktop.py','preferences.py','panel.py')


def backed_up_write(path, text):
    if path.exists() and path.read_text() == text:
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        shutil.copy2(path,path.with_name(path.name+'.bak.'+stamp))
    path.write_text(text)


def desktop_token(text):
    text = text.replace('%','%%')
    for character in ('\\','"','`','$'):
        text = text.replace(character,'\\'+character)
    return '"'+text.replace('\\','\\\\')+'"'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disable',action='store_true',help='Disable custom controls, retaining the settings panel')
    parser.add_argument('--no-restart',action='store_true')
    parser.add_argument('--no-menu',action='store_true')
    parser.add_argument('--no-window-rule',action='store_true')
    args=parser.parse_args()
    if os.geteuid()==0:
        parser.error('Run as the desktop user, without sudo.')
    home=Path.home()
    directory=home/'.local/share/omarchy-touchbar'
    selection=Selection()
    desktop=home/'.local/share/applications/me.kerim.OmarchyTouchBar.desktop'
    if args.disable:
        selection.set_enabled(False)
    else:
        import cairo
        import gi
        gi.require_version('Gtk','4.0')
        gi.require_version('Adw','1')
        if not Path('/usr/lib/t1bridge/t1-touchbar').is_file():
            parser.error('Install and verify T1Bridge first.')
        if not os.access('/usr/local/libexec/t1bridge-omarchy-desktop',os.X_OK):
            parser.error('Install the documented Omarchy desktop provider first.')
        menu=home/'.config/omarchy/extensions/omarchy-menu.jsonc'
        old_menu=menu.read_text() if menu.exists() else '{\n}\n'
        new_menu=re.sub(r'\n  // BEGIN omarchy-touchbar\n.*?  // END omarchy-touchbar\n','',old_menu,flags=re.S)
        if not args.no_menu:
            if re.search(r'^\s*"setup\.touchbar"\s*:',new_menu,re.M) or not new_menu.lstrip().startswith('{'):
                parser.error('A custom Touch Bar menu or unsupported format exists; use --no-menu.')
            entry=json.dumps({'label':'Touch Bar','icon':'󰌌','description':'Customize Touch Bar controls',
                              'action':shlex.quote(str(directory/'settings'))})
            block='\n  // BEGIN omarchy-touchbar\n  "setup.touchbar": '+entry+',\n  // END omarchy-touchbar\n'
            index=new_menu.index('{')+1
            new_menu=new_menu[:index]+block+new_menu[index:]
        directory.mkdir(parents=True,exist_ok=True)
        for name in FILES:
            shutil.copyfile(Path(__file__).resolve().parent/name,directory/name)
        for name,script in [('launch','renderer.py'),('settings','panel.py')]:
            launcher=directory/name
            launcher.write_text('#!/bin/sh\nexec /usr/bin/python3 '+shlex.quote(str(directory/script))+'\n')
            launcher.chmod(0o755)
        selection.set_enabled(True)
        desktop.parent.mkdir(parents=True,exist_ok=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Omarchy Touch Bar\n'
                           'Comment=Enable and customize Touch Bar controls\n'
                           'Exec=/usr/bin/python3 '+desktop_token(str(directory/'panel.py'))+'\n'
                           'Icon=input-keyboard-symbolic\nTerminal=false\nCategories=Settings;HardwareSettings;\n'
                           'StartupWMClass=me.kerim.OmarchyTouchBar\n')
        if not args.no_menu:
            backed_up_write(menu,new_menu)
        hypr=home/'.config/hypr/hyprland.lua'
        if not args.no_window_rule and hypr.exists():
            original=hypr.read_text()
            modified=re.sub(r'\n-- BEGIN omarchy-touchbar\n.*?-- END omarchy-touchbar\n','',original,flags=re.S)
            modified+='\n-- BEGIN omarchy-touchbar\no.window("^me[.]kerim[.]OmarchyTouchBar$", { float = true, center = true, size = { 520, 690 }, fullscreen = false })\n-- END omarchy-touchbar\n'
            backed_up_write(hypr,modified)
        if shutil.which('update-desktop-database'):
            subprocess.run(['update-desktop-database',str(desktop.parent)],check=True)
    if not args.no_restart:
        subprocess.run(['systemctl','--user','restart','t1-touchbar.service'],check=True)
    print('Custom controls disabled. Re-enable them in Omarchy Touch Bar settings.' if args.disable else
          'Installed. Open Omarchy Touch Bar in the launcher or Setup → Touch Bar.')


if __name__=='__main__':
    main()
