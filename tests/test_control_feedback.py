"""Control lights, LED rings and screens: drivers' messages and what a Surface shows on them."""

import pytest

from pyxelwidgets import Button, Fader, Surface
from pyxelwidgets.binding import Takeover
from pyxelwidgets.color import Colors
from pyxelwidgets.devices.ableton import Push2
from pyxelwidgets.devices.akai import APC40MK2, APCMini
from pyxelwidgets.devices.arturia import MiniLab3
from pyxelwidgets.devices.novation import LaunchControlXL, LaunchkeyMK3, LaunchpadMiniMK3
from pyxelwidgets.devices.presonus import ATOM
from pyxelwidgets.events import ControlChanged, ControlPressed, ControlReleased


class Output:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(list(message))

    def close_port(self):
        pass


def device(cls, port = None, **kwargs):
    made = cls(**kwargs)
    made._midi_output = Output()
    made._midi_output_name = port or cls.ports[0]
    made.connected = True
    return made


def sent(made, buttons = False):
    """The messages sent since last asked; ``buttons``: only the APC Mini's buttons (notes from 64), not its pads."""
    messages = made._midi_output.messages[:]
    made._midi_output.messages.clear()
    return [m for m in messages if m[1] >= 64] if buttons else messages


def test_one_color_lights_are_on_for_any_bright_color():
    apc = device(APCMini)
    apc.set_control('Button_1', Colors.Red)
    apc.set_control('Button_10', Colors.Black)
    apc.set_control('Button_9', Colors.Red)          # Shift: no light
    assert sent(apc) == [[0x90, 64, 1], [0x90, 89, 0]]


def test_apc40_lights_and_rings():
    apc = device(APC40MK2)
    apc.set_control('Record_3', Colors.Red)          # track buttons: the channel is the track
    apc.set_control('Scene_0', Colors.Red)           # RGB like the pads
    apc.set_control('Play', Colors.Lime)
    apc.set_ring('DeviceKnob_2', 0.5)
    apc.set_ring('DeviceKnob_2', 0.5)                # unchanged: not sent again
    apc.set_ring('SceneKnob_7', 1.0)
    assert sent(apc) == [[0x93, 0x30, 1], [0x90, 82, 5], [0x90, 91, 1], [0xB0, 18, 64], [0xB0, 55, 127]]
    assert 'Shift' not in apc.lights() and 'DeviceKnob_0' in APC40MK2.describe()['rings']


def test_push2_white_and_color_buttons():
    push = device(Push2)
    push.set_control('Undo', Colors.White)
    push.set_control('Undo', Colors.Black)
    push.set_control('Play', Colors.Lime)
    assert sent(push) == [[0xB0, 119, 127], [0xB0, 119, 0], [0xB0, 85, 126]]


def test_atom_color_buttons_send_their_color_and_turn_on():
    atom = device(ATOM)
    atom.set_control('Play', Colors.Blue)
    atom.set_control('Stop', Colors.White)
    assert sent(atom) == [[0xB1, 109, 0], [0xB2, 109, 0], [0xB3, 109, 127], [0xB0, 109, 127], [0xB0, 111, 127]]


def test_launch_control_xl_button_lights():
    xl = device(LaunchControlXL)
    xl.set_control('Solo', Colors.Yellow)
    xl.set_control('Up', Colors.Black)
    assert sent(xl) == [[0xF0, 0, 0x20, 0x29, 2, 0x11, 0x78, 0xF, 42, 0x3F, 0xF7],
                        [0xF0, 0, 0x20, 0x29, 2, 0x11, 0x78, 0xF, 44, 0x0C, 0xF7]]


def test_minilab3_screen():
    lab = device(MiniLab3)
    lab.set_screen('Screen', ['Cutoff', '52%'])
    lab.set_screen('Screen', ['Cutoff', '52%'])
    message = sent(lab)
    assert len(message) == 1
    assert message[0][-12:] == [1, *b'Cutoff', 0, 2, *b'52%', 0, 0xF7][-12:]


def test_launchkey_screen_rows_and_clear():
    key = device(LaunchkeyMK3)
    key.set_screen('Screen', ['A very long top line', 'B'])
    key.set_screen('Screen', [])
    header = [0xF0, 0, 0x20, 0x29, 2, 0x0F]
    assert sent(key) == [header + [4, 0] + list(b'A very long top ') + [0xF7],
                         header + [4, 1] + list(b'B') + [0xF7],
                         header + [6, 0xF7]]
    big = device(LaunchkeyMK3, port = 'Launchkey 88 MK3 DAW Out')
    big.set_screen('Screen', ['', 'x'])
    assert sent(big)[0][5] == 0x12


def surface_with(made, width, height):
    surface = Surface(width, height)
    surface.add_device(made)
    return surface


def test_held_buttons_light_and_links_set_lights():
    apc = device(APCMini)
    surface = surface_with(apc, 8, 8)
    apc.emit(ControlPressed(apc, 'Button_2', 1.0))
    surface.update()
    assert sent(apc, True) == [[0x90, 65, 1]]
    apc.emit(ControlReleased(apc, 'Button_2', 0.0))
    surface.update()
    assert sent(apc, True) == [[0x90, 65, 0]]
    light = surface.light(apc, 'Button_3')
    light.configure(light = Colors.Red)
    surface.update()
    assert sent(apc, True) == [[0x90, 66, 1]]
    light.configure(light = Colors.Invisible)
    surface.update()
    assert sent(apc, True) == [[0x90, 66, 0]]


