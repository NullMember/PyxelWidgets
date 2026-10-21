"""
Mappings send a widget's events to an output (a MIDI port, OSC, Mackie
Control, ...) as messages, and with ``feedback`` show what the other side
sends back on the widget::

    from pyxelwidgets.message import NoteOn, NoteOff, ControlChange, Command, Source

    Mapping(kick, synth, NoteOn(36), on = Pressed)                 # velocity from the press
    Mapping(kick, synth, NoteOff(36), on = Released)
    Mapping(volume, synth, ControlChange(7), on = Changed, feedback = True)
    Mapping(play, mackie, Command('Play'), on = Pressed, feedback = True)   # LED follows the DAW
    Mapping(clock, mackie, Command('Timecode', Source('text')), feedback = True)
    Mapping(surface.control(launchpad, 'Knob1'), synth, ControlChange(74), on = ControlChanged)

The message's Sources come from the event (see ``sources``): its fields
(``velocity``, ``value``, ``x``, ``state``, ``note``...) plus ``cell`` (the
pad's number in the widget, left to right from the bottom row), ``delta`` (a
value change in 1/127 steps) and ``value_x``/``value_y`` for two-axis values.

A device's control (``events.ControlInput``) sends like a widget, with no
feedback (it has nothing to show it on).

Feedback calls ``widget.receive(values)`` with what the received message
carries; widgets show it without emitting events, so nothing is sent back.
``surface.map(...)`` creates mappings holding the surface's lock.
"""

import contextlib
import dataclasses
import functools

import pyxelwidgets.events

__all__ = ['Mapping', 'sources', 'available']

# Who sent an event, not a value of it (a control's name: the rule names its control)
_SENDERS = ('widget', 'device', 'control')

def available(event_type: type) -> list:
    """Names of the values events of ``event_type`` give a message."""
    names = [field.name for field in dataclasses.fields(event_type) if field.name not in _SENDERS]
    if 'x' in names and 'y' in names:
        names.append('cell')
    if 'value' in names:
        # A number, or value_x/value_y for two axes (XY)
        names += ['delta', 'value_x', 'value_y']
    return names

@functools.lru_cache(maxsize = None)
def _value_names(event_type: type) -> tuple:
    return tuple(field.name for field in dataclasses.fields(event_type) if field.name not in _SENDERS)

def sources(event, widget = None, last_value = None) -> dict:
    """The values a message can take from ``event``."""
    found = {}
    for name in _value_names(type(event)):
        value = getattr(event, name)
        if isinstance(value, bool):
            value = 1.0 if value else 0.0
        if isinstance(value, tuple) and name == 'value' and len(value) == 2:
            found['value_x'], found['value_y'] = value
        elif isinstance(value, (int, float, str)):
            found[name] = value
    widget = widget if widget is not None else getattr(event, 'widget', None)
    if 'x' in found and 'y' in found and widget is not None and hasattr(widget, 'rect'):
        found['cell'] = found['x'] + found['y'] * widget.rect.w
    if isinstance(found.get('value'), float):
        found['delta'] = round((found['value'] - (last_value or 0.0)) * 127)
    return found

class Mapping:
    """
    Sends ``message`` resolved from each ``on`` event of ``widget`` to
    ``output`` (anything with ``send(message)``); with ``feedback``, messages
    the output receives that match ``message`` update the widget. Without
    ``on`` it only receives. ``lock`` is held while updating the widget.
    """

    def __init__(self, widget, output, message, *, on: type | None = None, feedback: bool = False, lock = None) -> None:
        if on is None and not feedback:
            raise ValueError('a Mapping needs an event to send on, feedback, or both')
        if feedback and not hasattr(widget, 'receive'):
            raise ValueError(f'{getattr(widget, "name", widget)} has no feedback: it can only send')
        if on is not None:
            names = available(on)
            for name in message.needs:
                if name not in names:
                    raise ValueError(f'{on.__name__} has no {name!r} for the message (it has {", ".join(names)})')
        self.widget = widget
        self.output = output
        self.message = message
        self.on = on
        self.feedback = feedback
        self.lock = lock if lock is not None else contextlib.nullcontext()
        value = getattr(widget, 'value', None)
        self._last_value = value if isinstance(value, float) else None
        if on is not None:
            widget.on(on, self._send)
        if feedback:
            output.on(pyxelwidgets.events.MessageReceived, self._receive)

    def close(self) -> None:
        if self.on is not None:
            self.widget.off(self.on, self._send)
        if self.feedback:
            self.output.off(pyxelwidgets.events.MessageReceived, self._receive)

    def _send(self, event) -> None:
        values = sources(event, self.widget, self._last_value)
        if isinstance(values.get('value'), float):
            self._last_value = values['value']
        try:
            message = self.message.resolve(values)
        except ValueError as error:
            # A computed field that can't be (ExpressionError is one)
            print(f'Mapping from {getattr(self.widget, "name", self.widget)}: {error}', flush = True)
            return
        self.output.send(message)

    def _receive(self, event) -> None:
        values = self.message.match(event.message)
        if values is None:
            return
        with self.lock:
            self.widget.receive(values)
            if isinstance(getattr(self.widget, 'value', None), float):
                self._last_value = self.widget.value
