import pyxelwidgets.animation
import pyxelwidgets.buffer
import pyxelwidgets.events
import pyxelwidgets.font
import pyxelwidgets.color
import pyxelwidgets.rate
import pyxelwidgets.rectangle
import numpy
import enum
import math
import random
import time
import typing

# A note value such as '1/16', '1/8.' or 'bar': how often a Transport plays a widget
# (see pyxelwidgets.transport). Widgets only store it.
Rate = pyxelwidgets.rate.Rate

# Sprite frames: a list of RGBA buffers, or of 2-d arrays/lists of Colors
Frames = typing.NewType('Frames', list)

def _copy_overlap(target: numpy.ndarray, source) -> None:
    """Copy the part of ``source`` that fits into ``target`` (e.g. after a resize)."""
    source = numpy.asarray(source)
    if source.ndim != target.ndim:
        return
    area = tuple(slice(0, min(a, b)) for a, b in zip(target.shape, source.shape))
    target[area] = source[area]

def state_to_json(state):
    """
    A ``save_state()`` result as JSON data: numpy arrays become
    ``{"$array": rows, "dtype": ...}``, tuples ``{"$tuple": [...]}`` and dicts
    with keys other than text ``{"$items": [[key, value], ...]}``.
    ``state_from_json`` turns it back.
    """
    if isinstance(state, numpy.ndarray):
        return {'$array': state.tolist(), 'dtype': str(state.dtype)}
    if isinstance(state, numpy.generic):
        return state.item()
    if isinstance(state, tuple):
        return {'$tuple': [state_to_json(item) for item in state]}
    if isinstance(state, list):
        return [state_to_json(item) for item in state]
    if isinstance(state, dict):
        if all(isinstance(key, str) for key in state):
            return {key: state_to_json(value) for key, value in state.items()}
        return {'$items': [[state_to_json(key), state_to_json(value)] for key, value in state.items()]}
    return state

def state_from_json(data):
    """A widget state from ``state_to_json`` data (anything else is returned as it is)."""
    if isinstance(data, list):
        return [state_from_json(item) for item in data]
    if not isinstance(data, dict):
        return data
    if set(data) == {'$array', 'dtype'}:
        return numpy.array(data['$array'], dtype = data['dtype'])
    if set(data) == {'$tuple'}:
        return tuple(state_from_json(item) for item in data['$tuple'])
    if set(data) == {'$items'}:
        return {_hashable(state_from_json(key)): state_from_json(value) for key, value in data['$items']}
    return {key: state_from_json(value) for key, value in data.items()}

def _hashable(key):
    return tuple(_hashable(item) for item in key) if isinstance(key, list) else key

def _level(values: dict) -> float | None:
    """The 0.0-1.0 state a received message carries, if any."""
    for key in ('value', 'state', 'velocity', 'pressure', 'active'):
        value = values.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None

class Propagation(enum.Enum):
    """
    What happens to a press after a widget handles it, when widgets overlap.

    Stop: widgets underneath don't receive it (default).
    Pass: it continues to the widget underneath (default for display-only widgets).
    """
    Stop = enum.auto()
    Pass = enum.auto()

class Widget(pyxelwidgets.events.Emitter):
    """
    Base class for all widgets: a rectangle of pads with its own frame buffer.

    A widget works on its own: feed it input with ``press``/``release``/...,
    call ``render()`` and read ``buffer``. Subscribe to its events with ``on``.
    Subclasses override ``draw`` and the ``handle_*`` input hooks.
    """
    # Per class counters for default names (Button_0, Fader_0, ...)
    _counts = {}

    #: Events the widget emits besides its base classes' (e.g. for editors offering them)
    emits: tuple = (pyxelwidgets.events.Pressed, pyxelwidgets.events.Released, pyxelwidgets.events.Held, pyxelwidgets.events.DoublePressed, pyxelwidgets.events.Pressure)

    @classmethod
    def events(cls) -> list:
        """Every event class the widget emits, its base classes' included."""
        found = []
        for klass in reversed(cls.__mro__):
            for event in klass.__dict__.get('emits', ()):
                if event not in found:
                    found.append(event)
        return found

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 name: str | None = None,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.White,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Black,
                 visible: bool = True,
                 propagation: Propagation = Propagation.Stop):
        """
        Parameters
        ----------
        x, y: int
            Position in the parent Group, from left to right and bottom to top.
        width, height: int
            Size in pads, should be >= 1.
        name: str, optional
            Label used to find the widget in a Group. Defaults to ``<ClassName>_<n>``.
        active_color: Color = Colors.White, optional
            Color of active pads.
        inactive_color: Color = Colors.Black, optional
            Color of inactive pads.
        visible: bool = True, optional
            Hidden widgets are neither drawn nor receive input in a Group.
        propagation: Propagation = Propagation.Stop, optional
            Whether a press continues to overlapped widgets underneath.
        """
        self.name = name if name is not None else self._default_name()
        self.rect = pyxelwidgets.rectangle.Rectangle2D(x, y, width, height)
        self.active_color = active_color
        self.inactive_color = inactive_color
        self.propagation = propagation
        self._visible = visible
        self.updated = True
        self.buffer = pyxelwidgets.buffer.new(self.rect.w, self.rect.h, self.inactive_color)
        self._animation = None
        self.cell_animations = {}
        # The drawing before animations, while animated
        self._static = None
        # The Blink a received blinking state started
        self._flash = None
        #: Options changed with ``configure`` since construction, by name
        self.configured = {}
        self._resize(self.rect.w, self.rect.h)

    def _default_name(self) -> str:
        cls = type(self).__name__
        count = Widget._counts.get(cls, 0)
        Widget._counts[cls] = count + 1
        return f'{cls}_{count}'

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if value != self._visible:
            self._visible = value
            # Lets a parent Group notice the change and recompose
            self.updated = True

    @property
    def x(self) -> int:
        return self.rect.x

    @x.setter
    def x(self, value: int) -> None:
        if value != self.rect.x:
            self.rect.x = int(value)
            self.updated = True

    @property
    def y(self) -> int:
        return self.rect.y

    @y.setter
    def y(self, value: int) -> None:
        if value != self.rect.y:
            self.rect.y = int(value)
            self.updated = True

    @property
    def width(self) -> int:
        return self.rect.w
    
    @width.setter
    def width(self, value: int) -> None:
        if value > 0:
            self._set_size(value, self.rect.h)

    @property
    def height(self) -> int:
        return self.rect.h
    
    @height.setter
    def height(self, value: int) -> None:
        if value > 0:
            self._set_size(self.rect.w, value)

    def _set_size(self, width: int, height: int) -> None:
        # _resize implementations read self.rect, so update it first
        old = self.rect.w, self.rect.h
        self.rect.w, self.rect.h = width, height
        if not self._resize(width, height):
            self.rect.w, self.rect.h = old
            return
        self.buffer = pyxelwidgets.buffer.new(self.rect.w, self.rect.h, self.inactive_color)
        self.updated = True
        self.emit(pyxelwidgets.events.Resized(self, self.rect.w, self.rect.h))

    # Options

    #: Options whose change recalculates the widget's layout (``_resize``)
    reshaping: tuple = ()

    #: Methods links can call, by name: None for no argument, or the argument's kind ('int')
    actions: dict = {}

    def configure(self, **options) -> None:
        """
        Change options after construction, given as the constructor takes them
        (``fader.configure(active_color = Colors.Red, visible = False)``), plus
        ``x``, ``y``, ``width`` and ``height``; the widget redraws. Changes are
        kept in ``configured``. Raises AttributeError for unknown options.
        """
        for name in options:
            if name.startswith('_') or not hasattr(self, name) or callable(getattr(self, name)):
                raise AttributeError(f'{type(self).__name__} has no option {name!r}')
        reshape = False
        for name, value in options.items():
            self._configure(name, value)
            self.configured[name] = value
            reshape = reshape or name in self.reshaping
        if reshape:
            self._resize(self.rect.w, self.rect.h)
        self.updated = True

    def _configure(self, name: str, value) -> None:
        """Set one option; override for options stored differently."""
        setattr(self, name, value)

    # Input: public methods emit the event, then call the matching handle_* hook

    def press(self, x: int, y: int, velocity: float = 1.0) -> None:
        """Press the pad at widget coordinates ``x``, ``y``."""
        self.emit(pyxelwidgets.events.Pressed(self, x, y, velocity))
        self.handle_press(x, y, velocity)

    def release(self, x: int, y: int, velocity: float = 0.0) -> None:
        self.emit(pyxelwidgets.events.Released(self, x, y, velocity))
        self.handle_release(x, y, velocity)

    def hold(self, x: int, y: int, velocity: float = 1.0) -> None:
        self.emit(pyxelwidgets.events.Held(self, x, y, velocity))
        self.handle_hold(x, y, velocity)

    def double_press(self, x: int, y: int, velocity: float = 1.0) -> None:
        self.emit(pyxelwidgets.events.DoublePressed(self, x, y, velocity))
        self.handle_double_press(x, y, velocity)

    def pressure(self, x: int, y: int, pressure: float) -> None:
        """The pressure (aftertouch) of the held pad at ``x``, ``y`` changed."""
        self.emit(pyxelwidgets.events.Pressure(self, x, y, pressure))
        self.handle_pressure(x, y, pressure)

    def tap(self, x: int, y: int, velocity: float = 1.0) -> None:
        """Press and release the pad at ``x``, ``y``."""
        self.press(x, y, velocity)
        self.release(x, y, 0.0)

    def input(self, event: pyxelwidgets.events.PadEvent) -> bool:
        """
        Deliver a device pad event whose ``x``, ``y`` are already widget coordinates.
        Returns True if it should not reach widgets underneath.
        """
        x, y, velocity = event.x, event.y, event.velocity
        if isinstance(event, pyxelwidgets.events.PadPressed):
            self.press(x, y, velocity)
        elif isinstance(event, pyxelwidgets.events.PadReleased):
            self.release(x, y, velocity)
        elif isinstance(event, pyxelwidgets.events.PadHeld):
            self.hold(x, y, velocity)
        elif isinstance(event, pyxelwidgets.events.PadPressure):
            self.pressure(x, y, velocity)
        elif isinstance(event, pyxelwidgets.events.PadDoublePressed):
            self.double_press(x, y, velocity)
        return self.propagation == Propagation.Stop

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        """Override to react to a press; ``velocity`` is 1.0 on pads without velocity."""

    def handle_release(self, x: int, y: int, velocity: float) -> None:
        """Override to react to a release."""

    def handle_hold(self, x: int, y: int, velocity: float) -> None:
        """Override to react to a pad held longer than the controller's ``held_time``."""

    def handle_double_press(self, x: int, y: int, velocity: float) -> None:
        """Override to react to a double press."""

    def handle_pressure(self, x: int, y: int, pressure: float) -> None:
        """Override to react to pad pressure (aftertouch) on pads that report it."""

    # Drawing

    def render(self, time: pyxelwidgets.animation.Time | None = None) -> bool:
        """
        Redraw ``buffer`` if needed, and apply animations at ``time`` (default:
        now, at 120 bpm); returns True if it changed.
        """
        if self._static is not None:
            # Draw on the drawing, not on the animated copy
            self.buffer = self._static
        drawn = self.updated
        if drawn:
            self.updated = False
            self.draw()
        if self._animation is None and not self.cell_animations:
            self._static = None
            return drawn
        self._static = self.buffer
        self.buffer = self._animate(time if time is not None else pyxelwidgets.animation.now())
        return True

    # State

    def save_state(self) -> dict:
        """
        What input changed in the widget (its value, pressed cells, steps...),
        to restore on another instance with ``load_state``, e.g. after rebuilding
        a layout. Options aren't included.
        """
        return {}

    def load_state(self, state: dict) -> None:
        """Restore ``save_state`` data without emitting events; parts that don't fit are skipped."""

    # Feedback

    #: How fast a received blinking state (e.g. a Mackie LED) blinks, in seconds
    flash_rate = 0.5

    def receive(self, values: dict) -> None:
        """
        Show state sent from elsewhere (e.g. a DAW, through a Mapping) without
        emitting events. ``values`` are what the message carried: ``value``,
        ``state``, ``velocity``, ``x``/``y``/``cell``, ``text``, ``flash``...
        Subclasses override it; a blinking state (``flash``) blinks the widget.
        """
        flash = bool(values.get('flash')) and bool(_level(values))
        blink = self._flash
        if flash and (blink is None or self._animation is not blink):
            self._flash = self.animation = pyxelwidgets.animation.Blink(self.flash_rate)
        elif not flash and blink is not None:
            if self._animation is blink:
                self.animation = None
            self._flash = None

    # Animations

    @property
    def animation(self):
        """An Animation of the whole widget (e.g. ``Blink('1/8')``), or None."""
        return self._animation

    @animation.setter
    def animation(self, value) -> None:
        self._animation = value
        self.updated = True

    def animate_cell(self, x: int, y: int, animation) -> None:
        """Animate the cell at widget ``x``, ``y``; None stops animating it."""
        if animation is None:
            self.cell_animations.pop((x, y), None)
        else:
            self.cell_animations[(x, y)] = animation
        self.updated = True

    def _animate(self, time: pyxelwidgets.animation.Time) -> numpy.ndarray:
        frame = self._static.copy()
        for (x, y), animation in list(self.cell_animations.items()):
            if 0 <= x < self.rect.w and 0 <= y < self.rect.h:
                frame[x:x + 1, y:y + 1] = animation.apply(frame[x:x + 1, y:y + 1], time)
            if animation.finished(time):
                del self.cell_animations[(x, y)]
        animation = self._animation
        if animation is not None:
            frame = animation.apply(frame, time)
            if animation.finished(time):
                self._animation = None
                # A fade out ends hidden
                if getattr(animation, 'out', False):
                    self.visible = False
        return frame

    def draw(self) -> None:
        """Override to draw the whole widget into ``self.buffer``. Set ``self.updated`` to keep animating."""

    def _resize(self, width, height) -> bool:
        return True

class ValueWidget(Widget):
    """
    A widget with a single value set by input: a float from 0.0 to 1.0 by default.
    Input emits ``Changed``; setting ``value`` from code doesn't.
    """

    emits = (pyxelwidgets.events.Changed,)

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 value = 0.0,
                 interactive: bool = True,
                 **kwargs):
        """
        value: optional
            Initial value.
        interactive: bool = True, optional
            If False, input doesn't change the value (``Changed`` is still emitted),
            e.g. for widgets that only mirror state sent back from a DAW.
        """
        self._value = self._clamp(value)
        self.delta = 0.0
        self.interactive = interactive
        super().__init__(x, y, width, height, **kwargs)

    def _clamp(self, value):
        return round(min(1.0, max(0.0, value)), 6)

    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, value) -> None:
        value = self._clamp(value)
        if value != self._value:
            self.delta = self._delta(self._value, value)
            self._value = value
            self.updated = True

    def _delta(self, old, new):
        return new - old
    
    def save_state(self) -> dict:
        return {'value': self._value}

    def load_state(self, state: dict) -> None:
        if 'value' in state:
            value = state['value']
            # A one-axis value doesn't fit a two-axis widget and the other way round
            if isinstance(value, tuple) == isinstance(self._value, tuple):
                self.value = value

    def receive(self, values: dict) -> None:
        """Take ``value`` (or ``value_x``/``value_y``, or another 0.0-1.0 state) without emitting ``Changed``."""
        super().receive(values)
        if isinstance(self._value, tuple):
            current = list(self._value)
            for axis, key in enumerate(('value_x', 'value_y')):
                if isinstance(values.get(key), (int, float)):
                    current[axis] = values[key]
            self.value = tuple(current)
            return
        level = _level(values)
        if level is not None:
            self.value = level

    def set_value(self, value) -> None:
        """Set the value as input would: respects ``interactive`` and emits ``Changed``."""
        value = self._clamp(value)
        if self.interactive:
            self.value = value
        self.emit(pyxelwidgets.events.Changed(self, value))

class Scale(enum.Enum):
    """A musical scale, for widgets laying out or choosing notes (Keyboard, PianoRoll, ChordPads...)."""
    Major           = 0
    Minor           = 1
    Dorian          = 2
    Mixolydian      = 3
    Lydian          = 4
    Phrygian        = 5
    Locrian         = 6
    Diminished      = 7
    WholeHalf       = 8
    WholeTone       = 9
    MinorBlues      = 10
    MinorPentatonic = 11
    MajorPentatonic = 12
    MinorHarmonic   = 13
    MinorMelodic    = 14
    Chromatic       = 15
    MajorBlues      = 16
    MajorHarmonic   = 17
    PhrygianDominant = 18
    HungarianMinor  = 19
    DoubleHarmonic  = 20
    BebopDominant   = 21
    Hirajoshi       = 22
    InSen           = 23
    Iwato           = 24
    Augmented       = 25

#: Semitones from the root of each Scale, by name
SCALES = {
    'Major': [0, 2, 4, 5, 7, 9, 11],
    'Minor': [0, 2, 3, 5, 7, 8, 10],
    'Dorian': [0, 2, 3, 5, 7, 9, 10],
    'Mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'Lydian': [0, 2, 4, 6, 7, 9, 11],
    'Phrygian': [0, 1, 3, 5, 7, 8, 10],
    'Locrian': [0, 1, 3, 5, 6, 8, 10],
    'Diminished': [0, 1, 3, 4, 6, 7, 9, 10],
    'WholeHalf': [0, 2, 3, 5, 6, 8, 9, 11],
    'WholeTone': [0, 2, 4, 6, 8, 10],
    'MinorBlues': [0, 3, 5, 6, 7, 10],
    'MinorPentatonic': [0, 3, 5, 7, 10],
    'MajorPentatonic': [0, 2, 4, 7, 9],
    'MinorHarmonic': [0, 2, 3, 5, 7, 8, 11],
    'MinorMelodic': [0, 2, 3, 5, 7, 9, 11],
    'Chromatic': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    'MajorBlues': [0, 2, 3, 4, 7, 9],
    'MajorHarmonic': [0, 2, 4, 5, 7, 8, 11],
    'PhrygianDominant': [0, 1, 4, 5, 7, 8, 10],
    'HungarianMinor': [0, 2, 3, 6, 7, 8, 11],
    'DoubleHarmonic': [0, 1, 4, 5, 7, 8, 11],
    'BebopDominant': [0, 2, 4, 5, 7, 9, 10, 11],
    'Hirajoshi': [0, 2, 3, 7, 8],
    'InSen': [0, 1, 5, 7, 10],
    'Iwato': [0, 1, 5, 6, 10],
    'Augmented': [0, 3, 4, 7, 8, 11],
}

class Root(enum.Enum):
    """The root note of a scale (CS is C sharp)."""
    C   = 0
    CS  = 1
    D   = 2
    DS  = 3
    E   = 4
    F   = 5
    FS  = 6
    G   = 7
    GS  = 8
    A   = 9
    AS  = 10
    B   = 11

def scale_notes(scale: Scale, root: Root) -> list:
    """Every MIDI note (0-127) in ``scale`` from ``root``, lowest first."""
    steps = set(SCALES[scale.name])
    return [note for note in range(128) if (note - root.value) % 12 in steps]

class VelocityCurve(enum.Enum):
    """
    How hard a pad is hit becomes a note's velocity.

    Linear: as hit. Soft: louder soft hits (for a light touch). Hard: softer
    unless hit hard. Fixed: always the widget's ``fixed_velocity``.
    """
    Linear  = enum.auto()
    Soft    = enum.auto()
    Hard    = enum.auto()
    Fixed   = enum.auto()

