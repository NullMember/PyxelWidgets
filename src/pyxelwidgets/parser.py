"""
Layout files: a JSON description of a Surface, the devices it is shown on and
its widgets, as written by the designer (``python -m pyxelwidgets.designer``).

    {
      "format": "pyxelwidgets.layout", "version": 6,
      "surface": {"width": 9, "height": 9},
      "transport": {"bpm": 120, "signature": [4, 4]},
      "devices": [{"type": "novation.LaunchpadMiniMK3", "x": 0, "y": 0, "options": {}}],
      "bindings": [
        {"device": 0, "control": "Top1", "widget": "volume", "options": {"takeover": "Pickup"}},
        {"device": 0, "control": "Top8", "action": "transport.toggle"}
      ],
      "outputs": [{"name": "daw", "type": "mackie.MackieControl", "virtual": "PyxelWidgets", "options": {}}],
      "mappings": [
        {"widget": "volume", "on": "Changed", "output": "daw", "feedback": true,
         "message": {"type": "Command", "name": "Fader 1", "value": {"source": "value"}}}
      ],
      "links": [
        {"widget": "show", "on": "Changed", "target": "page", "option": "visible", "value": {"source": "value"}},
        {"widget": "up", "on": "Pressed", "target": "keys", "option": "octave", "change": "Add", "value": 1, "max": 4}
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

Outputs send widget events to other software: MIDI ports, OSC, Mackie
Control, HUI (``devices`` modules, with ``input``/``output`` port names or a
``virtual`` port name). Mappings send a widget's ``on`` event to an output as
``message`` (a class of ``pyxelwidgets.message`` with its fields, each a
constant or ``{"source": "velocity", "min": 0, "max": 127, "offset": 0}``);
with ``feedback`` what the output receives updates the widget.

Links change a ``target`` widget's ``option`` (one of its options, or ``x``,
``y``, ``width``, ``height``) on a widget's ``on`` event: ``change`` is
``Set`` (default), ``Add`` or ``Toggle``; ``value`` is a constant encoded like
the option, or ``{"source": "value", "offset": 0}``; optional ``min``/``max``
are the range a 0.0-1.0 source covers and clamp numbers (see
``pyxelwidgets.link``). Instead of an option a link can call an ``action``:
one of the target widget's ``actions`` (``advance``, ``play`` with a step
``value``, ``next``...) or, without a target, a transport action
(``ACTIONS``: ``transport.play``..., or ``VALUE_ACTIONS`` taking a
number: ``transport.tempo``, ``transport.tempo_add``).

Load a layout and attach behaviour by widget name::

    ui = pyxelwidgets.parser.load('layout.json')
    ui['volume'].on(Changed, lambda e: print(e.value))
    app = ui.app()              # Sequencers and Trackers follow app.transport
    app.transport.play()
    app.run()
"""

import copy
import dataclasses
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
import pyxelwidgets.events
import pyxelwidgets.group
import pyxelwidgets.link
import pyxelwidgets.mapping
import pyxelwidgets.message
import pyxelwidgets.rate
import pyxelwidgets.surface
import pyxelwidgets.transport
import pyxelwidgets.widgets

FORMAT = 'pyxelwidgets.layout'
VERSION = 6

# Actions a binding can trigger, on the transport given to Parser.bind
ACTIONS = {
    'transport.play': lambda transport: transport.play,
    'transport.stop': lambda transport: transport.stop,
    'transport.toggle': lambda transport: transport.toggle,
    'transport.rewind': lambda transport: (lambda: transport.locate(0)),
}

# Transport actions links can call with a number (tempo in bpm, or bpm to add)
VALUE_ACTIONS = {
    'transport.tempo': lambda transport: (lambda bpm: setattr(transport, 'bpm', max(1.0, float(bpm)))),
    'transport.tempo_add': lambda transport: (lambda amount: setattr(transport, 'bpm', max(1.0, transport.bpm + amount))),
}

# Animations a widget entry can have, by name
ANIMATIONS = {cls.__name__: cls for cls in (pyxelwidgets.animation.Blink, pyxelwidgets.animation.Pulse, pyxelwidgets.animation.Fade)}

