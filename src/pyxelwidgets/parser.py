"""
Layout files: a JSON description of a Surface, the devices it is shown on and
its widgets, as written by the designer (``python -m pyxelwidgets.designer``).

    {
      "format": "pyxelwidgets.layout", "version": 4,
      "surface": {"width": 9, "height": 9},
      "transport": {"bpm": 120, "signature": [4, 4]},
      "devices": [{"type": "novation.LaunchpadMiniMK3", "x": 0, "y": 0, "options": {}}],
      "bindings": [
        {"device": 0, "control": "Top1", "widget": "volume", "options": {"takeover": "Pickup"}},
        {"device": 0, "control": "Top8", "action": "transport.toggle"}
      ],
      "widgets": [
        {"type": "Fader", "name": "volume", "x": 0, "y": 0, "width": 1, "height": 8,
         "options": {"active_color": "#00ffff", "mode": "Magnitude"},
         "animation": {"type": "Pulse", "options": {"rate": "1/2"}}},
        {"type": "Group", "name": "page", "x": 0, "y": 0, "width": 8, "height": 8,
         "options": {"visible": false}, "widgets": [...]}
      ]
    }

Widget options are the widget's constructor arguments: colors as ``#rrggbb``
or ``#rrggbbaa``, enums by member name (``"Magnitude"`` for ``Fader.Mode``),
rates as note values (``"1/16"``) or seconds where a widget allows both,
Sprite frames as lists of rows from the top, each a list of colors (``null``
is transparent). A widget's optional ``animation`` is one of ``ANIMATIONS``
with its options. Older versions are upgraded on load.

Bindings connect a device's named controls (by the device's index in
``devices``) to a widget, with Binding options (``takeover``, ``glide_time``,
``step``, ``axis``), or to an action (see ``ACTIONS``).
Device inputs/outputs are optional port names; without them devices are found
by their port names.

Load a layout and attach behaviour by widget name::

    ui = pyxelwidgets.parser.load('layout.json')
    ui['volume'].on(Changed, lambda e: print(e.value))
    app = ui.app()              # Sequencers and Trackers follow app.transport
    app.transport.play()
    app.run()
"""

import copy
import enum
import fractions
import importlib
import inspect
import json
import pathlib
import types
import typing

import numpy

import pyxelwidgets.animation
import pyxelwidgets.binding
import pyxelwidgets.buffer
import pyxelwidgets.color
import pyxelwidgets.group
import pyxelwidgets.rate
import pyxelwidgets.surface
import pyxelwidgets.transport
import pyxelwidgets.widgets

FORMAT = 'pyxelwidgets.layout'
VERSION = 4

# Actions a binding can trigger, on the transport given to Parser.bind
ACTIONS = {
    'transport.play': lambda transport: transport.play,
    'transport.stop': lambda transport: transport.stop,
    'transport.toggle': lambda transport: transport.toggle,
    'transport.rewind': lambda transport: (lambda: transport.locate(0)),
}

# Animations a widget entry can have, by name
ANIMATIONS = {cls.__name__: cls for cls in (pyxelwidgets.animation.Blink, pyxelwidgets.animation.Pulse, pyxelwidgets.animation.Fade)}

# Suggested values for rate options; any note value is accepted
RATES = ['1/1', '1/2', '1/4', '1/8', '1/16', '1/32', '1/4.', '1/8.', '1/16.', '1/4T', '1/8T', '1/16T', 'beat', 'bar']

class LayoutError(ValueError):
    """A layout that doesn't describe a valid surface; the message names where."""

def widget_types() -> dict:
    """Widget classes usable in layouts, by name."""
    types = {name: cls for name, cls in vars(pyxelwidgets.widgets).items()
             if isinstance(cls, type) and issubclass(cls, pyxelwidgets.widgets.Widget)
             and cls not in (pyxelwidgets.widgets.Widget, pyxelwidgets.widgets.ValueWidget)}
    types['Group'] = pyxelwidgets.group.Group
    types['Pages'] = pyxelwidgets.group.Pages
    return dict(sorted(types.items()))