class Velocity:
    """
    Mixin for widgets playing notes (Keyboard, DrumPads, Sequencer...): how
    the velocity of the notes they play comes from the pads. ``velocity_of``
    applies the curve to a hit, ``humanize`` the randomness to a played note.
    """

    def __init__(self, *args,
                 velocity_curve: VelocityCurve = VelocityCurve.Linear,
                 fixed_velocity: float = 1.0,
                 velocity_random: float = 0.0,
                 **kwargs):
        """
        velocity_curve: VelocityCurve = VelocityCurve.Linear, optional
            How hard hits turn into velocities; Fixed plays every note at ``fixed_velocity``.
        fixed_velocity: float = 1.0, optional
            The velocity of every note with the Fixed curve, from 0 to 1.
        velocity_random: float = 0.0, optional
            Each note played is louder or softer by up to this much, at random (0 to 1).
        """
        if not 0.0 < fixed_velocity <= 1.0:
            raise ValueError(f'fixed_velocity must be more than 0 and at most 1, got {fixed_velocity!r}')
        if not 0.0 <= velocity_random <= 1.0:
            raise ValueError(f'velocity_random must be from 0 to 1, got {velocity_random!r}')
        self.velocity_curve = velocity_curve
        self.fixed_velocity = fixed_velocity
        self.velocity_random = velocity_random
        if not hasattr(self, '_random'):
            # Tests seed it
            self._random = random.Random()
        super().__init__(*args, **kwargs)

    def velocity_of(self, velocity: float) -> float:
        """The velocity a hit this hard gives, through ``velocity_curve``."""
        velocity = min(max(float(velocity), 0.0), 1.0)
        curve = self.velocity_curve
        if curve == VelocityCurve.Fixed:
            return float(self.fixed_velocity)
        if curve == VelocityCurve.Soft:
            return round(velocity ** 0.5, 6)
        if curve == VelocityCurve.Hard:
            return round(velocity ** 2, 6)
        return velocity

    def humanize(self, velocity: float) -> float:
        """``velocity`` changed by up to ``velocity_random`` at random, kept above 0 (a note on stays one) and at most 1."""
        spread = min(max(float(self.velocity_random), 0.0), 1.0)
        if spread:
            velocity += self._random.uniform(-spread, spread)
        return round(min(max(velocity, 1 / 127), 1.0), 6)

# Button class
class Button(ValueWidget):
    """A pad area acting as one button: momentary (Button), toggle (Switch) or toggle on hold (Mixed)."""
    class Mode(enum.Enum):
        Button  = enum.auto()
        Switch  = enum.auto()
        Mixed   = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 mode: Mode = Mode.Button,
                 **kwargs):
        """
        mode: Mode = Mode.Button, optional
            Button: on while pressed. Switch: each press turns it on or off.
            Mixed: on while pressed, but holding it keeps it on until the next hold.
            The value is the press's velocity while on.
        """
        super().__init__(x, y, width, height, **kwargs)
        self.mode = mode
        self.state = False
        self.is_hold = False

    def handle_press(self, x: int, y: int, velocity: float):
        if self.mode == Button.Mode.Button:
            self.set_value(velocity)
        elif self.mode == Button.Mode.Switch:
            if self.state:
                self.set_value(0.0)
                self.state = False
            else:
                self.set_value(velocity)
                self.state = True
        elif self.mode == Button.Mode.Mixed:
            if not self.is_hold:
                self.set_value(velocity)

    def handle_release(self, x: int, y: int, velocity: float):
        if self.mode == Button.Mode.Button:
            self.set_value(0.0)
        elif self.mode == Button.Mode.Mixed and not self.is_hold:
            self.set_value(0.0)

    def handle_hold(self, x: int, y: int, velocity: float):
        if self.mode == Button.Mode.Mixed:
            self.is_hold = not self.is_hold

    def receive(self, values: dict) -> None:
        super().receive(values)
        # A switch turned on or off elsewhere toggles from there
        self.state = self._value > 0

    def _configure(self, name: str, value) -> None:
        super()._configure(name, value)
        if name == 'value':
            self.state = self._value > 0

    def save_state(self) -> dict:
        return {**super().save_state(), 'switch': self.state, 'hold': self.is_hold}

    def load_state(self, state: dict) -> None:
        super().load_state(state)
        self.state = bool(state.get('switch', self.state))
        self.is_hold = bool(state.get('hold', self.is_hold))

    def draw(self) -> None:
        area = self.rect.origin
        self.buffer[area.slice] = self.active_color * self._value if self._value else self.inactive_color

