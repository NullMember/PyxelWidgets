"""
Bindings connect a device's named controls (knobs, faders, encoders, buttons)
to widgets or actions::

    surface.bind(device, 'Knob1', volume)                        # glides to the knob
    surface.bind(device, 'Knob2', pan, takeover = Takeover.Pickup)
    surface.bind(device, 'Encoder1', cutoff, step = 1 / 64)      # relative
    surface.bind(device, 'XFader', xy, axis = 0)                 # one axis of an XY
    surface.bind(device, 'Play', transport.toggle)               # an action

Knobs and faders (ControlChanged) set the widget's value; ``takeover`` decides
what happens when they disagree with it. Encoders (ControlTurned) add
``delta * step``. Buttons (ControlPressed/Released) press and release the
widget, e.g. a Button. An action (any callable) is called with no arguments on
press, the value for knobs and faders, and the delta for encoders.

A Binding also works without a Surface: ``Binding(device, 'Knob1', fader)``;
call ``update()`` regularly (e.g. every frame) so gliding progresses.
"""

import enum
import time
import typing

import pyxelwidgets.events

__all__ = ['Binding', 'Takeover']

# One step of a 7-bit MIDI control
_RESOLUTION = 1 / 127

class Takeover(enum.Enum):
    """What an absolute control does when its position differs from the widget's value."""
    #: The widget moves to the control's value over ``glide_time``
    Glide = enum.auto()
    #: The control does nothing until it reaches the widget's value
    Pickup = enum.auto()
    #: The widget takes the control's value at once
    Jump = enum.auto()

class Binding:
    """
    Connects ``control`` events from ``source`` (a device, or a Surface with
    ``device`` naming which device) to ``target``: a widget with a 0.0-1.0
    ``value`` (or a tuple, with ``axis``), or a callable.

    ``glide_time`` is how long a glide across the whole range takes, in seconds.
    """

    def __init__(self, source, control: str, target, *,
                 device = None,
                 takeover: Takeover = Takeover.Glide,
                 glide_time: float = 0.3,
                 step: float = 1 / 64,
                 axis: int | None = None,
                 clock: typing.Callable[[], float] = time.monotonic) -> None:
        """
        takeover: Takeover = Takeover.Glide, optional
            How a knob or fader takes over a value it doesn't match: Glide moves there over
            ``glide_time``, Pickup waits until the control passes the value, Jump sets it at once.
        glide_time: float = 0.3, optional
            Seconds a glide over the whole range takes.
        step: float = 1/64, optional
            How much one step of an encoder (a relative control) moves the value.
        axis: int, optional
            Which value of a two-value widget (XY) the control sets: 0 for x, 1 for y.
        """
        self.source = source
        self.control = control
        self.target = target
        self.device = device
        self.takeover = takeover
        self.glide_time = glide_time
        self.step = step
        self.axis = axis
        self.clock = clock
        # Gliding: the value to reach and when it last moved
        self.goal = None
        self._moved = None
        # Pickup: the control's last value, whether it took over, and what it last set
        self._last_control = None
        self._engaged = False
        self._last_set = None
        source.on(pyxelwidgets.events.ControlEvent, self._handle)

    def close(self) -> None:
        """Stop following the control."""
        self.source.off(pyxelwidgets.events.ControlEvent, self._handle)

    @property
    def is_action(self) -> bool:
        return not hasattr(self.target, 'value')

    # Values

    def get(self) -> float:
        value = self.target.value
        return value[self.axis] if self.axis is not None else value

    def set(self, value: float) -> None:
        value = min(1.0, max(0.0, value))
        if self.axis is not None:
            values = list(self.target.value)
            values[self.axis] = value
            value = tuple(values)
        self.target.set_value(value)
        self._last_set = self.get()

    # Events

    def _handle(self, event) -> None:
        if event.control != self.control:
            return
        if self.device is not None and event.device is not self.device and getattr(event.device, 'name', None) != self.device:
            return
        if self.is_action:
            if isinstance(event, pyxelwidgets.events.ControlChanged):
                self.target(event.value)
            elif isinstance(event, pyxelwidgets.events.ControlTurned):
                self.target(event.delta)
            elif isinstance(event, pyxelwidgets.events.ControlPressed):
                self.target()
        elif isinstance(event, pyxelwidgets.events.ControlChanged):
            self._absolute(event.value)
        elif isinstance(event, pyxelwidgets.events.ControlTurned):
            self._relative(event.delta)
        elif isinstance(event, pyxelwidgets.events.ControlPressed):
            self.target.press(0, 0, event.velocity)
        elif isinstance(event, pyxelwidgets.events.ControlReleased):
            self.target.release(0, 0, event.velocity)

    def _relative(self, delta: int) -> None:
        self.goal = None
        self.set(self.get() + delta * self.step)

    def _absolute(self, value: float) -> None:
        if self.takeover is Takeover.Jump or (self.takeover is Takeover.Glide and self.glide_time <= 0):
            self.set(value)
        elif self.takeover is Takeover.Pickup:
            current = self.get()
            if self._last_set is None or abs(current - self._last_set) > 1e-6:
                # Changed elsewhere (or never set): wait for the control to reach it again
                self._engaged = False
            if not self._engaged:
                last = self._last_control
                self._engaged = abs(value - current) <= _RESOLUTION or (last is not None and (last - current) * (value - current) <= 0)
            if self._engaged:
                self.set(value)
        else:
            if self.goal is None:
                self._moved = self.clock()
            self.goal = value
            self.update()
        self._last_control = value

    def update(self) -> None:
        """Move a glide along; call it regularly (a Surface does every frame)."""
        if self.goal is None:
            return
        now = self.clock()
        reach = (now - self._moved) / self.glide_time
        self._moved = now
        current = self.get()
        if abs(self.goal - current) <= max(reach, 1e-6):
            self.set(self.goal)
            self.goal = None
        elif reach > 0:
            self.set(current + reach if self.goal > current else current - reach)
