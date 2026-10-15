import dataclasses

import pytest

from pyxelwidgets.events import Changed, Emitter, Event, Pressed, WidgetEvent


class Source(Emitter):
    pass


def test_on_off_emit_in_order():
    source, calls = Source(), []
    first = source.on(Changed, lambda e: calls.append(('first', e.value)))
    source.on(Changed, lambda e: calls.append(('second', e.value)))
    source.emit(Changed(source, 0.5))
    source.off(Changed, first)
    source.emit(Changed(source, 1.0))
    assert calls == [('first', 0.5), ('second', 0.5), ('second', 1.0)]


def test_decorator_and_base_class_subscription():
    source, seen = Source(), []

    @source.on(WidgetEvent)
    def any_widget_event(e):
        seen.append(type(e).__name__)

    source.emit(Pressed(source, 1, 2, 1.0))
    source.emit(Changed(source, 0.1))
    assert seen == ['Pressed', 'Changed']
    assert any_widget_event is not None


def test_events_are_immutable():
    event = Changed(None, 0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.value = 1.0
    assert isinstance(event, Event)


def test_pad_and_control_events():
    from pyxelwidgets.events import ControlEvent, ControlTurned, PadEvent, PadHeld
    held = PadHeld('device', 1, 2, 0.5)
    turned = ControlTurned('device', 'Encoder1', -3)
    assert isinstance(held, PadEvent) and (held.x, held.y, held.velocity) == (1, 2, 0.5)
    assert isinstance(turned, ControlEvent) and turned.delta == -3
