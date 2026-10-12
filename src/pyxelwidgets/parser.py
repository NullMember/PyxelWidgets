"""
Layout files: a JSON description of a Surface, the devices it is shown on and
its widgets, as written by the designer (``python -m pyxelwidgets.designer``).

    {
      "format": "pyxelwidgets.layout", "version": 2,
      "surface": {"width": 9, "height": 9},
      "transport": {"bpm": 120, "signature": [4, 4]},
      "devices": [{"type": "novation.LaunchpadMiniMK3", "x": 0, "y": 0, "options": {}}],
      "widgets": [
        {"type": "Fader", "name": "volume", "x": 0, "y": 0, "width": 1, "height": 8,
         "options": {"active_color": "#00ffff", "mode": "Magnitude"}},
        {"type": "Group", "name": "page", "x": 0, "y": 0, "width": 8, "height": 8,
         "options": {"visible": false}, "widgets": [...]}
      ]
    }

Widget options are the widget's constructor arguments: colors as ``#rrggbb``
or ``#rrggbbaa``, enums by member name (``"Magnitude"`` for ``Fader.Mode``),
rates as note values (``"1/16"``). Version 1 layouts are upgraded on load.
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

import pyxelwidgets.color
import pyxelwidgets.group
import pyxelwidgets.surface
import pyxelwidgets.transport
import pyxelwidgets.widgets

FORMAT = 'pyxelwidgets.layout'
VERSION = 2

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
    return dict(sorted(types.items()))

# Arguments set by the layout itself, not by options
_PLACEMENT = {'self', 'x', 'y', 'width', 'height', 'name'}

# Base class arguments a widget sets itself (a Group's background is its inactive_color)
_HIDDEN = {pyxelwidgets.group.Group: {'active_color', 'inactive_color'}}

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
    """(kind, enum class or None) of a constructor parameter."""
    annotation, default = parameter.annotation, parameter.default
    # Optional[X] / X | None: the kind of X
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        arguments = [argument for argument in typing.get_args(annotation) if argument is not type(None)]
        if len(arguments) == 1:
            annotation = arguments[0]
    if annotation is pyxelwidgets.widgets.Rate:
        return 'rate', None
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

def _encode(value, kind):
    if kind == 'color':
        return color_to_text(value)
    if kind == 'enum':
        return value.name
    if kind == 'point':
        return list(value)
    return value

def option_schema(cls) -> list:
    """Layout options of a widget or device class: name, kind, default and enum choices."""
    options = []
    for parameter in _parameters(cls):
        kind, enum_type = _kind(parameter)
        if kind == 'json':
            # Not representable in a layout (e.g. Sprite frames)
            continue
        option = {'name': parameter.name, 'kind': kind}
        if parameter.default is not parameter.empty:
            option['default'] = None if parameter.default is None else _encode(parameter.default, kind)
        if enum_type is not None:
            option['choices'] = [member.name for member in enum_type]
        elif kind == 'rate':
            option['choices'] = RATES
        options.append(option)
    return options

def schema() -> dict:
    """Widget types with their options (kind, default, enum choices), for building editors."""
    widgets = {}
    for name, cls in widget_types().items():
        widgets[name] = {
            # Only the class's own docstring: an inherited one describes the base class
            'doc': inspect.cleandoc(cls.__dict__['__doc__']).split('\n\n')[0].replace('\n', ' ') if cls.__dict__.get('__doc__') else '',
            'container': issubclass(cls, pyxelwidgets.group.Group),
            'options': option_schema(cls),
        }
    return {'format': FORMAT, 'version': VERSION, 'widgets': widgets}

def _options(cls, options: dict, where: str) -> dict:
    parameters = {parameter.name: parameter for parameter in _parameters(cls)}
    kwargs = {}
    for key, value in (options or {}).items():
        if key not in parameters:
            raise LayoutError(f'{where}.options: {cls.__name__} has no option {key!r} (options: {", ".join(parameters)})')
        kind, enum_type = _kind(parameters[key])
        try:
            if kind == 'color':
                value = text_to_color(value)
            elif kind == 'enum':
                if value not in enum_type.__members__:
                    raise ValueError(f'unknown value {value!r} (choices: {", ".join(enum_type.__members__)})')
                value = enum_type[value]
            elif kind == 'point':
                value = tuple(value)
            elif kind == 'rate':
                pyxelwidgets.transport.parse_rate(value)
        except (ValueError, TypeError) as error:
            raise LayoutError(f'{where}.options.{key}: {error}') from None
        kwargs[key] = value
    return kwargs

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
            where = f'devices[{index}]'
            module_name, _, class_name = device.get('type', '').rpartition('.')
            try:
                cls = getattr(importlib.import_module(f'pyxelwidgets.devices.{module_name}'), class_name)
            except (ImportError, AttributeError, ValueError):
                raise LayoutError(f'{where}.type: unknown device {device.get("type")!r}') from None
            instance = cls(**_options(cls, device.get('options'), where))
            if device.get('input') or device.get('output'):
                instance.connect(device.get('input'), device.get('output'))
            else:
                instance.connect()
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
            widget = cls(*geometry, name = name, **_options(cls, item.get('options'), path))
            self.widgets[name] = widget
            parent.add(widget)
            if item.get('widgets'):
                if not isinstance(widget, pyxelwidgets.group.Group):
                    raise LayoutError(f'{path}.widgets: only a Group can contain widgets')
                self._add_widgets(widget, item['widgets'], f'{path}.widgets')

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
        return app

def _fraction_text(value: fractions.Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f'{value.numerator}/{value.denominator}'

def upgrade(layout: dict) -> dict:
    """``layout`` converted to the current version (a copy if it changes); raises LayoutError if it isn't a layout."""
    if not isinstance(layout, dict) or layout.get('format') != FORMAT:
        raise LayoutError(f'not a {FORMAT} layout')
    version = layout.get('version')
    if version not in (1, VERSION):
        raise LayoutError(f'unsupported {FORMAT} version {version!r} (supported: 1 to {VERSION})')
    if version == VERSION:
        return layout
    # Version 1 had a tick based clock; Sequencer/Tracker timing was set in ticks per quarter note
    clock = layout.get('clock') or {}
    transport = {'bpm': clock.get('bpm', 120), 'signature': [4, 4]}
    # Same key order, with the transport where the clock was
    layout = {('transport' if key == 'clock' else key): (transport if key == 'clock' else copy.deepcopy(value))
              for key, value in layout.items()}
    layout['version'] = VERSION
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