# Arguments set by the layout itself, not by options
_PLACEMENT = {'self', 'x', 'y', 'width', 'height', 'name'}

# Arguments that aren't options: set by the class itself (a Group's background is its
# inactive_color) or by the layout entry (a binding's device, control and target)
_HIDDEN = {pyxelwidgets.group.Group: {'active_color', 'inactive_color'},
           pyxelwidgets.group.Pages: {'active_color', 'inactive_color'},
           # Shows its frames only
           pyxelwidgets.widgets.Sprite: {'active_color', 'inactive_color'},
           # Set by the binding entry itself
           pyxelwidgets.binding.Binding: {'source', 'control', 'target', 'device', 'clock'}}

def _parameters(cls) -> list:
    """Keyword arguments of ``cls``, following ``**kwargs`` into base classes."""
    found, seen = [], set()
    for klass in cls.__mro__:
        init = klass.__dict__.get('__init__')
        if init is None:
            continue
        signature = inspect.signature(init, eval_str = True)
        for parameter in signature.parameters.values():
            if parameter.kind in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL) or parameter.name in seen:
                continue
            seen.add(parameter.name)
            if parameter.name not in _PLACEMENT and parameter.name not in _HIDDEN.get(cls, ()):
                found.append(parameter)
        if not any(p.kind == p.VAR_KEYWORD for p in signature.parameters.values()):
            break
    return found

def _kind(parameter) -> tuple:
    """(kind, enum class or None) of a constructor parameter; a rate's second value is True if it also takes seconds."""
    annotation, default = parameter.annotation, parameter.default
    # Optional[X] / X | None: the kind of X
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        arguments = [argument for argument in typing.get_args(annotation) if argument is not type(None)]
        if pyxelwidgets.rate.Rate in arguments:
            # Rate | float: a note value or seconds
            return 'rate', float in arguments
        if len(arguments) == 1:
            annotation = arguments[0]
    if annotation is pyxelwidgets.rate.Rate:
        return 'rate', False
    if annotation is pyxelwidgets.widgets.Frames:
        return 'frames', None
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return 'enum', annotation
    if isinstance(default, enum.Enum):
        return 'enum', type(default)
    if annotation is pyxelwidgets.color.Color or isinstance(default, pyxelwidgets.color.Color):
        return 'color', None
    for kind, classes in (('bool', (bool,)), ('int', (int,)), ('float', (float,)), ('str', (str,)), ('point', (tuple,))):
        if annotation in classes or (default is not parameter.empty and default is not None and type(default) in classes):
            return kind, None
    return 'json', None

def color_to_text(color: pyxelwidgets.color.Color) -> str:
    text = f'#{color.r:02x}{color.g:02x}{color.b:02x}'
    alpha = round(color.a * 255)
    return text if alpha == 255 else text + f'{alpha:02x}'

def text_to_color(text: str) -> pyxelwidgets.color.Color:
    digits = text[1:] if isinstance(text, str) and text.startswith('#') else None
    if digits is None or len(digits) not in (6, 8):
        raise ValueError(f'expected "#rrggbb" or "#rrggbbaa", got {text!r}')
    values = [int(digits[i:i + 2], 16) for i in range(0, len(digits), 2)]
    return pyxelwidgets.color.Color(values[0], values[1], values[2], values[3] / 255 if len(values) == 4 else 1.0)

def frames_to_json(frames) -> list:
    """Sprite frames (RGBA buffers) as layout JSON: rows from the top, colors as text, None if transparent."""
    encoded = []
    for frame in frames:
        frame = numpy.asarray(frame)
        encoded.append([[color_to_text(pyxelwidgets.color.Color.from_array(frame[x, y])) if frame[x, y, 3] else None
                         for x in range(frame.shape[0])]
                        for y in reversed(range(frame.shape[1]))])
    return encoded

