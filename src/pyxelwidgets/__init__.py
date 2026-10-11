"""
GUI framework for low resolution devices (e.g. Novation Launchpad, LED keyboards).

Hardware controllers are not exported here so that the core works without
optional dependencies; import them from ``pyxelwidgets.controllers.*``.

Names are imported lazily on first access, so importing one module (e.g.
``pyxelwidgets.widgets``) does not load the rest of the framework.
"""

import importlib

__version__ = '0.1.0'

_exports = {
    'App': 'app',
    'Clock': 'clock',
    'Target': 'clock',
    'Controller': 'controllers',
    'Event': 'enums',
    'Parser': 'parser',
    'Colors': 'color',
    'Color': 'color',
    'Rectangle2D': 'rectangle',
    'Button': 'widgets',
    'ButtonGroup': 'widgets',
    'Fader': 'widgets',
    'Keyboard': 'widgets',
    'Knob': 'widgets',
    'Sequencer': 'widgets',
    'Sprite': 'widgets',
    'Tracker': 'widgets',
    'Widget': 'widgets',
    'XY': 'widgets',
    'Manager': 'window',
    'Window': 'window',
}

__all__ = sorted(_exports)

def __getattr__(name):
    if name in _exports:
        value = getattr(importlib.import_module(f'{__name__}.{_exports[name]}'), name)
        globals()[name] = value
        return value
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')

def __dir__():
    return sorted(set(globals()) | set(_exports))
