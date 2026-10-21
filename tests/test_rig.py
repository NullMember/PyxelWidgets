"""examples/Rig works as described: a Launchpad Mini MK3 and a MiniLab 3 (stand-ins) playing instruments and driving a DAW."""

import pathlib

import pytest

from pyxelwidgets import Transport, parser
from pyxelwidgets.devices.arturia import MiniLab3
from pyxelwidgets.devices.novation import LaunchpadMiniMK3
from pyxelwidgets.events import Emitter, MessageReceived
from pyxelwidgets.message import Command

LAYOUT = pathlib.Path(__file__).parent.parent / 'examples' / 'Rig' / 'layout.json'


class Port:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(list(message))

    def close_port(self):
        pass


class Output(Emitter):
    """An output recording what the mappings send; ``answer`` is the DAW sending something back."""

    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)

    def answer(self, message):
        self.emit(MessageReceived(self, message))


def connected(cls):
    device = cls()
    device._midi_output = Port()
    device._midi_output_name = cls.ports[0]
    device.connected = True
    return device


@pytest.fixture
def rig(tmp_path):
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
    outputs = {'instruments': Output(), 'daw': Output()}
    ui.map(outputs)
    ui.surface.update()
    return ui, pad, lab, transport, outputs


def press(device, x, y, velocity = 1.0):
    device.set_button(x, y, velocity)
    device.set_button(x, y, 0.0)


def bars(transport, count = 1):
    for _ in range(96 * count):
        transport.pulse()


def notes(output, channel = None):
    return [(m.channel, m.note) for m in output.sent if type(m).__name__ == 'NoteOn' and m.velocity and (channel is None or m.channel == channel)]


def commands(output):
    return [(m.name, m.value) for m in output.sent if isinstance(m, Command)]


def test_drums_play_on_channel_10(rig):
    ui, pad, lab, transport, outputs = rig
    press(pad, 0, 4)
    transport.play()
    bars(transport)
    assert notes(outputs['instruments']) == [(10, 36)]


def test_modes_bass_and_lead_rolls(rig):
    ui, pad, lab, transport, outputs = rig
    press(pad, 1, 8)                    # Bass
    ui.surface.update()
    assert ui['pages'].page == 0 and ui['seqmodes'].page == 1
    press(pad, 0, 1)                    # a note on the first step
    transport.play()
    bars(transport)
    assert {channel for channel, _ in notes(outputs['instruments'])} == {2}
    press(pad, 2, 8)                    # Lead
    assert ui['seqmodes'].page == 2


def test_the_key_follows_everywhere(rig):
    ui, pad, lab, transport, outputs = rig
    press(pad, 3, 8)                    # Keys
    press(pad, 4, 0)                    # root G
    press(pad, 7, 0)                    # sharp
    press(pad, 5, 1)                    # minor pentatonic
    ui.surface.update()
    for name in ('bass', 'lead', 'keys', 'chords', 'arp'):
        assert (ui[name].root.name, ui[name].scale.name) == ('GS', 'MinorPentatonic'), name
    press(pad, 0, 3)                    # the keyboard
    assert notes(outputs['instruments'], 4)


def test_chords_and_the_arpeggiator_from_the_minilab_keys(rig):
    ui, pad, lab, transport, outputs = rig
    press(pad, 4, 8)                    # Chords
    press(pad, 0, 1)
    assert len(notes(outputs['instruments'], 5)) >= 3
    outputs['instruments'].sent.clear()
    lab.decode([0x90, 60, 100])         # keys outside Arp mode: played on channel 4
    assert notes(outputs['instruments']) == [(4, 60)]
    lab.decode([0x80, 60, 0])
    press(pad, 5, 8)                    # Arp
    ui.surface.update()
    outputs['instruments'].sent.clear()
    lab.decode([0x90, 60, 100])
    lab.decode([0x90, 64, 100])
    assert notes(outputs['instruments'], 4) == []          # not played: fed to the arpeggiator
    transport.play()
    bars(transport)
    assert {note for _, note in notes(outputs['instruments'], 6)} == {60, 64}


def test_mixer_and_macros_drive_the_daw(rig):
    ui, pad, lab, transport, outputs = rig
    press(pad, 6, 8)                    # Mixer
    press(pad, 1, 1)                    # mute 2
    pad.set_button(0, 7, 1.0)           # volume 1, top
    assert ('Mute 2', 1.0) in commands(outputs['daw']) and any(name == 'Volume 1' and value > 0.5 for name, value in commands(outputs['daw']))
    outputs['daw'].answer(Command('Solo 3', 1.0))
    assert ui['solo3'].value > 0
    lab.decode([0xB0, 86, 100])         # knob 1: macro 1
    assert commands(outputs['daw'])[-1] == ('Macro 1', pytest.approx(100 / 127))
    outputs['daw'].answer(Command('Macro 2', 0.25))
    ui.surface.update()
    assert ui['macro2'].value == 0.25 and lab._rings['Knob_1'] == 0.25     # the knob goes on from there
    lab.decode([0xB0, 31, 64])          # fader 4: the DAW's selected track volume
    assert commands(outputs['daw'])[-1] == ('Selected Volume', pytest.approx(64 / 127))


def test_right_column(rig):
    ui, pad, lab, transport, outputs = rig
    press(pad, 8, 5)                    # record
    press(pad, 8, 2)                    # undo
    assert ('Record', 1.0) in commands(outputs['daw']) and ('Undo', 1.0) in commands(outputs['daw'])
    press(pad, 8, 7)                    # play
    assert transport.playing
    press(pad, 8, 6)                    # stop
    assert not transport.playing


def test_minilab_modes_patterns_and_drum_feel(rig):
    ui, pad, lab, transport, outputs = rig
    press(pad, 0, 4)                    # a kick step
    lab.decode([0xB0, 108, 127])        # Shift + Rec: patterns
    ui.surface.update()
    assert ui['lab'].page == 2 and lab._texts['Screen'] == ('Patterns', 'recall / store')
    press(lab, 0, 1)                    # store pattern 1
    press(pad, 7, 2)                    # clear the kick
    assert not ui['kick'].state.any()
    press(lab, 0, 0)                    # recall pattern 1
    assert ui['kick'].state[0, 0]
    lab.decode([0xB0, 105, 127])        # Shift + Loop: drum tracks
    press(lab, 1, 0)                    # select the snare
    lab.decode([0xB0, 14, 127])         # fader 1: its swing
    assert (ui['drumtracks'].page, ui['snare'].swing, ui['kick'].swing) == (1, 75.0, 50.0)


def test_clock_goes_out_through_the_instruments_port(rig):
    ui, pad, lab, transport, outputs = rig
    port = connected(LaunchpadMiniMK3)  # anything with a MIDI port
    senders = ui.clock_senders(transport, {'instruments': port})
    transport.play()
    transport.pulse()
    assert port._midi_output.messages[:2] == [[0xFA], [0xF8]]
    for sender in senders:
        sender.close()