def json_to_frames(frames) -> list:
    """Layout JSON frames to RGBA buffers (see ``frames_to_json``); rows may differ in length."""
    if not isinstance(frames, list) or not frames:
        raise ValueError('expected a list of frames, each a list of rows')
    buffers = []
    for index, rows in enumerate(frames):
        if not isinstance(rows, list) or not rows or not all(isinstance(row, list) for row in rows):
            raise ValueError(f'frame {index} must be a list of rows, each a list of colors')
        width = max(len(row) for row in rows)
        if not width:
            raise ValueError(f'frame {index} is empty')
        buffer = pyxelwidgets.buffer.new(width, len(rows))
        for top, row in enumerate(rows):
            for x, text in enumerate(row):
                if text is not None:
                    try:
                        buffer[x, len(rows) - 1 - top] = text_to_color(text)
                    except ValueError as error:
                        raise ValueError(f'frame {index} row {top}: {error}') from None
        buffers.append(buffer)
    return buffers

def _encode(value, kind):
    if kind == 'color':
        return color_to_text(value)
    if kind == 'enum':
        return value.name
    if kind == 'point':
        return list(value)
    if kind == 'frames':
        return frames_to_json(value)
    return value

def option_schema(cls) -> list:
    """Layout options of a widget or device class: name, kind, default and enum choices."""
    options = []
    for parameter in _parameters(cls):
        kind, extra = _kind(parameter)
        if kind == 'json':
            # Not representable in a layout (e.g. Sprite frames)
            continue
        option = {'name': parameter.name, 'kind': kind}
        if parameter.default is not parameter.empty:
            option['default'] = None if parameter.default is None else _encode(parameter.default, kind)
        if kind == 'enum':
            option['choices'] = [member.name for member in extra]
        elif kind == 'rate':
            option['choices'] = RATES
            if extra:
                # Also a number of seconds
                option['seconds'] = True
        options.append(option)
    return options

def _doc(cls) -> str:
    # Only the class's own docstring: an inherited one describes the base class
    return inspect.cleandoc(cls.__dict__['__doc__']).split('\n\n')[0].replace('\n', ' ') if cls.__dict__.get('__doc__') else ''

def schema() -> dict:
    """Widget types with their options (kind, default, enum choices), for building editors."""
    widgets = {}
    for name, cls in widget_types().items():
        widgets[name] = {
            'doc': _doc(cls),
            'container': issubclass(cls, pyxelwidgets.group.Group),
            # Has a value a knob, fader or button binding can set (Button, Fader, Knob, XY)
            'bindable': issubclass(cls, pyxelwidgets.widgets.ValueWidget),
            'options': option_schema(cls),
        }
    return {'format': FORMAT, 'version': VERSION, 'widgets': widgets,
            'animations': {name: {'doc': _doc(cls), 'options': option_schema(cls)} for name, cls in ANIMATIONS.items()},
            'binding': {'options': option_schema(pyxelwidgets.binding.Binding), 'actions': list(ACTIONS)}}

def _options(cls, options: dict, where: str) -> dict:
    parameters = {parameter.name: parameter for parameter in _parameters(cls)}
    kwargs = {}
    for key, value in (options or {}).items():
        if key not in parameters:
            raise LayoutError(f'{where}.options: {cls.__name__} has no option {key!r} (options: {", ".join(parameters)})')
        kind, extra = _kind(parameters[key])
        try:
            if kind == 'color':
                value = text_to_color(value)
            elif kind == 'enum':
                if value not in extra.__members__:
                    raise ValueError(f'unknown value {value!r} (choices: {", ".join(extra.__members__)})')
                value = extra[value]
            elif kind == 'point':
                value = tuple(value)
            elif kind == 'frames':
                value = json_to_frames(value)
            elif kind == 'rate':
                if extra and isinstance(value, (int, float)) and not isinstance(value, bool):
                    if not value > 0:
                        raise ValueError(f'must be a note value or positive seconds, got {value!r}')
                elif value is not None:
                    pyxelwidgets.rate.parse_rate(value if isinstance(value, str) else None)
        except (ValueError, TypeError) as error:
            raise LayoutError(f'{where}.options.{key}: {error}') from None
        kwargs[key] = value
    return kwargs

