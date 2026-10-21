"""
Links let a widget change another widget's options when it emits an event,
the way mappings send messages::

    Link(show, panel, 'visible', Source('value'), on = Changed)            # a switch shows a group
    Link(up, keys, 'octave', 1, on = Pressed, change = Link.Change.Add, maximum = 4)
    Link(tabs, pages, 'page', Source('cell'), on = Toggled)               # a ButtonGroup picks the page
    Link(level, pad, 'active_color', Source('value'), on = Changed)       # a fader dims a color
    Link(mode, fader, 'mode', on = Pressed, change = Link.Change.Toggle)  # next Fader.Mode

A device's control starts links too (``events.ControlInput``)::

    Link(surface.control(launchpad, 'Knob1'), pad, 'active_color', Source('value'), on = ControlChanged)
    Link(surface.control(launchpad, 'Encoder1'), keys, 'octave', Source('delta'), on = ControlTurned, change = Link.Change.Add)

Without an option the target is an action, called on each event, with the
value as its argument if there is one::

    Link(play, transport.toggle, on = Pressed)
    Link(step, sequencer.advance, on = Pressed)
    Link(pads, sequencer.play, value = Source('cell'), on = Pressed)     # jump to a step

The value is a constant or a ``Source`` from the event (see
``pyxelwidgets.mapping.sources``), turned into what the option holds:

- 0.0-1.0 values (``value``, ``velocity``...) cover ``minimum`` to ``maximum``:
  numbers (default 0-1, 0-127 for whole numbers), colors (default black to the
  option's color when linked), enum members (default all of them) and text;
  for on/off options anything above 0 is on.
- Whole numbers (``x``, ``cell``, ``step``, ``delta``...) have the source's
  ``offset`` added; for enums they are a member's index.

``Change.Add`` adds the value to numbers (or moves that many enum members);
a source is added as the event has it (``delta`` steps, or 0.0-1.0).
``Change.Toggle`` flips on/off options and steps enums to the next member.
Numbers end up clamped to ``minimum``/``maximum`` when given; a reversed
range (``minimum = 8, maximum = 7``) turns a 0.0-1.0 value around.

The value can also be a ``Condition``: an event value compared with a
constant chooses between two values::

    # Sequencer n shows only while cell n is chosen (16 links, one per sequencer)
    Link(tabs, sequencers[n], 'visible', Condition(Source('cell'), '==', n), on = Toggled)
    Link(tabs, pad, 'active_color', Condition(Source('x'), '<', 4, Colors.Red, Colors.Blue), on = Toggled)

Or a ``Choice``: an event value picks one of a list (whole numbers by
index, with their offset; 0.0-1.0 values spread over the list)::

    # A row of four pads sets a Sequencer's length
    Link(lengths, sequencer, 'length', Choice(Source('x'), (8, 16, 24, 32)), on = Toggled)
    Link(velocities, sequencer.set_velocity, Choice(Source('x'), (0.25, 0.5, 0.75, 1.0)), on = Pressed)

An action's value is a number: 0.0-1.0 sources cover ``minimum`` to
``maximum`` (whole numbers if both are), whole number sources add ``offset``.
A text value is filled in from the event: ``'pad {x},{y} at {velocity}'``;
``{all}`` is every value (``x=1 y=0 velocity=0.5``)::

    Link(pads, print, value = 'pressed {cell}', on = Pressed)

The value can be an ``Expression`` (``pyxelwidgets.expression``) of the
event's values and other widgets' options, or for text a ``Template``::

    Link(pads, roll, 'column', Expression('x * 4'), on = Pressed)
    Link(fader, roll, 'column', Expression('round(value * (roll.steps - roll.width))', {'roll': roll}), on = Changed)
    Link(roll, label, 'text', Template('{column + 1}/{roll.steps}', {'roll': roll}), on = ColumnChanged)

Its result is turned into what the option holds (whole numbers rounded,
choices by name or index, colors from "#rrggbb"); minimum and maximum clamp
numbers. An expression that can't be computed for an event is printed and
changes nothing.

A ``Formula`` keeps an option at what an expression computes, whenever it
changes (``surface.formula`` creates one updated every frame)::

    Formula(stepper, 'maximum', Expression('roll.steps - roll.width', {'roll': roll}))

Options change through ``target.configure``, which doesn't emit events, so
links don't trigger each other in loops (Pages emits PageChanged for a new
page; a link doesn't run again while it is running).
"""

import dataclasses
import enum
import operator
import typing

import pyxelwidgets.color
import pyxelwidgets.expression
import pyxelwidgets.mapping
import pyxelwidgets.message

__all__ = ['Link', 'Condition', 'Choice', 'Formula']

#: Computed link values: evaluated with the event's values
COMPUTED = (pyxelwidgets.expression.Expression, pyxelwidgets.expression.Template)