# Messages mappings send, by class name
MESSAGES = {name: getattr(pyxelwidgets.message, name) for name in (
    'NoteOn', 'NoteOff', 'ControlChange', 'ProgramChange', 'PitchBend', 'PolyPressure', 'ChannelPressure', 'OscMessage', 'Command')}

# Option kinds a link can take an event value for, and the ones it can add to or toggle
LINK_SOURCES = {'bool', 'int', 'float', 'color', 'enum', 'str'}
LINK_CHANGES = {'Set': None, 'Add': {'int', 'float', 'enum'}, 'Toggle': {'bool', 'enum'}}

# Suggested values for rate options; any note value is accepted
RATES = ['1/1', '1/2', '1/4', '1/8', '1/16', '1/32', '1/4.', '1/8.', '1/16.', '1/4T', '1/8T', '1/16T', 'beat', 'bar']

class LayoutError(ValueError):
    """A layout that doesn't describe a valid surface; the message names where."""

# Widget and device classes of your own, made usable in layouts with register()
_WIDGETS = {}
_DEVICES = {}

def register(cls: type) -> type:
    """
    Make a widget or device class of your own usable in layouts and in the
    designer (start it with ``--import your_module``): widgets by their class
    name, devices and outputs as ``"your_module.YourClass"``. Returns ``cls``,
    so it works as a class decorator.
    """
    if isinstance(cls, type) and issubclass(cls, pyxelwidgets.widgets.Widget):
        _WIDGETS[cls.__name__] = cls
    elif isinstance(cls, type) and callable(getattr(cls, 'describe', None)) and callable(getattr(cls, 'show', None)):
        _DEVICES[device_type(cls)] = cls
    else:
        raise TypeError(f'{cls!r} is neither a Widget nor a Device class')
    return cls

def device_type(cls: type) -> str:
    """A device class's ``type`` in layouts: ``"novation.LaunchpadX"`` for the package's, ``"module.Class"`` for others."""
    module = cls.__module__.removeprefix('pyxelwidgets.devices.')
    return f'{module}.{cls.__name__}'

def registered_devices() -> dict:
    """Device and output classes added with ``register``, by type."""
    return dict(_DEVICES)

def widget_types() -> dict:
    """Widget classes usable in layouts, by name (registered ones included)."""
    types = {name: cls for name, cls in vars(pyxelwidgets.widgets).items()
             if isinstance(cls, type) and issubclass(cls, pyxelwidgets.widgets.Widget)
             and cls not in (pyxelwidgets.widgets.Widget, pyxelwidgets.widgets.ValueWidget)}
    types['Group'] = pyxelwidgets.group.Group
    types['Pages'] = pyxelwidgets.group.Pages
    types.update(_WIDGETS)
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

def linkable(cls) -> list:
    """Options of a widget class a link can change: its position and size, then its options (not Sprite frames)."""
    geometry = [{'name': name, 'kind': 'int'} for name in ('x', 'y', 'width', 'height')]
    return geometry + [option for option in option_schema(cls) if option['kind'] != 'frames']

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
            'events': [event.__name__ for event in cls.events()],
            'linkable': linkable(cls),
            # Methods links can call: None, or the kind of their argument
            'actions': dict(cls.actions),
        }
    events = {event.__name__: {'doc': _doc(event), 'sources': pyxelwidgets.mapping.available(event)}
              for cls in widget_types().values() for event in cls.events()}
    return {'format': FORMAT, 'version': VERSION, 'widgets': widgets,
            'animations': {name: {'doc': _doc(cls), 'options': option_schema(cls)} for name, cls in ANIMATIONS.items()},
            'binding': {'options': option_schema(pyxelwidgets.binding.Binding), 'actions': list(ACTIONS)},
            'events': events, 'messages': message_schema(),
            'link': {'changes': {name: sorted(kinds) if kinds else None for name, kinds in LINK_CHANGES.items()},
                     'sources': sorted(LINK_SOURCES),
                     'actions': {**{name: None for name in ACTIONS}, **{name: 'float' for name in VALUE_ACTIONS}}}}

