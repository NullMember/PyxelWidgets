"""
Checks the REAPER script (pyxelwidgets.daws) against a real REAPER (macOS): run
it by hand, it isn't collected by pytest. A separate REAPER instance starts with
a scratch resource folder (your reaper.ini, license and plug-in caches copied,
every MIDI device enabled, no plug-in scan), a startup script makes three tracks
with a ReaEQ and runs the DAW script; then commands go out through the DAW
output and what REAPER sends back is checked. Your own REAPER folder is only read.

    python tests/manual/reaper_daw.py [scratch folder]

Learned the hard way: a reused scratch folder stops running startup scripts
after REAPER was killed (it is rebuilt each time); REAPER only runs
__startup.lua (not scripts given on the command line); a leftover process
holding a "PyxelWidgets DAW" port makes REAPER see two.
"""

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from pyxelwidgets import daws
from pyxelwidgets.devices.daw import BUTTONS, DAW
from pyxelwidgets.events import MessageReceived
from pyxelwidgets.message import Command

APP = '/Applications/REAPER.app/Contents/MacOS/REAPER'
USER = pathlib.Path.home() / 'Library' / 'Application Support' / 'REAPER'

SETUP = '''
for i, name in ipairs({'Drums', 'Bass', 'Lead'}) do
  reaper.InsertTrackAtIndex(i - 1, true)
  reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(0, i - 1), 'P_NAME', name, true)
end
reaper.TrackFX_AddByName(reaper.GetTrack(0, 1), 'ReaEQ', false, -1)
reaper.SetOnlyTrackSelected(reaper.GetTrack(0, 1))
dofile(%r)
'''


def scratch_reaper(folder: pathlib.Path) -> pathlib.Path:
    """A fresh resource folder with the DAW script started at startup; returns its reaper.ini."""
    if folder.exists():
        shutil.rmtree(folder)
    (folder / 'Scripts').mkdir(parents = True)
    (folder / 'novst').mkdir()
    shutil.copy(USER / 'reaper-license.rk', folder)
    for pattern in ('reaper-vstplugins*.ini', 'reaper-auplugins*.ini', 'reaper-clap-*.ini', 'reaper-jsfx.ini'):
        for path in USER.glob(pattern):
            shutil.copy(path, folder)
    lines = [line for line in (USER / 'reaper.ini').read_text(errors = 'replace').splitlines()
             if not re.match(r'(midiins|midiouts|csurf_|lastproj)\w*=', line)]
    at = lines.index('[reaper]') + 1
    every = str(2 ** 20 - 1)
    lines[at:at] = [f'{key}={every}' for key in ('midiins', 'midiins_cs', 'midiouts', 'midiins_nowarn', 'midiouts_nowarn')] + \
                   [f'{key}={folder / "novst"}' for key in ('vstpath_arm64', 'vstpath64', 'vstpath')]
    (folder / 'reaper.ini').write_text('\n'.join(lines) + '\n')
    script = daws.install('reaper', folder / 'daw')[0]
    (folder / 'Scripts' / '__startup.lua').write_text(SETUP % str(script))
    return folder / 'reaper.ini'


def main() -> int:
    folder = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(tempfile.gettempdir()) / 'pyxelwidgets-reaper'
    state, changed = {}, threading.Condition()

    def received(event):
        with changed:
            state[event.message.name] = event.message.value
            changed.notify_all()

    def wait(name, test, seconds = 5.0):
        end = time.monotonic() + seconds
        with changed:
            while not (name in state and test(state[name])):
                if time.monotonic() >= end:
                    return False
                changed.wait(end - time.monotonic())
        return True

    def send(name, value = 1.0):
        daw.send(Command(name, value))
        if name in BUTTONS:
            daw.send(Command(name, 0.0))

    results = []

    def check(what, ok):
        results.append(ok)
        print(('ok   ' if ok else 'FAIL ') + what, flush = True)

    daw = DAW()
    daw.on(MessageReceived, received)
    daw.connect_virtual('PyxelWidgets DAW')
    reaper = subprocess.Popen([APP, '-newinst', '-nosplash', '-cfgfile', str(scratch_reaper(folder))],
                              stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)
    try:
        check('hello from REAPER', wait('DAW', lambda value: value == 'REAPER', 40))
        check('track names', wait('Track Name 3', lambda value: value == 'Lead') and wait('Track Name 1', lambda value: value == 'Drums'))
        check('selected track and its plug-in', wait('Selected Name', lambda value: value == 'Bass') and wait('Device Name', lambda value: 'ReaEQ' in value))
        send('Select 1')
        check('Select 1', wait('Selected Name', lambda value: value == 'Drums'))
        send('Volume 1', 0.5)
        check('Volume 1', wait('Volume 1', lambda value: abs(value - 0.5) < 0.02))
        send('Pan 2', 0.25)
        check('Pan 2', wait('Pan 2', lambda value: abs(value - 0.25) < 0.02))
        send('Mute 3')
        check('Mute 3 light', wait('Mute 3', lambda value: value == 1.0))
        send('Mute 3')
        check('Mute 3 off', wait('Mute 3', lambda value: value == 0.0))
        send('Solo 1')
        check('Solo 1 light', wait('Solo 1', lambda value: value == 1.0))
        send('Select 2')
        check('back to Bass', wait('Selected Name', lambda value: value == 'Bass'))
        check('macro names', wait('Macro Name 1', lambda value: value != ''))
        send('Macro 1', 0.3)
        check('Macro 1', wait('Macro 1', lambda value: abs(value - 0.3) < 0.02))
        check('Macro 1 value text', wait('Macro Value 1', lambda value: value != ''))
        first = state.get('Macro Name 1')
        send('Macro Page Right')
        check('macro page', wait('Macro Name 1', lambda value: value != first, 2))
        send('Play')
        check('Play light', wait('Play', lambda value: value == 1.0))
        send('Stop')
        check('Play off after Stop', wait('Play', lambda value: value == 0.0))
        send('Loop')
        check('Loop light', wait('Loop', lambda value: value == 1.0))
        send('Master Volume', 0.6)
        check('Master Volume', wait('Master Volume', lambda value: abs(value - 0.6) < 0.02))
        send('Arm 2')
        check('Arm 2 light', wait('Arm 2', lambda value: value == 1.0))
        send('Device On')
        check('Device On toggles the plug-in', wait('Device On', lambda value: value == 0.0))
        send('Track Right')
        check('Track Right', wait('Selected Name', lambda value: value == 'Lead'))
        send('Track Left')
        check('Track Left', wait('Selected Name', lambda value: value == 'Bass'))
        send('Bank Right')
        check('Bank Right', wait('Track Name 1', lambda value: value not in ('Drums', ''), 3))
        send('Bank Left')
        check('Bank Left', wait('Track Name 1', lambda value: value == 'Drums'))
        send('Undo')
        check('Undo (Device On back)', wait('Device On', lambda value: value == 1.0, 3))
        state.pop('Track Name 1', None)
        daw.on_connect()
        check('refresh', wait('Track Name 1', lambda value: value == 'Drums'))
    finally:
        reaper.kill()
        daw.close()
    print(f'{sum(results)}/{len(results)} passed')
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
