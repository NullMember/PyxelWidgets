"""
Typed events and the :class:`Emitter` mixin that delivers them.

Handlers subscribe to an event class and receive the event object::

    fader.on(Changed, lambda e: print(e.widget.name, e.value))

    @button.on(Pressed)
    def pressed(e):
        ...

Subscribing to a base class (e.g. ``Event`` or ``WidgetEvent``) receives every
subclass too. Handlers run in the order they were added.
"""

from __future__ import annotations

import dataclasses
import typing

class Emitter:
    """Mixin giving any object ``on``, ``off`` and ``emit``. Needs no ``__init__`` call."""

    def _event_handlers(self) -> list:
        handlers = self.__dict__.get('_handlers')
        if handlers is None:
            handlers = self.__dict__['_handlers'] = []
        return handlers

    def on(self, event_type: type, handler: typing.Callable = None):
        """Call ``handler(event)`` for every emitted ``event_type``; usable as a decorator."""
        if handler is None:
            return lambda handler: self.on(event_type, handler)
        self._event_handlers().append((event_type, handler))
        return handler

    def off(self, event_type: type, handler: typing.Callable) -> None:
        """Remove a handler added with ``on``."""
        self._event_handlers().remove((event_type, handler))

    def emit(self, event: Event) -> None:
        for event_type, handler in list(self._event_handlers()):
            if isinstance(event, event_type):
                handler(event)

@dataclasses.dataclass(frozen = True)
class Event:
    """Base class of all events."""

# Widget events

@dataclasses.dataclass(frozen = True)
class WidgetEvent(Event):
    widget: typing.Any

@dataclasses.dataclass(frozen = True)
class Pressed(WidgetEvent):
    """A pad on the widget was pressed; ``x``, ``y`` are widget coordinates."""
    x: int
    y: int
    velocity: float

@dataclasses.dataclass(frozen = True)
class Released(WidgetEvent):
    x: int
    y: int
    velocity: float

@dataclasses.dataclass(frozen = True)
class Held(WidgetEvent):
    """A pad has been held longer than the controller's ``held_time``."""
    x: int
    y: int
    velocity: float

@dataclasses.dataclass(frozen = True)
class DoublePressed(WidgetEvent):
    x: int
    y: int
    velocity: float

@dataclasses.dataclass(frozen = True)
class Pressure(WidgetEvent):
    """The pressure (aftertouch) of a held pad changed, from 0.0 to 1.0."""
    x: int
    y: int
    pressure: float

@dataclasses.dataclass(frozen = True)
class Changed(WidgetEvent):
    """Input changed the widget's value: a float, or a tuple for multi-axis widgets (XY)."""
    value: typing.Any

@dataclasses.dataclass(frozen = True)
class Resized(WidgetEvent):
    width: int
    height: int

@dataclasses.dataclass(frozen = True)
class Toggled(WidgetEvent):
    """A cell of a ButtonGroup changed state."""
    x: int
    y: int
    state: bool

@dataclasses.dataclass(frozen = True)
class NoteOn(WidgetEvent):
    note: int
    velocity: float

@dataclasses.dataclass(frozen = True)
class NoteOff(WidgetEvent):
    note: int
    velocity: float

@dataclasses.dataclass(frozen = True)
class StepPlayed(WidgetEvent):
    """
    The Sequencer playhead moved to ``step``; ``active`` if that step plays.
    ``gate`` is how long it sounds, in steps (StepEnded follows), ``velocity``
    how loud (0 when it doesn't play) and ``note`` its note. A step with
    ratchets plays several times.
    """
    step: int
    active: bool
    gate: float = 1.0
    velocity: float = 1.0
    note: int = 36

@dataclasses.dataclass(frozen = True)
class StepEnded(WidgetEvent):
    """The gate of an active Sequencer ``step`` ended: send a NoteOff on its ``note``."""
    step: int
    note: int = 36

@dataclasses.dataclass(frozen = True)
class PageChanged(WidgetEvent):
    page: int

@dataclasses.dataclass(frozen = True)
class PageShown(WidgetEvent):
    """
    The widget shows ``page`` (from 0) of its pages, whatever changed it: a
    press, a link, an action or following the playing step. ``first`` and
    ``last`` tell whether it's at an end, e.g. to dim page buttons.
    """
    page: int
    first: bool
    last: bool

@dataclasses.dataclass(frozen = True)
class ColumnChanged(WidgetEvent):
    """
    The widget's ``column`` changed, whatever changed it (PianoRoll: the first
    step shown). ``first`` and ``last`` tell whether it can't go further.
    """
    column: int
    first: bool
    last: bool

@dataclasses.dataclass(frozen = True)
class RowChanged(WidgetEvent):
    """
    The widget's ``row`` changed, whatever changed it (Sequencer: the first
    row of steps shown; PianoRoll: the rows of the scale it's moved by).
    ``first`` and ``last`` tell whether it can't go further.
    """
    row: int
    first: bool
    last: bool

@dataclasses.dataclass(frozen = True)
class RowPlayed(WidgetEvent):
    """The Tracker playhead moved to ``row``; ``columns`` lists the active cells in it, ``notes`` their notes."""
    row: int
    columns: tuple
    notes: tuple = ()

@dataclasses.dataclass(frozen = True)
class ClipQueued(WidgetEvent):
    """A ClipLauncher clip waits for its clock to start (``launch``) or stop."""
    x: int
    y: int
    launch: bool

@dataclasses.dataclass(frozen = True)
class ClipStarted(WidgetEvent):
    """A ClipLauncher clip started playing."""
    x: int
    y: int