#: Comparisons a Condition makes
OPERATORS = {'==': operator.eq, '!=': operator.ne, '<': operator.lt, '<=': operator.le, '>': operator.gt, '>=': operator.ge}

@dataclasses.dataclass(frozen = True)
class Condition:
    """
    A link value chosen by a comparison: ``then`` if the event's ``source``
    (whole numbers with their offset, 0.0-1.0 values as they are) compared
    with ``op`` (==, !=, <, <=, >, >=) to ``to`` is true, else ``otherwise``.
    """
    source: pyxelwidgets.message.Source
    op: str = '=='
    to: typing.Any = 0
    then: typing.Any = True
    otherwise: typing.Any = False

    def __post_init__(self):
        if self.op not in OPERATORS:
            raise ValueError(f'op must be one of {", ".join(OPERATORS)}, got {self.op!r}')

    def test(self, sources: dict) -> bool:
        value = self.source.get(sources)
        if self.op in ('==', '!=') and isinstance(value, float) and isinstance(self.to, (int, float)):
            # 0.1 + 0.2 equals 0.3
            equal = abs(value - self.to) < 1e-6
            return equal if self.op == '==' else not equal
        try:
            return bool(OPERATORS[self.op](value, self.to))
        except TypeError:
            # Text compared with a number: only "not equal" holds
            return self.op == '!='

    def choose(self, sources: dict):
        return self.then if self.test(sources) else self.otherwise

@dataclasses.dataclass(frozen = True)
class Choice:
    """
    A link value picked from ``values`` by the event's ``source``: a whole
    number (with its offset) is the index, a 0.0-1.0 value spreads over the
    list; past either end it takes the first or last.
    """
    source: pyxelwidgets.message.Source
    values: tuple

    def __post_init__(self):
        if not self.values or isinstance(self.values, (str, bytes)):
            raise ValueError('a Choice needs values to choose from')
        object.__setattr__(self, 'values', tuple(self.values))

    def index(self, sources: dict) -> int:
        value = self.source.get(sources)
        if isinstance(value, str):
            return 0
        if not self.source.integer:
            value = round(float(value) * (len(self.values) - 1))
        return min(max(int(value), 0), len(self.values) - 1)

    def choose(self, sources: dict):
        return self.values[self.index(sources)]

#: Link values computed from the event: they ``choose`` the value
CHOOSERS = (Condition, Choice)

def _short(value):
    return round(value, 3) if isinstance(value, float) else value

def _every(sources: dict) -> str:
    return ' '.join(f'{name}={_short(value)}' for name, value in sources.items())

def fill_text(template, sources: dict) -> str:
    """
    ``template`` (text or a Template) with its ``{formulas}`` (``{name}``,
    ``{name+1}``...) computed from event values (those that can't be are
    kept), ``{all}`` with every value.
    """
    if isinstance(template, str):
        try:
            template = pyxelwidgets.expression.Template(template)
        except pyxelwidgets.expression.ExpressionError:
            return _fill_placeholders(template, sources)
    return template.evaluate({**sources, 'all': _every(sources)}, keep_unknown = True, show = lambda value: str(_short(value)))

def _fill_placeholders(template: str, sources: dict) -> str:
    def replace(match) -> str:
        if match.group(0) == '{all}':
            return _every(sources)
        source = pyxelwidgets.message._placeholders(match.group(0))[0]
        if source.name not in sources:
            return match.group(0)
        return str(_short(source.get(sources)))
    return pyxelwidgets.message._PLACEHOLDER.sub(replace, template)

def _kind(value) -> str:
    """What an option holds, from its current value."""
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, enum.Enum):
        return 'enum'
    if isinstance(value, pyxelwidgets.color.Color):
        return 'color'
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, str):
        return 'str'
    return 'other'