def device_class(device: dict, where: str = 'device') -> type:
    """The class of a layout ``device`` entry, e.g. ``"novation.LaunchpadMiniMK3"``."""
    module_name, _, class_name = device.get('type', '').rpartition('.')
    try:
        return getattr(importlib.import_module(f'pyxelwidgets.devices.{module_name}'), class_name)
    except (ImportError, AttributeError, ValueError):
        raise LayoutError(f'{where}.type: unknown device {device.get("type")!r}') from None

def build_device(device: dict, where: str = 'device'):
    """Create a layout ``device`` entry and connect it to its ports (or the ports found by name)."""
    cls = device_class(device, where)
    instance = cls(**_options(cls, device.get('options'), where))
    if device.get('input') or device.get('output'):
        instance.connect(device.get('input'), device.get('output'))
    else:
        instance.connect()
    return instance

class Parser():
    """
    Builds a Surface from a layout (a path, JSON text or a dict). ``surface``,
    ``devices`` and ``widgets`` (every widget by name, groups included) are
    available after construction; ``ui['name']`` finds a widget.

    With ``devices = False`` the devices aren't created (no ports are opened),
    e.g. to validate or preview a layout.
    """

    def __init__(self, layout, *, devices: bool = True) -> None:
        if isinstance(layout, dict):
            self.json = layout
        elif isinstance(layout, str) and layout.lstrip().startswith('{'):
            self.json = json.loads(layout)
        else:
            self.json = json.loads(pathlib.Path(layout).read_text())
        self.json = upgrade(self.json)
        self.transport_settings()
        self.devices = []
        self.widgets = {}
        self.surface = None
        self.get_surface()
        if devices:
            self.get_devices()
        self.get_widgets()
        self.binding_settings()
        self.bindings = self.bind(self.devices) if devices else []

    def __getitem__(self, name: str):
        return self.widgets[name]

    def get_surface(self):
        surface = self.json.get('surface', {})
        try:
            self.surface = pyxelwidgets.surface.Surface(int(surface['width']), int(surface['height']))
        except (KeyError, TypeError, ValueError):
            raise LayoutError('surface: needs integer "width" and "height"') from None

    def get_devices(self):
        for index, device in enumerate(self.json.get('devices', [])):
            instance = build_device(device, f'devices[{index}]')
            self.surface.add_device(instance, device.get('x', 0), device.get('y', 0))
            self.devices.append(instance)

    def get_widgets(self):
        self._add_widgets(self.surface.root, self.json.get('widgets', []), 'widgets')

    def _add_widgets(self, parent, widgets: list, where: str) -> None:
        types = widget_types()
        for index, item in enumerate(widgets):
            path = f'{where}[{index}]'
            cls = types.get(item.get('type'))
            if cls is None:
                raise LayoutError(f'{path}.type: unknown widget {item.get("type")!r} (types: {", ".join(types)})')
            name = item.get('name')
            if not name or name in self.widgets:
                raise LayoutError(f'{path}.name: widget names must be given and unique, got {name!r}')
            try:
                geometry = [int(item.get(key, default)) for key, default in (('x', 0), ('y', 0), ('width', 1), ('height', 1))]
            except (TypeError, ValueError):
                raise LayoutError(f'{path}: x, y, width and height must be integers') from None
            if geometry[2] < 1 or geometry[3] < 1:
                raise LayoutError(f'{path}: width and height must be at least 1')
            try:
                widget = cls(*geometry, name = name, **_options(cls, item.get('options'), path))
            except (ValueError, TypeError) as error:
                if isinstance(error, LayoutError):
                    raise
                raise LayoutError(f'{path}.options: {error}') from None
            if item.get('animation') is not None:
                widget.animation = self._animation(item['animation'], f'{path}.animation')
            self.widgets[name] = widget
            parent.add(widget)
            if item.get('widgets'):
                if not isinstance(widget, pyxelwidgets.group.Group):
                    raise LayoutError(f'{path}.widgets: only a Group can contain widgets')
                self._add_widgets(widget, item['widgets'], f'{path}.widgets')

    def _animation(self, entry, where: str):
        if not isinstance(entry, dict) or entry.get('type') not in ANIMATIONS:
            kind = entry.get('type') if isinstance(entry, dict) else entry
            raise LayoutError(f'{where}.type: unknown animation {kind!r} (animations: {", ".join(ANIMATIONS)})')
        cls = ANIMATIONS[entry['type']]
        try:
            return cls(**_options(cls, entry.get('options'), where))
        except (ValueError, TypeError) as error:
            if isinstance(error, LayoutError):
                raise
            raise LayoutError(f'{where}.options: {error}') from None

    def transport_settings(self) -> dict:
        """Keyword arguments for a Transport (or App) from the layout's ``transport``."""
        settings = self.json.get('transport') or {}
        bpm = settings.get('bpm', 120)
        if isinstance(bpm, bool) or not isinstance(bpm, (int, float)) or bpm <= 0:
            raise LayoutError(f'transport.bpm: must be a positive number, got {bpm!r}')
        try:
            signature = pyxelwidgets.transport.parse_signature(settings.get('signature', (4, 4)))
        except ValueError as error:
            raise LayoutError(f'transport.signature: {error}') from None
        return {'bpm': bpm, 'signature': signature}

    def attach(self, transport) -> list:
        """Subscribe every Sequencer and Tracker to ``transport`` at its ``rate``; returns the Subscriptions."""
        return [transport.every(widget.rate, widget.play) for widget in self.widgets.values()
                if isinstance(widget, (pyxelwidgets.widgets.Sequencer, pyxelwidgets.widgets.Tracker))]

    def app(self, fps: float = 60.0):
        """An App running the surface, with Sequencers and Trackers following its transport."""
        import pyxelwidgets.app
        app = pyxelwidgets.app.App(self.surface, fps, **self.transport_settings())
        self.attach(app.transport)
        self.bindings += self.bind(self.devices, app.transport, widgets = False)
        return app

    def binding_settings(self) -> list:
        """The layout's bindings as (device index, control, widget or None, action or None, Binding options)."""
        bindings = self.json.get('bindings') or []
        if not isinstance(bindings, list):
            raise LayoutError('bindings: must be a list')
        count = len(self.json.get('devices') or [])
        settings = []
        for index, binding in enumerate(bindings):
            where = f'bindings[{index}]'
            device, control = binding.get('device'), binding.get('control')
            widget, action = binding.get('widget'), binding.get('action')
            if isinstance(device, bool) or not isinstance(device, int) or not 0 <= device < count:
                raise LayoutError(f'{where}.device: must be the index of one of the {count} devices, got {device!r}')
            if not isinstance(control, str) or not control:
                raise LayoutError(f'{where}.control: must be a control name, got {control!r}')
            if (widget is None) == (action is None):
                raise LayoutError(f'{where}: needs either "widget" or "action"')
            if widget is not None and widget not in self.widgets:
                raise LayoutError(f'{where}.widget: no widget named {widget!r}')
            if action is not None and action not in ACTIONS:
                raise LayoutError(f'{where}.action: unknown action {action!r} (actions: {", ".join(ACTIONS)})')
            settings.append((device, control, widget, action, _options(pyxelwidgets.binding.Binding, binding.get('options'), where)))
        return settings

    def bind(self, devices: list, transport = None, *, widgets: bool = True) -> list:
        """
        Create the layout's bindings on the surface: widget bindings (with
        ``widgets``) and, given a ``transport``, action bindings. ``devices``
        are in layout order; a missing one (None) is skipped. Returns the Bindings.
        """
        created = []
        for index, control, widget, action, options in self.binding_settings():
            device = devices[index] if index < len(devices) else None
            if device is None:
                continue
            if widget is not None and widgets:
                created.append(self.surface.bind(device, control, self.widgets[widget], **options))
            elif action is not None and transport is not None:
                created.append(self.surface.bind(device, control, ACTIONS[action](transport)))
        return created

