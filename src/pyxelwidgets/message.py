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
"""

import dataclasses
import re
import typing

__all__ = ['Source', 'Message', 'MidiMessage', 'NoteOn', 'NoteOff', 'ControlChange', 'ProgramChange',
           'PitchBend', 'PolyPressure', 'ChannelPressure', 'OscMessage', 'Command', 'INTEGER_SOURCES']

#: Sources that are whole numbers; the others are 0.0-1.0 (``text`` is a string)
INTEGER_SOURCES = frozenset({'x', 'y', 'cell', 'note', 'step', 'row', 'page', 'delta'})

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

def _resolve(value, sources: dict, field_range):
    if not isinstance(value, Source):
        return value
    low, high = field_range or (None, None)
    result = value.get(sources, low, high)
    if field_range is not None and not isinstance(result, str):
        result = int(min(high, max(low, round(result))))
    return result

def _recover(template, value, found: dict, field_range) -> bool:
    """Match one field: a constant must be equal, a Source stores what it carries in ``found``."""
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