def message_schema() -> dict:
    """Mapping message types with their fields: name, default (encoded) and range (whole numbers) or kind."""
    messages = {}
    for name, cls in MESSAGES.items():
        if cls is pyxelwidgets.message.OscMessage:
            fields = [{'name': 'address', 'kind': 'text', 'default': '/'}, {'name': 'args', 'kind': 'list', 'default': []}]
        else:
            fields = []
            for field in dataclasses.fields(cls):
                if field.name == 'flash':
                    continue
                entry = {'name': field.name, 'default': _encode_field(field.default)}
                if field.name in cls.ranges:
                    entry['range'] = list(cls.ranges[field.name])
                else:
                    entry['kind'] = 'text' if isinstance(field.default, str) else 'value'
                fields.append(entry)
        messages[name] = {'doc': _doc(cls), 'fields': fields}
    return messages

def _encode_field(value):
    if isinstance(value, pyxelwidgets.message.Source):
        encoded = {'source': value.name}
        for key, default in (('min', None), ('max', None), ('offset', 0)):
            if getattr(value, key) != default:
                encoded[key] = getattr(value, key)
        return encoded
    return value

def message_to_json(message: pyxelwidgets.message.Message) -> dict:
    """A mapping message as layout JSON."""
    data = {'type': type(message).__name__}
    if isinstance(message, pyxelwidgets.message.OscMessage):
        data.update(address = message.address, args = [_encode_field(arg) for arg in message.args])
    else:
        data.update({field.name: _encode_field(getattr(message, field.name))
                     for field in dataclasses.fields(message) if field.name != 'flash'})
    return data

def _decode_field(value, where: str, field_range = None):
    if isinstance(value, dict):
        name = value.get('source')
        unknown = set(value) - {'source', 'min', 'max', 'offset'}
        if not isinstance(name, str) or not name or unknown:
            raise LayoutError(f'{where}: a source is {{"source": name, "min", "max", "offset"}}, got {value!r}')
        for key in ('min', 'max'):
            if value.get(key) is not None and (isinstance(value[key], bool) or not isinstance(value[key], (int, float))):
                raise LayoutError(f'{where}.{key}: must be a number, got {value[key]!r}')
        offset = value.get('offset', 0)
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise LayoutError(f'{where}.offset: must be a whole number, got {offset!r}')
        return pyxelwidgets.message.Source(name, value.get('min'), value.get('max'), offset)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise LayoutError(f'{where}: must be a number, text or a source, got {value!r}')
    if field_range is not None and (not isinstance(value, int) or not field_range[0] <= value <= field_range[1]):
        raise LayoutError(f'{where}: must be a whole number from {field_range[0]} to {field_range[1]}, got {value!r}')
    return value

def message_from_json(data, where: str = 'message') -> pyxelwidgets.message.Message:
    """A mapping message from layout JSON; raises LayoutError naming the field."""
    cls = MESSAGES.get(data.get('type')) if isinstance(data, dict) else None
    if cls is None:
        kind = data.get('type') if isinstance(data, dict) else data
        raise LayoutError(f'{where}.type: unknown message {kind!r} (messages: {", ".join(MESSAGES)})')
    if cls is pyxelwidgets.message.OscMessage:
        address, args = data.get('address'), data.get('args', [])
        if not isinstance(address, str) or not address.startswith('/'):
            raise LayoutError(f'{where}.address: must start with "/", got {address!r}')
        if not isinstance(args, list):
            raise LayoutError(f'{where}.args: must be a list')
        return cls(address, *[_decode_field(arg, f'{where}.args[{i}]') for i, arg in enumerate(args)])
    names = [field.name for field in dataclasses.fields(cls) if field.name != 'flash']
    fields = {}
    for key, value in data.items():
        if key == 'type':
            continue
        if key not in names:
            raise LayoutError(f'{where}: {cls.__name__} has no field {key!r} (fields: {", ".join(names)})')
        fields[key] = _decode_field(value, f'{where}.{key}', cls.ranges.get(key))
    if cls is pyxelwidgets.message.Command and not isinstance(fields.get('name', 'Play'), str):
        raise LayoutError(f'{where}.name: must be a command name')
    return cls(**fields)

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
    """The class of a layout ``device`` entry, e.g. ``"novation.LaunchpadMiniMK3"`` (or a registered one)."""
    kind = device.get('type', '')
    if kind in _DEVICES:
        return _DEVICES[kind]
    module_name, _, class_name = kind.rpartition('.')
    try:
        return getattr(importlib.import_module(f'pyxelwidgets.devices.{module_name}'), class_name)
    except (ImportError, AttributeError, ValueError):
        raise LayoutError(f'{where}.type: unknown device {kind!r} (devices of your own need parser.register)') from None

