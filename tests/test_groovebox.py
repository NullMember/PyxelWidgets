"""examples/Groovebox works as described: a Launchpad Mini MK3 and a MiniLab 3 (stand-ins) driving 8 tracks."""

import pathlib

import pytest

from pyxelwidgets import Transport, parser
from pyxelwidgets.devices.arturia import MiniLab3
from pyxelwidgets.devices.novation import LaunchpadMiniMK3

LAYOUT = pathlib.Path(__file__).parent.parent / 'examples' / 'Groovebox' / 'layout.json'


class Port:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(list(message))

    def close_port(self):
        pass


class Output:
    """The MIDI output: records what the mappings send."""

    def __init__(self):
        self.sent = []

    def on(self, *args):
        pass

    def off(self, *args):
        pass

    def send(self, message):
        self.sent.append(message)


def connected(cls):
    device = cls()
    device._midi_output = Port()
    device._midi_output_name = cls.ports[0]
    device.connected = True
    return device


@pytest.fixture
def box(tmp_path):
    layout = tmp_path / 'layout.json'
    layout.write_text(LAYOUT.read_text())
    ui = parser.load(layout, devices = False)
    pad, lab = connected(LaunchpadMiniMK3), connected(MiniLab3)
    ui.surface.add_device(pad, 0, 0)
    ui.surface.add_device(lab, 0, 9)
    ui.devices = [pad, lab]
    ui.place_controls(ui.devices)
    transport = Transport(sync = True)
    ui.surface.transport = transport
    ui.attach(transport)
    ui.bind(ui.devices, transport)
    ui.link(transport, widgets = False)
    midi = Output()
    ui.map({'midi': midi})
    ui.surface.update()
    return ui, pad, lab, transport, midi


def press(device, x, y):
    device.set_button(x, y, 1.0)
    device.set_button(x, y, 0.0)


def control(lab, number, value):
    lab.decode([0xB0, number, value])


def bars(transport, count = 1):
    for _ in range(96 * count):
        transport.pulse()


def notes(midi, kind = 'NoteOn'):
    return [(m.channel, m.note, m.velocity) for m in midi.sent if type(m).__name__ == kind and getattr(m, 'velocity', 1)]


def test_steps_play_at_their_track_level(box):
    ui, pad, lab, transport, midi = box
    # The kick's first step (steps start at the top half's bottom left), velocity 75% from the step tools
    pad.set_button(0, 4, 1.0)
    pad.set_button(2, 3, 1.0)
    pad.set_button(2, 3, 0.0)
    pad.set_button(0, 4, 0.0)
    transport.play()
    bars(transport)
    assert notes(midi) == [(10, 36, round(0.75 * 0.8 * 127))]
    assert any(type(m).__name__ == 'NoteOff' and m.note == 36 for m in midi.sent)


def test_knobs_pick_the_track_and_set_its_level(box):
    ui, pad, lab, transport, midi = box
    control(lab, 87, 64)                     # knob 2: the snare
    ui.surface.update()
    assert ui['tracks'].page == 1 and ui['select'].selected == 1 and ui['labselect'].selected == 1
    assert ui['snare_level'].value == pytest.approx(64 / 127)
    assert lab._texts['Screen'] == ('Snare', 'Level 50%')
    press(pad, 0, 4)                         # now a snare step
    transport.play()
    bars(transport)
    assert notes(midi) == [(10, 37, round(64 / 127 * 127))]


def test_faders_change_the_selected_track_only(box):
    ui, pad, lab, transport, midi = box
    control(lab, 89, 10)                     # knob 3: the clap
    control(lab, 14, 127)                    # fader 1: swing
    control(lab, 15, 0)                      # fader 2: gate (at least 5%)
    ui.surface.update()
    assert (ui['clap'].swing, ui['clap'].gate) == (75.0, 0.05)
    assert (ui['kick'].swing, ui['kick'].gate) == (50.0, 0.5)
    assert lab._texts['Screen'] == ('Gate', '5%')
    control(lab, 31, 127)                    # fader 4: velocity humanize, melodic tracks too
    control(lab, 86, 10)
    control(lab, 31, 64)
    assert ui['clap'].velocity_random == 0.5 and ui['kick'].velocity_random == pytest.approx(64 / 127 * 0.5)


def test_length_rate_clear_and_mutes(box):
    ui, pad, lab, transport, midi = box
    press(pad, 2, 2)                         # 32 steps
    press(pad, 6, 2)                         # 1/8
    ui.surface.update()
    assert (ui['kick'].length, ui['kick'].rate) == (32, '1/8')
    press(pad, 0, 4)
    press(pad, 0, 0)                         # mute the kick: on the MiniLab too
    ui.surface.update()
    assert not ui['kick'].running and ui['labmute_kick'].value == 0
    transport.play()
    bars(transport)
    assert notes(midi) == []
    lab.set_button(0, 1, 1.0)                # unmuted on the MiniLab (Tracks mode, bank B)
    lab.set_button(0, 1, 0.0)
    ui.surface.update()
    assert ui['kick'].running and ui['mute_kick'].value == 1
    press(pad, 7, 2)                         # clear
    assert not ui['kick'].state.any()


def test_patterns_store_and_recall_steps(box):
    ui, pad, lab, transport, midi = box
    press(pad, 0, 4)
    press(pad, 8, 7)                         # store in the top slot
    press(pad, 7, 2)                         # clear
    press(pad, 8, 7)                         # recall
    assert ui['kick'].state[0, 0]


def test_minilab_modes_key_and_tap(box):
    ui, pad, lab, transport, midi = box
    control(lab, 106, 127)                   # Shift + Stop: drum pads
    ui.surface.update()
    assert ui['lab'].page == 1 and lab._lit['Stop'][:3] == (255, 160, 0) and 'Loop' not in lab._lit
    lab.set_button(2, 0, 0.5)
    assert notes(midi)[-1] == (10, 38, 64)
    control(lab, 108, 127)                   # Shift + Rec: key
    lab.set_button(4, 0, 1.0)                # root G
    lab.set_button(5, 1, 1.0)                # Minor pentatonic
    ui.surface.update()
    assert (ui['bass'].root.name, ui['lead'].scale.name) == ('G', 'MinorPentatonic')
    control(lab, 28, 65)                     # the encoder: tempo up a bpm
    assert transport.bpm == pytest.approx(121)
    ui.surface.update()
    assert lab._texts['Screen'] == ('Tempo', '121 bpm')


def test_melodic_tracks(box):
    ui, pad, lab, transport, midi = box
    control(lab, 117, 30)                    # knob 8: the lead
    ui.surface.update()
    press(pad, 0, 3)                         # a note on the first step, lowest row
    transport.play()
    bars(transport)
    played = notes(midi)
    assert played and played[0][0] == 3
    press(pad, 1, 2)                         # 32 steps
    press(pad, 3, 2)                         # an octave up
    ui.surface.update()
    assert ui['lead'].steps == 32 and ui['lead'].octave == 5
