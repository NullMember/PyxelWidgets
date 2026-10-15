import time

import pytest

from pyxelwidgets import buffer
from pyxelwidgets.color import Color, Colors
from pyxelwidgets.devices import Control, Device, RGB
from pyxelwidgets.events import ControlChanged, PadEvent, PadHeld, PadPressed, PadReleased


class FakeDevice(Device):
    model = 'Fake'
    grid = (4, 2)
    controls = (Control('Volume', 'absolute'),)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent = []

    def send_pixel(self, x, y, value):
        self.sent.append((x, y, value))


def connected(**kwargs):
    device = FakeDevice(**kwargs)
    device.connect()
    return device


def test_describe():
    info = FakeDevice.describe()
    assert info['grid'] == {'width': 4, 'height': 2}
    assert info['controls'] == [{'name': 'Volume', 'kind': 'absolute'}]
    assert info['colors']['model'] == 'PassThrough'


def test_show_sends_only_changes_and_offsets():
    device = connected()
    device.fill(Colors.Red)
    assert len(device.sent) == 8 and device.sent[0] == (0, 0, Colors.Red)
    device.sent.clear()
    device.fill(Colors.Red)
    assert device.sent == []
    device.show(buffer.new(2, 2, Colors.Blue), x = 3, y = 1)
    assert device.sent == [(3, 1, Colors.Blue)]
    device.invalidate()
    device.sent.clear()
    device.fill(Colors.Red)
    assert len(device.sent) == 8


def test_show_needs_connection_and_uses_color_model():
    class RGBDevice(FakeDevice):
        color_model = RGB(bits = 7)
    device = RGBDevice()
    device.fill(Colors.White)
    assert device.sent == []
    device.connect()
    device.fill(Colors.White)
    assert device.sent[0] == (0, 0, (127, 127, 127))


def test_pad_events_and_bounds():
    device = connected()
    events = []
    device.on(PadEvent, events.append)
    device.set_button(1, 1, 0.5)
    device.set_button(1, 1, 0.0)
    device.set_button(9, 9, 1.0)
    assert [(type(e), e.x, e.y, e.velocity, e.device) for e in events] == [
        (PadPressed, 1, 1, 0.5, device), (PadReleased, 1, 1, 0.0, device)]


def test_hold_detected_on_show_and_by_timer():
    device = connected(held_time = 0.05)
    held = []
    device.on(PadHeld, held.append)
    device.set_button(0, 0, 1.0)
    time.sleep(0.06)
    device.fill(Colors.Black)
    assert len(held) == 1
    device.set_button(2, 1, 1.0)
    device.start_input_timer(0.005)
    time.sleep(0.1)
    device.close()
    assert [(e.x, e.y) for e in held] == [(0, 0), (2, 1)]
    assert device.terminated


def test_control_events_are_plain_emits():
    device = connected()
    seen = []
    device.on(ControlChanged, seen.append)
    device.emit(ControlChanged(device, 'Volume', 0.25))
    assert seen[0].value == 0.25


def test_unknown_argument_raises():
    with pytest.raises(TypeError):
        FakeDevice(widht = 3)
