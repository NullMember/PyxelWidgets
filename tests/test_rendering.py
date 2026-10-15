import numpy
import pytest

from pyxelwidgets import (Button, ButtonGroup, Color, Colors, Fader, Group, Keyboard, Knob,
                          Sprite, Surface, buffer)
from pyxelwidgets.devices import Device
from pyxelwidgets.animation import Pulse, Time


class FakeDevice(Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent = {}

    def send_pixel(self, x, y, pixel):
        self.sent[x, y] = pixel


def setup(width = 4, height = 4):
    controller = FakeDevice(width = width, height = height)
    controller.connect()
    surface = Surface(width, height)
    surface.add_device(controller, 0, 0)
    return controller, surface


@pytest.mark.parametrize('pixel', [Colors.Red, Colors.Invisible, Color(10, 20, 30, 0.5), Color(1, 2, 3, 0.2)])
def test_pixel_buffer_round_trip(pixel):
    frame = buffer.new(2, 2, pixel)
    assert frame.dtype == numpy.uint8 and frame.shape == (2, 2, 4)
    assert Color.from_array(frame[1, 1]) == pixel


def test_to_buffer_from_pixels():
    frame = buffer.to_buffer([[Colors.Red, Colors.Lime], [Colors.Blue, Colors.Invisible]])
    assert frame[0, 1].tolist() == [0, 255, 0, 255]
    assert frame[1, 1].tolist() == [0, 0, 0, 0]


def test_composite():
    dst = buffer.new(1, 3, Colors.Blue)
    src = buffer.new(1, 3)
    src[0, 0] = Colors.Red
    src[0, 1] = Color(255, 0, 0, 0.5)
    buffer.composite(dst, src)
    assert dst[0, 0].tolist() == [255, 0, 0, 255]
    assert dst[0, 1].tolist() == [128, 0, 127, 255]
    assert dst[0, 2].tolist() == [0, 0, 255, 255]


def test_top_widget_stays_visible_when_lower_one_redraws():
    controller, surface = setup()
    lower = surface.add(Button(0, 0, 2, 2, active_color = Colors.Red))
    surface.add(Button(1, 1, 1, 1, inactive_color = Colors.Lime))
    surface.update()
    lower.value = 1.0
    surface.update()
    assert controller.sent[0, 0] == Colors.Red
    assert controller.sent[1, 1] == Colors.Lime


def test_transparent_pixels_show_widget_below():
    controller, surface = setup(3, 3)
    surface.add(Button(1, 1, 1, 1, inactive_color = Colors.Lime))
    surface.add(Knob(0, 0, 3, 3))
    surface.update()
    # The knob ring is drawn, its hollow center shows the button underneath
    assert controller.sent[1, 1] == Colors.Lime
    assert controller.sent[0, 0] == Colors.Black


def test_switching_groups_redraws_everything():
    controller, surface = setup(2, 1)
    red, blue = Group(0, 0, 2, 1), Group(0, 0, 1, 1)
    red.add(Button(0, 0, 2, 1, inactive_color = Colors.Red))
    blue.add(Button(0, 0, 1, 1, inactive_color = Colors.Blue))
    surface.add(red)
    surface.update()
    surface.remove(red)
    surface.add(blue)
    surface.update()
    assert controller.sent[0, 0] == Colors.Blue
    # Area not covered by the smaller group is cleared to black
    assert controller.sent[1, 0] == Colors.Black


def test_hiding_a_group_redraws_what_is_underneath():
    controller, surface = setup(1, 1)
    surface.add(Button(0, 0, 1, 1, inactive_color = Colors.Red))
    page = surface.add(Group(0, 0, 1, 1))
    page.add(Button(0, 0, 1, 1, inactive_color = Colors.Blue))
    surface.update()
    assert controller.sent[0, 0] == Colors.Blue
    page.visible = False
    surface.update()
    assert controller.sent[0, 0] == Colors.Red


def test_idle_frames_send_nothing():
    controller, surface = setup()
    surface.add(Fader(0, 0, 1, 4))
    surface.update()
    controller.sent.clear()
    surface.update()
    assert controller.sent == {}


def test_controller_receives_python_ints():
    received = []
    class Recorder(FakeDevice):
        def send_pixel(self, x, y, pixel):
            received.append((type(x), type(y)))
    controller = Recorder(width = 2, height = 2)
    controller.connect()
    controller.show(buffer.new(2, 2, Colors.Red))
    assert set(received) == {(int, int)}


def test_resize_updates_dependent_state():
    keyboard = Keyboard(0, 0, 4, 4)
    keyboard.width = 2
    assert keyboard.notes.shape == (2, 4)
    assert keyboard.buffer.shape == (2, 4, 4)
    fader = Fader(0, 0, 1, 4, mode = Fader.Mode.Magnitude)
    fader.height = 8
    fader.tap(0, 7)
    assert fader.value == 1.0


def test_button_group_renders_states():
    group = ButtonGroup(0, 0, 3, 1, mode = ButtonGroup.Mode.Multi)
    group.press(2, 0, 1.0)
    group.render()
    assert Color.from_array(group.buffer[2, 0]) == Colors.White
    assert Color.from_array(group.buffer[1, 0]) == Colors.Black


def test_sprite_uses_given_frames():
    frames = [buffer.new(2, 2, Colors.Red), [[Colors.Blue] * 2] * 2]
    sprite = Sprite(0, 0, 2, 2, frames = frames)
    assert len(sprite.frames) == 2
    assert Color.from_array(sprite.buffer[0, 0]) == Colors.Red


def test_pulse_scales_color_not_alpha():
    pulse = Pulse('1/4', minimum = 0.0)
    frame = buffer.new(1, 1, Color(200, 100, 50, 0.5))
    assert pulse.apply(frame, Time(0, 0.0))[0, 0].tolist() == [200, 100, 50, 128]
    assert pulse.apply(frame, Time(0, 0.5))[0, 0].tolist() == [0, 0, 0, 128]


@pytest.mark.parametrize('kind', list(Keyboard.Type))
def test_keyboard_any_size(kind):
    for width in range(1, 11):
        for height in range(1, 11):
            Keyboard(0, 0, width, height, type = kind)


def test_sequencer_redraws_when_steps_change():
    from pyxelwidgets import Sequencer
    sequencer = Sequencer(0, 0, 4, 4)
    sequencer.render()
    sequencer.steps = 32
    assert sequencer.render()


def test_sprite_changes_frames_every_rate():
    from pyxelwidgets.animation import Time
    frames = [buffer.new(1, 1, Colors.Red), buffer.new(1, 1, Colors.Blue)]
    sprite = Sprite(0, 0, 1, 1, frames = frames, rate = '1/4')
    sprite.render(Time(0.0, 0.5))
    assert Color.from_array(sprite.buffer[0, 0]) == Colors.Red
    assert sprite.render(Time(0.0, 1.2)) and Color.from_array(sprite.buffer[0, 0]) == Colors.Blue
    assert not sprite.render(Time(0.0, 1.5))
    seconds = Sprite(0, 0, 1, 1, frames = frames, rate = 0.5)
    seconds.render(Time(0.6, 0.0))
    assert Color.from_array(seconds.buffer[0, 0]) == Colors.Blue


def test_sprite_fits_frames_from_the_bottom_left():
    sprite = Sprite(0, 0, 2, 2, frames = [[[Colors.Red]]])
    assert sprite.frames[0].shape == (2, 2, 4) and Color.from_array(sprite.frames[0][0, 0]) == Colors.Red
    sprite.width = 1
    assert sprite.frames[0].shape == (1, 2, 4)
    with pytest.raises(ValueError):
        Sprite(0, 0, 1, 1, rate = 0)