class Link:
    """
    On each ``on`` event of ``widget``, changes ``option`` of ``target`` to
    ``value`` (``Change.Set``), by ``value`` (``Change.Add``) or to the next
    state (``Change.Toggle``, which takes no value). Without ``option``,
    ``target`` is called (with ``value`` if given). See the module docs.
    """

    class Change(enum.Enum):
        Set     = enum.auto()
        Add     = enum.auto()
        Toggle  = enum.auto()

    def __init__(self, widget, target, option: str | None = None, value = None, *, on: type,
                 change: Change = Change.Set, minimum = None, maximum = None) -> None:
        if option is None:
            if not callable(target):
                raise ValueError('without an option the target must be an action (a callable)')
            if change != Link.Change.Set:
                raise ValueError('an action is called, not changed')
            current, kind = None, 'action'
        elif option.startswith('_') or not hasattr(target, option):
            raise ValueError(f'{type(target).__name__} has no option {option!r}')
        else:
            current = getattr(target, option)
            kind = _kind(current)
        if change == Link.Change.Toggle and kind not in ('bool', 'enum'):
            raise ValueError(f'only on/off and choice options toggle, not {option!r}')
        if change == Link.Change.Add and kind not in ('int', 'float', 'enum'):
            raise ValueError(f'only numbers and choices can be added to, not {option!r}')
        if change != Link.Change.Toggle and value is None and kind != 'action':
            raise ValueError('a value is needed to set or add')
        if isinstance(value, COMPUTED):
            names = pyxelwidgets.mapping.available(on) + (['all'] if isinstance(value, pyxelwidgets.expression.Template) else [])
            unknown = [name for name in value.free if name not in names]
            if unknown:
                raise ValueError(f'{value}: {on.__name__} has no {unknown[0]!r} (it has {", ".join(names)})')
            if kind == 'other':
                raise ValueError(f'{option!r} takes a constant, not an expression')
        if isinstance(value, CHOOSERS):
            names = pyxelwidgets.mapping.available(on)
            if value.source.name not in names:
                raise ValueError(f'{on.__name__} has no {value.source.name!r} (it has {", ".join(names)})')
        if isinstance(value, pyxelwidgets.message.Source):
            names = pyxelwidgets.mapping.available(on)
            if value.name not in names:
                raise ValueError(f'{on.__name__} has no {value.name!r} (it has {", ".join(names)})')
            if kind == 'other' or (kind == 'color' and value.integer):
                raise ValueError(f'{option!r} takes a constant, not a value from the event')
        self.widget = widget
        self.target = target
        self.option = option
        self.value = value
        self.on = on
        self.change = change
        self.minimum = minimum
        self.maximum = maximum
        self._kind = kind
        # What a color covers up to by default
        self._color = current if kind == 'color' else None
        self._running = False
        widget.on(on, self._changed)

    def close(self) -> None:
        self.widget.off(self.on, self._changed)

    def _changed(self, event) -> None:
        if self._running:
            return
        self._running = True
        try:
            if self._kind == 'action':
                if self.value is None:
                    self.target()
                else:
                    self.target(self.argument(pyxelwidgets.mapping.sources(event, self.widget)))
                return
            current = getattr(self.target, self.option)
            new = self.apply(current, pyxelwidgets.mapping.sources(event, self.widget))
            if new != current:
                self.target.configure(**{self.option: new})
        except pyxelwidgets.expression.ExpressionError as error:
            print(f'Link from {getattr(self.widget, "name", self.widget)}: {error}', flush = True)
        finally:
            self._running = False

    def argument(self, sources: dict):
        """An action's argument from the event's ``sources``."""
        value = self.value.choose(sources) if isinstance(self.value, CHOOSERS) else self.value
        if isinstance(value, (str, pyxelwidgets.expression.Template)):
            return fill_text(value, sources)
        if isinstance(value, pyxelwidgets.expression.Expression):
            value = value.evaluate(sources)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                bounds = [bound for bound in (self.minimum, self.maximum) if bound is not None]
                if len(bounds) == 2:
                    value = min(max(value, min(bounds)), max(bounds))
            return value
        if not isinstance(value, pyxelwidgets.message.Source):
            return value
        raw = sources[value.name]
        if isinstance(raw, str):
            return raw
        if value.integer:
            return int(raw) + value.offset
        low = self.minimum if self.minimum is not None else 0
        high = self.maximum if self.maximum is not None else 1
        number = low + (high - low) * float(raw)
        return int(round(number)) if isinstance(low, int) and isinstance(high, int) and (low, high) != (0, 1) else number

    def apply(self, current, sources: dict):
        """The option's new value, from ``current`` and the event's ``sources``."""
        kind = self._kind
        if self.change == Link.Change.Toggle:
            if kind == 'bool':
                return not current
            members = list(type(current))
            return members[(members.index(current) + 1) % len(members)]
        given = self.value.choose(sources) if isinstance(self.value, CHOOSERS) else self.value
        if isinstance(given, pyxelwidgets.expression.Template):
            given = given.evaluate(sources)
        elif isinstance(given, pyxelwidgets.expression.Expression):
            given = given.evaluate(sources)
            if self.change != Link.Change.Add:
                given = convert(kind, given, current)
        if self.change == Link.Change.Add:
            if isinstance(given, pyxelwidgets.message.Source):
                # As the event has it: whole number steps (delta...) or 0.0-1.0
                source = sources[given.name]
                value = int(source) + given.offset if given.integer else float(source)
            else:
                value = given
            if kind == 'enum':
                members = list(type(current))
                return members[(members.index(current) + int(value)) % len(members)]
            value = current + value
            value = int(round(value)) if kind == 'int' else float(value)
        elif isinstance(given, pyxelwidgets.message.Source):
            value = self._source(sources, current)
        else:
            value = given
        if kind in ('int', 'float') and not isinstance(value, bool):
            bounds = [bound for bound in (self.minimum, self.maximum) if bound is not None]
            if len(bounds) == 2:
                # A reversed range (minimum > maximum) turns a 0.0-1.0 value around
                value = min(max(value, min(bounds)), max(bounds))
            elif self.minimum is not None:
                value = max(self.minimum, value)
            elif self.maximum is not None:
                value = min(self.maximum, value)
        return value

    def _source(self, sources: dict, current):
        """The Source's value as the option holds it."""
        source, kind = self.value, self._kind
        raw = sources[source.name]
        if isinstance(raw, str):
            return raw if kind == 'str' else current
        if source.integer:
            number = int(raw) + source.offset
            if kind == 'enum':
                members = list(type(current))
                return members[min(len(members) - 1, max(0, number))]
            return {'bool': lambda: number > 0, 'float': lambda: float(number), 'str': lambda: str(number)}.get(kind, lambda: number)()
        raw = float(raw)
        if kind == 'bool':
            return raw > 0
        if kind == 'color':
            low = self.minimum if self.minimum is not None else pyxelwidgets.color.Colors.Black
            high = self.maximum if self.maximum is not None else self._color
            return pyxelwidgets.color.Color(*(a + (b - a) * raw for a, b in zip(low.rgb, high.rgb)), low.a + (high.a - low.a) * raw)
        if kind == 'enum':
            members = list(type(current))
            low = members.index(self.minimum) if self.minimum is not None else 0
            high = members.index(self.maximum) if self.maximum is not None else len(members) - 1
            return members[round(low + (high - low) * raw)]
        low = self.minimum if self.minimum is not None else 0
        high = self.maximum if self.maximum is not None else (127 if kind == 'int' else 1)
        value = low + (high - low) * raw
        if kind == 'int':
            return int(round(value))
        if kind == 'str':
            # Whole numbers for a whole number range, else two decimals
            return str(int(round(value))) if isinstance(low, int) and isinstance(high, int) and (low, high) != (0, 1) else f'{value:.2f}'
        return value