# ButtonGroup class
class ButtonGroup(Widget):
    """A grid of buttons: one selected at a time (Switch), toggles (Multi) or momentary (Button); emits Toggled."""

    emits = (pyxelwidgets.events.Toggled,)

    class Mode(enum.Enum):
        Button = enum.auto()
        Switch = enum.auto()
        Multi = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 mode: Mode = Mode.Switch,
                 allow_none: bool = False,
                 selected: int | None = None,
                 **kwargs):
        """
        mode: Mode = Mode.Switch, optional
            Switch: one cell on at a time (the bottom-left one at first).
            Multi: each press turns a cell on or off. Button: cells are on while pressed.
        allow_none: bool = False, optional
            Switch: pressing the cell that's on turns it off, and none is on at first.
        selected: int, optional
            Switch: the cell on (0 is the bottom-left, then left to right and up);
            setting it (``configure``, links) moves there without emitting Toggled.
            Defaults to the first cell, or none with ``allow_none``.
        """
        self.state = numpy.zeros((1, 1), dtype = numpy.bool_)
        # The Switch's cell that's on
        self._selected = None
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        self.mode = mode
        self.allow_none = allow_none
        self.state.fill(False)
        if self.mode == ButtonGroup.Mode.Switch:
            self._select(selected if selected is not None else (None if allow_none else 0))

    @property
    def selected(self) -> int | None:
        """The Switch's cell that's on (0 is the bottom-left), or None."""
        return None if self._selected is None else self._selected[0] + self._selected[1] * self.rect.w

    def _select(self, cell: int | None) -> None:
        if self._selected is not None:
            self.state[self._selected] = False
        self._selected = None
        if cell is not None and 0 <= int(cell) < self.rect.area:
            self._selected = (int(cell) % self.rect.w, int(cell) // self.rect.w)
            self.state[self._selected] = True
        self.updated = True

    def _configure(self, name: str, value) -> None:
        if name == 'selected':
            self._select(value)
        else:
            super()._configure(name, value)

    def handle_press(self, x: int, y: int, velocity: float):
        before = self.state.copy()
        if self.mode == ButtonGroup.Mode.Button:
            self.state[x, y] = True
        elif self.mode == ButtonGroup.Mode.Switch:
            if self._selected == (x, y) and self.allow_none:
                self.state[x, y] = False
                self._selected = None
            else:
                if self._selected is not None:
                    self.state[self._selected] = False
                self._selected = (x, y)
                self.state[x, y] = True
        elif self.mode == ButtonGroup.Mode.Multi:
            self.state[x, y] = not self.state[x, y]
        self._emit_toggled(before)

    def handle_release(self, x: int, y: int, velocity: float):
        if self.mode == ButtonGroup.Mode.Button:
            before = self.state.copy()
            self.state[x, y] = False
            self._emit_toggled(before)

    def save_state(self) -> dict:
        return {'cells': self.state.copy()}

    def load_state(self, state: dict) -> None:
        if 'cells' not in state:
            return
        _copy_overlap(self.state, state['cells'])
        on = numpy.argwhere(self.state)
        if self.mode == ButtonGroup.Mode.Switch and len(on):
            # One cell at most
            self.state.fill(False)
            self.state[tuple(on[0])] = True
            self._selected = (int(on[0][0]), int(on[0][1]))
        self.updated = True

    def receive(self, values: dict) -> None:
        """Turn the cell at ``x``, ``y`` (or ``cell``) on or off without emitting Toggled."""
        super().receive(values)
        level = _level(values)
        if 'cell' in values:
            x, y = values['cell'] % self.rect.w, values['cell'] // self.rect.w
        else:
            x, y = values.get('x', 0), values.get('y', 0)
        if level is None or not (0 <= x < self.rect.w and 0 <= y < self.rect.h):
            return
        on = level > 0
        if self.mode == ButtonGroup.Mode.Switch and on:
            self.state.fill(False)
            self._selected = (x, y)
        elif self.mode == ButtonGroup.Mode.Switch and self._selected == (x, y):
            self._selected = None
        self.state[x, y] = on
        self.updated = True

    def _emit_toggled(self, before) -> None:
        # Cells turned off first, so the last event is the one turned on (a Switch's new choice)
        changed = sorted((tuple(cell) for cell in numpy.argwhere(before != self.state)), key = lambda cell: bool(self.state[cell]))
        for x, y in changed:
            self.updated = True
            self.emit(pyxelwidgets.events.Toggled(self, int(x), int(y), bool(self.state[x, y])))

    def draw(self) -> None:
        area = self.rect.origin
        self.buffer[area.slice] = numpy.where(self.state[(*area.slice, None)], self.active_color, self.inactive_color)

    def _resize(self, width, height):
        self.state = _fit(self.state, (width, height), False)
        if self._selected is not None and not (self._selected[0] < width and self._selected[1] < height):
            self._selected = None
        return True

# Fader class
class Fader(ValueWidget):
    """A fader along a row or column (or across the whole area with Matrix grid), drawn in several styles."""

    class Direction(enum.Enum):
        """Vertical faders go from the bottom to the top, horizontal ones from left to right."""
        Vertical    = enum.auto()
        Horizontal  = enum.auto()

    class Grid(enum.Enum):
        """
        How a fader thicker than one pad works. Simple: the extra pads repeat
        (one value per row or column). Matrix: every pad is a part of the
        range, row after row (or column after column).
        """
        Simple      = enum.auto()
        Matrix      = enum.auto()

    class Type(enum.Enum):
        """
        How the value is lit. Single: only the value's pad. BoostCut: from the
        middle up or down. Wrap: from the start up to the value. Spread: from
        the middle out both ways. Collapse: from both ends in.
        """
        Single      = enum.auto()
        BoostCut    = enum.auto()
        Wrap        = enum.auto()
        Spread      = enum.auto()
        Collapse    = enum.auto()

    class Mode(enum.Enum):
        """
        What a press sets. Simple: the start of the pad's part of the range.
        Multi: pressing the same pad again steps through its part
        (``resolution`` steps). Magnitude: spread so the last pad is the top.
        Sensitive: within the pad's part, by velocity. Relative: hold a pad
        and press another to set a value within the held pad's part.
        """
        Simple      = enum.auto()
        Multi       = enum.auto()
        Magnitude   = enum.auto()
        Sensitive   = enum.auto()
        Relative    = enum.auto()

    reshaping = ('direction', 'grid')

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 direction: Direction = Direction.Vertical,
                 grid: Grid = Grid.Simple,
                 type: Type = Type.Wrap,
                 mode: Mode = Mode.Multi,
                 resolution: int = 4,
                 slew: float = 0.0,
                 clock: typing.Callable[[], float] = time.monotonic,
                 **kwargs):
        """
        direction: Direction = Direction.Vertical, optional
            Bottom to top, or left to right.
        grid: Grid = Grid.Simple, optional
            How the pads across the direction work: repeating, or as more of the range.
        type: Type = Type.Wrap, optional
            How the value is lit.
        mode: Mode = Mode.Multi, optional
            What a press sets.
        resolution: int = 4, optional
            Multi mode: the steps within each pad.
        slew: float = 0.0, optional
            Seconds it takes to glide over the whole range to a pressed value
            (emitting Changed on the way); 0 jumps there.

        Holding the first pad sets 0, the last 1, any other 0.5 (not in Relative mode).
        """
        self.direction = direction
        self.grid = grid
        self.type = type
        self.mode = mode
        self.resolution = resolution
        self.slew = slew
        self.clock = clock
        # Where a slew is going, and when it last moved
        self._target = None
        self._last = None
        super().__init__(x, y, width, height, **kwargs)
        self._multi_step = 0
        self._old_button = None
        self._held_button = None

    def _go(self, value: float) -> None:
        """Set ``value`` as input: at once, or gliding there with ``slew``."""
        if self.slew > 0 and self.interactive:
            self._target = self._clamp(value)
            self._last = self.clock()
            self.updated = True
        else:
            self._target = None
            self.set_value(value)

    def render(self, time = None) -> bool:
        if self._target is not None:
            now = self.clock()
            elapsed, self._last = now - self._last, now
            distance = self._target - self._value
            move = elapsed / self.slew if self.slew > 0 else abs(distance)
            if abs(distance) <= move:
                value, self._target = self._target, None
            else:
                value = self._value + math.copysign(move, distance)
            if value != self._value:
                self.set_value(value)
        return super().render(time)

    def handle_press(self, x: int, y: int, velocity: float):
        if self.mode == Fader.Mode.Simple:
            self._go(self._pressed_simple(x, y, velocity))
        elif self.mode == Fader.Mode.Multi:
            self._go(self._pressed_multi(x, y, velocity))
        elif self.mode == Fader.Mode.Magnitude:
            self._go(self._pressed_magnitude(x, y, velocity))
        elif self.mode == Fader.Mode.Sensitive:
            self._go(self._pressed_sensitive(x, y, velocity))
        elif self.mode == Fader.Mode.Relative:
            self._go(self._pressed_relative(x, y, velocity))
        self.updated = True

    def _pressed_simple(self, x, y, value):
        if self.type == Fader.Type.BoostCut:
            if self._min_v[x][y] < 0.5:
                return self._min_v[x][y]
            else:
                return self._max_v[x][y]
        else:
            return self._min_v[x][y]

    def _pressed_multi(self, x, y, value):
        again = self._old_button == (x, y)
        self._old_button = (x, y)
        if self.type == Fader.Type.BoostCut and self._min_v[x][y] >= 0.5 or self.type not in (Fader.Type.BoostCut, Fader.Type.Collapse):
            # Upwards: from the pad's start
            self._multi_step = (self._multi_step + 1) % self.resolution if again else 0
        else:
            # Downwards (cuts, collapsing): from the pad's end
            self._multi_step = (self._multi_step - 1) % self.resolution if again else self.resolution - 1
        return self._calc_fader_value(x, y, self._multi_step / self.resolution)

    def _pressed_magnitude(self, x, y, value):
        return self._calc_fader_value(x, y, self._calc_fader_magnitude(x, y))

    def _pressed_sensitive(self, x, y, value):
        if self.type == Fader.Type.BoostCut:
            if self._min_v[x][y] < 0.5:
                return self._calc_fader_value(x, y, 1.0 - value)
            else:
                return self._calc_fader_value(x, y, value)
        elif self.type == Fader.Type.Collapse:
            return self._calc_fader_value(x, y, 1.0 - value)
        else:
            return self._calc_fader_value(x, y, value)

    def _pressed_relative(self, x, y, value):
        if self._held_button is not None:
            return self._calc_fader_value(*self._held_button, self._calc_fader_magnitude(x, y))
        self._held_button = (x, y)
        return self._calc_fader_value(x, y, self._calc_fader_magnitude(x, y))

    def handle_hold(self, x: int, y: int, velocity: float):
        if self.mode != Fader.Mode.Relative:
            if x == 0 and y == 0:
                self._go(0.0)
            elif x == self.rect.w - 1 and y == self.rect.h - 1:
                self._go(1.0)
            else:
                self._go(0.5)
        self.updated = True

    def handle_release(self, x: int, y: int, velocity: float):
        if self._held_button == (x, y):
            self._held_button = None

    def draw(self) -> None:
        halfval = self._value / 2.0
        halfvalpluspointfive = halfval + 0.5
        area = self.rect.origin
        for x in area.columns:
            for y in area.rows:
                min_v = self._min_v[x][y]
                max_v = self._max_v[x][y]
                if self.type == Fader.Type.Single:
                    # if current pad lower than last pressed pad
                    if max_v <= self._value:
                        self.buffer[x, y] = self.inactive_color
                    # if current pad higher than last pressed pad
                    elif min_v > self._value:
                        self.buffer[x, y] = self.inactive_color
                    # if current pad is last pressed pad
                    else:
                        coefficient = min(self._calc_pixel_coefficient(self._value - min_v) + self._calc_pixel_step(), 1.0)
                        self.buffer[x, y] = self.active_color * coefficient
                elif self.type == Fader.Type.BoostCut:
                    # if last pressed pad in upper half
                    if self._value > 0.5:
                        # if current pad in lower half
                        if min_v < 0.5:
                            self.buffer[x, y] = self.inactive_color
                        # if current pad in upper half
                        else:
                            # if current pad is lower than last pressed pad
                            if max_v <= self._value:
                                self.buffer[x, y] = self.active_color
                            # if current pad is higher than last pressed pad
                            elif min_v > self._value:
                                self.buffer[x, y] = self.inactive_color
                            # if current pad is last pressed pad
                            else:
                                coefficient = min(self._calc_pixel_coefficient(self._value - min_v) + self._calc_pixel_step(), 1.0)
                                self.buffer[x, y] = self.active_color * coefficient
                    # if last pressed pad in lower half
                    elif self._value < 0.5:
                        # if current pad in upper half
                        if max_v > 0.5:
                            self.buffer[x, y] = self.inactive_color
                        # if current pad in lower half
                        else:
                            # if current pad is higher than last pressed pad
                            if min_v >= self._value:
                                self.buffer[x, y] = self.active_color
                            # if current pad is lower than last pressed pad
                            elif max_v < self._value:
                                self.buffer[x, y] = self.inactive_color
                            # if current pad is last pressed pad
                            else:
                                # reverse brightness to match type
                                coefficient = 1.0 - self._calc_pixel_coefficient(self._value - min_v)
                                self.buffer[x, y] = self.active_color * coefficient
                    # if current value is 0.5
                    else:
                        # lit middle pad(s)
                        if min_v == 0.5 or max_v == 0.5:
                            self.buffer[x, y] = self.active_color
                        # unlit every other pad
                        else:
                            self.buffer[x, y] = self.inactive_color
                elif self.type == Fader.Type.Wrap:
                    # if current pad lower than last pressed pad
                    if max_v <= self._value:
                        self.buffer[x, y] = self.active_color
                    # if current pad higher than last pressed pad
                    elif min_v > self._value:
                        self.buffer[x, y] = self.inactive_color
                    # if current pad is last pressed pad
                    else:
                        coefficient = min(self._calc_pixel_coefficient(self._value - min_v) + self._calc_pixel_step(), 1.0)
                        self.buffer[x, y] = self.active_color * coefficient
                elif self.type == Fader.Type.Spread:
                    # if current pad in upper half
                    if min_v >= 0.5:
                        # if current pad higher than current value
                        if min_v > halfvalpluspointfive:
                            self.buffer[x, y] = self.inactive_color
                        # if current pad lower than current value
                        elif max_v <= halfvalpluspointfive:
                            self.buffer[x, y] = self.active_color
                        # if current value is in current pad's boundary
                        else:
                            coefficient = self._calc_pixel_coefficient(halfvalpluspointfive - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                    # if current pad in lower half
                    elif max_v <= 0.5:
                        # if current pad higher than current value
                        if min_v >= (1.0 - halfvalpluspointfive):
                            self.buffer[x, y] = self.active_color
                        # if current pad lower than current value
                        elif max_v < (1.0 - halfvalpluspointfive):
                            self.buffer[x, y] = self.inactive_color
                        # if current value is in current pad's boundary
                        else:
                            coefficient = 1.0 - self._calc_pixel_coefficient((1.0 - halfvalpluspointfive) - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                elif self.type == Fader.Type.Collapse:
                    # if current pad in upper half
                    if min_v >= 0.5:
                        # if current pad lower than current value
                        if min_v >= (1.0 - halfval):
                            self.buffer[x, y] = self.inactive_color
                        # if current pad higher than current value
                        elif max_v < (1.0 - halfval):
                            self.buffer[x, y] = self.active_color
                        # if current value is in current pad's boundary
                        else:
                            coefficient = self._calc_pixel_coefficient((1.0 - halfval) - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                    # if current pad in lower half
                    elif max_v <= 0.5:
                        # if current pad lower than current value
                        if min_v > halfval:
                            self.buffer[x, y] = self.active_color
                        # if current pad higher than current value
                        elif max_v <= halfval:
                            self.buffer[x, y] = self.inactive_color
                        # if current value is in current pad's boundary
                        else:
                            coefficient = 1.0 - self._calc_pixel_coefficient(halfval - min_v)
                            self.buffer[x, y] = self.active_color * coefficient

    def _resize(self, width, height):
        self._min_v = [[self._calc_fader_value(x, y, 0.0) for y in range(height)] for x in range(width)]
        self._max_v = [[self._calc_fader_value(x, y, 1.0) for y in range(height)] for x in range(width)]
        return True

    """
        For 2-d widgets, where output values are single float,
        we must calculate single float from 2-d area.
        Calculation done from left to right, bottom to top in order
        to get final value for vertical faders. its basically (y * step) + x.
        Vertical matrix faders are left to right, bottom to up in order.
        Horizontal matrix faders are bottom to up, left to right in order.
        Simple faders are bottom to up for vertical, left to right for horizontal.
    """
    def _calc_fader_value(self, x: int, y: int, value: float) -> float:
        """Calculate fader value from pad location"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return round(((y / self.rect.h) + (value / self.rect.h)), 6)
            elif self.direction == Fader.Direction.Horizontal:
                return round(((x / self.rect.w) + (value / self.rect.w)), 6)
        elif self.grid == Fader.Grid.Matrix:
            if self.direction == Fader.Direction.Vertical:
                base = (x / self.rect.area) + (y / self.rect.h)
            elif self.direction == Fader.Direction.Horizontal:
                base = (y / self.rect.area) + (x / self.rect.w)
            return round(base + (value / self.rect.area), 6)
    
    def _calc_fader_magnitude(self, x: int, y: int) -> float:
        """Calculate pad magnitude from pad location"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return self._calc_fader_value(x, y, y / (self.rect.h - 1))
            elif self.direction == Fader.Direction.Horizontal:
                return self._calc_fader_value(x, y, x / (self.rect.w - 1))
        elif self.grid == Fader.Grid.Matrix:
            if self.direction == Fader.Direction.Vertical:
                base = (x / (self.rect.area - 1)) + (y / (self.rect.h - 1))
            elif self.direction == Fader.Direction.Horizontal:
                base = (y / (self.rect.area - 1)) + (x / (self.rect.w - 1))
            return self._calc_fader_value(x, y, base)
    
    def _calc_pixel_coefficient(self, value: float) -> float:
        """Calculate pixel coefficient for different fader options"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return (value * self.rect.h)
            elif self.direction == Fader.Direction.Horizontal:
                return (value * self.rect.w)
        elif self.grid == Fader.Grid.Matrix:
            return (value * self.rect.area)
    
    def _calc_pixel_step(self):
        if self.mode == Fader.Mode.Simple:
            return 0.5
        elif self.mode == Fader.Mode.Multi:
            return 1.0 / self.resolution
        elif self.mode == Fader.Mode.Magnitude:
            return 1.0 / 256
        elif self.mode == Fader.Mode.Sensitive:
            return 1.0 / 256
        elif self.mode == Fader.Mode.Relative:
            if self.grid == Fader.Grid.Simple:
                if self.direction == Fader.Direction.Vertical:
                    return 1.0/ self.rect.h
                elif self.direction == Fader.Direction.Horizontal:
                    return 1.0 / self.rect.w
            elif self.grid == Fader.Grid.Matrix:
                return 1.0 / self.rect.area

# Keyboard class
class Keyboard(Velocity, Widget):
    """A playable note layout (piano, chromatic or in-scale) emitting NoteOn and NoteOff."""

    emits = (pyxelwidgets.events.NoteOn, pyxelwidgets.events.NoteOff)

    class Type(enum.Enum):
        Keyboard            = 0
        ChromaticVertical   = 1
        ChromaticHorizontal = 2
        Diatonic            = 3
        DiatonicVertical    = 4
        DiatonicHorizontal  = 5

    # The scales and roots are the module's (Keyboard.Scale is Scale)
    Scale = Scale
    Root = Root

    Scales = {
        **SCALES,
        # Rows of a piano: white keys, then black keys (-1 where there is none)
        'Keyboard': [0, 2, 4, 5, 7, 9, 11],
        'KeyboardUpper': [-1, 1, 3, -1, 6, 8, 10]
    }

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 octave: int = 0,
                 fold: int = 4,
                 type: Type = Type.Diatonic,
                 scale: Scale = Scale.Major,
                 root: Root = Root.C,
                 root_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Magenta,
                 keyboard_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Cyan,
                 non_scale_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Yellow,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Green,
                 transpose: int = 0,
                 **kwargs):
        """
        octave: int = 0, optional
            Moves every note by octaves; octave 0 starts from MIDI note 0 (plus the root).
        fold: int = 4, optional
            Where rows repeat: the Chromatic types move each row by ``fold - 1``
            semitones (6 makes rows of fourths, like a guitar or bass), the
            Diatonic vertical and horizontal types by ``fold - 1`` scale notes
            (4: in-key fourths, as on the Push).
        type: Type = Type.Diatonic, optional
            Keyboard: piano rows of white and black keys. Chromatic: every
            semitone, rows moved by ``fold``. Diatonic: only the scale's notes,
            each row an octave above the one below; the vertical and horizontal
            variants overlap rows by ``fold``.
        scale, root: optional
            The notes in key: lit in ``keyboard_color`` (the root in
            ``root_color``) and the only ones Diatonic types lay out.
        transpose: int = 0, optional
            Semitones added to the notes played, without moving the layout or its colors.
        root_color, keyboard_color, non_scale_color: Color, optional
            The root notes, the other notes of the scale, and notes outside it (Chromatic and
            Keyboard types).
        """
        self._octave = octave
        self.transpose = transpose
        # The note each held pad played, so it ends even if the layout changed since
        self._held = {}
        self._fold = fold
        self._type: Keyboard.Type = type
        self._scale: Scale = scale
        self._root: Root = root
        self._root_color: pyxelwidgets.color.Color = root_color
        self._keyboard_color: pyxelwidgets.color.Color = keyboard_color
        self._non_scale_color: pyxelwidgets.color.Color = non_scale_color
        self.buttons = None
        self.notes = None
        self.colors = None
        self.states = None
        super().__init__(x=x, y=y, width=width, height=height, active_color = active_color, **kwargs)

    @property
    def octave(self):
        return self._octave
    
    @octave.setter
    def octave(self, octave: int):
        self._octave = octave
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def fold(self):
        return self._fold
    
    @fold.setter
    def fold(self, fold: int):
        self._fold = fold
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def type(self):
        return self._type
    
    @type.setter
    def type(self, mode: Type):
        self._type = mode
        self._resize(self.width, self.height)
        self.updated = True
    
    @property
    def scale(self):
        return self._scale
    
    @scale.setter
    def scale(self, scale: Scale):
        self._scale = scale
        self._resize(self.width, self.height)
        self.updated = True
    
    @property
    def root(self):
        return self._root
    
    @root.setter
    def root(self, root: Root):
        self._root = root
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def root_color(self):
        return self._root_color
    
    @root_color.setter
    def root_color(self, root_color: pyxelwidgets.color.Color):
        self._root_color = root_color
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def keyboard_color(self):
        return self._keyboard_color
    
    @keyboard_color.setter
    def keyboard_color(self, keyboard_color: pyxelwidgets.color.Color):
        self._keyboard_color = keyboard_color
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def non_scale_color(self):
        return self._non_scale_color
    
    @non_scale_color.setter
    def non_scale_color(self, non_scale_color: pyxelwidgets.color.Color):
        self._non_scale_color = non_scale_color
        self._resize(self.width, self.height)
        self.updated = True

    def handle_press(self, x: int, y: int, velocity: float):
        note = int(self.notes[x, y])
        if note >= 0:
            for button in self.buttons[note]:
                self.states[button[0], button[1]] = True
            self.updated = True
            played = note + self.transpose
            if 0 <= played <= 127:
                self._held[(x, y)] = played
                self.emit(pyxelwidgets.events.NoteOn(self, played, self.humanize(self.velocity_of(velocity))))

    def handle_release(self, x: int, y: int, velocity: float):
        note = int(self.notes[x, y])
        if note >= 0:
            for button in self.buttons[note]:
                self.states[button[0], button[1]] = False
            self.updated = True
        played = self._held.pop((x, y), None)
        if played is not None:
            self.emit(pyxelwidgets.events.NoteOff(self, played, velocity))

    def draw(self) -> None:
        area = self.rect.origin
        for x in area.columns:
            for y in area.rows:
                note = self.notes[x, y]
                if note >= 0:
                    if self.states[x, y]:
                        self.buffer[x, y] = self.active_color
                    else:
                        self.buffer[x, y] = self.colors[note]
                else:
                    self.buffer[x, y] = self.inactive_color

    def _resize(self, width, height) -> bool:
        self.notes = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.states = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.colors = [pyxelwidgets.color.Colors.Invisible for i in range(128)]
        self.buttons = [[] for i in range(128)]
        self._calc_notes()
        return True

    def _calc_notes(self):
        base = self._root.value + (self._octave * 12)
        scale = Keyboard.Scales[self._scale.name]
        precalc = []
        #precalculate scale values, enough for the largest index any layout below reads
        for i in range((self.rect.w + self.rect.h) * max(len(scale), self._fold)):
            precalc.append(scale[i % len(scale)] + base + ((i // len(scale)) * 12))
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                #calculate notes
                if self._type == Keyboard.Type.Keyboard:
                    base = Keyboard.Root.C.value + (self._octave * 12)
                    length = 7 if 7 < self.rect.w else self.rect.w
                    if y % 2 == 0:
                        scale = Keyboard.Scales['Keyboard']
                    else:
                        scale = Keyboard.Scales['KeyboardUpper']
                    if scale[x % length] == -1:
                        self.notes[x, y] = -1
                    else:
                        self.notes[x, y] = scale[x % length] + base + ((y // 2) * 12) + ((x // length) * 12)
                elif self._type == Keyboard.Type.ChromaticVertical:
                    index = x + (y * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._type == Keyboard.Type.ChromaticHorizontal:
                    index = y + (x * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._type == Keyboard.Type.Diatonic:
                    self.notes[x, y] = precalc[x + (y * len(scale))]
                elif self._type == Keyboard.Type.DiatonicVertical:
                    self.notes[x, y] = precalc[x + (y * len(scale)) - (y * (len(scale) - self._fold + 1))]
                elif self._type == Keyboard.Type.DiatonicHorizontal:
                    self.notes[x, y] = precalc[y + (x * len(scale)) - (x * (len(scale) - self._fold + 1))]
                #clear notes 128 or higher
                if self.notes[x, y] > 127:
                    self.notes[x, y] = -1
                #make array from same buttons
                if self.notes[x, y] != -1:
                    self.buttons[self.notes[x, y]].append([x, y])
                #change colors
                if self.notes[x, y] != -1:
                    if (self.notes[x, y] - self._root.value) % 12 == 0:
                        self.colors[self.notes[x, y]] = self._root_color
                    elif (self.notes[x, y] - self._root.value) % 12 in Keyboard.Scales[self._scale.name]:
                        self.colors[self.notes[x, y]] = self._keyboard_color
                    else:
                        self.colors[self.notes[x, y]] = self._non_scale_color

# Knob class
class Knob(ValueWidget):
    """A value shown around the border of the area; holding a pad turns it continuously."""

    class Type(enum.Enum):
        Single      = enum.auto()
        BoostCut    = enum.auto()
        Wrap        = enum.auto()
        Spread      = enum.auto()
        Collapse    = enum.auto()

    reshaping = ('type',)

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 speed: float = 1.5,
                 type: Type = Type.Wrap,
                 clock: typing.Callable[[], float] = time.monotonic,
                 **kwargs):
        """
        speed: float = 1.5, optional
            How fast a held pad turns the knob, in full turns per second at the
            pads farthest from the top (pads nearer it turn slower). Pads on the
            left (or bottom) half turn it down, on the right (or top) half up;
            a pad on each side at once centres it.
        type: Type = Type.Wrap, optional
            How the value lights the ring, as Fader's types.
        """
        super().__init__(x, y, width, height, **kwargs)
        self.speed = speed
        self.type = type
        self.clock = clock
        #: Turning: a pad is held
        self.state = False
        self._held = None
        self._last = None

    def handle_press(self, x: int, y: int, velocity: float):
        weight = self._calc_knob_weight(self._calc_knob_index(x, y))
        if self._held is None:
            if weight != 0.0:
                self._held = (x, y)
                self.state = True
                self._last = self.clock()
                self.updated = True
        else:
            # A pad on the other side while one is held centres the value
            held = self._calc_knob_weight(self._calc_knob_index(*self._held))
            if held * weight < 0.0:
                self.state = False
                self.set_value(0.5)

    def handle_release(self, x: int, y: int, velocity: float):
        self._held = None
        self.state = False

    def turn(self, seconds: float) -> None:
        """Turn by what the held pad does in ``seconds`` (``render`` calls it while a pad is held)."""
        if self.state and self._held is not None:
            weight = self._calc_knob_weight(self._calc_knob_index(*self._held))
            # Weights are at most 0.5
            value = self._clamp(self._value + weight * 2.0 * self.speed * seconds)
            if value != self._value:
                self.set_value(value)

    def render(self, time = None) -> bool:
        if self.state:
            now = self.clock()
            elapsed, self._last = now - self._last, now
            self.turn(elapsed)
        return super().render(time)

    def draw(self) -> None:
        halfval = self._value / 2.0
        halfvalpluspointfive = halfval + 0.5
        area = self.rect.origin
        for x in area.columns:
            for y in area.rows:
                index = self.indexes[x][y]
                min_v = self._min_v[index]
                max_v = self._max_v[index]
                if index == -1:
                    self.buffer[x, y] = pyxelwidgets.color.Colors.Invisible
                elif index >= self._pads:
                    # The bottom middle pad of an odd width is where the ring ends
                    self.buffer[x, y] = self.inactive_color
                else:
                    if self.type == Knob.Type.Single:
                        if max_v < self._value:
                            self.buffer[x, y] = self.inactive_color
                        elif min_v > self._value:
                            self.buffer[x, y] = self.inactive_color
                        else:
                            coefficient = self._calc_pixel_coefficient(self._value - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                    elif self.type == Knob.Type.BoostCut:
                        if min_v < 0.5 < max_v:
                            # A pad on the middle (odd widths) marks it
                            self.buffer[x, y] = self.active_color
                        elif self._value > 0.5:
                            if min_v < 0.5:
                                self.buffer[x, y] = self.inactive_color
                            else:
                                if max_v <= self._value:
                                    self.buffer[x, y] = self.active_color
                                elif min_v > self._value:
                                    self.buffer[x, y] = self.inactive_color
                                else:
                                    coefficient = self._calc_pixel_coefficient(self._value - min_v)
                                    self.buffer[x, y] = self.active_color * coefficient
                        elif self._value < 0.5:
                            if max_v > 0.5:
                                self.buffer[x, y] = self.inactive_color
                            else:
                                if min_v >= self._value:
                                    self.buffer[x, y] = self.active_color
                                elif max_v < self._value:
                                    self.buffer[x, y] = self.inactive_color
                                else:
                                    coefficient = 1.0 - self._calc_pixel_coefficient(self._value - min_v)
                                    self.buffer[x, y] = self.active_color * coefficient
                        else:
                            if min_v == 0.5 or max_v == 0.5:
                                self.buffer[x, y] = self.active_color
                            else:
                                self.buffer[x, y] = self.inactive_color
                    elif self.type == Knob.Type.Wrap:
                        if max_v <= self._value:
                            self.buffer[x, y] = self.active_color
                        elif min_v > self._value:
                            self.buffer[x, y] = self.inactive_color
                        else:
                            coefficient = self._calc_pixel_coefficient(self._value - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                    elif self.type == Knob.Type.Spread:
                        if min_v >= 0.5:
                            if min_v > halfvalpluspointfive:
                                self.buffer[x, y] = self.inactive_color
                            elif max_v <= halfvalpluspointfive:
                                self.buffer[x, y] = self.active_color
                            else:
                                coefficient = self._calc_pixel_coefficient(halfvalpluspointfive - min_v)
                                self.buffer[x, y] = self.active_color * coefficient
                        elif max_v <= 0.5:
                            if min_v >= (1.0 - halfvalpluspointfive):
                                self.buffer[x, y] = self.active_color
                            elif max_v < (1.0 - halfvalpluspointfive):
                                self.buffer[x, y] = self.inactive_color
                            else:
                                coefficient = 1.0 - self._calc_pixel_coefficient((1.0 - halfvalpluspointfive) - min_v)
                                self.buffer[x, y] = self.active_color * coefficient
                        else:
                            # The pad on the middle (odd widths) fills first
                            coefficient = min(1.0, self._calc_pixel_coefficient(self._value))
                            self.buffer[x, y] = self.active_color * coefficient
                    elif self.type == Knob.Type.Collapse:
                        if halfval < 0.5:
                            if max_v <= 0.5:
                                if min_v > halfval:
                                    self.buffer[x, y] = self.active_color
                                elif max_v <= halfval:
                                    self.buffer[x, y] = self.inactive_color
                                else:
                                    coefficient = 1.0 - self._calc_pixel_coefficient(halfval - min_v)
                                    self.buffer[x, y] = self.active_color * coefficient
                            elif min_v >= 0.5:
                                if min_v >= (1.0 - halfval):
                                    self.buffer[x, y] = self.inactive_color
                                elif max_v < (1.0 - halfval):
                                    self.buffer[x, y] = self.active_color
                                else:
                                    coefficient = self._calc_pixel_coefficient((1.0 - halfval) - min_v)
                                    self.buffer[x, y] = self.active_color * coefficient
                            else:
                                # The pad on the middle (odd widths) empties last
                                coefficient = min(1.0, self._calc_pixel_coefficient(1.0 - self._value))
                                self.buffer[x, y] = self.active_color * coefficient
                        else:
                            self.buffer[x, y] = self.inactive_color
    
    def _resize(self, width, height):
        self.perimeter = self._calc_perimeter(width, height)
        ring = width > 1 and height > 1
        # Pads showing the value: around an odd width, all but the bottom middle
        # one, so the top middle pad shows 0.5
        self._pads = self.perimeter - 1 if ring and width % 2 else self.perimeter
        self.indexes = [[self._calc_knob_index(x, y) for y in range(height)] for x in range(width)]
        self._min_v = [self._calc_knob_value(index, 0.0) for index in range(self.perimeter)]
        self._max_v = [self._calc_knob_value(index, 1.0) for index in range(self.perimeter)]
        # Turning speed per pad: minus on the first half, plus on the second,
        # fastest at the ends and slowest next to the middle. With an odd
        # number of pads, a pad centred on the middle (and around a border,
        # the bottom pad centred on the ends) doesn't turn the knob.
        offset = 1.0 if ring and width % 2 else 0.5
        half = self.perimeter / 2
        sides = [index + offset - half for index in range(self.perimeter)]
        ranks = [0 if side in (0.0, half) else math.ceil(abs(side)) for side in sides]
        fastest = 2 * max(ranks, default = 0)
        self._weights = [round(math.copysign(rank / fastest, side), 6) if rank else 0.0
                         for rank, side in zip(ranks, sides)]
        return True

    def _calc_knob_index(self, x: int, y: int) -> float:
        if self.rect.w == 1:
            return y
        elif self.rect.h == 1:
            return x
        halfwidth = int(self.rect.w / 2)
        if y == (self.rect.h - 1):
            return (y + halfwidth + x) - 1
        elif x < halfwidth:
            if y == 0:
                return (halfwidth - x) - 1
            elif x == 0:
                return (y + halfwidth) - 1
        elif x >= halfwidth:
            if y == 0:
                return (self.perimeter - (x - halfwidth)) - 1
            elif x == (self.rect.w - 1):
                return (self.perimeter - (x - halfwidth) - y) - 1
        return -1

    def _calc_knob_value(self, index: int, value: float) -> float:
        if index == -1:
            return 0.0
        return round(((index / self._pads) + (value / self._pads)), 6)
    
    def _calc_knob_weight(self, index: int) -> float:
        if index == -1:
            return 0.0
        return self._weights[index]

    def _calc_pixel_coefficient(self, value: float) -> float:
        return value * self._pads
    
    def _calc_perimeter(self, width, height) -> float:    
        if width == 1:
            return height
        elif height == 1:
            return width
        return ((width - 1) * 2) + ((height - 1) * 2)

# Paged class
class Paged:
    """
    Mixin for widgets showing one ``page`` of their ``pages`` at a time: emits
    PageShown when the page shown changes, or the number of pages does, and
    has the actions ``next_page``/``previous_page``, which stop at the ends.
    Widgets call ``_page_shown()`` after anything that may change them.
    """

    emits = (pyxelwidgets.events.PageShown,)

    #: Link actions to page through the widget
    page_actions = {'next_page': None, 'previous_page': None}

    def next_page(self) -> None:
        """Show the next page; nothing on the last."""
        if self.page < self.pages - 1:
            self.page = self.page + 1

    def previous_page(self) -> None:
        """Show the previous page; nothing on the first."""
        if self.page > 0:
            self.page = self.page - 1

    def _ends(self) -> tuple:
        """Whether the view is at the first page, and at the last."""
        return self.page == 0, self.page == self.pages - 1

    def _page_shown(self) -> None:
        first, last = self._ends()
        shown = (self.page, self.pages, first, last)
        if shown != self.__dict__.get('_shown'):
            self._shown = shown
            self.emit(pyxelwidgets.events.PageShown(self, shown[0], first, last))

class Follow(enum.Enum):
    """
    How the view of a PianoRoll or Sequencer follows the playing step.

    Off: the view stays where it is.
    Page: it turns to the playing step's page when the step moves to another page.
    Playhead: it scrolls along, keeping the playing step in the middle (except near the first and last steps).
    """
    Off         = enum.auto()
    Page        = enum.auto()
    Playhead    = enum.auto()

class Scrolled(Paged):
    """
    Mixin for widgets showing a strip of lanes (PianoRoll's columns of steps,
    Sequencer's rows of steps), one screen of them at a time. The view starts
    at lane ``_first`` and scrolls a lane at a time (``scroll_forward``/
    ``scroll_back``) or a page, a screen, at a time; the last page ends at the
    last lane. Widgets define ``_lanes()`` and ``_screen()`` (lanes shown) and
    call ``_follow`` when a step plays.
    """

    _first = 0

    #: Link actions to scroll a lane at a time
    scroll_actions = {'scroll_forward': None, 'scroll_back': None}

    def _last_first(self) -> int:
        return max(self._lanes() - self._screen(), 0)

    def _scroll_to(self, first: int) -> None:
        self._first = min(max(int(first), 0), self._last_first())
        self.updated = True
        self._page_shown()

    def scroll_forward(self) -> None:
        """Show one more lane at the end (right or top); nothing at the last."""
        self._scroll_to(self._first + 1)

    def scroll_back(self) -> None:
        """Show one more lane at the start (left or bottom); nothing at the first."""
        self._scroll_to(self._first - 1)

    @property
    def pages(self) -> int:
        return (self._lanes() - 1) // self._screen() + 1

    @property
    def page(self) -> int:
        """The page shown: the last once the view reaches the end, else the one its first lane is on."""
        return self.pages - 1 if self._first >= self._last_first() else self._first // self._screen()

    @page.setter
    def page(self, value: int) -> None:
        self._scroll_to(int(value) % self.pages * self._screen())

    def _ends(self) -> tuple:
        return self._first == 0, self._first >= self._last_first()

    def next_page(self) -> None:
        """Show the next page; nothing at the end."""
        if self._first < self._last_first():
            self._scroll_to((self._first // self._screen() + 1) * self._screen())

    def previous_page(self) -> None:
        """Show the page before (the start of this one when scrolled into it); nothing at the start."""
        if self._first > 0:
            self._scroll_to((self._first - 1) // self._screen() * self._screen())

    def _follow(self, lane: int, turned: bool) -> None:
        """Show the playing ``lane`` as ``follow`` has it; ``turned``: it moved to another page (or was moved to)."""
        if self.follow == Follow.Playhead:
            # Centered: an even screen has one more lane ahead
            self._scroll_to(lane - (self._screen() - 1) // 2)
        elif self.follow == Follow.Page and turned:
            self._scroll_to(lane // self._screen() * self._screen())

# Sequencer class
class Clock(enum.Enum):
    """
    What plays a timed widget (Sequencer, Tracker, ClipLauncher) every ``rate``.

    Transport: the transport, at its tempo, only while it plays (default).
    Own: a clock of its own at the widget's ``bpm``, running whether the transport plays or not.
    Off: nothing; only ``play``/``advance`` calls (e.g. from links) play it.
    """
    Transport   = enum.auto()
    Own         = enum.auto()
    Off         = enum.auto()

class Timed:
    """
    Mixin for widgets a clock plays every ``rate``. Widgets don't know about
    clocks: glue (``App.attach``, ``Parser.attach``, ``Parser.start_clocks``) calls ``tick``
    from the transport or from a clock of the widget's own.
    """

    #: Link actions to pause and resume the widget on its clock
    clock_actions = {'start': None, 'stop': None, 'toggle': None}

    #: Calls of ``tick`` per ``rate``: more than one lets the widget time things
    #: within a step (a Sequencer's swing and gates), ``count`` then counts them
    divisions = 1

    def __init__(self, *args,
                 clock: Clock = Clock.Transport,
                 bpm: float = 120.0,
                 running: bool = True,
                 **kwargs):
        """
        clock: Clock = Clock.Transport, optional
            What plays it every ``rate``: the transport, its own clock at ``bpm``, or nothing (links only).
        bpm: float = 120.0, optional
            The tempo of its own clock (``clock = Clock.Own``).
        running: bool = True, optional
            Played by its clock; False pauses it (``start``/``stop``/``toggle``).
        """
        if not bpm > 0:
            raise ValueError(f'bpm must be positive, got {bpm!r}')
        self.clock = clock
        self.bpm = bpm
        self.running = running
        super().__init__(*args, **kwargs)

    def tick(self, count: int) -> None:
        """
        Called by its clock with the number of ``rate`` lengths since it started:
        while ``running``, the transport places it at ``count``, its own clock
        moves it one on (so it resumes where it paused).
        """
        if self.running:
            if self.clock == Clock.Transport:
                self.play(count)
            else:
                self.advance()

    def silence(self) -> None:
        """End what's sounding (a Sequencer's gate); glue calls it when the clock stops."""

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False
        self.silence()

    def toggle(self) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

def _fit(array: numpy.ndarray, shape: tuple, fill) -> numpy.ndarray:
    """``array`` at ``shape``: the part that fits kept in place, the rest ``fill``."""
    fitted = numpy.full(shape, fill, dtype = array.dtype)
    _copy_overlap(fitted, array)
    return fitted

class Sequencer(Timed, Scrolled, Velocity, Widget):
    """
    Step sequencer. Each step plays when ``play(step)`` or ``advance()`` is
    called; its ``clock`` (the transport, one of its own, or none) does every
    ``rate``, with ``swing``. Emits StepPlayed, and StepEnded when an active
    step's ``gate`` ends. Steps go left to right in rows going up; more rows
    than the pads scroll a row at a time (``row``) or a page at a time.

    Pressing a step turns it on (with the press's velocity); pressing an
    active one turns it off when it's let go, unless it was edited while held:
    link actions (``set_velocity``, ``set_probability``, ``set_ratchets``,
    ``set_note``) change the held steps, or the last one pressed.
    """

    emits = (pyxelwidgets.events.StepPlayed, pyxelwidgets.events.StepEnded, pyxelwidgets.events.PageChanged)

    # Called 24 times a step, to time swing, gates and ratchets
    divisions = 24

    actions = {'advance': None, 'play': 'int', 'reset': None,
               'set_velocity': 'float', 'set_probability': 'float', 'set_ratchets': 'int', 'set_note': 'int',
               **Paged.page_actions, **Scrolled.scroll_actions, **Timed.clock_actions}

    Follow = Follow

    class Direction(enum.Enum):
        """The order steps play in: forward, backward, forward then back (PingPong), or at random."""
        Forward     = enum.auto()
        Backward    = enum.auto()
        PingPong    = enum.auto()
        Random      = enum.auto()

    #: The most hits a step can repeat in (``set_ratchets``)
    MAX_RATCHETS = 8

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 steps: int | None = None,
                 length: int | None = None,
                 rate: Rate = '1/16',
                 step: int = 0,
                 page: int = 0,
                 row: int = 0,
                 follow: Follow = Follow.Page,
                 direction: Direction = Direction.Forward,
                 note: int = 36,
                 swing: float = 50.0,
                 gate: float = 0.5,
                 gate_random: float = 0.0,
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Lime,
                 current_active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Red,
                 **kwargs):
        """
        steps: int, optional
            How many steps there are; more than the pads go on pages. Defaults to the pads.
        length: int, optional
            How many of them play before it starts over (the clock and
            ``advance`` only); the rest keep what's on them. Defaults to ``steps``.
        step: int = 0, optional
            The current (playing) step.
        page: int = 0, optional
            The page shown and edited.
        row: int = 0, optional
            The first row of steps shown (at the bottom), counting rows over all pages; instead of ``page``.
        follow: Follow = Follow.Page, optional
            How the view follows the playing step: not at all, a page at a
            time, or scrolling with it in the middle (Playhead).
        direction: Direction = Direction.Forward, optional
            The order the clock and ``advance`` play steps in.
        note: int = 36, optional
            The note steps play (StepPlayed's ``note``) unless one has its own (``set_note``).
        swing: float = 50.0, optional
            Where every second step starts, in percent of a pair of steps: 50
            is straight, 66 a triplet feel, 75 the most. Needs a clock (calls
            of ``play``/``advance`` aren't delayed).
        gate: float = 0.5, optional
            How long an active step sounds, in steps (up to 1): StepEnded then.
            Without a clock it ends when the next step plays.
        gate_random: float = 0.0, optional
            Each hit's gate is longer or shorter by up to this many steps, at random.
        rate: Rate = '1/16', optional
            The length of a step: a note value such as '1/16', '1/8T' or 'bar'.
        current_color, current_active_color: Color, optional
            The playing step: its empty cells and its active ones.
        """
        if not 50.0 <= swing <= 75.0:
            raise ValueError(f'swing must be from 50 to 75 percent, got {swing!r}')
        if not 0.0 < gate <= 1.0:
            raise ValueError(f'gate must be more than 0 and at most 1 step, got {gate!r}')
        if not 0.0 <= gate_random <= 1.0:
            raise ValueError(f'gate_random must be from 0 to 1 step, got {gate_random!r}')
        if not 0 <= note <= 127:
            raise ValueError(f'note must be from 0 to 127, got {note!r}')
        self.swing = swing
        self.gate = gate
        self.gate_random = gate_random
        self.direction = direction
        self.note = note
        self._random = random.Random()
        # Clock time in steps (its own clock counts while running), the swung step it played last,
        # the active step sounding and when (in steps) its gate ends
        self._position = 0.0
        self._last_count = None
        self._slot = None
        self._sounding = None
        self._gate_length = 0.0
        self._gate_end = None
        # Ratchets of the sounding step still to come: (when the next one starts, how many, how far apart)
        self._ratchet = None
        # PingPong's way: +1 or -1
        self._heading = 1
        # Pads held: (x, y) → [step, turned off when let go]
        self._held = {}
        self._selected = None
        self.state = numpy.zeros((1, 1), dtype = numpy.bool_)
        #: Each step's velocity, chance to play (0-1), hits (ratchets) and note (-1: the widget's ``note``)
        self.velocities = numpy.ones((1, 1))
        self.probabilities = numpy.ones((1, 1))
        self.ratchets = numpy.ones((1, 1), dtype = numpy.int8)
        self.notes = numpy.full((1, 1), -1, dtype = numpy.int16)
        self._steps = steps if steps is not None else width * height
        self._length = None
        self._step = 0
        self._page_count = 1
        self.current_page = 0
        self.follow = follow
        super().__init__(x, y, width, height, **kwargs)
        self.state.fill(False)
        self.length = length
        self.rate = rate
        self.current_color = current_color
        self.current_active_color = current_active_color
        self.step = step
        self.page = page
        if row:
            self.row = row

    def _lanes(self) -> int:
        return (self._steps - 1) // self.rect.w + 1

    def _screen(self) -> int:
        return self.rect.h

    @property
    def row(self) -> int:
        """The first row of steps shown (at the bottom), from 0 to the rows of steps less the pads' height."""
        return self._first

    @row.setter
    def row(self, value: int) -> None:
        self._scroll_to(value)

    @property
    def step(self) -> int:
        """The current step; setting it moves there without playing it."""
        return self._step
    
    @step.setter
    def step(self, value: int) -> None:
        self._step = int(value) % self._steps
        self.current_page = self._step // self.rect.area
        self.updated = True
        self._follow(self._step // self.rect.w, True)

    @property
    def steps(self) -> int:
        return self._steps

    @steps.setter
    def steps(self, value: int) -> None:
        self._steps = max(int(value), 1)
        self._fit_steps(self.rect.w, self.rect.h)
        self.updated = True

    @property
    def length(self) -> int:
        """How many steps play before it starts over (at most ``steps``)."""
        return min(self._length, self._steps) if self._length is not None else self._steps

    @length.setter
    def length(self, value: int | None) -> None:
        self._length = None if value is None else max(int(value), 1)
        self.updated = True

    @property
    def current(self) -> bool:
        return bool(self.state[self._tick_x(), self._tick_y()])
    
    @current.setter
    def current(self, state: bool) -> None:
        self.state[self._tick_x(), self._tick_y()] = state
        self.updated = True

    def _cell(self, step: int) -> tuple:
        """Where ``step`` is in the step arrays."""
        return step % self.rect.w, step // self.rect.w

    def note_of(self, step: int) -> int:
        """The note ``step`` plays."""
        note = int(self.notes[self._cell(step)])
        return note if note >= 0 else self.note

    def play(self, step: int) -> None:
        """
        Move to ``step`` (wrapped to ``steps``) and emit StepPlayed; a sounding
        step ends first. An active step plays as its probability has it.
        """
        self.silence()
        self._ratchet = None
        self._step = int(step) % self._steps
        page = self._step // self.rect.area
        turned = page != self.current_page
        if turned:
            self.current_page = page
            self.emit(pyxelwidgets.events.PageChanged(self, self.current_page))
        self._follow(self._step // self.rect.w, turned)
        cell = self._cell(self._step)
        active = bool(self.state[cell])
        if active and self.probabilities[cell] < 1.0:
            active = self._random.random() < self.probabilities[cell]
        gate = velocity = 0.0
        if active:
            spread = min(max(float(self.gate_random), 0.0), 1.0)
            gate = float(self.gate) + (self._random.uniform(-spread, spread) if spread else 0.0)
            # At least one division, at most a step; ratchets share it
            gate = min(max(gate, 1 / self.divisions), 1.0) / max(int(self.ratchets[cell]), 1)
            gate = max(gate, 1 / self.divisions)
            velocity = self.humanize(float(self.velocities[cell]))
            self._sounding, self._gate_length, self._gate_end = self._step, gate, None
        self.emit(pyxelwidgets.events.StepPlayed(self, self._step, active, gate, velocity, self.note_of(self._step)))
        self.updated = True

    def silence(self) -> None:
        """End the sounding step's gate now (StepEnded), e.g. when the clock stops."""
        if self._sounding is not None:
            step, self._sounding, self._gate_end = self._sounding, None, None
            self.emit(pyxelwidgets.events.StepEnded(self, step, self.note_of(step)))

    def tick(self, count: int) -> None:
        """
        Called by its clock ``divisions`` times a step: plays steps (every second
        one late by ``swing``) in ``direction``, repeats ratchets and ends gates.
        ``count`` counts divisions.
        """
        last, self._last_count = self._last_count, count
        if not self.running:
            self.silence()
            self._ratchet = None
            # Its own clock resumes where it paused
            self._last_count = None
            return
        if self.clock == Clock.Transport:
            # The transport's position: relocating moves it, and back (or replaying) plays again
            self._position = count / self.divisions
            if last is not None and count <= last:
                self._slot = None
        elif last is not None:
            self._position += (count - last) / self.divisions
        if self._gate_end is not None and self._position >= self._gate_end:
            self.silence()
        slot = math.floor(self._position)
        delay = (min(max(float(self.swing), 50.0), 75.0) / 50.0) - 1.0
        if slot % 2 and self._position - slot < delay:
            # Every second step starts late
            slot -= 1
        if slot == self._slot:
            self._repeat()
            return
        self._slot = slot
        if self.clock == Clock.Transport:
            self.play(self._order(slot))
        else:
            self.advance()
        if self._sounding is not None:
            start = slot + (delay if slot % 2 else 0.0)
            self._gate_end = start + self._gate_length
            hits = int(self.ratchets[self._cell(self._sounding)])
            if hits > 1:
                # Until the next step starts: shorter after a late step, longer before one
                length = 1.0 - delay if slot % 2 else 1.0 + delay
                self._ratchet = (start + length / hits, hits - 1, length / hits)

    def _repeat(self) -> None:
        """Play the sounding step's next ratchet when its time comes."""
        if self._ratchet is None or self._position < self._ratchet[0]:
            return
        start, left, apart = self._ratchet
        step = self._step
        self.silence()
        cell = self._cell(step)
        self._sounding, self._gate_end = step, start + self._gate_length
        self._ratchet = (start + apart, left - 1, apart) if left > 1 else None
        self.emit(pyxelwidgets.events.StepPlayed(self, step, True, self._gate_length,
                                                 self.humanize(float(self.velocities[cell])), self.note_of(step)))

    def _order(self, count: int) -> int:
        """The step the transport's ``count``-th step is, in ``direction`` over ``length`` steps."""
        length = self.length
        if self.direction == Sequencer.Direction.Backward:
            return length - 1 - count % length
        if self.direction == Sequencer.Direction.PingPong:
            if length == 1:
                return 0
            index = count % (2 * (length - 1))
            return index if index < length else 2 * (length - 1) - index
        if self.direction == Sequencer.Direction.Random:
            return self._random.randrange(length)
        return count % length

    def advance(self) -> None:
        """Play the next step, in ``direction`` over ``length`` steps."""
        length, step = self.length, self._step
        if self.direction == Sequencer.Direction.Backward:
            following = step - 1 if 0 < step < length else length - 1
        elif self.direction == Sequencer.Direction.PingPong:
            if length == 1:
                following = 0
            else:
                if not 0 <= step + self._heading < length:
                    self._heading = -self._heading
                following = min(max(step + self._heading, 0), length - 1)
        elif self.direction == Sequencer.Direction.Random:
            following = self._random.randrange(length)
        else:
            following = step + 1 if step + 1 < length else 0
        self.play(following)

    def handle_press(self, x: int, y: int, velocity: float):
        step = self._calc_tick_position(x, y)
        if step >= self._steps:
            return
        cell = self._cell(step)
        self._selected = step
        if self.state[cell]:
            # Off when let go, unless edited while held
            self._held[(x, y)] = [step, True]
        else:
            self.state[cell] = True
            self.velocities[cell] = self.velocity_of(velocity)
            self.probabilities[cell] = 1.0
            self.ratchets[cell] = 1
            self.notes[cell] = -1
            self._held[(x, y)] = [step, False]
        self.updated = True

    def handle_release(self, x: int, y: int, velocity: float):
        held = self._held.pop((x, y), None)
        if held is not None and held[1]:
            self.state[self._cell(held[0])] = False
            self.updated = True

    def _edited(self) -> list:
        """The steps an edit action changes: the held ones (kept on), else the last one pressed."""
        if self._held:
            for held in self._held.values():
                held[1] = False
            return [held[0] for held in self._held.values()]
        return [self._selected] if self._selected is not None and self._selected < self._steps else []

    def set_velocity(self, velocity: float) -> None:
        """Set the velocity (0-1) of the held steps, or the last one pressed."""
        for step in self._edited():
            self.velocities[self._cell(step)] = min(max(float(velocity), 1 / 127), 1.0)
        self.updated = True

    def set_probability(self, probability: float) -> None:
        """Set how likely (0-1) the held steps, or the last one pressed, play when their turn comes."""
        for step in self._edited():
            self.probabilities[self._cell(step)] = min(max(float(probability), 0.0), 1.0)

    def set_ratchets(self, hits: int) -> None:
        """Repeat the held steps, or the last one pressed, ``hits`` times within the step (needs a clock)."""
        for step in self._edited():
            self.ratchets[self._cell(step)] = min(max(int(hits), 1), Sequencer.MAX_RATCHETS)

    def set_note(self, note: int) -> None:
        """Give the held steps, or the last one pressed, a note of their own (-1: the widget's ``note``)."""
        for step in self._edited():
            self.notes[self._cell(step)] = min(max(int(note), -1), 127)

    def save_state(self) -> dict:
        return {'cells': self.state.copy(), 'velocities': self.velocities.copy(), 'probabilities': self.probabilities.copy(),
                'ratchets': self.ratchets.copy(), 'notes': self.notes.copy(), 'step': self._step,
                'page': self.page, 'row': self._first}

    def load_state(self, state: dict) -> None:
        for key, array in (('cells', self.state), ('velocities', self.velocities), ('probabilities', self.probabilities),
                           ('ratchets', self.ratchets), ('notes', self.notes)):
            if key in state:
                _copy_overlap(array, state[key])
        if 'step' in state:
            self.step = state['step']
        # The view comes back only whole: without one of them, the page or row given in the options stays
        if 'page' in state and 'row' in state:
            self.row = state['row']
        self.updated = True

    def reset(self):
        """Clear every step."""
        self.state.fill(False)
        self.velocities.fill(1.0)
        self.probabilities.fill(1.0)
        self.ratchets.fill(1)
        self.notes.fill(-1)
        self.updated = True

    def draw(self) -> None:
        length = self.length
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                step = self._calc_tick_position(x, y)
                cell = (x, y + self._first)
                if self.state[cell]:
                    # Softer steps are dimmer
                    color = self.active_color * (0.25 + 0.75 * float(self.velocities[cell]))
                else:
                    color = self.inactive_color
                if step == self._step:
                    color = self.current_active_color if self.state[cell] else self.current_color
                elif step >= length and self.state[cell]:
                    # Past the length: kept, but not played
                    color = color * 0.25
                self.buffer[x, y] = color

    def _fit_steps(self, width: int, height: int) -> None:
        self._page_count = int((self._steps - 1) / (width * height)) + 1
        shape = (width, height * self._page_count)
        self.state = _fit(self.state, shape, False)
        self.velocities = _fit(self.velocities, shape, 1.0)
        self.probabilities = _fit(self.probabilities, shape, 1.0)
        self.ratchets = _fit(self.ratchets, shape, 1)
        self.notes = _fit(self.notes, shape, -1)
        self._step %= self._steps
        self.current_page = self._step // (width * height)
        self._scroll_to(self._first)

    def _resize(self, width, height):
        self._fit_steps(width, height)
        return True
    
    def _calc_tick_position(self, x, y):
        return x + (y + self._first) * self.rect.w

    def _tick_x(self):
        return self._step % self.rect.w
    
    def _tick_y(self):
        return self._step // self.rect.w
    
    def _is_tick_active(self):
        return self.state[self._tick_x()][self._tick_y()]
    
# PianoRoll class
class PianoRoll(Timed, Scrolled, Velocity, Widget):
    """
    A melody editor: columns are steps, rows the notes of ``scale`` (the root's
    rows tinted). Press a pad to add a note; hold a note's first pad and press
    further along its row to make it longer; press a note to delete it. Plays
    its notes (NoteOn, then NoteOff when they end) when ``play(step)`` or
    ``advance()`` is called, its ``clock`` does every ``rate``. More steps
    than the columns scroll a column at a time (``column``) or a page at a time.
    """

    emits = (pyxelwidgets.events.NoteOn, pyxelwidgets.events.NoteOff, pyxelwidgets.events.PageChanged)

    actions = {'advance': None, 'play': 'int', 'reset': None, 'set_velocity': 'float',
               **Paged.page_actions, **Scrolled.scroll_actions, **Timed.clock_actions}

    Follow = Follow

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 steps: int = 16,
                 rate: Rate = '1/16',
                 step: int = 0,
                 page: int = 0,
                 column: int = 0,
                 follow: Follow = Follow.Page,
                 octave: int = 4,
                 row: int = 0,
                 scale: Scale = Scale.Major,
                 root: Root = Root.C,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Orange,
                 root_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(32, 0, 48),
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(0, 48, 0),
                 current_active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.White,
                 **kwargs):
        """
        steps: int = 16, optional
            How many steps the melody has; more than the columns go on pages.
        step: int = 0, optional
            The current (playing) step.
        page: int = 0, optional
            The steps shown and edited, ``width`` per page.
        column: int = 0, optional
            The first step shown (at the left); instead of ``page``.
        follow: Follow = Follow.Page, optional
            How the view follows the playing step: not at all, a page at a
            time, or scrolling with it in the middle (Playhead).
        octave: int = 4, optional
            The bottom row is the root in this octave (4 with C: MIDI note 48)...
        row: int = 0, optional
            ...moved up (or down, as far as MIDI note 0) by this many rows of the scale.
        scale, root: optional
            The notes rows have: one row per note in the scale.
        root_color: Color, optional
            The background of the root's rows.
        current_color, current_active_color: Color, optional
            The playing step's column, and its notes.
        rate: Rate = '1/16', optional
            The length of a step (a note value).
        """
        if steps < 1:
            raise ValueError(f'steps must be at least 1, got {steps!r}')
        self.rate = rate
        self.follow = follow
        self.octave = octave
        self.row = row
        self.scale = scale
        self.root = root
        self.root_color = root_color
        self.current_color = current_color
        self.current_active_color = current_active_color
        #: Notes by (first step, MIDI note): [length in steps, velocity]
        self.notes = {}
        # Notes sounding: MIDI note → steps left
        self._sounding = {}
        # Pads held: (x, y) → [first step, note, deleted when let go]
        self._held = {}
        self._selected = None
        self._steps = steps
        self._step = 0
        self.current_page = 0
        super().__init__(x, y, width, height, active_color = active_color, **kwargs)
        self.step = step
        self.page = page
        if column:
            self.column = column

    def _lanes(self) -> int:
        return self._steps

    def _screen(self) -> int:
        return self.rect.w

    @property
    def steps(self) -> int:
        return self._steps

    @steps.setter
    def steps(self, value: int) -> None:
        self._steps = max(int(value), 1)
        self._step %= self._steps
        self.current_page = self._step // self.rect.w
        self._scroll_to(self._first)

    @property
    def column(self) -> int:
        """The first step shown (at the left), from 0 to ``steps`` less the width."""
        return self._first

    @column.setter
    def column(self, value: int) -> None:
        self._scroll_to(value)

    @property
    def step(self) -> int:
        """The current step; setting it moves there without playing it."""
        return self._step

    @step.setter
    def step(self, value: int) -> None:
        self._step = int(value) % self._steps
        self.current_page = self._step // self.rect.w
        self.updated = True
        self._follow(self._step, True)

    def rows(self) -> list:
        """The MIDI note of each row from the bottom, None past the highest note."""
        notes = scale_notes(self.scale, self.root)
        base = self.root.value + 12 * self.octave
        # Never below the lowest note
        bottom = max(next((index for index, note in enumerate(notes) if note >= base), len(notes)) + self.row, 0)
        return [notes[bottom + y] if bottom + y < len(notes) else None for y in range(self.rect.h)]

    def note_at(self, step: int, note: int):
        """The first step of the note covering ``step`` on ``note``, or None."""
        for (start, pitch), (length, _) in self.notes.items():
            if pitch == note and start <= step < start + length:
                return start
        return None

    def add_note(self, step: int, note: int, length: int = 1, velocity: float = 1.0) -> None:
        """Add a note (replacing the ones it overlaps on its row)."""
        for start, pitch in list(self.notes):
            other = self.notes[(start, pitch)][0]
            if pitch == note and start < step + length and step < start + other:
                del self.notes[(start, pitch)]
        self.notes[(int(step), int(note))] = [max(int(length), 1), float(velocity)]
        self.updated = True

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        step = self._first + x
        note = self.rows()[y]
        if note is None or step >= self._steps:
            return
        # A note's first pad held: this pad makes it longer (or shorter)
        for held in self._held.values():
            start, pitch, _ = held
            if pitch == note and start < step and (start, pitch) in self.notes:
                self.notes[(start, pitch)][0] = step - start + 1
                for other in list(self.notes):
                    if other[1] == note and start < other[0] <= step:
                        del self.notes[other]
                held[2] = False
                self.updated = True
                return
        start = self.note_at(step, note)
        if start is not None:
            # Deleted when let go, unless made longer or edited
            self._held[(x, y)] = [start, note, True]
        else:
            self.add_note(step, note, 1, self.velocity_of(velocity))
            self._held[(x, y)] = [step, note, False]
            start = step
        self._selected = (start, note)

    def handle_release(self, x: int, y: int, velocity: float) -> None:
        held = self._held.pop((x, y), None)
        if held is not None and held[2]:
            self.notes.pop((held[0], held[1]), None)
            self.updated = True

    def set_velocity(self, velocity: float) -> None:
        """Set the velocity (0-1) of the held notes, or the last one pressed."""
        if self._held:
            for held in self._held.values():
                held[2] = False
            keys = [(held[0], held[1]) for held in self._held.values()]
        else:
            keys = [self._selected] if self._selected is not None else []
        for key in keys:
            if key in self.notes:
                self.notes[key][1] = min(max(float(velocity), 1 / 127), 1.0)
        self.updated = True

    def play(self, step: int) -> None:
        """Move to ``step`` (wrapped to ``steps``): notes ending there end (NoteOff), notes starting there start (NoteOn)."""
        self._step = int(step) % self._steps
        page = self._step // self.rect.w
        turned = page != self.current_page
        if turned:
            self.current_page = page
            self.emit(pyxelwidgets.events.PageChanged(self, page))
        self._follow(self._step, turned)
        for note in list(self._sounding):
            self._sounding[note] -= 1
            if self._sounding[note] <= 0:
                del self._sounding[note]
                self.emit(pyxelwidgets.events.NoteOff(self, note, 0.0))
        for (start, note), (length, velocity) in sorted(self.notes.items()):
            if start == self._step and 0 <= note <= 127:
                if note in self._sounding:
                    self.emit(pyxelwidgets.events.NoteOff(self, note, 0.0))
                self._sounding[note] = length
                self.emit(pyxelwidgets.events.NoteOn(self, note, self.humanize(velocity)))
        self.updated = True

    def advance(self) -> None:
        """Play the next step."""
        self.play(self._step + 1)

    def silence(self) -> None:
        """End every sounding note (NoteOff), e.g. when the clock stops."""
        for note in list(self._sounding):
            del self._sounding[note]
            self.emit(pyxelwidgets.events.NoteOff(self, note, 0.0))

    def reset(self) -> None:
        """Delete every note."""
        self.notes.clear()
        self.updated = True

    def save_state(self) -> dict:
        return {'notes': {key: list(value) for key, value in self.notes.items()}, 'step': self._step,
                'page': self.page, 'column': self._first}

    def load_state(self, state: dict) -> None:
        if isinstance(state.get('notes'), dict):
            self.notes = {tuple(key): list(value) for key, value in state['notes'].items()}
        if 'step' in state:
            self.step = state['step']
        # The view comes back only whole: without one of them, the page or column given in the options stays
        if 'page' in state and 'column' in state:
            self.column = state['column']
        self.updated = True

    def draw(self) -> None:
        covered = {}
        for (start, note), (length, velocity) in self.notes.items():
            for offset in range(length):
                covered[(start + offset, note)] = (offset == 0, velocity)
        rows = self.rows()
        for x in range(self.rect.w):
            step = self._first + x
            for y, note in enumerate(rows):
                if note is None or step >= self._steps:
                    self.buffer[x, y] = pyxelwidgets.color.Colors.Black
                    continue
                cell = covered.get((step, note))
                current = step == self._step
                if cell is not None:
                    first, velocity = cell
                    if current:
                        color = self.current_active_color
                    else:
                        # A note's first pad by its velocity, the rest of it dimmer
                        color = self.active_color * ((0.3 + 0.7 * velocity) if first else 0.35)
                elif current:
                    color = self.current_color
                elif (note - self.root.value) % 12 == 0:
                    color = self.root_color
                else:
                    color = self.inactive_color
                self.buffer[x, y] = color

    def _resize(self, width, height) -> bool:
        self.current_page = self._step // width
        self._scroll_to(self._first)
        return True

# Sprite class
class Sprite(Widget):
    """
    Shows a picture, or animates through ``frames`` changing every ``rate``
    (a note value, or seconds). Display-only: presses pass through by default.
    """
    def __init__(self, x: int, y: int, width: int, height: int, *,
                 frames: Frames | None = None,
                 rate: Rate | float | None = None,
                 propagation: Propagation = Propagation.Pass,
                 **kwargs):
        """
        frames: Frames, optional
            The pictures it shows (painted in the designer), fitted to its size from the
            bottom-left.
        rate: Rate | float, optional
            How long each frame shows: a note value or seconds; none shows the first frame only.
        """
        if isinstance(rate, str):
            pyxelwidgets.rate.parse_rate(rate)
        elif rate is not None and not rate > 0:
            raise ValueError(f'rate must be a note value or positive seconds, got {rate!r}')
        self.rate = rate
        self.frame = 0
        self.frames = [pyxelwidgets.buffer.to_buffer(frame) for frame in frames or []]
        super().__init__(x=x, y=y, width=width, height=height, propagation = propagation, **kwargs)
        self.buffer = self.frames[0].copy()

    def _resize(self, width, height):
        # Frames of another size are cropped or padded from the bottom-left
        fitted = []
        for frame in self.frames or [pyxelwidgets.buffer.new(width, height)]:
            buffer = pyxelwidgets.buffer.new(width, height)
            w, h = min(width, frame.shape[0]), min(height, frame.shape[1])
            buffer[:w, :h] = frame[:w, :h]
            fitted.append(buffer)
        self.frames = fitted
        self.frame %= len(fitted)
        return True

    def _configure(self, name: str, value) -> None:
        if name == 'frames':
            self.frames = [pyxelwidgets.buffer.to_buffer(frame) for frame in value or []]
            self._resize(self.rect.w, self.rect.h)
        else:
            super()._configure(name, value)

    def render(self, time: pyxelwidgets.animation.Time | None = None) -> bool:
        if self.rate is not None and len(self.frames) > 1:
            time = time if time is not None else pyxelwidgets.animation.now()
            if isinstance(self.rate, str):
                position = time.beats / pyxelwidgets.rate.quarter_notes(self.rate, time.signature)
            else:
                position = time.seconds / self.rate
            frame = int(position // 1) % len(self.frames)
            if frame != self.frame:
                self.frame = frame
                self.updated = True
        return super().render(time)

    def draw(self) -> None:
        self.buffer[:] = self.frames[self.frame]

# Tracker class
class Tracker(Timed, Paged, Velocity, Widget):
    """
    A scrolling step grid where rows are steps and columns are tracks. Rows
    play when ``play(row)`` or ``advance()`` is called; its ``clock`` does
    every ``rate``. Emits RowPlayed, and for each active cell a NoteOn (its
    track's note, ``note + column``, or its own) ending with a NoteOff when
    the next row plays. The rows shown and edited start at ``bar`` (top) on
    ``page``.

    Pressing a cell turns it on (with the press's velocity); pressing an
    active one turns it off when it's let go, unless it was edited while held
    (``set_note``, ``set_velocity``: the held cells, or the last one pressed).
    """

    emits = (pyxelwidgets.events.RowPlayed, pyxelwidgets.events.NoteOn, pyxelwidgets.events.NoteOff)

    reshaping = ('bars', 'pages')

    actions = {'advance': None, 'play': 'int', 'set_note': 'int', 'set_velocity': 'float', **Paged.page_actions, **Timed.clock_actions}

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 bars: int = 64,
                 pages: int = 1,
                 rate: Rate = '1/16',
                 step: int = 0,
                 page: int = 0,
                 bar: int = 0,
                 follow: bool = True,
                 note: int = 36,
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Cyan,
                 current_active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Magenta,
                 **kwargs):
        """
        bars: int = 64, optional
            Rows on each page.
        pages: int = 1, optional
            Pages of ``bars`` rows, played one after the other.
        step: int = 0, optional
            The current (playing) row over all pages: ``page * bars + bar``.
        page: int = 0, optional
            The page shown and edited.
        bar: int = 0, optional
            The first row shown, at the top.
        follow: bool = True, optional
            Scroll to the playing row when it plays.
        note: int = 36, optional
            The first column's note; each column to the right plays the next one.
        rate: Rate = '1/16', optional
            How long each row plays (a note value).
        current_color, current_active_color: Color, optional
            The playing row: its empty cells and its active ones.
        """
        self.bars = bars
        self.bars = self.bars if self.bars >= height else height
        self.pages = pages
        self.pages = self.pages if self.pages > 0 else 1
        self.note = note
        self.states = numpy.zeros((1, 1, 1), dtype = numpy.bool_)
        #: Each cell's note (-1: its column's) and velocity
        self.notes = numpy.full((1, 1, 1), -1, dtype = numpy.int16)
        self.velocities = numpy.ones((1, 1, 1))
        # Notes sounding; pads held: (x, y) → [(page, column, row), turned off when let go]
        self._sounding = []
        self._held = {}
        self._selected = None
        self.current_bar = 0
        self.current_page = 0
        self._page = 0
        self._bar = 0
        self.follow = follow
        self.rate = rate
        super().__init__(x, y, width, height, **kwargs)
        self.states.fill(False)
        self.current_color = current_color
        self.current_active_color = current_active_color
        self.step = step
        self.page = page
        self.bar = bar

    @property
    def step(self) -> int:
        """The current row over all pages: ``current_page * bars + current_bar``; setting it moves there without playing it."""
        return self.current_page * self.bars + self.current_bar

    @step.setter
    def step(self, value: int) -> None:
        self.scroll(int(value))

    @property
    def page(self) -> int:
        """The page shown and edited."""
        return self._page

    @page.setter
    def page(self, value: int) -> None:
        self._page = int(value) % self.pages
        self.updated = True
        self._page_shown()

    @property
    def bar(self) -> int:
        """The first row shown (at the top), from 0 to ``bars - height``."""
        return self._bar

    @bar.setter
    def bar(self, value: int) -> None:
        self._bar = min(max(int(value), 0), max(self.bars - self.rect.h, 0))
        self.updated = True

    @property
    def current_top(self) -> int:
        return self._bar

    @property
    def current_bottom(self) -> int:
        return self._bar + self.rect.h - 1

    def note_of(self, page: int, column: int, row: int) -> int:
        """The note of a cell: its own, or its column's."""
        note = int(self.notes[page, column, row])
        return note if note >= 0 else self.note + column

    def handle_press(self, x: int, y: int, velocity: float):
        row = self.rect.h - 1 - y + self._bar
        if row >= self.bars:
            return
        cell = (self._page, x, row)
        self._selected = cell
        if self.states[cell]:
            # Off when let go, unless edited while held
            self._held[(x, y)] = [cell, True]
        else:
            self.states[cell] = True
            self.notes[cell] = -1
            self.velocities[cell] = self.velocity_of(velocity)
            self._held[(x, y)] = [cell, False]
        self.updated = True

    def handle_release(self, x: int, y: int, velocity: float):
        held = self._held.pop((x, y), None)
        if held is not None and held[1]:
            self.states[held[0]] = False
            self.updated = True

    def _edited(self) -> list:
        if self._held:
            for held in self._held.values():
                held[1] = False
            return [held[0] for held in self._held.values()]
        return [self._selected] if self._selected is not None else []

    def set_note(self, note: int) -> None:
        """Give the held cells, or the last one pressed, a note of their own (-1: their column's)."""
        for cell in self._edited():
            self.notes[cell] = min(max(int(note), -1), 127)

    def set_velocity(self, velocity: float) -> None:
        """Set the velocity (0-1) of the held cells, or the last one pressed."""
        for cell in self._edited():
            self.velocities[cell] = min(max(float(velocity), 1 / 127), 1.0)

    def play(self, step: int) -> None:
        """
        Move to ``step`` (wrapping through rows, then pages): the last row's
        notes end, RowPlayed with the row's active columns, then their notes.
        """
        self.silence()
        self.scroll(step)
        row = self.states[self.current_page, :, self.current_bar]
        columns = tuple(int(i) for i in numpy.flatnonzero(row))
        notes = tuple(self.note_of(self.current_page, column, self.current_bar) for column in columns)
        self.emit(pyxelwidgets.events.RowPlayed(self, self.current_bar, columns, notes))
        for column, note in zip(columns, notes):
            if 0 <= note <= 127 and note not in self._sounding:
                self._sounding.append(note)
                velocity = float(self.velocities[self.current_page, column, self.current_bar])
                self.emit(pyxelwidgets.events.NoteOn(self, note, self.humanize(velocity)))

    def silence(self) -> None:
        """End the notes sounding (NoteOff)."""
        for note in self._sounding:
            self.emit(pyxelwidgets.events.NoteOff(self, note, 0.0))
        self._sounding = []

    def advance(self) -> None:
        """Play the next row."""
        self.play(self.step + 1)

    def scroll(self, step: int) -> None:
        """Move to ``step`` without playing it; with ``follow`` the view keeps the row in the middle."""
        self.current_page = (step // self.bars) % self.pages
        self.current_bar = step % self.bars
        if self.follow:
            self._page = self.current_page
            # Centered, an even height has one more row below
            self.bar = self.current_bar - (self.rect.h - 1) // 2
        self.updated = True
        self._page_shown()

    def save_state(self) -> dict:
        return {'cells': self.states.copy(), 'notes': self.notes.copy(), 'velocities': self.velocities.copy(),
                'step': self.step, 'page': self._page, 'bar': self._bar}

    def load_state(self, state: dict) -> None:
        for key, array in (('cells', self.states), ('notes', self.notes), ('velocities', self.velocities)):
            if key in state:
                _copy_overlap(array, state[key])
        for key in ('step', 'page', 'bar'):
            if key in state:
                setattr(self, key, state[key])
        self.updated = True

    def draw(self) -> None:
        area = self.rect.origin
        rows = self.states[self._page, :, self._bar:self._bar + self.rect.h]
        self.buffer[area.slice] = self.inactive_color
        self.buffer[:, self.rect.h - rows.shape[1]:] = numpy.fliplr(numpy.where(rows[..., None], self.active_color, self.inactive_color))
        if self._page == self.current_page and self._bar <= self.current_bar <= self.current_bottom:
            self.buffer[:, self.current_bottom - self.current_bar] = numpy.where(self.states[self.current_page, :, self.current_bar, None], self.current_active_color, self.current_color)

    def _resize(self, width, height) -> bool:
        shape = (self.pages, width, self.bars)
        self.states = _fit(self.states, shape, False)
        self.notes = _fit(self.notes, shape, -1)
        self.velocities = _fit(self.velocities, shape, 1.0)
        self._page %= self.pages
        self.scroll(self.step)
        self.bar = self._bar
        return True

# DrumPads class
class DrumPads(Velocity, Widget):
    """
    Drum pads: one note per pad, ``note`` at the bottom-left, then left to
    right and up (4x4 from 36 is the General MIDI kit), moved by ``bank``
    times the pads. Emits NoteOn/NoteOff; pads light while held (brighter for
    harder hits) and for notes received, e.g. a DAW playing the pattern back.
    """

    emits = (pyxelwidgets.events.NoteOn, pyxelwidgets.events.NoteOff)

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 note: int = 36,
                 bank: int = 0,
                 velocity: bool = True,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Orange,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(64, 32, 0),
                 **kwargs):
        """
        note: int = 36, optional
            The note of the bottom-left pad.
        bank: int = 0, optional
            Moves every pad's note by this many times the number of pads (e.g. linked to bank buttons).
        velocity: bool = True, optional
            Light pads by how hard they're hit (and pressed); else fully.
        """
        self.note = note
        self.bank = bank
        self.velocity = velocity
        self.levels = numpy.zeros((1, 1))
        super().__init__(x, y, width, height, active_color = active_color, inactive_color = inactive_color, **kwargs)

    def note_at(self, x: int, y: int) -> int | None:
        """The note of the pad at ``x``, ``y``, or None if it is beyond 127."""
        note = self.note + self.bank * self.rect.area + x + y * self.rect.w
        return note if 0 <= note <= 127 else None

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        note = self.note_at(x, y)
        if note is not None:
            velocity = self.humanize(self.velocity_of(velocity))
            self._light(x, y, velocity)
            self.emit(pyxelwidgets.events.NoteOn(self, note, velocity))

    def handle_release(self, x: int, y: int, velocity: float) -> None:
        note = self.note_at(x, y)
        if note is not None:
            self._light(x, y, 0.0)
            self.emit(pyxelwidgets.events.NoteOff(self, note, velocity))

    def handle_pressure(self, x: int, y: int, pressure: float) -> None:
        if self.levels[x, y] > 0:
            self._light(x, y, max(pressure, 0.01))

    def receive(self, values: dict) -> None:
        """Light the pad of a received ``note`` (or ``x``/``y``, ``cell``) by its velocity or value."""
        super().receive(values)
        level = _level(values)
        if level is None:
            return
        if 'note' in values:
            cell = int(values['note']) - self.note - self.bank * self.rect.area
        elif 'cell' in values:
            cell = int(values['cell'])
        else:
            cell = int(values.get('x', 0)) + int(values.get('y', 0)) * self.rect.w
        if 0 <= cell < self.rect.area:
            self._light(cell % self.rect.w, cell // self.rect.w, level)

    def _light(self, x: int, y: int, level: float) -> None:
        self.levels[x, y] = (level if self.velocity else 1.0) if level > 0 else 0.0
        self.updated = True

    def draw(self) -> None:
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                level = self.levels[x, y]
                if self.note_at(x, y) is None:
                    self.buffer[x, y] = pyxelwidgets.color.Colors.Black
                elif level > 0:
                    # Never too dim to see
                    self.buffer[x, y] = self.active_color * (0.3 + 0.7 * level)
                else:
                    self.buffer[x, y] = self.inactive_color

    def _resize(self, width, height) -> bool:
        self.levels = numpy.zeros((width, height))
        return True

def _meter_fall(meter, value: float, shown: float, peak: float, peak_time: float, now: float, elapsed: float) -> tuple:
    """A meter's (shown level, peak, peak time) after ``elapsed`` seconds showing ``value`` (Meter, MeterBank)."""
    if meter.falloff > 0 and value < shown:
        shown = max(value, shown - meter.falloff * elapsed)
    else:
        shown = value
    if shown >= peak:
        peak, peak_time = shown, now
    elif now - peak_time >= meter.hold:
        peak = shown
    return shown, peak, peak_time

def _meter_bar(meter, shown: float, peak: float, cells: int) -> list:
    """The colors of a meter's ``cells`` from the bottom (or left) showing ``shown`` and ``peak``."""
    peak = min(int(peak * cells - 1e-9), cells - 1) if meter.hold > 0 and peak > shown else -1
    colors = []
    for index in range(cells):
        # Each cell covers its part of the range; the top lit one is partly lit
        lit = min(1.0, max(0.0, shown * cells - index))
        level = (index + 0.5) / cells
        color = meter.danger_color if level > meter.danger else meter.warning_color if level > meter.warning else meter.active_color
        if lit > 0:
            color = color * lit
        elif index != peak:
            color = meter.inactive_color
        colors.append(color)
    return colors

# Meter class
class Meter(ValueWidget):
    """
    A level meter: the value lights a bar from the bottom (or the left), in
    ``active_color`` up to ``warning``, ``warning_color`` up to ``danger`` and
    ``danger_color`` above. The highest level stays lit for ``hold`` seconds.
    Display only: values come from links, mappings (a DAW's meters) or code.
    """

    class Direction(enum.Enum):
        Vertical    = enum.auto()
        Horizontal  = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 direction: Direction = Direction.Vertical,
                 warning: float = 0.6,
                 danger: float = 0.85,
                 hold: float = 1.0,
                 falloff: float = 0.0,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Lime,
                 warning_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Yellow,
                 danger_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Red,
                 interactive: bool = False,
                 propagation: Propagation = Propagation.Pass,
                 clock: typing.Callable[[], float] = time.monotonic,
                 **kwargs):
        """
        warning, danger: float, optional
            Levels (0.0-1.0) where the bar turns ``warning_color`` and ``danger_color``.
        hold: float = 1.0, optional
            Seconds the peak stays lit; 0 doesn't show it.
        falloff: float = 0.0, optional
            How fast the bar falls, in full heights per second; 0 falls at once (e.g. meters a DAW already smooths).
        direction: Direction = Direction.Vertical, optional
            The bar grows from the bottom (Vertical) or from the left (Horizontal).
        warning_color, danger_color: Color, optional
            The bar above ``warning`` and above ``danger``.
        """
        self.direction = direction
        self.warning = warning
        self.danger = danger
        self.hold = hold
        self.falloff = falloff
        self.warning_color = warning_color
        self.danger_color = danger_color
        self.clock = clock
        self._shown = 0.0
        self._peak = 0.0
        self._peak_time = clock()
        self._last = clock()
        super().__init__(x, y, width, height, interactive = interactive, active_color = active_color,
                         propagation = propagation, **kwargs)
        self._shown = self._peak = self._value

    @property
    def level(self) -> float:
        """The level shown: the value, or above it while falling."""
        return self._shown

    @property
    def peak(self) -> float:
        return self._peak

    def render(self, time = None) -> bool:
        now = self.clock()
        elapsed, self._last = now - self._last, now
        shown, peak, self._peak_time = _meter_fall(self, self._value, self._shown, self._peak, self._peak_time, now, elapsed)
        if (shown, peak) != (self._shown, self._peak):
            self._shown, self._peak = shown, peak
            self.updated = True
        return super().render(time)

    def draw(self) -> None:
        vertical = self.direction == Meter.Direction.Vertical
        for index, color in enumerate(_meter_bar(self, self._shown, self._peak, self.rect.h if vertical else self.rect.w)):
            if vertical:
                self.buffer[:, index] = color
            else:
                self.buffer[index, :] = color

# ClipLauncher class
class ClipLauncher(Timed, Widget):
    """
    A grid of clips, columns are tracks and rows scenes (scene 0 at the top).
    Pressing a clip queues it (blinking) and it starts on the next ``rate``
    from its clock, a bar by default, stopping the track's playing clip;
    pressing a playing clip queues it to stop (pulsing). Without a clock
    (``clock = Clock.Off``) clips start and stop at once. Emits ClipQueued,
    ClipStarted and ClipStopped.
    """

    emits = (pyxelwidgets.events.ClipQueued, pyxelwidgets.events.ClipStarted, pyxelwidgets.events.ClipStopped)

    actions = {'launch_scene': 'int', 'stop_track': 'int', 'stop_all': None, 'advance': None, **Timed.clock_actions}

    Empty, Stopped, Playing = 0, 1, 2

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 rate: Rate = 'bar',
                 filled: bool = True,
                 blink_rate: Rate | float = '1/8',
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Lime,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(0, 72, 72),
                 empty_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Black,
                 **kwargs):
        """
        rate: Rate = 'bar', optional
            When queued clips start and stop: every ``rate`` of its clock.
        filled: bool = True, optional
            Every slot starts with a clip; False starts empty (clips come from a DAW).
        blink_rate: Rate | float = '1/8', optional
            How fast queued clips blink.
        active_color, inactive_color, empty_color: Color, optional
            Playing clips, stopped clips and empty slots.
        """
        self.rate = rate
        self.filled = filled
        self.blink_rate = blink_rate
        self.empty_color = empty_color
        self.clips = numpy.zeros((1, 1), dtype = numpy.int8)
        # Track (column) → (row, launch) waiting for the clock
        self.queued = {}
        super().__init__(x, y, width, height, active_color = active_color, inactive_color = inactive_color, **kwargs)
        self.clips.fill(ClipLauncher.Stopped if filled else ClipLauncher.Empty)

    def playing(self, track: int) -> int | None:
        """The row of the clip playing in ``track``, or None."""
        rows = numpy.flatnonzero(self.clips[track] == ClipLauncher.Playing)
        return int(rows[0]) if len(rows) else None

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        state = self.clips[x, y]
        if state == ClipLauncher.Playing:
            self.queue(x, y, False)
        elif state == ClipLauncher.Stopped:
            self.queue(x, y, True)

    def queue(self, x: int, y: int, launch: bool) -> None:
        """Start (``launch``) or stop the clip at ``x``, ``y`` on the next ``rate``, or at once without a clock."""
        previous = self.queued.get(x)
        if previous is not None:
            self.animate_cell(x, previous[0], None)
        self.queued[x] = (y, launch)
        self.emit(pyxelwidgets.events.ClipQueued(self, x, y, launch))
        if self.clock == Clock.Off:
            self.advance()
            return
        animation = pyxelwidgets.animation.Blink(self.blink_rate) if launch else pyxelwidgets.animation.Pulse(self.blink_rate)
        self.animate_cell(x, y, animation)

    def launch_scene(self, scene: int) -> None:
        """Queue the clips of ``scene`` (a row, 0 at the top); tracks without one stop."""
        y = self.rect.h - 1 - int(scene)
        if not 0 <= y < self.rect.h:
            return
        for x in range(self.rect.w):
            if self.clips[x, y] != ClipLauncher.Empty:
                if self.clips[x, y] != ClipLauncher.Playing:
                    self.queue(x, y, True)
            else:
                self.stop_track(x)

    def stop_track(self, track: int) -> None:
        """Queue the clip playing in ``track`` (a column) to stop."""
        if 0 <= track < self.rect.w:
            row = self.playing(track)
            if row is not None:
                self.queue(track, row, False)

    def stop_all(self) -> None:
        for track in range(self.rect.w):
            self.stop_track(track)

    def play(self, count: int | None = None) -> None:
        """Start and stop the queued clips (called every ``rate`` by its clock)."""
        queued, self.queued = self.queued, {}
        for x, (y, launch) in queued.items():
            self.animate_cell(x, y, None)
            row = self.playing(x)
            if row is not None and (launch or row == y):
                self.clips[x, row] = ClipLauncher.Stopped
                self.emit(pyxelwidgets.events.ClipStopped(self, x, row))
            if launch and self.clips[x, y] != ClipLauncher.Empty:
                self.clips[x, y] = ClipLauncher.Playing
                self.emit(pyxelwidgets.events.ClipStarted(self, x, y))
        self.updated = True

    def advance(self) -> None:
        """Start and stop the queued clips now."""
        self.play()

    def receive(self, values: dict) -> None:
        """
        Show a clip's state from elsewhere (a DAW): at ``x``/``y`` (or ``cell``),
        playing if the value is above 0, else stopped; ``flash`` shows it queued.
        """
        level = _level(values)
        if 'cell' in values:
            x, y = values['cell'] % self.rect.w, values['cell'] // self.rect.w
        else:
            x, y = values.get('x', 0), values.get('y', 0)
        if level is None or not (0 <= x < self.rect.w and 0 <= y < self.rect.h):
            return
        if values.get('flash'):
            self.animate_cell(x, y, pyxelwidgets.animation.Blink(self.blink_rate))
            return
        self.animate_cell(x, y, None)
        if level > 0:
            row = self.playing(x)
            if row is not None:
                self.clips[x, row] = ClipLauncher.Stopped
            self.clips[x, y] = ClipLauncher.Playing
        else:
            self.clips[x, y] = ClipLauncher.Stopped
        self.updated = True

    def save_state(self) -> dict:
        return {'clips': self.clips.copy()}

    def load_state(self, state: dict) -> None:
        if 'clips' in state:
            _copy_overlap(self.clips, state['clips'])
            self.updated = True

    def draw(self) -> None:
        colors = {ClipLauncher.Empty: self.empty_color, ClipLauncher.Stopped: self.inactive_color, ClipLauncher.Playing: self.active_color}
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                state = self.clips[x, y]
                queued = self.queued.get(x)
                # A queued clip blinks (or pulses) in the playing color
                self.buffer[x, y] = self.active_color if queued is not None and queued[0] == y else colors[int(state)]

    def _resize(self, width, height) -> bool:
        old = self.clips
        self.clips = numpy.full((width, height), ClipLauncher.Stopped if getattr(self, 'filled', True) else ClipLauncher.Empty, dtype = numpy.int8)
        _copy_overlap(self.clips, old)
        self.queued = {x: queued for x, queued in self.queued.items() if x < width and queued[0] < height}
        return True

# XY class
class XY(ValueWidget):
    """A two dimensional value (x, y) set by pressing anywhere in the area."""

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 x_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Cyan,
                 y_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Magenta,
                 value: tuple = (0.0, 0.0),
                 spring: bool = False,
                 rest: tuple = (0.5, 0.5),
                 **kwargs):
        """
        x_color, y_color: Color, optional
            The column of the x value and the row of the y value.
        value: tuple = (0.0, 0.0), optional
            Initial (x, y), each from 0.0 to 1.0.
        spring: bool = False, optional
            Goes back to ``rest`` when every pad is let go, like a joystick.
        rest: tuple = (0.5, 0.5), optional
            Where ``spring`` brings it back to.

        Holding a pad and pressing others sets values within the held pad.
        """
        super().__init__(x, y, width, height, value = value, **kwargs)
        self.x_color = x_color
        self.y_color = y_color
        self.spring = spring
        self.rest = rest
        self._held_button = None
        self._pressed = set()

    def _clamp(self, value) -> tuple:
        return tuple(round(min(1.0, max(0.0, v)), 6) for v in value)

    def _delta(self, old, new) -> tuple:
        return tuple(n - o for o, n in zip(old, new))

    def handle_press(self, x: int, y: int, velocity: float):
        self._pressed.add((x, y))
        if self._held_button is not None:
            self.set_value(self._calc_xy_value_with_magnitude(*self._held_button, x, y))
        else:
            self.set_value(self._calc_xy_value(x, y, velocity))

    def handle_hold(self, x: int, y: int, velocity: float):
        if self._held_button is None:
            self._held_button = (x, y)
            self.set_value(self._calc_xy_value_with_magnitude(x, y, x, y))

    def handle_release(self, x: int, y: int, velocity: float):
        self._pressed.discard((x, y))
        if self._held_button == (x, y):
            self._held_button = None
        if self.spring and not self._pressed:
            self.set_value(self.rest)

    def draw(self) -> None:
        area = self.rect.origin
        x_point = self._find_x_point()
        y_point = self._find_y_point()
        self.buffer[area.slice] = self.inactive_color
        self.buffer[x_point, area.slice[1]] = self.x_color * self._value[0]
        self.buffer[area.slice[0], y_point] = self.y_color * self._value[1]
        min_v = self._min_v[x_point][y_point]
        coefficient_x = ((self.value[0] - min_v[0]) * self.rect.w) / 2
        coefficient_y = ((self.value[1] - min_v[1]) * self.rect.h) / 2
        color = (self.x_color * coefficient_x) + (self.y_color * coefficient_y)
        self.buffer[x_point, y_point] = color

    def _resize(self, width, height) -> bool:
        self._min_v = [[self._calc_xy_value(x, y, 0.0) for y in range(height)] for x in range(width)]
        self._max_v = [[self._calc_xy_value(x, y, 1.0) for y in range(height)] for x in range(width)]
        return True

    def _find_x_point(self):
        point = (self._value[0] * self.rect.w)
        if point > 0.0:
            point = point - 1 if point % 1.0 == 0.0 else point
        return int(point)
    
    def _find_y_point(self):
        point = (self._value[1] * self.rect.h)
        if point > 0.0:
            point = point - 1 if point % 1.0 == 0.0 else point
        return int(point)

    def _calc_x_value(self, x: int, value: float) -> float:
        return round(((x / self.rect.w) + (value / self.rect.w)), 6)
    
    def _calc_y_value(self, y: int, value: float) -> float:
        return round(((y / self.rect.h) + (value / self.rect.h)), 6)

    def _calc_xy_value(self, x: int, y: int, value: float):
        return [self._calc_x_value(x, value), self._calc_y_value(y, value)]
    
    def _calc_x_magnitude(self, x: int) -> float:
        return self._calc_x_value(x, (x + 1) / self.rect.w)
    
    def _calc_y_magnitude(self, y: int) -> float:
        return self._calc_y_value(y, (y + 1) / self.rect.h)

    def _calc_xy_magnitude(self, x: int, y: int):
        return [self._calc_x_magnitude(x), self._calc_y_magnitude(y)]
    
    def _calc_xy_value_with_magnitude(self, val_x: int, val_y: int, mag_x: int, mag_y: int):
        return [self._calc_x_value(val_x, self._calc_x_magnitude(mag_x)), self._calc_y_value(val_y, self._calc_y_magnitude(mag_y))]

# Text class
class Text(Widget):
    """
    Text in a 3x5 pixel font (``pyxelwidgets.font``), e.g. a tempo or a track
    name, vertically centered. Text that doesn't fit scrolls (``scroll``) at
    ``speed`` columns per second. Display only: presses pass through.
    """

    class Align(enum.Enum):
        Left    = enum.auto()
        Center  = enum.auto()
        Right   = enum.auto()

    class Scroll(enum.Enum):
        #: Scroll only when the text is wider than the widget
        Auto    = enum.auto()
        Always  = enum.auto()
        Off     = enum.auto()

    #: Empty columns between the end of scrolling text and its start
    GAP = 3

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 text: str = '',
                 align: Align = Align.Left,
                 scroll: Scroll = Scroll.Auto,
                 speed: float = 8.0,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Invisible,
                 propagation: Propagation = Propagation.Pass,
                 clock: typing.Callable[[], float] = time.monotonic,
                 **kwargs):
        """
        text: str = '', optional
            What it shows.
        align: Align = Align.Left, optional
            Where text that fits sits: left, centered or right.
        scroll: Scroll = Scroll.Auto, optional
            Scrolling: when the text doesn't fit (Auto), Always, or Off.
        speed: float = 8.0, optional
            Scrolling speed in columns per second.
        """
        self._text = str(text)
        self._bitmap = pyxelwidgets.font.text_bitmap(self._text)
        self.align = align
        self.scroll = scroll
        self.speed = speed
        self.clock = clock
        self._start = clock()
        self._offset = 0
        super().__init__(x, y, width, height, inactive_color = inactive_color, propagation = propagation, **kwargs)

    @property
    def text(self) -> str:
        return self._text

    def save_state(self) -> dict:
        return {'text': self._text}

    def load_state(self, state: dict) -> None:
        if 'text' in state:
            self.text = state['text']

    def receive(self, values: dict) -> None:
        """Show received ``text`` (e.g. a DAW's track name or timecode)."""
        super().receive(values)
        text = values.get('text', values.get('state'))
        if isinstance(text, str):
            self.text = text

    @text.setter
    def text(self, value) -> None:
        value = str(value)
        if value != self._text:
            self._text = value
            self._bitmap = pyxelwidgets.font.text_bitmap(value)
            # Scrolling starts over
            self._start = self.clock()
            self._offset = 0
            self.updated = True

    @property
    def scrolling(self) -> bool:
        if self.scroll == Text.Scroll.Off or self.speed <= 0 or not self._text:
            return False
        return self.scroll == Text.Scroll.Always or self._bitmap.shape[0] > self.rect.w

    def render(self, time = None) -> bool:
        if self.scrolling:
            period = self._bitmap.shape[0] + Text.GAP
            offset = int((self.clock() - self._start) * self.speed) % period
            if offset != self._offset:
                self._offset = offset
                self.updated = True
        return super().render(time)

    def draw(self) -> None:
        self.buffer[:] = self.inactive_color
        bitmap = self._bitmap
        if self.scrolling:
            # The text followed by a gap, repeated, starting at the scroll offset
            strip = numpy.zeros((bitmap.shape[0] + Text.GAP, bitmap.shape[1]), dtype = bool)
            strip[:bitmap.shape[0]] = bitmap
            columns = strip[(numpy.arange(self.rect.w) + self._offset) % strip.shape[0]]
            left = 0
        else:
            columns = bitmap[:self.rect.w] if self.align != Text.Align.Right else bitmap[max(bitmap.shape[0] - self.rect.w, 0):]
            free = self.rect.w - columns.shape[0]
            left = {Text.Align.Left: 0, Text.Align.Center: free // 2, Text.Align.Right: free}[self.align]
        # Vertically centered; rows that don't fit are cut from the top
        bottom = (self.rect.h - pyxelwidgets.font.HEIGHT) // 2
        for row in range(pyxelwidgets.font.HEIGHT):
            y = bottom + row
            if 0 <= y < self.rect.h:
                lit = columns[:, row]
                xs = numpy.flatnonzero(lit) + left
                self.buffer[xs, y] = self.active_color

# ChordPads class
class ChordPads(Velocity, Widget):
    """
    Chords in key: columns are the degrees of ``scale`` (I, II, III... from the
    left, then on in the next octave), rows kinds of chords built on them from
    the scale's notes (``CHORDS``, from the bottom). A pad plays its chord's
    notes (NoteOn, NoteOff); a note two chords share ends with the last one.
    """

    emits = (pyxelwidgets.events.NoteOn, pyxelwidgets.events.NoteOff)

    #: Each row from the bottom: (name, the chord's notes in scale notes from the degree);
    #: more rows repeat them an octave up
    CHORDS = (('triad', (0, 2, 4)), ('seventh', (0, 2, 4, 6)), ('first inversion', (2, 4, 7)),
              ('second inversion', (4, 7, 9)), ('sus2', (0, 1, 4)), ('sus4', (0, 3, 4)),
              ('ninth', (0, 2, 4, 6, 8)), ('open', (0, 4, 9)))

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 octave: int = 4,
                 scale: Scale = Scale.Major,
                 root: Root = Root.C,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Lime,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(0, 40, 64),
                 root_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(80, 0, 80),
                 **kwargs):
        """
        octave: int = 4, optional
            The first column's chords start on the root in this octave (4 with C: MIDI note 48).
        scale, root: optional
            The key the chords are in.
        root_color: Color, optional
            The columns of the root (I).
        """
        self.octave = octave
        self.scale = scale
        self.root = root
        self.root_color = root_color
        # Pads held → the notes they play; notes sounding → how many pads play them
        self._held = {}
        self._counts = {}
        super().__init__(x, y, width, height, active_color = active_color, inactive_color = inactive_color, **kwargs)

    def chord_at(self, x: int, y: int) -> list:
        """The notes of the pad at ``x``, ``y`` (those up to 127)."""
        notes = scale_notes(self.scale, self.root)
        base = self.root.value + 12 * self.octave
        first = next((index for index, note in enumerate(notes) if note >= base), len(notes))
        steps = len(SCALES[self.scale.name])
        _, chord = ChordPads.CHORDS[y % len(ChordPads.CHORDS)]
        first += x + (y // len(ChordPads.CHORDS)) * steps
        return [notes[first + step] for step in chord if 0 <= first + step < len(notes)]

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        notes = self.chord_at(x, y)
        if not notes or (x, y) in self._held:
            return
        self._held[(x, y)] = notes
        velocity = self.velocity_of(velocity)
        for note in notes:
            self._counts[note] = self._counts.get(note, 0) + 1
            if self._counts[note] == 1:
                self.emit(pyxelwidgets.events.NoteOn(self, note, self.humanize(velocity)))
        self.updated = True

    def handle_release(self, x: int, y: int, velocity: float) -> None:
        for note in self._held.pop((x, y), []):
            self._counts[note] -= 1
            if not self._counts[note]:
                del self._counts[note]
                self.emit(pyxelwidgets.events.NoteOff(self, note, velocity))
        self.updated = True

    def draw(self) -> None:
        steps = len(SCALES[self.scale.name])
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                if (x, y) in self._held:
                    color = self.active_color
                elif not self.chord_at(x, y):
                    color = pyxelwidgets.color.Colors.Black
                elif x % steps == 0:
                    color = self.root_color
                else:
                    color = self.inactive_color
                self.buffer[x, y] = color

# Arpeggiator class
class Arpeggiator(Timed, Velocity, Widget):
    """
    Plays the notes held on it one at a time, every ``rate``, in ``mode``
    over ``octaves``. Its pads are the notes of ``scale`` (each row an octave
    above the one below); notes can also come from links (``add``/``remove``,
    e.g. a Keyboard's NoteOn/NoteOff). With ``latch`` notes keep playing when
    let go, until new ones are pressed. Emits NoteOn and NoteOff.
    """

    emits = (pyxelwidgets.events.NoteOn, pyxelwidgets.events.NoteOff)

    # Called 24 times a step, to time gates
    divisions = 24

    actions = {'advance': None, 'play': 'int', 'add': 'int', 'remove': 'int', 'clear': None, **Timed.clock_actions}

    class Mode(enum.Enum):
        """Up, Down, up then down (UpDown), at random, or in the order they were pressed (Played)."""
        Up      = enum.auto()
        Down    = enum.auto()
        UpDown  = enum.auto()
        Random  = enum.auto()
        Played  = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 rate: Rate = '1/16',
                 mode: Mode = Mode.Up,
                 octaves: int = 1,
                 gate: float = 0.5,
                 latch: bool = False,
                 octave: int = 4,
                 scale: Scale = Scale.Major,
                 root: Root = Root.C,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Cyan,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(24, 24, 24),
                 root_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(64, 0, 64),
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.White,
                 **kwargs):
        """
        mode: Mode = Mode.Up, optional
            The order notes play in.
        octaves: int = 1, optional
            The notes play in this many octaves, one after the other (1 to 4).
        gate: float = 0.5, optional
            How long each note sounds, in steps (up to 1). Without a clock it ends when the next one plays.
        latch: bool = False, optional
            Notes keep playing when let go; pressing after letting go of every pad starts new ones.
        octave: int = 4, optional
            The bottom-left pad is the root in this octave (4 with C: MIDI note 48).
        scale, root: optional
            The notes of the pads.
        root_color, current_color: Color, optional
            The root's pads, and the note playing.
        rate: Rate = '1/16', optional
            How often a note plays (a note value).
        """
        if not 1 <= octaves <= 4:
            raise ValueError(f'octaves must be from 1 to 4, got {octaves!r}')
        if not 0.0 < gate <= 1.0:
            raise ValueError(f'gate must be more than 0 and at most 1 step, got {gate!r}')
        self.rate = rate
        self.mode = mode
        self.octaves = octaves
        self.gate = gate
        self._latch = latch
        self.octave = octave
        self.scale = scale
        self.root = root
        self.root_color = root_color
        self.current_color = current_color
        #: The notes held, in the order they came
        self.held = []
        # Pads and links holding notes; velocities by note
        self._fingers = 0
        self._velocities = {}
        self._index = -1
        self._heading = 1
        self._sounding = None
        self._position = 0.0
        self._last_count = None
        self._slot = None
        self._gate_end = None
        super().__init__(x, y, width, height, active_color = active_color, inactive_color = inactive_color, **kwargs)

    @property
    def latch(self) -> bool:
        return self._latch

    @latch.setter
    def latch(self, value: bool) -> None:
        self._latch = bool(value)
        if not self._latch and not self._fingers:
            # Nothing holds the latched notes any more
            self.clear()

    def note_at(self, x: int, y: int) -> int | None:
        """The note of the pad at ``x``, ``y``, or None past 127."""
        notes = scale_notes(self.scale, self.root)
        base = self.root.value + 12 * self.octave
        index = next((i for i, note in enumerate(notes) if note >= base), len(notes)) + x + y * len(SCALES[self.scale.name])
        return notes[index] if 0 <= index < len(notes) else None

    def _sequence(self) -> list:
        # (note, the held note it comes from) in the order they play
        held = list(self.held) if self.mode == Arpeggiator.Mode.Played else sorted(self.held)
        notes = [(note + 12 * octave, note) for octave in range(self.octaves) for note in held if note + 12 * octave <= 127]
        if self.mode == Arpeggiator.Mode.Down:
            notes.reverse()
        elif self.mode == Arpeggiator.Mode.UpDown:
            notes = notes + notes[-2:0:-1]
        return notes

    def sequence(self) -> list:
        """The notes in the order they play (Random picks from them)."""
        return [note for note, _ in self._sequence()]

    def add(self, note: int, velocity: float = 1.0) -> None:
        """Hold ``note`` (from a link or code), as a pad would."""
        note = int(note)
        if not 0 <= note <= 127:
            return
        if self._latch and not self._fingers:
            # A new chord after letting go
            self.held.clear()
        self._fingers += 1
        if note not in self.held:
            self.held.append(note)
        self._velocities[note] = self.velocity_of(velocity)
        self.updated = True

    def remove(self, note: int) -> None:
        """Let go of ``note``; with ``latch`` it keeps playing."""
        self._fingers = max(self._fingers - 1, 0)
        if not self._latch and int(note) in self.held:
            self.held.remove(int(note))
            if not self.held:
                self.silence()
        self.updated = True

    def clear(self) -> None:
        """Stop playing every note."""
        self.held.clear()
        self.silence()
        self.updated = True

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        note = self.note_at(x, y)
        if note is not None:
            self.add(note, velocity)

    def handle_release(self, x: int, y: int, velocity: float) -> None:
        note = self.note_at(x, y)
        if note is not None:
            self.remove(note)

    def play(self, count: int) -> None:
        """Play the ``count``-th note of ``sequence`` (wrapped); the sounding one ends first."""
        self.silence()
        notes = self._sequence()
        if not notes:
            return
        if self.mode == Arpeggiator.Mode.Random:
            self._index = self._random.randrange(len(notes))
        else:
            self._index = int(count) % len(notes)
        note, held = notes[self._index]
        self._sounding = note
        self.emit(pyxelwidgets.events.NoteOn(self, note, self.humanize(self._velocities.get(held, 1.0))))
        self.updated = True

    def advance(self) -> None:
        """Play the next note."""
        self.play(self._index + 1)

    def silence(self) -> None:
        """End the sounding note (NoteOff)."""
        if self._sounding is not None:
            note, self._sounding, self._gate_end = self._sounding, None, None
            self.emit(pyxelwidgets.events.NoteOff(self, note, 0.0))
            self.updated = True

    def tick(self, count: int) -> None:
        """Called by its clock ``divisions`` times a step: plays a note each step and ends it after ``gate``."""
        last, self._last_count = self._last_count, count
        if not self.running:
            self.silence()
            self._last_count = None
            return
        if self.clock == Clock.Transport:
            self._position = count / self.divisions
            if last is not None and count <= last:
                self._slot = None
        elif last is not None:
            self._position += (count - last) / self.divisions
        if self._gate_end is not None and self._position >= self._gate_end:
            self.silence()
        slot = math.floor(self._position)
        if slot == self._slot:
            return
        self._slot = slot
        if self.clock == Clock.Transport:
            self.play(slot)
        else:
            self.advance()
        if self._sounding is not None:
            self._gate_end = slot + min(max(float(self.gate), 1 / self.divisions), 1.0)

    def draw(self) -> None:
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                note = self.note_at(x, y)
                if note is None:
                    color = pyxelwidgets.color.Colors.Black
                elif note == self._sounding:
                    color = self.current_color
                elif note in self.held:
                    color = self.active_color
                elif (note - self.root.value) % 12 == 0:
                    color = self.root_color
                else:
                    color = self.inactive_color
                self.buffer[x, y] = color

# Euclidean class
def euclidean(pulses: int, steps: int, rotation: int = 0) -> list:
    """``pulses`` hits spread as evenly as they go over ``steps`` (a list of bools), moved right by ``rotation``."""
    if steps <= 0:
        return []
    pulses = min(max(int(pulses), 0), steps)
    pattern = [(index * pulses) % steps < pulses for index in range(steps)]
    rotation %= steps
    return pattern[-rotation:] + pattern[:-rotation] if rotation else pattern

class Euclidean(Timed, Velocity, Widget):
    """
    Euclidean rhythms: each row is a voice playing ``pulses`` hits spread
    evenly over its length (at most the width), every ``rate``. Press a pad
    to set its row's hits to the pads up to it (again: none); press past the
    row's end to make it longer; hold a pad and press another in its row to
    turn the rhythm by the distance. Row ``y`` plays ``note + y`` (NoteOn, and
    NoteOff on the next step).
    """

    emits = (pyxelwidgets.events.NoteOn, pyxelwidgets.events.NoteOff)

    actions = {'advance': None, 'play': 'int', 'reset': None, 'select': 'int', 'set_pulses': 'int', 'set_rotation': 'int',
               'set_length': 'int', **Timed.clock_actions}

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 rate: Rate = '1/16',
                 note: int = 36,
                 length: int | None = None,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Orange,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(24, 24, 24),
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(0, 64, 0),
                 current_active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.White,
                 **kwargs):
        """
        note: int = 36, optional
            The bottom row's note; each row above plays the next one.
        length: int, optional
            How many steps new rows have (up to the width). Defaults to the width.
        current_color, current_active_color: Color, optional
            Each row's playing step, without and with a hit.
        rate: Rate = '1/16', optional
            The length of a step (a note value).
        """
        self.rate = rate
        self.note = note
        self.length = length
        self.current_color = current_color
        self.current_active_color = current_active_color
        #: Per row: hits, rotation and length (None: ``length``)
        self.pulses = [0]
        self.rotations = [0]
        self.lengths = [None]
        self._count = 0
        self._sounding = set()
        self._held = {}
        self._selected = 0
        super().__init__(x, y, width, height, active_color = active_color, inactive_color = inactive_color, **kwargs)

    def row_length(self, row: int) -> int:
        length = self.lengths[row] if self.lengths[row] is not None else (self.length or self.rect.w)
        return min(max(int(length), 1), self.rect.w)

    def pattern(self, row: int) -> list:
        return euclidean(self.pulses[row], self.row_length(row), self.rotations[row])

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        self._selected = y
        for (held_x, held_y), held in self._held.items():
            if held_y == y and held_x != x:
                # Turn the rhythm by the distance
                self.rotations[y] = (self.rotations[y] + x - held_x) % self.row_length(y)
                held[0] = False
                self.updated = True
                return
        self._held[(x, y)] = [True]

    def handle_release(self, x: int, y: int, velocity: float) -> None:
        held = self._held.pop((x, y), None)
        if held is None or not held[0]:
            return
        if x >= self.row_length(y):
            self.lengths[y] = x + 1
        else:
            self.pulses[y] = 0 if self.pulses[y] == x + 1 else x + 1
        self.updated = True

    def select(self, row: int) -> None:
        """Make ``row`` (0 at the bottom) the one ``set_pulses``, ``set_rotation`` and ``set_length`` change."""
        self._selected = min(max(int(row), 0), self.rect.h - 1)

    def set_pulses(self, pulses: int) -> None:
        """Set the hits of the last row pressed (or selected)."""
        self.pulses[self._selected] = min(max(int(pulses), 0), self.row_length(self._selected))
        self.updated = True

    def set_rotation(self, rotation: int) -> None:
        """Set how far the last row pressed is turned."""
        self.rotations[self._selected] = int(rotation) % self.row_length(self._selected)
        self.updated = True

    def set_length(self, length: int) -> None:
        """Set the length of the last row pressed (up to the width)."""
        self.lengths[self._selected] = min(max(int(length), 1), self.rect.w)
        self.pulses[self._selected] = min(self.pulses[self._selected], self.lengths[self._selected])
        self.updated = True

    def play(self, count: int) -> None:
        """Play step ``count`` of every row (each wrapped to its length): the last hits end, the new ones start."""
        self.silence()
        self._count = int(count)
        for row in range(self.rect.h):
            pattern = self.pattern(row)
            note = self.note + row
            if pattern and pattern[self._count % len(pattern)] and 0 <= note <= 127:
                self._sounding.add(note)
                self.emit(pyxelwidgets.events.NoteOn(self, note, self.humanize(self.velocity_of(1.0))))
        self.updated = True

    def advance(self) -> None:
        self.play(self._count + 1)

    def silence(self) -> None:
        for note in sorted(self._sounding):
            self.emit(pyxelwidgets.events.NoteOff(self, note, 0.0))
        self._sounding.clear()

    def reset(self) -> None:
        """Take every row's hits away."""
        self.pulses = [0] * self.rect.h
        self.rotations = [0] * self.rect.h
        self.updated = True

    def save_state(self) -> dict:
        return {'pulses': list(self.pulses), 'rotations': list(self.rotations), 'lengths': list(self.lengths)}

    def load_state(self, state: dict) -> None:
        for key in ('pulses', 'rotations', 'lengths'):
            values = state.get(key)
            if isinstance(values, list):
                current = getattr(self, key)
                current[:min(len(values), len(current))] = values[:len(current)]
        self.updated = True

    def draw(self) -> None:
        for y in range(self.rect.h):
            pattern = self.pattern(y)
            playing = self._count % len(pattern) if pattern else -1
            for x in range(self.rect.w):
                if x >= len(pattern):
                    color = pyxelwidgets.color.Colors.Black
                elif x == playing:
                    color = self.current_active_color if pattern[x] else self.current_color
                else:
                    color = self.active_color if pattern[x] else self.inactive_color
                self.buffer[x, y] = color

    def _resize(self, width, height) -> bool:
        for name, fill in (('pulses', 0), ('rotations', 0), ('lengths', None)):
            values = getattr(self, name)
            setattr(self, name, (values + [fill] * height)[:height])
        self._selected = min(self._selected, height - 1)
        return True

# Automaton class
def parse_rule(rule: str) -> tuple:
    """A life-like rule 'B3/S23' as (birth counts, survival counts)."""
    parts = {part[0]: part[1:] for part in str(rule).replace(' ', '').upper().split('/') if part[:1] in ('B', 'S')}
    try:
        birth = {int(digit) for digit in parts['B']}
        survive = {int(digit) for digit in parts.get('S', '')}
    except (KeyError, ValueError):
        raise ValueError(f'a rule is written like "B3/S23" (births, then survivals by neighbours), got {rule!r}') from None
    if not birth <= set(range(9)) or not survive <= set(range(9)):
        raise ValueError(f'neighbour counts are 0 to 8, got {rule!r}')
    return birth, survive

class Automaton(Timed, Velocity, Widget):
    """
    A cellular automaton (Conway's Life by default) making notes: every
    ``rate`` a generation passes and cells born play the note of their row
    (in ``scale``), louder to the right, up to ``max_notes`` at once (NoteOn,
    NoteOff on the next generation). Press pads to turn cells on or off.
    """

    emits = (pyxelwidgets.events.NoteOn, pyxelwidgets.events.NoteOff)

    actions = {'advance': None, 'randomize': None, 'clear': None, **Timed.clock_actions}

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 rate: Rate = '1/8',
                 rule: str = 'B3/S23',
                 wrap: bool = True,
                 reseed: bool = True,
                 density: float = 0.3,
                 max_notes: int = 4,
                 octave: int = 4,
                 scale: Scale = Scale.MinorPentatonic,
                 root: Root = Root.C,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Lime,
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.White,
                 **kwargs):
        """
        rule: str = 'B3/S23', optional
            How many neighbours make a cell born (B) and keep one alive (S):
            B3/S23 is Life, B36/S23 HighLife, B2/S Seeds, B3678/S34678 Day & Night.
        wrap: bool = True, optional
            Edges join the other side.
        reseed: bool = True, optional
            Start again at random when every cell dies or nothing changes any more.
        density: float = 0.3, optional
            How many cells ``randomize`` (and reseeding) turns on, from 0 to 1.
        max_notes: int = 4, optional
            The most notes a generation plays; the lowest rows first.
        octave: int = 4, optional
            The bottom row plays the root in this octave (4 with C: MIDI note 48).
        scale, root: optional
            The rows' notes, from the bottom.
        current_color: Color, optional
            Cells just born.
        rate: Rate = '1/8', optional
            How often a new generation grows (a note value).
        """
        parse_rule(rule)
        if not 0.0 <= density <= 1.0:
            raise ValueError(f'density must be from 0 to 1, got {density!r}')
        self.rate = rate
        self.rule = rule
        self.wrap = wrap
        self.reseed = reseed
        self.density = density
        self.max_notes = max_notes
        self.octave = octave
        self.scale = scale
        self.root = root
        self.current_color = current_color
        self.cells = numpy.zeros((1, 1), dtype = numpy.bool_)
        self.born = numpy.zeros((1, 1), dtype = numpy.bool_)
        # Generations before, to notice when nothing changes
        self._history = []
        self._sounding = []
        self.generation = 0
        super().__init__(x, y, width, height, active_color = active_color, **kwargs)

    def row_note(self, y: int) -> int | None:
        notes = scale_notes(self.scale, self.root)
        index = next((i for i, note in enumerate(notes) if note >= self.root.value + 12 * self.octave), len(notes)) + y
        return notes[index] if 0 <= index < len(notes) else None

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        self.cells[x, y] = not self.cells[x, y]
        self.born[x, y] = False
        self._history.clear()
        self.updated = True

    def randomize(self) -> None:
        """Turn cells on at random (``density`` of them)."""
        self.cells = numpy.array([[self._random.random() < self.density for _ in range(self.rect.h)] for _ in range(self.rect.w)],
                                 dtype = numpy.bool_)
        self.born[:] = False
        self._history.clear()
        self.updated = True

    def clear(self) -> None:
        self.cells[:] = False
        self.born[:] = False
        self.silence()
        self.updated = True

    def _neighbours(self) -> numpy.ndarray:
        cells = self.cells.astype(numpy.int8)
        if self.wrap:
            return sum(numpy.roll(numpy.roll(cells, dx, 0), dy, 1)
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0))
        padded = numpy.pad(cells, 1)
        w, h = cells.shape
        return sum(padded[1 + dx:1 + dx + w, 1 + dy:1 + dy + h] for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0))

    def play(self, count: int | None = None) -> None:
        """Pass a generation and play the cells born."""
        self.silence()
        birth, survive = parse_rule(self.rule)
        neighbours = self._neighbours()
        cells = numpy.where(self.cells, numpy.isin(neighbours, list(survive)), numpy.isin(neighbours, list(birth)))
        self.born = cells & ~self.cells
        self.cells = cells
        self.generation += 1
        if self.reseed and (not cells.any() or any(numpy.array_equal(cells, old) for old in self._history)):
            self.randomize()
        else:
            self._history = (self._history + [cells.copy()])[-2:]
        played = set()
        for y in range(self.rect.h):
            columns = numpy.flatnonzero(self.born[:, y])
            note = self.row_note(y)
            if not len(columns) or note is None or note in played or len(played) >= self.max_notes:
                continue
            played.add(note)
            # Louder to the right
            hit = 0.4 + 0.6 * (columns.max() / max(self.rect.w - 1, 1))
            self._sounding.append(note)
            self.emit(pyxelwidgets.events.NoteOn(self, note, self.humanize(self.velocity_of(hit))))
        self.updated = True

    def advance(self) -> None:
        self.play()

    def silence(self) -> None:
        for note in self._sounding:
            self.emit(pyxelwidgets.events.NoteOff(self, note, 0.0))
        self._sounding = []

    def save_state(self) -> dict:
        return {'cells': self.cells.copy()}

    def load_state(self, state: dict) -> None:
        if 'cells' in state:
            _copy_overlap(self.cells, state['cells'])
            self.updated = True

    def draw(self) -> None:
        self.buffer[:] = self.inactive_color
        self.buffer[self.cells] = self.active_color
        self.buffer[self.born & self.cells] = self.current_color

    def _resize(self, width, height) -> bool:
        self.cells = _fit(self.cells, (width, height), False)
        self.born = numpy.zeros((width, height), dtype = numpy.bool_)
        self._history = []
        return True

