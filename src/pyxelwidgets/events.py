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
    """The Sequencer playhead moved to ``step``; ``active`` if that step is on."""
    step: int
    active: bool

@dataclasses.dataclass(frozen = True)
class PageChanged(WidgetEvent):
    page: int

@dataclasses.dataclass(frozen = True)
class RowPlayed(WidgetEvent):
    """The Tracker playhead moved to ``row``; ``columns`` lists the active cells in it."""
    row: int
    columns: tuple

# Surface events

@dataclasses.dataclass(frozen = True)
class Frame(Event):
    """Emitted by a Surface before rendering each frame."""
    surface: typing.Any
    frame: int

@dataclasses.dataclass(frozen = True)
class Control(Event):
    """Input from a non-grid control (knob, fader, encoder, extra button) of a controller."""
    surface: typing.Any
    controller: str
    control: str
    action: typing.Any
    value: typing.Any
