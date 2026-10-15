from pyxelwidgets.color import Colors
from pyxelwidgets.devices.arturia import MiniLab3, MiniLabMK2
from pyxelwidgets.events import ControlChanged, ControlPressed, ControlReleased, ControlTurned, Event, PadPressed, PadPressure, PadReleased

HEADER = [0xF0, 0x00, 0x20, 0x6B, 0x7F, 0x42]


class Output:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(list(message))

    def close_port(self):
        pass


def device(cls):
    pad = cls()
    pad._midi_output = Output()
    pad.connected = True
    seen = []
    pad.on(Event, seen.append)
    return pad, seen


def test_pads_are_two_banks_from_the_bottom():
    for cls in (MiniLabMK2, MiniLab3):
        pad, seen = device(cls)
        assert (pad.width, pad.height) == (8, 2)
        pad.decode([0x99, 36, 127])       # bank 1, pad 1
        pad.decode([0x99, 51, 64])        # bank 2, pad 8
        pad.decode([0xA9, 51, 127])
        pad.decode([0x89, 36, 0])
        pad.decode([0x90, 36, 127])       # keys: another channel
        assert [type(e) for e in seen] == [PadPressed, PadPressed, PadPressure, PadReleased]
        assert [(e.x, e.y) for e in seen] == [(0, 0), (7, 1), (7, 1), (0, 0)]


def test_mk2_sets_up_the_working_memory():
    pad, _ = device(MiniLabMK2)
    pad.on_connect()
    messages = pad._midi_output.messages
    assert all(m[:6] == HEADER and m[6:8] == [0x02, 0x00] and m[-1] == 0xF7 for m in messages)
    assert len(messages) == 16 * 4 * 2
    # Pad 16 plays note 51 on channel 10
    assert HEADER + [0x02, 0x00, 3, 0x7F, 51, 0xF7] in messages
    assert HEADER + [0x02, 0x00, 2, 0x7F, 9, 0xF7] in messages


def test_mk2_colors_and_encoders():
    pad, seen = device(MiniLabMK2)
    pad.fill(Colors.Yellow)
    leds = {m[9]: m[10] for m in pad._midi_output.messages}
    assert leds == {led: 0x05 for led in range(0x70, 0x80)}
    pad.decode([0xB1, 22, 1])
    pad.decode([0xB1, 55, 126])
    pad.decode([0xB0, 22, 1])         # another channel
    assert [(type(e), e.control, e.delta) for e in seen] == [(ControlTurned, 'Encoder_0', 1), (ControlTurned, 'Encoder_15', -2)]


def test_minilab3_daw_mode_leds_and_screen():
    pad, seen = device(MiniLab3)
    pad.on_connect()
    assert pad._midi_output.messages[-1] == HEADER + [0x02, 0x00, 0x40, 0x6A, 0x21, 0xF7]
    pad.fill(Colors.Red)
    leds = {m[9]: m[10:13] for m in pad._midi_output.messages[1:]}
    assert sorted(leds) == list(range(0x34, 0x3C)) + list(range(0x44, 0x4C))
    assert leds[0x34] == [127, 0, 0]
    pad.show_text('Hello', 'World')
    assert pad._midi_output.messages[-1][6:9] == [0x04, 0x02, 0x60]
    assert bytes(pad._midi_output.messages[-1][-15:-1]) == b'\x01Hello\x00\x02World\x00'


def test_minilab3_controls():
    pad, seen = device(MiniLab3)
    pad.decode([0xB0, 86, 127])
    pad.decode([0xB0, 31, 0])
    pad.decode([0xB0, 28, 66])
    pad.decode([0xB0, 28, 63])
    pad.decode([0xB0, 107, 127])
    pad.decode([0xB0, 107, 0])
    assert [type(e) for e in seen] == [ControlChanged, ControlChanged, ControlTurned, ControlTurned, ControlPressed, ControlReleased]
    assert [e.control for e in seen] == ['Knob_0', 'Fader_3', 'Display', 'Display', 'Play', 'Play']
    assert (seen[0].value, seen[2].delta, seen[3].delta) == (1.0, 2, -1)
    kinds = {c['name']: c['kind'] for c in MiniLab3.describe()['controls']}
    assert (kinds['Knob_0'], kinds['Display'], kinds['Shift']) == ('absolute', 'relative', 'button')