# TapTempo class
class TapTempo(Widget):
    """
    Tap it in time: emits TempoTapped with the tempo of the last ``taps``
    taps (link it to the transport's tempo). It blinks on the beat, and on taps.
    """

    emits = (pyxelwidgets.events.TempoTapped,)

    actions = {'reset': None}

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 taps: int = 4,
                 timeout: float = 2.0,
                 minimum: float = 30.0,
                 maximum: float = 300.0,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Red,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(48, 0, 0),
                 clock: typing.Callable[[], float] = time.monotonic,
                 **kwargs):
        """
        taps: int = 4, optional
            How many of the last taps the tempo comes from (at least 2).
        timeout: float = 2.0, optional
            Seconds without a tap after which tapping starts over.
        minimum, maximum: float, optional
            The slowest and fastest tempo it gives.
        """
        if taps < 2:
            raise ValueError(f'taps must be at least 2, got {taps!r}')
        self.taps = taps
        self.timeout = timeout
        self.minimum = minimum
        self.maximum = maximum
        self.clock = clock
        #: The tempo tapped last, or None
        self.bpm = None
        self._times = []
        self._lit = False
        super().__init__(x, y, width, height, active_color = active_color, inactive_color = inactive_color, **kwargs)

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        now = self.clock()
        if self._times and now - self._times[-1] > self.timeout:
            self._times = []
        self._times = (self._times + [now])[-self.taps:]
        self.updated = True
        if len(self._times) < 2:
            return
        interval = (self._times[-1] - self._times[0]) / (len(self._times) - 1)
        if interval <= 0:
            return
        self.bpm = round(min(max(60.0 / interval, self.minimum), self.maximum), 2)
        self.emit(pyxelwidgets.events.TempoTapped(self, self.bpm))

    def reset(self) -> None:
        """Forget the taps."""
        self._times = []

    def render(self, time = None) -> bool:
        time = time if time is not None else pyxelwidgets.animation.now()
        tapped = bool(self._times) and self.clock() - self._times[-1] < 0.1
        lit = tapped or time.beats % 1.0 < 0.15
        if lit != self._lit:
            self._lit = lit
            self.updated = True
        return super().render(time)

    def draw(self) -> None:
        self.buffer[:] = self.active_color if self._lit else self.inactive_color

