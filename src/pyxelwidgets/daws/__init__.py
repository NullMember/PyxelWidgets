"""
Scripts that make DAWs speak the PyxelWidgets DAW protocol (see
``pyxelwidgets.devices.daw``), one per DAW with a way to add controllers, the
way controller makers ship theirs. ``pyxelwidgets daw install <daw>`` writes
one where its DAW looks for it; ``files(daw)`` gives the files to put
elsewhere. Each is written from a template in this package with the
protocol's table filled in, so they all speak the same commands.

``DAWS`` lists them: REAPER (a Lua script), Ableton Live (a remote script)
and Cubase/Nuendo (a MIDI Remote script). Logic and Pro Tools have no such
scripts: use the Mackie Control and HUI outputs with them.
"""

import json
import os
import pathlib
import platform

import pyxelwidgets.devices.daw

__all__ = ['DAWS', 'files', 'install', 'folder']

_HERE = pathlib.Path(__file__).parent
_HOME = pathlib.Path.home()

def _documents() -> pathlib.Path:
    return _HOME / 'Documents'

def _reaper() -> pathlib.Path:
    if platform.system() == 'Darwin':
        return _HOME / 'Library' / 'Application Support' / 'REAPER'
    if platform.system() == 'Windows':
        return pathlib.Path(os.environ.get('APPDATA', _HOME)) / 'REAPER'
    return _HOME / '.config' / 'REAPER'

#: name -> (what it is, template files (relative to this package), where the DAW looks, how to turn it on)
DAWS = {
    'reaper': ('REAPER', ['reaper/PyxelWidgets DAW.lua'], lambda: _reaper() / 'Scripts' / 'PyxelWidgets',
               'Preferences > MIDI Devices: enable "PyxelWidgets DAW" as input and output; Actions > Show action list > '
               'New action > Load ReaScript: "PyxelWidgets DAW.lua", run it (or set it as a startup action).'),
    'live': ('Ableton Live', ['live/PyxelWidgets/__init__.py'],
             lambda: (_HOME / 'Music' if platform.system() == 'Darwin' else _documents()) / 'Ableton' / 'User Library' / 'Remote Scripts',
             'Settings > Link, Tempo & MIDI: a Control Surface slot "PyxelWidgets", input and output "PyxelWidgets DAW".'),
    'cubase': ('Cubase / Nuendo', ['cubase/pyxelwidgets/daw/pyxelwidgets_daw.js'],
               lambda: _documents() / 'Steinberg' / 'Cubase' / 'MIDI Remote' / 'Driver Scripts' / 'Local',
               'Studio > MIDI Remote Manager > Reload Scripts; it finds "PyxelWidgets DAW" by its port name '
               '(or add it in the MIDI Remote tab with that port as input and output).'),
}

def _lua(value) -> str:
    """``value`` (dicts, lists, numbers, text) as a Lua table literal."""
    if isinstance(value, dict):
        return '{' + ', '.join(f'[{_lua(key)}] = {_lua(item)}' for key, item in value.items()) + '}'
    if isinstance(value, list):
        return '{' + ', '.join(_lua(item) for item in value) + '}'
    if isinstance(value, str):
        return json.dumps(value)
    return repr(value)

def _protocol(template: str) -> str:
    data = pyxelwidgets.devices.daw.protocol()
    if template.endswith('.lua'):
        return _lua(data)
    if template.endswith('.py'):
        return repr(data)
    return json.dumps(data)

def files(daw: str) -> dict:
    """The script's files for ``daw`` (a key of ``DAWS``): relative path -> text."""
    if daw not in DAWS:
        raise ValueError(f'no script for {daw!r} (there are: {", ".join(DAWS)})')
    found = {}
    for template in DAWS[daw][1]:
        text = (_HERE / template).read_text()
        relative = template.split('/', 1)[1]
        found[relative] = text.replace('__PROTOCOL__', _protocol(template))
    return found

def folder(daw: str) -> pathlib.Path:
    """Where ``daw`` looks for scripts of its kind."""
    return DAWS[daw][2]()

def install(daw: str, to: str | os.PathLike | None = None) -> list:
    """Write ``daw``'s script into ``to`` (default: where the DAW looks); returns the files written."""
    target = pathlib.Path(to) if to is not None else folder(daw)
    written = []
    for relative, text in files(daw).items():
        path = target / relative
        path.parent.mkdir(parents = True, exist_ok = True)
        path.write_text(text)
        written.append(path)
    return written