@dataclasses.dataclass(frozen = True)
class ClipStopped(WidgetEvent):
    """A ClipLauncher clip stopped."""
    x: int
    y: int

@dataclasses.dataclass(frozen = True)
class TempoTapped(WidgetEvent):
    """A TapTempo was tapped in time: ``bpm`` is the tempo of the taps."""
    bpm: float

@dataclasses.dataclass(frozen = True)
class PresetRecalled(WidgetEvent):
    """A Presets group brought back what it stored in ``slot``."""
    slot: int

@dataclasses.dataclass(frozen = True)
class PresetStored(WidgetEvent):
    """A Presets group stored its widgets' state in ``slot``."""
    slot: int

# Device events

@dataclasses.dataclass(frozen = True)
class PadEvent(Event):
    """Input from a grid pad of a device; ``x``, ``y`` are grid coordinates."""
    device: typing.Any
    x: int
    y: int
    velocity: float

@dataclasses.dataclass(frozen = True)
class PadPressed(PadEvent):
    pass

@dataclasses.dataclass(frozen = True)
class PadReleased(PadEvent):
    pass

@dataclasses.dataclass(frozen = True)
class PadHeld(PadEvent):
    """The pad has been held longer than the device's ``held_time``."""

@dataclasses.dataclass(frozen = True)
class PadDoublePressed(PadEvent):
    """Emitted right after PadPressed when the previous press was within ``double_press_time``."""

@dataclasses.dataclass(frozen = True)
class PadPressure(PadEvent):
    """The pressure (aftertouch) of a held pad changed; ``velocity`` is the pressure from 0.0 to 1.0."""

@dataclasses.dataclass(frozen = True)
class ControlEvent(Event):
    """Input from a named non-grid control of a device (button, knob, fader, encoder, touch strip)."""
    device: typing.Any
    control: str

@dataclasses.dataclass(frozen = True)
class ControlPressed(ControlEvent):
    """A button was pressed (or a touch-sensitive control touched)."""
    velocity: float

@dataclasses.dataclass(frozen = True)
class ControlReleased(ControlEvent):
    velocity: float

@dataclasses.dataclass(frozen = True)
class ControlChanged(ControlEvent):
    """An absolute control (knob, fader) moved to ``value`` from 0.0 to 1.0."""
    value: float

@dataclasses.dataclass(frozen = True)
class ControlTurned(ControlEvent):
    """A relative control (endless encoder) turned by ``delta`` steps; negative is counter-clockwise."""
    delta: int

@dataclasses.dataclass(frozen = True)
class KeyPressed(ControlEvent):
    """A key of a device's keyboard (a control of kind ``keys``) went down: its MIDI ``note`` and ``velocity`` (0.0-1.0)."""
    note: int
    velocity: float

@dataclasses.dataclass(frozen = True)
class KeyReleased(ControlEvent):
    """A key of a device's keyboard came up."""
    note: int
    velocity: float

class ControlInput(Emitter):
    """
    One named control of a device as an emitter of its control events, so
    links and mappings can start from a knob the way they start from a widget::

        knob = ControlInput(surface, 'Knob1', device = launchpad)
        surface.link(knob, keys, 'octave', Source('delta'), on = ControlTurned, change = Link.Change.Add)

    ``source`` is the device, or a Surface (which re-emits its devices' control
    events while holding its lock) with ``device`` picking the device (or its
    name; None: any). ``device`` can be changed later, e.g. when the device is
    replaced. It listens to ``source`` only while something listens to it.
    """

    def __init__(self, source, control: str, *, device = None) -> None:
        self.source = source
        self.control = control
        self.device = device
        self.name = control

    def on(self, event_type: type, handler: typing.Callable = None):
        if handler is None:
            return lambda handler: self.on(event_type, handler)
        if not self._event_handlers():
            self.source.on(ControlEvent, self._forward)
        return super().on(event_type, handler)

    def off(self, event_type: type, handler: typing.Callable) -> None:
        super().off(event_type, handler)
        if not self._event_handlers():
            self.source.off(ControlEvent, self._forward)

    def _forward(self, event: ControlEvent) -> None:
        if event.control != self.control:
            return
        device = self.device
        if device is not None and event.device is not device and (not isinstance(device, str) or getattr(event.device, 'name', None) != device):
            return
        self.emit(event)

@dataclasses.dataclass(frozen = True)
class MessageReceived(Event):
    """An output (MIDI port, OSC, Mackie Control, ...) received ``message`` (see ``pyxelwidgets.message``)."""
    device: typing.Any
    message: typing.Any

@dataclasses.dataclass(frozen = True)
class DeviceDisconnected(Event):
    """A device's ports went away (it was unplugged); it reconnects when they're back."""
    device: typing.Any

@dataclasses.dataclass(frozen = True)
class DeviceReconnected(Event):
    """An unplugged device is back and connected again."""
    device: typing.Any

# Surface events

@dataclasses.dataclass(frozen = True)
class Frame(Event):
    """Emitted by a Surface before rendering each frame."""
    surface: typing.Any
    frame: int

# Transport events

@dataclasses.dataclass(frozen = True)
class TransportEvent(Event):
    transport: typing.Any

@dataclasses.dataclass(frozen = True)
class TransportStarted(TransportEvent):
    """Playback started at ``tick``."""
    tick: int

@dataclasses.dataclass(frozen = True)
class TransportStopped(TransportEvent):
    """Playback stopped at ``tick``."""
    tick: int

@dataclasses.dataclass(frozen = True)
class TransportLocated(TransportEvent):
    """The position was moved to ``tick``."""
    tick: int

@dataclasses.dataclass(frozen = True)
class TempoChanged(TransportEvent):
    bpm: float
