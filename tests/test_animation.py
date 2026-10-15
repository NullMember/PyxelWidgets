import pytest

from pyxelwidgets import Blink, Button, Colors, Fade, Group, Pulse, Sprite, Surface, Transport
from pyxelwidgets.animation import Time, now


def at(beats = 0.0, seconds = 0.0, signature = (4, 4)):
    return Time(seconds, beats, signature)


def rgba(widget, x = 0, y = 0):
    return tuple(int(v) for v in widget.buffer[x, y])


def test_blink_follows_beats():
    button = Button(0, 0, 1, 1, inactive_color = Colors.Red)
    button.animation = Blink('1/4')
    assert button.render(at(0.0)) and rgba(button) == (255, 0, 0, 255)
    assert button.render(at(0.6)) and rgba(button) == (0, 0, 0, 0)
    assert button.render(at(1.1)) and rgba(button) == (255, 0, 0, 255)


def test_blink_off_color_and_duty():
    button = Button(0, 0, 1, 1, inactive_color = Colors.Red)
    button.animation = Blink(1.0, duty = 0.25, off_color = Colors.Blue)
    button.render(at(seconds = 0.2))
    assert rgba(button) == (255, 0, 0, 255)
    button.render(at(seconds = 0.3))
    assert rgba(button) == (0, 0, 255, 255)


def test_note_values_use_the_signature():
    button = Button(0, 0, 1, 1)
    button.animation = Blink('bar')
    button.render(at(2.5, signature = (6, 8)))   # a 6/8 bar is 3 quarter notes: second half
    assert rgba(button)[3] == 0


def test_pulse_breathes():
    button = Button(0, 0, 1, 1, inactive_color = Colors.White)
    button.animation = Pulse('1/4', minimum = 0.0)
    button.render(at(0.0))
    assert rgba(button)[:3] == (255, 255, 255)
    button.render(at(0.5))
    assert rgba(button)[:3] == (0, 0, 0)
    button.render(at(0.25))
    assert rgba(button)[0] == 128


def test_fade_in_then_removed():
    button = Button(0, 0, 1, 1, inactive_color = Colors.Red)
    button.animation = Fade(1.0)
    button.render(at(seconds = 10.0))
    assert rgba(button)[3] == 0
    button.render(at(seconds = 10.5))
    assert rgba(button)[3] == 128
    button.render(at(seconds = 11.0))
    assert button.animation is None and rgba(button) == (255, 0, 0, 255)
    # Static again: nothing to redraw
    assert not button.render(at(seconds = 12.0))


def test_fade_out_hides():
    button = Button(0, 0, 1, 1)
    button.animation = Fade('1/4', out = True)
    button.render(at(1.0))
    button.render(at(2.0))
    assert not button.visible and button.animation is None


def test_cell_animation():
    group = Button(0, 0, 2, 1, inactive_color = Colors.Red)
    group.animate_cell(1, 0, Blink('1/4'))
    group.render(at(0.6))
    assert rgba(group, 0, 0) == (255, 0, 0, 255) and rgba(group, 1, 0)[3] == 0
    group.animate_cell(1, 0, None)
    group.render(at(0.6))
    assert rgba(group, 1, 0) == (255, 0, 0, 255)


def test_animation_doesnt_corrupt_the_drawing():
    # Widgets draw onto their drawing, not the animated copy
    button = Button(0, 0, 1, 1, mode = Button.Mode.Switch, inactive_color = Colors.Red, active_color = Colors.Lime)
    button.animation = Pulse('1/4', minimum = 0.0)
    button.render(at(0.5))
    button.press(0, 0)
    button.render(at(0.0))
    assert rgba(button) == (0, 255, 0, 255)


def test_sprite_frames_untouched():
    frame = [[Colors.Red]]
    sprite = Sprite(0, 0, 1, 1, frames = [frame])
    sprite.animation = Blink('1/4')
    sprite.render(at(0.6))
    assert rgba(sprite)[3] == 0 and tuple(sprite.frames[0][0, 0]) == (255, 0, 0, 255)


def test_groups_redraw_while_children_animate():
    group = Group(0, 0, 2, 1)
    child = group.add(Button(1, 0, 1, 1, inactive_color = Colors.Red))
    child.animation = Blink('1/4')
    assert group.render(at(0.0)) and rgba(group, 1, 0)[0] == 255
    assert group.render(at(0.6)) and rgba(group, 1, 0)[3] == 0
    group.animation = Pulse('1/4', minimum = 0.0)
    group.render(at(0.5))
    child.animation = None
    group.render(at(0.5))
    assert rgba(group, 1, 0)[:3] == (0, 0, 0)


def test_time_from_transport():
    transport = Transport(90, signature = (3, 4), sync = True)
    time = now(transport)
    # Stopped: free running at its tempo
    assert time.beats == pytest.approx(time.seconds * 1.5) and time.signature == (3, 4)
    transport.locate(2)
    transport.play()
    assert now(transport).beats == 2.0
    assert now().beats == pytest.approx(now().seconds * 2, rel = 1e-3)


def test_surface_and_app_supply_transport_time():
    from pyxelwidgets import App
    surface = Surface(1, 1)
    app = App(surface)
    assert surface.transport is app.transport
    button = surface.add(Button(0, 0, 1, 1))
    button.animation = Blink('1/4')
    surface.update()
    app.close()


def test_invalid_rates():
    with pytest.raises(ValueError):
        Blink('1/0')
    with pytest.raises(ValueError):
        Pulse(0)