def _fraction_text(value: fractions.Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f'{value.numerator}/{value.denominator}'

def upgrade(layout: dict) -> dict:
    """``layout`` converted to the current version (a copy if it changes); raises LayoutError if it isn't a layout."""
    if not isinstance(layout, dict) or layout.get('format') != FORMAT:
        raise LayoutError(f'not a {FORMAT} layout')
    version = layout.get('version')
    if isinstance(version, bool) or version not in range(1, VERSION + 1):
        raise LayoutError(f'unsupported {FORMAT} version {version!r} (supported: 1 to {VERSION})')
    if version == VERSION:
        return layout
    layout = _from_version_1(layout) if version == 1 else copy.deepcopy(layout)
    # Version 3 added the optional "bindings"; nothing to convert
    _from_version_3(layout.get('widgets'))
    layout['version'] = VERSION
    return layout

def _from_version_3(widgets) -> None:
    """Version 4 timed Sprites with a ``rate``: their frame counting options are gone (and added ``animation``)."""
    for widget in widgets or []:
        if widget.get('type') == 'Sprite' and widget.get('options'):
            for key in ('animate', 'target', 'tick'):
                widget['options'].pop(key, None)
        _from_version_3(widget.get('widgets'))

def _from_version_1(layout: dict) -> dict:
    """Version 1 had a tick based clock; Sequencer/Tracker timing was set in ticks per quarter note."""
    clock = layout.get('clock') or {}
    transport = {'bpm': clock.get('bpm', 120), 'signature': [4, 4]}
    # Same key order, with the transport where the clock was
    layout = {('transport' if key == 'clock' else key): (transport if key == 'clock' else copy.deepcopy(value))
              for key, value in layout.items()}
    layout['version'] = 2
    layout.setdefault('transport', transport)
    def convert(widgets, where):
        for index, widget in enumerate(widgets or []):
            options = widget.get('options') or {}
            try:
                if widget.get('type') == 'Sequencer':
                    note, beat = options.pop('note', 4.0), options.pop('beat', 4.0)
                    options.pop('ppq', None)
                    rate = 1 / (fractions.Fraction(note) * fractions.Fraction(beat))
                elif widget.get('type') == 'Tracker':
                    numerator, denominator = options.pop('numerator', 1.0), options.pop('denominator', 4.0)
                    options.pop('ppq', None)
                    # Rows were numerator/denominator quarter notes long
                    rate = fractions.Fraction(numerator) / (fractions.Fraction(denominator) * 4)
                else:
                    rate = None
            except (TypeError, ValueError, ZeroDivisionError):
                raise LayoutError(f'{where}[{index}].options: invalid version 1 timing options') from None
            if rate is not None and rate != fractions.Fraction(1, 16):
                options['rate'] = _fraction_text(rate.limit_denominator(1024))
                widget['options'] = options
            convert(widget.get('widgets'), f'{where}[{index}].widgets')
    convert(layout.get('widgets'), 'widgets')
    return layout

def load(layout, **kwargs) -> Parser:
    """Build a Surface from a layout file (or JSON text, or a dict)."""
    return Parser(layout, **kwargs)
