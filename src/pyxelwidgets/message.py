"""
Messages for other software (a DAW, a synth, an OSC app): MIDI messages, OSC
messages and control surface commands (Mackie Control, HUI). A message is a
template: each field is a constant or a ``Source`` taken from a widget event::

    NoteOn(note = 36, velocity = Source('velocity'))            # the press velocity
    NoteOn(note = Source('cell', offset = 36))                   # one note per cell
    ControlChange(control = 7, value = Source('value'))          # a fader, 0-127
    OscMessage('/track/{x+1}/mute', Source('state'))             # one track per column
    Command('Play')                                              # Mackie/HUI

``resolve(sources)`` fills the fields from an event's values (see
``pyxelwidgets.mapping``); ``match(message)`` does the reverse for a message
received from the other software, returning the values it carries (e.g.
``{'value': 0.5}``) or None when it is a different message.

Values: ``velocity``, ``value``, ``pressure``, ``state``... are 0.0-1.0 and are
scaled to a field's range (``min``/``max`` narrow it); ``x``, ``y``, ``cell``,
``note``, ``step``, ``delta``... are whole numbers, moved by ``offset``.

A field can also be computed: anything with ``evaluate(sources)`` and
``free`` (the event values it needs), e.g. a ``pyxelwidgets.expression.Expression``
such as ``{note + 12}`` or ``{velocity * 100}`` (event values as the event
has them; the result is rounded and clamped to the field's range). Computed
fields take whatever is received (they carry nothing back).
"""

import dataclasses
import re
import typing

__all__ = ['Source', 'Message', 'MidiMessage', 'NoteOn', 'NoteOff', 'ControlChange', 'ProgramChange',
           'PitchBend', 'PolyPressure', 'ChannelPressure', 'OscMessage', 'Command', 'PluginParameter', 'TrackParameter',
           'TRACK_PARAMETERS', 'INTEGER_SOURCES',
           'Hotkey', 'Key', 'TypeText', 'MouseMove', 'MouseButton', 'MouseClick', 'Scroll', 'KEY_NAMES', 'parse_keys']

#: Sources that are whole numbers; the others are 0.0-1.0 (``text`` is a string)
INTEGER_SOURCES = frozenset({'x', 'y', 'cell', 'note', 'step', 'row', 'column', 'page', 'delta'})

@dataclasses.dataclass(frozen = True)
class Source:
    """
    A field value taken from the event: ``name`` is one of its values. A 0.0-1.0
    value covers ``min`` to ``max`` (default: the field's whole range); a whole
    number has ``offset`` added.
    """
    name: str
    min: float | None = None
    max: float | None = None
    offset: int = 0

    @property
    def integer(self) -> bool:
        return self.name in INTEGER_SOURCES

    def get(self, sources: dict, low = None, high = None):
        """This source's value for a field ranging ``low``-``high`` (None: unbounded)."""
        value = sources[self.name]
        if isinstance(value, str):
            return value
        if self.integer:
            return int(value) + self.offset
        low = self.min if self.min is not None else low
        high = self.max if self.max is not None else high
        if low is None or high is None:
            return float(value)
        return low + float(value) * (high - low)

    def recover(self, value, low = None, high = None):
        """The event value that gives the field ``value`` (the reverse of ``get``)."""
        if isinstance(value, str):
            return value
        if self.integer:
            return int(value) - self.offset
        low = self.min if self.min is not None else low
        high = self.max if self.max is not None else high
        if low is None or high is None or high == low:
            return float(value)
        return min(1.0, max(0.0, (value - low) / (high - low)))

def _computed(value) -> bool:
    return not isinstance(value, Source) and callable(getattr(value, 'evaluate', None))

def _resolve(value, sources: dict, field_range):
    if _computed(value):
        result = value.evaluate(sources)
        if field_range is not None:
            if isinstance(result, str):
                raise ValueError(f'{value}: a number is needed, got {result!r}')
            result = int(min(field_range[1], max(field_range[0], round(result))))
        return result
    if not isinstance(value, Source):
        return value
    low, high = field_range or (None, None)
    result = value.get(sources, low, high)
    if field_range is not None and not isinstance(result, str):
        result = int(min(high, max(low, round(result))))
    return result

