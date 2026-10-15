import pytest

from pyxelwidgets import (Binding, Button, Changed, ControlChanged, ControlPressed, ControlReleased, ControlTurned,
                          Fader, Surface, Takeover, XY)
from pyxelwidgets.devices import Device


class FakeDevice(Device):
    def send_pixel(self, x, y, color):
        pass

    def knob(self, value, control = 'Knob1'):
        self.emit(ControlChanged(self, control, value))

    def turn(self, delta, control = 'Encoder1'):
        self.emit(ControlTurned(self, control, delta))

    def button(self, pressed, control = 'Play'):
        self.emit((ControlPressed if pressed else ControlReleased)(self, control, 1.0 if pressed else 0.0))


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def device():
    return FakeDevice()


def test_jump(device):
    fader = Fader(0, 0, 1, 8)
    Binding(device, 'Knob1', fader, takeover = Takeover.Jump)
    device.knob(0.7)
    device.knob(0.5, control = 'Knob2')
    assert fader.value == 0.7


def test_glide_reaches_value_over_time(device):
    clock = Clock()
    fader = Fader(0, 0, 1, 8)
    changes = []
    fader.on(Changed, lambda e: changes.append(e.value))
    binding = Binding(device, 'Knob1', fader, glide_time = 1.0, clock = clock)
    device.knob(1.0)
    assert fader.value == 0.0 and binding.goal == 1.0
    clock.now = 0.25
    binding.update()
    assert fader.value == 0.25
    device.knob(0.4)       # a new goal on the way
    clock.now = 0.35
    binding.update()
    assert fader.value == pytest.approx(0.35)
    clock.now = 0.5
    binding.update()
    assert fader.value == 0.4 and binding.goal is None
    clock.now = 2
    binding.update()
    assert changes == [0.25, 0.35, 0.4]


def test_glide_small_moves_are_immediate(device):
    # Turning a knob normally moves by small steps: no audible lag
    clock = Clock()
    fader = Fader(0, 0, 1, 8, value = 0.5)
    binding = Binding(device, 'Knob1', fader, clock = clock)
    device.knob(0.5 + 1 / 127)
    clock.now = 1 / 60
    binding.update()
    assert fader.value == pytest.approx(0.5 + 1 / 127, abs = 1e-6)


def test_glide_time_zero_jumps(device):
    fader = Fader(0, 0, 1, 8)
    Binding(device, 'Knob1', fader, glide_time = 0)
    device.knob(0.6)
    assert fader.value == 0.6


def test_pickup(device):
    fader = Fader(0, 0, 1, 8, value = 0.5)
    Binding(device, 'Knob1', fader, takeover = Takeover.Pickup)
    device.knob(0.1)
    device.knob(0.3)
    assert fader.value == 0.5
    device.knob(0.6)       # crossed 0.5: takes over
    assert fader.value == 0.6
    device.knob(0.2)
    assert fader.value == 0.2
    fader.set_value(0.9)   # changed on the grid: wait for the knob again
    device.knob(0.3)
    assert fader.value == 0.9
    device.knob(0.9)
    assert fader.value == 0.9
    device.knob(0.8)
    assert fader.value == 0.8


def test_pickup_when_landing_on_value(device):
    fader = Fader(0, 0, 1, 8, value = 0.5)
    Binding(device, 'Knob1', fader, takeover = Takeover.Pickup)
    device.knob(0.5)
    device.knob(0.55)
    assert fader.value == 0.55


def test_relative(device):
    fader = Fader(0, 0, 1, 8, value = 0.5)
    Binding(device, 'Encoder1', fader, step = 0.1)
    device.turn(2)
    assert fader.value == pytest.approx(0.7)
    device.turn(-10)
    assert fader.value == 0.0


def test_axis(device):
    xy = XY(0, 0, 4, 4)
    Binding(device, 'Knob1', xy, axis = 1, takeover = Takeover.Jump)
    device.knob(0.75)
    assert xy.value == (0.0, 0.75)


def test_button_presses_widget(device):
    momentary = Button(0, 0, 1, 1)
    toggle = Button(1, 0, 1, 1, mode = Button.Mode.Switch)
    Binding(device, 'Play', momentary)
    Binding(device, 'Play', toggle)
    device.button(True)
    assert momentary.value == 1.0 and toggle.value == 1.0
    device.button(False)
    assert momentary.value == 0.0 and toggle.value == 1.0
    device.button(True)
    device.button(False)
    assert toggle.value == 0.0


def test_actions(device):
    calls = []
    Binding(device, 'Play', lambda: calls.append('play'))
    Binding(device, 'Knob1', lambda value: calls.append(value))
    Binding(device, 'Encoder1', lambda delta: calls.append(delta))
    device.button(True)
    device.button(False)
    device.knob(0.5)
    device.turn(-3)
    assert calls == ['play', 0.5, -3]


def test_close(device):
    fader = Fader(0, 0, 1, 8)
    binding = Binding(device, 'Knob1', fader, takeover = Takeover.Jump)
    binding.close()
    device.knob(1.0)
    assert fader.value == 0.0


def test_non_interactive_widget_is_not_changed(device):
    fader = Fader(0, 0, 1, 8, interactive = False)
    Binding(device, 'Knob1', fader, takeover = Takeover.Jump)
    device.knob(1.0)
    assert fader.value == 0.0


def test_surface_bind_filters_device_and_glides_each_frame(device):
    other = FakeDevice()
    surface = Surface(8, 8)
    surface.add_device(device)
    surface.add_device(other)
    fader = surface.add(Fader(0, 0, 1, 8))
    clock = Clock()
    binding = surface.bind(device, 'Knob1', fader, glide_time = 1.0, clock = clock)
    other.knob(1.0)
    assert binding.goal is None
    device.knob(1.0)
    clock.now = 0.5
    surface.update()
    assert fader.value == 0.5
    clock.now = 1.0
    surface.update()
    assert fader.value == 1.0
    surface.remove_device(device)
    assert surface.bindings == []
    device.knob(0.0)
    assert fader.value == 1.0


def test_surface_bind_by_device_name(device):
    surface = Surface(8, 8)
    surface.add_device(device)
    fader = surface.add(Fader(0, 0, 1, 8))
    binding = surface.bind(device.name, 'Knob1', fader, takeover = Takeover.Jump)
    device.knob(0.3)
    assert fader.value == 0.3
    surface.unbind(binding)
    device.knob(0.9)
    assert fader.value == 0.3