def build_output(entry: dict, where: str = 'output'):
    """Create a layout ``outputs`` entry and connect it: to its ports, a ``virtual`` port, or (OSC) its address."""
    cls = device_class(entry, where)
    instance = cls(name = entry['name'], **_options(cls, entry.get('options'), where))
    if entry.get('virtual'):
        instance.connect_virtual(entry['virtual'])
    elif entry.get('input') or entry.get('output'):
        instance.connect(entry.get('input'), entry.get('output'))
    else:
        instance.connect()
    return instance

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
        # Clocks of widgets with their own (start_clocks)
        self.clocks = []
        self.devices = []
        self.widgets = {}
        self.surface = None
        self.get_surface()
        if devices:
            self.get_devices()
        self.get_widgets()
        self.binding_settings()
        self.bindings = self.bind(self.devices) if devices else []
        self.outputs = {}
        self.mapping_settings()
        if devices:
            for index, entry in enumerate(self.output_settings()):
                self.outputs[entry['name']] = build_output(entry, f'outputs[{index}]')
        self.mappings = self.map(self.outputs) if devices else []
        self.links = self.link()

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

    def timed(self, clock: pyxelwidgets.widgets.Clock) -> list:
        """The widgets (Sequencers, Trackers...) played by ``clock``."""
        return [widget for widget in self.widgets.values()
                if isinstance(widget, pyxelwidgets.widgets.Timed) and widget.clock == clock]

    def attach(self, transport) -> list:
        """Subscribe the widgets the transport plays (``clock = Clock.Transport``) to ``transport`` at their ``rate``; returns the Subscriptions."""
        return [transport.every(widget.rate, widget.tick) for widget in self.timed(pyxelwidgets.widgets.Clock.Transport)]

    def start_clocks(self, *, lock = None) -> list:
        """
        Start a clock (a Transport, holding ``lock``) for each widget with a
        clock of its own (``clock = Clock.Own``), following its ``bpm``; returns
        them, to ``close()`` when done (``close_clocks``).
        """
        signature = self.transport_settings()['signature']
        for widget in self.timed(pyxelwidgets.widgets.Clock.Own):
            clock = pyxelwidgets.transport.Transport(widget.bpm, signature = signature, lock = lock)
            def tick(count, widget = widget, clock = clock):
                # The widget's tempo may change (e.g. from a link)
                clock.bpm = widget.bpm
                widget.tick(count)
            clock.every(widget.rate, tick)
            clock.play()
            self.clocks.append(clock)
        return list(self.clocks)

    def close_clocks(self) -> None:
        for clock in self.clocks:
            clock.close()
        self.clocks = []

    def app(self, fps: float = 60.0):
        """An App running the surface, with the widgets following its transport, and their own clocks started."""
        import pyxelwidgets.app
        app = pyxelwidgets.app.App(self.surface, fps, **self.transport_settings())
        self.attach(app.transport)
        self.start_clocks(lock = app.lock)
        self.bindings += self.bind(self.devices, app.transport, widgets = False)
        self.links += self.link(app.transport, widgets = False)
        return app

    def output_settings(self) -> list:
        """The layout's ``outputs`` entries, checked: unique names and known types."""
        outputs = self.json.get('outputs') or []
        if not isinstance(outputs, list):
            raise LayoutError('outputs: must be a list')
        names = set()
        for index, entry in enumerate(outputs):
            where = f'outputs[{index}]'
            name = entry.get('name') if isinstance(entry, dict) else None
            if not isinstance(name, str) or not name or name in names:
                raise LayoutError(f'{where}.name: output names must be given and unique, got {name!r}')
            names.add(name)
            cls = device_class(entry, where)
            if not getattr(cls, 'messages', None):
                raise LayoutError(f'{where}.type: {entry["type"]} is not an output')
            for key in ('input', 'output', 'virtual'):
                if entry.get(key) is not None and not isinstance(entry[key], str):
                    raise LayoutError(f'{where}.{key}: must be a port name')
            _options(cls, entry.get('options'), where)
        return outputs

    def mapping_settings(self) -> list:
        """The layout's mappings as (widget name, event class or None, output name, message, feedback)."""
        mappings = self.json.get('mappings') or []
        if not isinstance(mappings, list):
            raise LayoutError('mappings: must be a list')
        outputs = {entry['name']: device_class(entry) for entry in self.output_settings()}
        settings = []
        for index, entry in enumerate(mappings):
            where = f'mappings[{index}]'
            if not isinstance(entry, dict):
                raise LayoutError(f'{where}: must be an object')
            widget, on, output = entry.get('widget'), entry.get('on'), entry.get('output')
            feedback = entry.get('feedback', False)
            if widget not in self.widgets:
                raise LayoutError(f'{where}.widget: no widget named {widget!r}')
            if output not in outputs:
                raise LayoutError(f'{where}.output: no output named {output!r} (outputs: {", ".join(outputs) or "none"})')
            if not isinstance(feedback, bool):
                raise LayoutError(f'{where}.feedback: must be true or false')
            event = None
            if on is not None:
                events = {cls.__name__: cls for cls in type(self.widgets[widget]).events()}
                if on not in events:
                    raise LayoutError(f'{where}.on: {widget} ({type(self.widgets[widget]).__name__}) has no event {on!r} (events: {", ".join(events)})')
                event = events[on]
            elif not feedback:
                raise LayoutError(f'{where}: needs "on", "feedback" or both')
            message = message_from_json(entry.get('message'), f'{where}.message')
            cls = outputs[output]
            if type(message).__name__ not in cls.messages:
                raise LayoutError(f'{where}.message.type: {cls.model} takes {", ".join(cls.messages)}, not {type(message).__name__}')
            commands = getattr(cls, 'commands', None)
            if isinstance(message, pyxelwidgets.message.Command) and commands and '{' not in message.name and message.name not in commands:
                raise LayoutError(f'{where}.message.name: {cls.model} has no command {message.name!r}')
            if event is not None:
                names = pyxelwidgets.mapping.available(event)
                for source in message.sources:
                    if source.name not in names:
                        raise LayoutError(f'{where}.message: {on} has no {source.name!r} (it has {", ".join(names)})')
            settings.append((widget, event, output, message, feedback))
        return settings

    def map(self, outputs: dict) -> list:
        """Create the layout's mappings on the surface for ``outputs`` (by name; missing ones are skipped)."""
        return [self.surface.map(self.widgets[widget], outputs[output], message, on = on, feedback = feedback)
                for widget, on, output, message, feedback in self.mapping_settings() if output in outputs]

    def link_settings(self) -> list:
        """
        The layout's links, checked, as dicts: ``widget`` and ``target`` names
        (target None for transport actions), ``on`` (event class), ``option`` or
        ``action``, ``value``, ``change`` (Link.Change), ``minimum``, ``maximum``.
        """
        links = self.json.get('links') or []
        if not isinstance(links, list):
            raise LayoutError('links: must be a list')
        settings = []
        for index, entry in enumerate(links):
            where = f'links[{index}]'
            if not isinstance(entry, dict):
                raise LayoutError(f'{where}: must be an object')
            unknown = set(entry) - {'widget', 'on', 'target', 'option', 'action', 'change', 'value', 'min', 'max'}
            if unknown:
                raise LayoutError(f'{where}: unknown keys {", ".join(sorted(unknown))}')
            widget, on, target = entry.get('widget'), entry.get('on'), entry.get('target')
            if widget not in self.widgets:
                raise LayoutError(f'{where}.widget: no widget named {widget!r}')
            events = {cls.__name__: cls for cls in type(self.widgets[widget]).events()}
            if on not in events:
                raise LayoutError(f'{where}.on: {widget} ({type(self.widgets[widget]).__name__}) has no event {on!r} (events: {", ".join(events)})')
            if ('option' in entry) == ('action' in entry):
                raise LayoutError(f'{where}: needs either "option" or "action"')
            setting = {'widget': widget, 'on': events[on], 'target': target, 'option': entry.get('option'), 'action': entry.get('action'),
                       'value': None, 'change': pyxelwidgets.link.Link.Change.Set, 'minimum': None, 'maximum': None}
            if 'action' in entry:
                self._link_action(entry, setting, events[on], where)
            else:
                self._link_option(entry, setting, events[on], where)
            settings.append(setting)
        return settings

    def _link_action(self, entry: dict, setting: dict, event: type, where: str) -> None:
        action, target = entry['action'], entry.get('target')
        if 'change' in entry:
            raise LayoutError(f'{where}.change: an action is called, not changed')
        if isinstance(action, str) and action.startswith('transport.'):
            if target is not None:
                raise LayoutError(f'{where}.target: transport actions have no target')
            if action not in ACTIONS and action not in VALUE_ACTIONS:
                raise LayoutError(f'{where}.action: unknown action {action!r} (transport actions: {", ".join([*ACTIONS, *VALUE_ACTIONS])})')
            kind = 'float' if action in VALUE_ACTIONS else None
        else:
            if target not in self.widgets:
                raise LayoutError(f'{where}.target: no widget named {target!r}')
            actions = type(self.widgets[target]).actions
            if action not in actions:
                names = [*actions, *ACTIONS]
                raise LayoutError(f'{where}.action: {target} ({type(self.widgets[target]).__name__}) has no action {action!r} (actions: {", ".join(names)})')
            kind = actions[action]
        value = entry.get('value')
        if kind is None:
            if value is not None or 'min' in entry or 'max' in entry:
                raise LayoutError(f'{where}.value: {action} takes no value')
            return
        if value is None:
            raise LayoutError(f'{where}.value: {action} needs a value')
        numbers = int if kind == 'int' else (int, float)
        what = 'a whole number' if kind == 'int' else 'a number'
        if isinstance(value, dict):
            value = self._link_source(value, event, f'{where}.value')
        elif isinstance(value, bool) or not isinstance(value, numbers):
            raise LayoutError(f'{where}.value: must be {what}, got {value!r}')
        setting['value'] = value
        for key, name in (('min', 'minimum'), ('max', 'maximum')):
            bound = entry.get(key)
            if bound is not None and (isinstance(bound, bool) or not isinstance(bound, numbers)):
                raise LayoutError(f'{where}.{key}: must be {what}, got {bound!r}')
            setting[name] = bound

    def _link_option(self, entry: dict, setting: dict, event: type, where: str) -> None:
        target, option = entry.get('target'), entry.get('option')
        if target not in self.widgets:
            raise LayoutError(f'{where}.target: no widget named {target!r}')
        cls = type(self.widgets[target])
        options = {item['name']: item for item in linkable(cls)}
        if option not in options:
            raise LayoutError(f'{where}.option: {target} ({cls.__name__}) has no option {option!r} (options: {", ".join(options)})')
        kind = options[option]['kind']
        change = entry.get('change', 'Set')
        if change not in LINK_CHANGES:
            raise LayoutError(f'{where}.change: must be one of {", ".join(LINK_CHANGES)}, got {change!r}')
        kinds = LINK_CHANGES[change]
        if kinds is not None and kind not in kinds:
            raise LayoutError(f'{where}.change: {change} works on {" and ".join(sorted(kinds))} options, {option!r} is {kind}')
        value = entry.get('value')
        if change == 'Toggle':
            if value is not None:
                raise LayoutError(f'{where}.value: Toggle takes no value')
        elif value is None:
            raise LayoutError(f'{where}.value: needed to {change}')
        elif isinstance(value, dict):
            value = self._link_source(value, event, f'{where}.value')
            if change == 'Set' and kind not in LINK_SOURCES:
                raise LayoutError(f'{where}.value: {option!r} ({kind}) takes a constant')
            if kind == 'color' and value.integer:
                raise LayoutError(f'{where}.value: a color takes a 0.0-1.0 value, not {value.name!r}')
        elif change == 'Add':
            if isinstance(value, bool) or not isinstance(value, (int, float)) or (kind != 'float' and not isinstance(value, int)):
                raise LayoutError(f'{where}.value: Add takes a {"number" if kind == "float" else "whole number"}, got {value!r}')
        else:
            value = self._link_constant(cls, option, kind, value, f'{where}.value')
        setting.update(value = value, change = pyxelwidgets.link.Link.Change[change])
        for key, name in (('min', 'minimum'), ('max', 'maximum')):
            bound = entry.get(key)
            if bound is not None:
                if kind not in ('int', 'float', 'color', 'enum', 'str'):
                    raise LayoutError(f'{where}.{key}: {option!r} ({kind}) has no range')
                if kind == 'str':
                    # The numbers text shows a 0.0-1.0 value as
                    if isinstance(bound, bool) or not isinstance(bound, (int, float)):
                        raise LayoutError(f'{where}.{key}: must be a number, got {bound!r}')
                else:
                    bound = self._link_constant(cls, option, kind, bound, f'{where}.{key}')
            setting[name] = bound

    @staticmethod
    def _link_source(value: dict, event: type, where: str) -> pyxelwidgets.message.Source:
        name, offset = value.get('source'), value.get('offset', 0)
        if set(value) - {'source', 'offset'} or not isinstance(name, str):
            raise LayoutError(f'{where}: a source is {{"source": name, "offset": n}} (the range is the link\'s "min" and "max"), got {value!r}')
        names = pyxelwidgets.mapping.available(event)
        if name not in names:
            raise LayoutError(f'{where}.source: {event.__name__} has no {name!r} (it has {", ".join(names)})')
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise LayoutError(f'{where}.offset: must be a whole number, got {offset!r}')
        return pyxelwidgets.message.Source(name, offset = offset)

    @staticmethod
    def _link_constant(cls, option: str, kind: str, value, where: str):
        """A link value or bound encoded like the option (geometry: whole numbers)."""
        if option in ('x', 'y', 'width', 'height') or kind == 'int':
            if isinstance(value, bool) or not isinstance(value, int):
                raise LayoutError(f'{where}: must be a whole number, got {value!r}')
            return value
        if kind == 'float':
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise LayoutError(f'{where}: must be a number, got {value!r}')
            return float(value)
        if kind == 'bool' and not isinstance(value, bool):
            raise LayoutError(f'{where}: must be true or false, got {value!r}')
        try:
            return _options(cls, {option: value}, where)[option]
        except LayoutError as error:
            # Name the value, not the option
            raise LayoutError(str(error).replace(f'{where}.options.{option}', where)) from None

    def link(self, transport = None, *, widgets: bool = True) -> list:
        """
        Create the layout's links on the surface: links to widgets (with
        ``widgets``) and, given a ``transport``, transport actions. Returns the Links.
        """
        created = []
        for setting in self.link_settings():
            action, target = setting['action'], setting['target']
            if action is not None and action.startswith('transport.'):
                if transport is None:
                    continue
                target, option = (ACTIONS.get(action) or VALUE_ACTIONS[action])(transport), None
            elif not widgets:
                continue
            elif action is not None:
                target, option = getattr(self.widgets[target], action), None
            else:
                target, option = self.widgets[target], setting['option']
            created.append(self.surface.link(self.widgets[setting['widget']], target, option, setting['value'], on = setting['on'],
                                             change = setting['change'], minimum = setting['minimum'], maximum = setting['maximum']))
        return created

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
    # Version 3 added the optional "bindings", version 5 "outputs" and "mappings", version 6 "links"; nothing to convert
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