# Stepper class
class Stepper(ValueWidget):
    """
    A whole number from ``minimum`` to ``maximum`` (``number``) changed a step
    at a time: the first pad (left or bottom) goes down, the last up, the
    pads between show where it is and jump there: a point of light moves along
    them, lighting the nearest pads by how near it is. Holding a step pad repeats.
    ``value`` is the number as 0.0-1.0; link Changed with ``minimum``/``maximum``
    as the range to get the number.
    """

    actions = {'increment': None, 'decrement': None}

    class Direction(enum.Enum):
        Horizontal  = enum.auto()
        Vertical    = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 minimum: int = 0,
                 maximum: int = 7,
                 wrap: bool = False,
                 direction: Direction = Direction.Horizontal,
                 repeat: float = 0.1,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Yellow,
                 clock: typing.Callable[[], float] = time.monotonic,
                 **kwargs):
        """
        minimum, maximum: int, optional
            The range of the number.
        wrap: bool = False, optional
            Going past one end comes back at the other.
        direction: Direction = Direction.Horizontal, optional
            Down on the left and up on the right, or down at the bottom and up on top.
        repeat: float = 0.1, optional
            Seconds between steps while a step pad is held (after the device's
            hold time); 0 doesn't repeat.
        """
        if maximum <= minimum:
            raise ValueError(f'maximum must be more than minimum, got {minimum!r} and {maximum!r}')
        self.minimum = minimum
        self.maximum = maximum
        self.wrap = wrap
        self.direction = direction
        self.repeat = repeat
        self.clock = clock
        # The step pad repeating (-1 or +1) and when it next steps
        self._repeating = None
        super().__init__(x, y, width, height, active_color = active_color, **kwargs)

    def _clamp(self, value):
        # Only the numbers' places
        span = max(getattr(self, 'maximum', 1) - getattr(self, 'minimum', 0), 1)
        return round(round(min(1.0, max(0.0, value)) * span) / span, 6)

    @property
    def number(self) -> int:
        return self.minimum + round(self._value * (self.maximum - self.minimum))

    def set_number(self, number: int) -> None:
        """Set the number as input would (emits Changed)."""
        span = self.maximum - self.minimum
        number = int(number)
        if self.wrap:
            number = self.minimum + (number - self.minimum) % (span + 1)
        number = min(max(number, self.minimum), self.maximum)
        self.set_value((number - self.minimum) / span)

    def increment(self) -> None:
        self.set_number(self.number + 1)

    def decrement(self) -> None:
        self.set_number(self.number - 1)

    def _pads(self) -> int:
        return self.rect.w if self.direction == Stepper.Direction.Horizontal else self.rect.h

    def _index(self, x: int, y: int) -> int:
        return x if self.direction == Stepper.Direction.Horizontal else y

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        index, pads = self._index(x, y), self._pads()
        if pads == 1 or index == pads - 1:
            self.increment()
        elif index == 0:
            self.decrement()
        elif pads > 3:
            # The pads between: where the number is
            span = self.maximum - self.minimum
            self.set_number(self.minimum + round((index - 1) / (pads - 3) * span))

    def handle_hold(self, x: int, y: int, velocity: float) -> None:
        index, pads = self._index(x, y), self._pads()
        if self.repeat > 0 and (index == 0 or index == pads - 1):
            self._repeating = (1 if pads == 1 or index == pads - 1 else -1, self.clock() + self.repeat)

    def handle_release(self, x: int, y: int, velocity: float) -> None:
        self._repeating = None

    def render(self, time = None) -> bool:
        if self._repeating is not None:
            way, due = self._repeating
            now = self.clock()
            if now >= due:
                self.set_number(self.number + way)
                self._repeating = (way, now + self.repeat)
        return super().render(time)

    def draw(self) -> None:
        pads = self._pads()
        span = self.maximum - self.minimum
        colors = [self.inactive_color] * pads
        if pads <= 2:
            colors = [self.active_color * (0.2 + 0.8 * self._value)] * pads
        else:
            # The ends step, dim where they can't go further
            colors[0] = self.active_color * (0.15 if self.number == self.minimum and not self.wrap else 0.4)
            colors[-1] = self.active_color * (0.15 if self.number == self.maximum and not self.wrap else 0.4)
            # A point of light moves from half a pad before the first pad
            # between to half a pad after the last; each pad is as bright as
            # it is near
            between = pads - 2
            point = self._value * between - 0.5
            for pad in range(between):
                near = 1 - abs(point - pad)
                if near > 0:
                    colors[1 + pad] = self.active_color * near
        for index, color in enumerate(colors):
            if self.direction == Stepper.Direction.Horizontal:
                self.buffer[index, :] = color
            else:
                self.buffer[:, index] = color

