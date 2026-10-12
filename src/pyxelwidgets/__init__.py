"""
GUI framework for low resolution devices (e.g. Novation Launchpad, LED keyboards).

Hardware devices are not exported here so that the core works without
optional dependencies; import them from ``pyxelwidgets.devices.*``.

Names are imported lazily on first access, so importing one module (e.g.
``pyxelwidgets.widgets``) does not load the rest of the framework.
"""

import importlib

__version__ = '0.1.0'

_exports = {
    'Animation': 'animation',
    'App': 'app',
    'Blink': 'animation',
    'Fade': 'animation',
    'Pulse': 'animation',
    'Binding': 'binding',
    'Link': 'link',
    'Mapping': 'mapping',
    'Source': 'message',
    'Takeover': 'binding',
    'Color': 'color',
    'Colors': 'color',
    'Device': 'devices',
    'Group': 'group',
    'Pages': 'group',
    'Parser': 'parser',
    'Rectangle2D': 'rectangle',
    'Surface': 'surface',
    'Transport': 'transport',
    'Button': 'widgets',
    'ClipLauncher': 'widgets',
    'Clock': 'widgets',
    'DrumPads': 'widgets',
    'Meter': 'widgets',
    'ButtonGroup': 'widgets',
    'Fader': 'widgets',
    'Keyboard': 'widgets',
    'Knob': 'widgets',
    'Propagation': 'widgets',
    'Sequencer': 'widgets',
    'Sprite': 'widgets',
    'Tracker': 'widgets',
    'ValueWidget': 'widgets',
    'Widget': 'widgets',
    'XY': 'widgets',
    'Text': 'widgets',
    'Event': 'events',
    'WidgetEvent': 'events',
    'Pressed': 'events',
    'Pressure': 'events',
    'Released': 'events',
    'Held': 'events',
    'DoublePressed': 'events',
    'Changed': 'events',
    'Resized': 'events',
    'Toggled': 'events',
    'NoteOn': 'events',
    'NoteOff': 'events',
    'StepPlayed': 'events',
    'PageChanged': 'events',
    'RowPlayed': 'events',
    'ClipQueued': 'events',
    'ClipStarted': 'events',
    'ClipStopped': 'events',
    'Frame': 'events',
    'PadEvent': 'events',
    'PadPressed': 'events',
    'PadReleased': 'events',
    'PadHeld': 'events',
    'PadDoublePressed': 'events',
    'PadPressure': 'events',
    'MessageReceived': 'events',
    'ControlEvent': 'events',
    'ControlPressed': 'events',
    'ControlReleased': 'events',
    'ControlChanged': 'events',
    'ControlTurned': 'events',
    'TransportEvent': 'events',
    'TransportStarted': 'events',
    'TransportStopped': 'events',
    'TransportLocated': 'events',
    'TempoChanged': 'events',
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