def _hex_color(text: str):
    digits = text[1:] if text.startswith('#') else ''
    if len(digits) not in (6, 8):
        raise ValueError(f'expected a color ("#rrggbb"), got {text!r}')
    values = [int(digits[i:i + 2], 16) for i in range(0, len(digits), 2)]
    return pyxelwidgets.color.Color(values[0], values[1], values[2], values[3] / 255 if len(values) == 4 else 1.0)

def convert(kind: str, value, current = None):
    """An expression's result as an option of ``kind`` holds it (``current``: the option's value, for choices)."""
    if kind == 'bool':
        return bool(value)
    if kind == 'int':
        if isinstance(value, str) or value is None:
            raise ValueError(f'a whole number is needed, got {value!r}')
        return int(round(value))
    if kind == 'float':
        if isinstance(value, str) or value is None:
            raise ValueError(f'a number is needed, got {value!r}')
        return float(value)
    if kind == 'str':
        return value if isinstance(value, str) else pyxelwidgets.expression._text(value)
    if kind == 'enum':
        members = list(type(current))
        if isinstance(value, enum.Enum):
            return value
        if isinstance(value, str):
            for member in members:
                if member.name == value:
                    return member
            raise ValueError(f'unknown choice {value!r} (choices: {", ".join(member.name for member in members)})')
        return members[min(max(int(value), 0), len(members) - 1)]
    if kind == 'color':
        if isinstance(value, pyxelwidgets.color.Color):
            return value
        if isinstance(value, str):
            return _hex_color(value)
        raise ValueError(f'a color is needed, got {value!r}')
    return value

class Formula:
    """
    Keeps ``option`` of ``target`` at what ``expression`` (an Expression, or
    a Template for text) computes: ``refresh()`` changes it (through
    ``configure``) when the result differs. ``error`` says why the last
    refresh couldn't (and the option stays as it was), else None.
    """

    def __init__(self, target, option: str, expression) -> None:
        if option.startswith('_') or not hasattr(target, option):
            raise ValueError(f'{type(target).__name__} has no option {option!r}')
        if expression.free:
            raise ValueError(f'{expression}: unknown name {expression.free[0]!r} (names: {", ".join(expression.names)})')
        self.target = target
        self.option = option
        self.expression = expression
        self.error = None
        self._kind = _kind(getattr(target, option))

    def refresh(self) -> bool:
        """Compute the option again; True if it changed."""
        current = getattr(self.target, self.option)
        try:
            value = convert(self._kind, self.expression.evaluate(), current)
            if value != current:
                self.target.configure(**{self.option: value})
        except (ValueError, TypeError) as error:
            # ExpressionError included; also a value the option refuses
            self.error = str(error)
            return False
        self.error = None
        return value != current