# MeterBank class
class MeterBank(Widget):
    """
    A row of level meters, one per column (or per row, Horizontal), e.g. a
    mixer's tracks: each works like a Meter (``warning``, ``danger``, peak
    ``hold``, ``falloff``). Levels come from mappings (a received ``x`` or
    ``cell`` picks the meter: ``Meter {x+1}`` for Mackie meters), links or
    ``set_level``. Display only.
    """

    actions = {'reset': None}

    Direction = Meter.Direction

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 direction: Meter.Direction = Meter.Direction.Vertical,
                 warning: float = 0.6,
                 danger: float = 0.85,
                 hold: float = 1.0,
                 falloff: float = 0.0,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Lime,
                 warning_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Yellow,
                 danger_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Red,
                 propagation: Propagation = Propagation.Pass,
                 clock: typing.Callable[[], float] = time.monotonic,
                 **kwargs):
        """
        direction: Direction = Direction.Vertical, optional
            Vertical: a meter per column, rising from the bottom. Horizontal: one per row, from the left.
        warning, danger: float, optional
            Levels (0.0-1.0) where bars turn ``warning_color`` and ``danger_color``.
        hold: float = 1.0, optional
            Seconds peaks stay lit; 0 doesn't show them.
        falloff: float = 0.0, optional
            How fast bars fall, in full heights per second; 0 falls at once.
        warning_color, danger_color: Color, optional
            The bars above ``warning`` and above ``danger``.
        """
        self.direction = direction
        self.warning = warning
        self.danger = danger
        self.hold = hold
        self.falloff = falloff
        self.warning_color = warning_color
        self.danger_color = danger_color
        self.clock = clock
        self._last = clock()
        self.levels = [0.0]
        self._shown = [0.0]
        self._peaks = [0.0]
        self._peak_times = [self._last]
        super().__init__(x, y, width, height, active_color = active_color, propagation = propagation, **kwargs)

    @property
    def channels(self) -> int:
        return self.rect.w if self.direction == Meter.Direction.Vertical else self.rect.h

    def set_level(self, channel: int, level: float) -> None:
        """Show ``level`` (0.0-1.0) on meter ``channel`` (from the left, or the bottom)."""
        if 0 <= channel < len(self.levels):
            self.levels[channel] = round(min(max(float(level), 0.0), 1.0), 6)
            self.updated = True

    def reset(self) -> None:
        """Every meter to 0."""
        for channel in range(len(self.levels)):
            self.levels[channel] = 0.0
        self.updated = True

    def receive(self, values: dict) -> None:
        """Show a received level on the meter of its ``x`` (or ``cell``, or ``y`` when Horizontal)."""
        super().receive(values)
        level = _level(values)
        if level is None:
            return
        if 'cell' in values:
            channel = int(values['cell'])
        else:
            channel = int(values.get('x' if self.direction == Meter.Direction.Vertical else 'y', values.get('x', 0)))
        self.set_level(channel, level)

    def save_state(self) -> dict:
        return {'levels': list(self.levels)}

    def load_state(self, state: dict) -> None:
        for channel, level in enumerate(state.get('levels', [])[:len(self.levels)]):
            self.set_level(channel, level)

    def render(self, time = None) -> bool:
        now = self.clock()
        elapsed, self._last = now - self._last, now
        for channel, level in enumerate(self.levels):
            shown, peak, self._peak_times[channel] = _meter_fall(self, level, self._shown[channel], self._peaks[channel],
                                                                 self._peak_times[channel], now, elapsed)
            if (shown, peak) != (self._shown[channel], self._peaks[channel]):
                self._shown[channel], self._peaks[channel] = shown, peak
                self.updated = True
        return super().render(time)

    def draw(self) -> None:
        vertical = self.direction == Meter.Direction.Vertical
        cells = self.rect.h if vertical else self.rect.w
        for channel in range(self.channels):
            for index, color in enumerate(_meter_bar(self, self._shown[channel], self._peaks[channel], cells)):
                self.buffer[(channel, index) if vertical else (index, channel)] = color

    def _resize(self, width, height) -> bool:
        channels = self.channels
        now = self.clock()
        for name, fill in (('levels', 0.0), ('_shown', 0.0), ('_peaks', 0.0), ('_peak_times', now)):
            values = getattr(self, name)
            setattr(self, name, (values + [fill] * channels)[:channels])
        return True