def test_a_link_set_light_wins_over_the_bound_widget():
    pad = device(LaunchpadMiniMK3, side_buttons = False)
    surface = surface_with(pad, 8, 8)
    button = surface.add(Button(0, 0, 1, 1, active_color = Colors.Lime, inactive_color = Colors.Black))
    surface.bind(pad, 'Top1', button)
    surface.update()
    sent(pad)
    surface.light(pad.name, 'Top1').configure(light = Colors.Blue)
    surface.update()
    assert pad._lit['Top1'] == (0, 0, 255, 255)


def test_rings_follow_bound_widgets():
    apc = device(APC40MK2)
    surface = surface_with(apc, 8, 5)
    fader = surface.add(Fader(0, 0, 1, 5, value = 0.25))
    surface.bind(apc, 'DeviceKnob_0', fader)
    surface.update()
    assert [0xB0, 16, 32] in sent(apc)
    fader.set_value(1.0)
    surface.update()
    assert [0xB0, 16, 127] in sent(apc)


def test_screens_show_a_moved_control_then_their_text():
    lab = device(MiniLab3)
    surface = surface_with(lab, 8, 2)
    fader = surface.add(Fader(0, 0, 1, 2, name = 'cutoff'))
    surface.bind(lab, 'Knob_0', fader, takeover = Takeover.Jump)
    screen = surface.screen(lab)
    screen.configure(text = 'Hello\nworld')
    surface.update()
    assert lab._texts['Screen'] == ('Hello', 'world')
    lab.emit(ControlChanged(lab, 'Knob_0', 0.5))
    surface.update()
    assert lab._texts['Screen'] == ('cutoff', '50%')
    surface._showing[lab.name] = (surface.bindings[0], 0)    # the time is up
    surface.update()
    assert lab._texts['Screen'] == ('Hello', 'world')


def test_layout_links_set_device_lights_and_screens():
    from pyxelwidgets import parser
    from pyxelwidgets.events import Changed
    layout = {'format': 'pyxelwidgets.layout', 'version': 3, 'surface': {'width': 8, 'height': 2},
              'devices': [{'type': 'arturia.MiniLab3', 'x': 0, 'y': 0}, {'type': 'akai.APCMini', 'x': 0, 'y': 0}],
              'widgets': [{'type': 'Fader', 'name': 'cutoff', 'x': 0, 'y': 0, 'width': 1, 'height': 2}],
              'links': [{'widget': 'cutoff', 'on': 'Changed', 'target': {'device': 0, 'control': 'Screen'}, 'option': 'text',
                         'value': 'Cutoff\n{round(value * 100)}'},
                        {'widget': 'cutoff', 'on': 'Changed', 'target': {'device': 1, 'control': 'Button_1'}, 'option': 'light',
                         'value': {'if': {'source': 'value'}, 'op': '>', 'to': 0.5, 'then': '#ff0000', 'else': '#00000000'}}]}
    ui = parser.load(layout, devices = False)
    lab, apc = device(MiniLab3), device(APCMini)
    ui.surface.add_device(lab)
    ui.surface.add_device(apc)
    ui.place_controls([lab, apc])
    ui['cutoff'].set_value(1.0)
    ui.surface.update()
    assert lab._texts['Screen'] == ('Cutoff', '100')
    assert apc._lit['Button_1'] == (255, 0, 0, 255)
    ui['cutoff'].set_value(0.0)
    ui.surface.update()
    assert 'Button_1' not in apc._lit or apc._lit['Button_1'] == (0, 0, 0, 255)
    for bad, message in (({'device': 5, 'control': 'X'}, 'index of one of the 2 devices'), ({'device': 0}, 'a device control is')):
        broken = {**layout, 'links': [{**layout['links'][0], 'target': bad}]}
        with pytest.raises(parser.LayoutError, match = message):
            parser.load(broken, devices = False)
    broken = {**layout, 'links': [{**layout['links'][0], 'option': 'visible'}]}
    with pytest.raises(parser.LayoutError, match = 'options light, text'):
        parser.load(broken, devices = False)


def test_python_code_for_device_link_targets():
    from pyxelwidgets import codegen
    layout = {'format': 'pyxelwidgets.layout', 'version': 3, 'surface': {'width': 8, 'height': 2},
              'devices': [{'type': 'arturia.MiniLab3', 'x': 0, 'y': 0}, {'type': 'akai.APCMini', 'x': 0, 'y': 0}],
              'widgets': [{'type': 'Fader', 'name': 'cutoff', 'x': 0, 'y': 0, 'width': 1, 'height': 2}],
              'links': [{'widget': 'cutoff', 'on': 'Changed', 'target': {'device': 0, 'control': 'Screen'}, 'option': 'text', 'value': 'Cutoff'},
                        {'widget': 'cutoff', 'on': 'Changed', 'target': {'device': 1, 'control': 'Button_1'}, 'option': 'light', 'value': '#ff0000'}]}
    code = codegen.standalone(layout, run = False)
    assert "screen = surface.screen(mini_lab3, 'Screen')" in code
    assert "button_1_light = surface.light(apc_mini, 'Button_1')" in code
    assert "surface.link(cutoff, screen, 'text', 'Cutoff', on = Changed)" in code
    assert "surface.link(cutoff, button_1_light, 'light', Colors.Red, on = Changed)" in code
