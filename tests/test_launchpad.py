from pyxelwidgets.color import Colors
from pyxelwidgets.devices.novation import LaunchpadMiniMK3, LaunchpadProMK3
from pyxelwidgets.events import ControlPressed, ControlReleased, Event, PadPressed


class Output:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(list(message))

    def close_port(self):
        pass


def device(cls, **kwargs):
    pad = cls(**kwargs)
    pad._midi_output = Output()
    pad.connected = True
    seen = []
    pad.on(Event, seen.append)
    return pad, seen


def test_mini_mk3_grid_starts_at_bottom_left_pad():
    pad, seen = device(LaunchpadMiniMK3)
    assert (pad.width, pad.height) == (9, 9)
    pad.decode([0x90, 11, 127])       # bottom left pad
    pad.decode([0xB0, 91, 127])       # top row, first button
    pad.decode([0xB0, 19, 127])       # right column, bottom button
    assert [(e.x, e.y) for e in seen] == [(0, 0), (0, 8), (8, 0)]
    pad.show(pad.buffer[:1, :1].copy() * 0 + 255)
    assert pad._midi_output.messages[-1][7:9] == [3, 11]


def test_side_buttons_as_controls():
    pad, seen = device(LaunchpadMiniMK3, side_buttons = False)
    assert (pad.width, pad.height) == (8, 8)
    pad.decode([0x90, 88, 100])       # top right pad
    pad.decode([0xB0, 91, 127])
    pad.decode([0xB0, 91, 0])
    pad.decode([0xB0, 89, 127])
    assert [type(e) for e in seen] == [PadPressed, ControlPressed, ControlReleased, ControlPressed]
    assert (seen[0].x, seen[0].y) == (7, 7)
    assert [e.control for e in seen[1:]] == ['Top1', 'Top1', 'Right8']
    pad.fill(Colors.White)
    leds = pad._midi_output.messages[-1][7:-1][1::5]
    assert sorted(leds) == sorted(10 * y + x for x in range(1, 9) for y in range(1, 9))


def test_pro_mk3_has_four_sides():
    pad, seen = device(LaunchpadProMK3, side_buttons = False)
    for index in (1, 10, 19, 91):
        pad.decode([0xB0, index, 127])
    assert [e.control for e in seen] == ['Bottom1', 'Left1', 'Right1', 'Top1']
    names = {b['name'] for b in LaunchpadProMK3.describe()['side_buttons']}
    assert len(names) == 32 and LaunchpadProMK3.describe()['grid'] == {'width': 10, 'height': 10}


def test_side_button_lights_match_the_grid():
    # A side button lit as a control sends what the same LED gets as part of the grid
    lit, _ = device(LaunchpadMiniMK3, side_buttons = False)
    assert 'Top1' in lit.lights() and 'Right8' in lit.lights()
    lit.set_control('Top1', Colors.Red)
    lit.set_control('Top1', Colors.Red)      # unchanged: not sent again
    lit.set_control('Knob9', Colors.Red)     # no such light: ignored
    grid, _ = device(LaunchpadMiniMK3)
    assert grid.lights() == ()
    frame = grid.buffer.copy()
    frame[0, 8] = Colors.Red
    grid.show(frame)
    assert lit._midi_output.messages == grid._midi_output.messages
    lit.invalidate()
    lit.set_control('Top1', Colors.Red)
    assert len(lit._midi_output.messages) == 2


def test_bound_controls_light_up():
    from pyxelwidgets import Button, Fader, Surface
    surface = Surface(8, 8)
    pad, _ = device(LaunchpadMiniMK3, side_buttons = False)
    surface.add_device(pad)
    button = surface.add(Button(0, 0, 1, 1, active_color = Colors.Red))
    fader = surface.add(Fader(1, 0, 1, 8))
    surface.bind(pad, 'Top1', button)
    surface.bind(pad, 'Top2', fader)

    class Transport:
        playing = False
        def toggle(self):
            self.playing = not self.playing
    transport = Transport()
    surface.bind(pad, 'Right1', transport.toggle)
    surface.update()
    assert pad._lit['Top1'] == (0, 0, 0, 255) and pad._lit['Right1'] == (0, 0, 0, 255)
    pad.decode([0xB0, 91, 127])                # Top1 pressed: the button turns on
    pad.decode([0xB0, 19, 127])                # Right1: play
    fader.value = 1.0
    surface.update()
    assert pad._lit['Top1'] == (255, 0, 0, 255) and pad._lit['Right1'] == (0, 255, 0, 255)
    assert pad._lit['Top2'] == tuple(int(v) for v in Colors.White.__array__())


def test_raw_listeners_see_messages_before_decoding():
    pad, seen = device(LaunchpadMiniMK3)
    raw = []
    pad.raw_listeners.append(raw.append)
    pad.process_midi(([0x90, 11, 127], 0.0), None)
    assert raw == [[0x90, 11, 127]] and isinstance(seen[0], PadPressed)