def _recover(template, value, found: dict, field_range) -> bool:
    """Match one field: a constant must be equal, a Source stores what it carries in ``found``."""
    if _computed(template):
        return True
    if isinstance(template, Source):
        low, high = field_range or (None, None)
        if template.name == 'delta' and not isinstance(value, str):
            # Relative controls send steps but receive a position (e.g. a V-Pot's LED ring)
            found['value'] = Source('value').recover(value, low, high)
        else:
            found[template.name] = template.recover(value, low, high)
        return True
    if isinstance(template, float) or isinstance(value, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and abs(template - value) < 1e-6
    return template == value

class Message:
    """Base of message templates; a template with constants only is a concrete message."""

    #: Field name → (lowest, highest) value, for fields that are whole numbers in a range
    ranges: typing.ClassVar[dict] = {}

    def _fields(self) -> list:
        return [field.name for field in dataclasses.fields(self)]

    def resolve(self, sources: dict) -> 'Message':
        """The concrete message for an event's ``sources``."""
        return dataclasses.replace(self, **{name: _resolve(getattr(self, name), sources, self.ranges.get(name))
                                            for name in self._fields()})

    def match(self, message: 'Message') -> dict | None:
        """The values ``message`` carries if it is this message (constants equal), else None."""
        if type(message) is not type(self):
            return None
        found = {}
        for name in self._fields():
            if not _recover(getattr(self, name), getattr(message, name), found, self.ranges.get(name)):
                return None
        return found

    @property
    def sources(self) -> list:
        return [value for value in vars(self).values() if isinstance(value, Source)]

    @property
    def needs(self) -> list:
        """Names of the event values it takes: its sources' and its computed fields'."""
        values = [value for field in vars(self).values() for value in (field if isinstance(field, tuple) else (field,))]
        return list(dict.fromkeys([source.name for source in self.sources]
                                  + [name for value in values if _computed(value) for name in value.free]))

# MIDI

_BYTE = (0, 127)
_CHANNEL = (1, 16)

class MidiMessage(Message):
    """A MIDI channel message; ``channel`` is 1-16."""

    status: typing.ClassVar[int] = 0

    def to_midi(self) -> list:
        raise NotImplementedError

    @staticmethod
    def from_midi(midi: list) -> 'MidiMessage | None':
        """The message for raw MIDI bytes (channel messages only), or None."""
        if not midi or not 0x80 <= midi[0] < 0xF0:
            return None
        status, channel = midi[0] & 0xF0, (midi[0] & 0x0F) + 1
        data = list(midi[1:3]) + [0, 0]
        if status == 0x80:
            return NoteOff(data[0], data[1], channel)
        if status == 0x90:
            return NoteOn(data[0], data[1], channel)
        if status == 0xA0:
            return PolyPressure(data[0], data[1], channel)
        if status == 0xB0:
            return ControlChange(data[0], data[1], channel)
        if status == 0xC0:
            return ProgramChange(data[0], channel)
        if status == 0xD0:
            return ChannelPressure(data[0], channel)
        return PitchBend(data[0] | (data[1] << 7), channel)

    def _status(self) -> int:
        return self.status | ((self.channel - 1) & 0x0F)

@dataclasses.dataclass(frozen = True)
class NoteOn(MidiMessage):
    note: typing.Any = 60
    velocity: typing.Any = Source('velocity')
    channel: typing.Any = 1
    status: typing.ClassVar[int] = 0x90
    ranges: typing.ClassVar[dict] = {'note': _BYTE, 'velocity': _BYTE, 'channel': _CHANNEL}

    def to_midi(self) -> list:
        return [self._status(), self.note, self.velocity]

@dataclasses.dataclass(frozen = True)
class NoteOff(MidiMessage):
    note: typing.Any = 60
    velocity: typing.Any = 0
    channel: typing.Any = 1
    status: typing.ClassVar[int] = 0x80
    ranges: typing.ClassVar[dict] = {'note': _BYTE, 'velocity': _BYTE, 'channel': _CHANNEL}

    def to_midi(self) -> list:
        return [self._status(), self.note, self.velocity]

@dataclasses.dataclass(frozen = True)
class ControlChange(MidiMessage):
    control: typing.Any = 1
    value: typing.Any = Source('value')
    channel: typing.Any = 1
    status: typing.ClassVar[int] = 0xB0
    ranges: typing.ClassVar[dict] = {'control': _BYTE, 'value': _BYTE, 'channel': _CHANNEL}

    def to_midi(self) -> list:
        return [self._status(), self.control, self.value]

@dataclasses.dataclass(frozen = True)
class ProgramChange(MidiMessage):
    program: typing.Any = 0
    channel: typing.Any = 1
    status: typing.ClassVar[int] = 0xC0
    ranges: typing.ClassVar[dict] = {'program': _BYTE, 'channel': _CHANNEL}

    def to_midi(self) -> list:
        return [self._status(), self.program]

@dataclasses.dataclass(frozen = True)
class PitchBend(MidiMessage):
    """``value`` is 0-16383; 8192 is the centre."""
    value: typing.Any = Source('value')
    channel: typing.Any = 1
    status: typing.ClassVar[int] = 0xE0
    ranges: typing.ClassVar[dict] = {'value': (0, 16383), 'channel': _CHANNEL}

    def to_midi(self) -> list:
        return [self._status(), self.value & 0x7F, self.value >> 7]

@dataclasses.dataclass(frozen = True)
class PolyPressure(MidiMessage):
    note: typing.Any = 60
    pressure: typing.Any = Source('pressure')
    channel: typing.Any = 1
    status: typing.ClassVar[int] = 0xA0
    ranges: typing.ClassVar[dict] = {'note': _BYTE, 'pressure': _BYTE, 'channel': _CHANNEL}

    def to_midi(self) -> list:
        return [self._status(), self.note, self.pressure]

@dataclasses.dataclass(frozen = True)
class ChannelPressure(MidiMessage):
    pressure: typing.Any = Source('pressure')
    channel: typing.Any = 1
    status: typing.ClassVar[int] = 0xD0
    ranges: typing.ClassVar[dict] = {'pressure': _BYTE, 'channel': _CHANNEL}

    def to_midi(self) -> list:
        return [self._status(), self.pressure]

# Names with placeholders: '/track/{x+1}/volume', 'Mute {cell+1}'

_PLACEHOLDER = re.compile(r'\{(\w+)\s*(?:([+-])\s*(\d+))?\}')

def _placeholders(template: str) -> list:
    """Sources of the ``{name+offset}`` placeholders in ``template``."""
    return [Source(name, offset = int(number) * (-1 if sign == '-' else 1) if number else 0)
            for name, sign, number in _PLACEHOLDER.findall(template)]

def _fill(template: str, sources: dict) -> str:
    return _PLACEHOLDER.sub(lambda m: str(_placeholders(m.group(0))[0].get(sources)), template)

def _match_name(template: str, name: str, found: dict) -> bool:
    pattern, last = '', 0
    for placeholder in _PLACEHOLDER.finditer(template):
        pattern += re.escape(template[last:placeholder.start()]) + r'(-?\d+)'
        last = placeholder.end()
    match = re.fullmatch(pattern + re.escape(template[last:]), name)
    if match is None:
        return False
    for source, text in zip(_placeholders(template), match.groups()):
        found[source.name] = source.recover(int(text))
    return True

@dataclasses.dataclass(frozen = True)
class OscMessage(Message):
    """
    An OSC message. ``address`` may hold ``{source}`` or ``{source+1}``
    placeholders; each of ``args`` is a constant (number or string) or a Source
    (0.0-1.0 values are sent as they are unless ``min``/``max`` are given).
    """
    address: str = '/'
    args: tuple = ()

    def __init__(self, address: str = '/', *args):
        # OscMessage('/volume', Source('value')) and OscMessage(address, args = (...))
        if len(args) == 1 and isinstance(args[0], (tuple, list)):
            args = tuple(args[0])
        object.__setattr__(self, 'address', address)
        object.__setattr__(self, 'args', tuple(args))

    def resolve(self, sources: dict) -> 'OscMessage':
        return OscMessage(_fill(self.address, sources), tuple(_resolve(arg, sources, None) for arg in self.args))

    def match(self, message) -> dict | None:
        if type(message) is not OscMessage:
            return None
        found = {}
        if not _match_name(self.address, message.address, found) or len(message.args) < len(self.args):
            return None
        for template, value in zip(self.args, message.args):
            if not _recover(template, value, found, None):
                return None
        return found

    @property
    def sources(self) -> list:
        return _placeholders(self.address) + [arg for arg in self.args if isinstance(arg, Source)]

@dataclasses.dataclass(frozen = True)
class Command(Message):
    """
    A control surface command (Mackie Control, HUI): a button such as
    ``'Play'`` or ``'Mute {x+1}'``, a fader (``'Fader 1'``, value 0.0-1.0), a
    V-Pot (``'V-Pot 1'``, value in steps, negative turns left) or, received,
    a display (``'Timecode'``, value a string). Buttons are pressed while
    ``value`` > 0. Received LEDs set ``flash`` when blinking.
    """
    name: str = 'Play'
    value: typing.Any = 1.0
    flash: bool = False

    def resolve(self, sources: dict) -> 'Command':
        return Command(_fill(self.name, sources), _resolve(self.value, sources, None))

    def match(self, message) -> dict | None:
        if type(message) is not Command:
            return None
        found = {}
        if not _match_name(self.name, message.name, found):
            return None
        if isinstance(self.value, Source):
            _recover(self.value, message.value, found, None)
        else:
            # A constant value: receive whatever state the other side sends (e.g. an LED)
            found['state'] = message.value if isinstance(message.value, str) else float(message.value)
        found['flash'] = message.flash
        return found

    @property
    def sources(self) -> list:
        return _placeholders(self.name) + ([self.value] if isinstance(self.value, Source) else [])

@dataclasses.dataclass(frozen = True)
class PluginParameter(Message):
    """
    A plug-in parameter, by name: ``track``, ``plugin`` and ``parameter`` are
    names as the output scanned them from the DAW (``scan_tracks``,
    ``scan_plugins``, ``scan_parameters``). ``value`` is V-Pot steps for
    Mackie Control's plug-in mode (a knob's or fader's ``delta``) and the
    position 0.0-1.0 for REAPER's OSC (a widget's ``value``); received, it is
    the parameter's position 0.0-1.0.
    """
    track: str = ''
    plugin: str = ''
    parameter: str = ''
    value: typing.Any = Source('delta')

    #: Fields named from a scan of the DAW, for editors
    scanned: typing.ClassVar[tuple] = ('track', 'plugin', 'parameter')

#: What TrackParameter reaches on a track
TRACK_PARAMETERS = ('Volume', 'Pan', 'Mute', 'Solo', 'Record')

@dataclasses.dataclass(frozen = True)
class TrackParameter(Message):
    """
    A track's ``Volume``, ``Pan``, ``Mute``, ``Solo`` or ``Record`` (arm), by
    the track's name as the output scanned it (``scan_tracks``), wherever the
    track is shown. ``value``: Volume is the fader's position 0.0-1.0; Pan is
    V-Pot steps for Mackie Control (a ``delta``) and the position 0.0-1.0 for
    REAPER; Mute, Solo and Record are on above 0.5. Received, every value is
    0.0-1.0.
    """
    track: str = ''
    parameter: str = 'Volume'
    value: typing.Any = Source('value')

    scanned: typing.ClassVar[tuple] = ('track',)
    choices: typing.ClassVar[dict] = {'parameter': TRACK_PARAMETERS}

    def __post_init__(self):
        if self.parameter not in TRACK_PARAMETERS:
            raise ValueError(f'parameter must be one of {", ".join(TRACK_PARAMETERS)}, got {self.parameter!r}')

# Keyboard and mouse (see pyxelwidgets.devices.desktop)

#: Named keys for Hotkey and Key, besides single characters ('a', '1', '/')
KEY_NAMES = frozenset({
    'ctrl', 'shift', 'alt', 'cmd', 'enter', 'space', 'tab', 'esc', 'backspace', 'delete', 'caps_lock',
    'up', 'down', 'left', 'right', 'home', 'end', 'page_up', 'page_down',
    *(f'f{n}' for n in range(1, 21)),
    'media_play_pause', 'media_next', 'media_previous', 'media_volume_up', 'media_volume_down', 'media_volume_mute',
})

# Other names people write for them
_KEY_ALIASES = {
    'control': 'ctrl', 'option': 'alt', 'opt': 'alt', 'command': 'cmd', 'super': 'cmd', 'win': 'cmd', 'meta': 'cmd',
    'return': 'enter', 'escape': 'esc', 'pgup': 'page_up', 'pgdn': 'page_down', 'del': 'delete', 'plus': '+',
    'play': 'media_play_pause', 'next': 'media_next', 'previous': 'media_previous',
    'volume_up': 'media_volume_up', 'volume_down': 'media_volume_down', 'mute': 'media_volume_mute',
}

def parse_keys(keys: str) -> tuple:
    """``'ctrl+shift+s'`` → ``('ctrl', 'shift', 's')``; raises ValueError for unknown keys."""
    names = []
    text = str(keys).lower().replace(' ', '')
    for part in ['+'] if text == '+' else text.split('+'):
        name = _KEY_ALIASES.get(part, part)
        if not name:
            raise ValueError(f'empty key in {keys!r} (write "plus" for +)')
        if name not in KEY_NAMES and len(name) != 1:
            raise ValueError(f'unknown key {part!r} in {keys!r} (keys: single characters, {", ".join(sorted(KEY_NAMES - {f"f{n}" for n in range(2, 21)}))}...)')
        names.append(name)
    if not names:
        raise ValueError('no keys')
    return tuple(names)

def _check_keys(keys) -> None:
    # Keys with placeholders ('f{x+1}') are checked once filled in
    if isinstance(keys, str) and '{' not in keys:
        parse_keys(keys)

_BUTTONS = ('left', 'right', 'middle')

@dataclasses.dataclass(frozen = True)
class Hotkey(Message):
    """Press ``keys`` together, then let go: ``'ctrl+c'``, ``'cmd+shift+4'``, ``'f{x+1}'`` (one per column)."""
    keys: str = 'ctrl+c'

    def __post_init__(self):
        _check_keys(self.keys)

    def resolve(self, sources: dict) -> 'Hotkey':
        return Hotkey(_fill(self.keys, sources))

    @property
    def sources(self) -> list:
        return _placeholders(self.keys)

@dataclasses.dataclass(frozen = True)
class Key(Message):
    """Hold ``keys`` down while ``state`` is above 0, let go at 0 (e.g. push to talk, a held Shift)."""
    keys: str = 'shift'
    state: typing.Any = Source('value')

    def __post_init__(self):
        _check_keys(self.keys)

    def resolve(self, sources: dict) -> 'Key':
        return Key(_fill(self.keys, sources), _resolve(self.state, sources, None))

    @property
    def sources(self) -> list:
        return _placeholders(self.keys) + ([self.state] if isinstance(self.state, Source) else [])

@dataclasses.dataclass(frozen = True)
class TypeText(Message):
    """Type ``text`` (placeholders such as ``{x+1}`` take a value from the event)."""
    text: str = 'Hello'

    def resolve(self, sources: dict) -> 'TypeText':
        return TypeText(_fill(self.text, sources))

    @property
    def sources(self) -> list:
        return _placeholders(self.text)

@dataclasses.dataclass(frozen = True)
class MouseMove(Message):
    """
    Move the pointer: to ``x``, ``y`` on the main screen (0.0-1.0 from the
    bottom-left, e.g. an XY's ``value_x``/``value_y``), or with ``relative``
    by ``x``, ``y`` pixels (positive y is up).
    """
    x: typing.Any = Source('value_x')
    y: typing.Any = Source('value_y')
    relative: bool = False

@dataclasses.dataclass(frozen = True)
class MouseButton(Message):
    """Hold a mouse ``button`` (left, right, middle) down while ``state`` is above 0, let go at 0 (dragging)."""
    button: str = 'left'
    state: typing.Any = Source('value')
    choices: typing.ClassVar[dict] = {'button': _BUTTONS}

    def __post_init__(self):
        if self.button not in _BUTTONS:
            raise ValueError(f'button must be one of {", ".join(_BUTTONS)}, got {self.button!r}')

@dataclasses.dataclass(frozen = True)
class MouseClick(Message):
    """Click a mouse ``button`` (left, right, middle) ``count`` times (2: a double click)."""
    button: str = 'left'
    count: typing.Any = 1
    ranges: typing.ClassVar[dict] = {'count': (1, 3)}
    choices: typing.ClassVar[dict] = {'button': _BUTTONS}

    def __post_init__(self):
        if self.button not in _BUTTONS:
            raise ValueError(f'button must be one of {", ".join(_BUTTONS)}, got {self.button!r}')

@dataclasses.dataclass(frozen = True)
class Scroll(Message):
    """Scroll by ``dx``, ``dy`` steps (positive dy is up), e.g. a knob's ``delta``."""
    dx: typing.Any = 0
    dy: typing.Any = Source('delta')
