"""examples/MiniLabStudio works as described: a MiniLab 3 (a stand-in) on its own playing six synth channels."""

import pathlib

import pytest

from pyxelwidgets import Transport, parser
from pyxelwidgets.devices.arturia import MiniLab3
from pyxelwidgets.events import Emitter

LAYOUT = pathlib.Path(__file__).parent.parent / 'examples' / 'MiniLabStudio' / 'layout.json'
PAGES = ['Drums', 'Beat', 'Snare', 'Bass', 'Chords', 'Arp', 'Lead', 'Gen', 'Mutes', 'FX', 'Patterns', 'Tempo']


class Port:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(list(message))

    def close_port(self):
        pass


class Output(Emitter):
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


@pytest.fixture
def studio(tmp_path):
    layout = tmp_path / 'layout.json'
    layout.write_text(LAYOUT.read_text())
    ui = parser.load(layout, devices = False)
    lab = MiniLab3()
    lab._midi_output = Port()
    lab._midi_output_name = MiniLab3.ports[0]
    lab.connected = True
    ui.surface.add_device(lab, 0, 0)
    ui.devices = [lab]
    ui.place_controls(ui.devices)
    transport = Transport(sync = True)
    ui.surface.transport = transport
    ui.attach(transport)
    ui.bind(ui.devices, transport)
    ui.link(transport, widgets = False)
    synths = Output()
    ui.map({'synths': synths})
    ui.surface.update()
    return ui, lab, transport, synths


def press(device, x, y, velocity = 1.0):
    device.set_button(x, y, velocity)
    device.set_button(x, y, 0.0)


def turn(lab, steps, shift = False):
    """The display encoder: one message per detent."""
    for _ in range(abs(steps)):
        lab.decode([0xB0, 29 if shift else 28, 65 if steps > 0 else 62])


def page(lab, name):
    turn(lab, -20)
    turn(lab, PAGES.index(name))


def bars(transport, count = 1):
    for _ in range(96 * count):
        transport.pulse()


def notes(synths, channel = None):
    return [(m.channel, m.note) for m in synths.sent if type(m).__name__ == 'NoteOn' and m.velocity and (channel is None or m.channel == channel)]


def ccs(synths, channel = None):
    return [(m.control, m.value) for m in synths.sent if type(m).__name__ == 'ControlChange' and (channel is None or m.channel == channel)]


def test_the_encoder_picks_the_page_and_names_it(studio):
    ui, lab, transport, synths = studio
    turn(lab, 3)
    ui.surface.update()
    assert (ui['pages'].page, ui['music'].page) == (0, 3) and lab._texts['Screen'] == ('Bass', 'keys set the note')
    turn(lab, 7)                        # past Mutes and FX: Patterns
    assert ui['pages'].page == 2
    ui.surface.update()
    assert lab._lit['Record'] != lab._lit.get('Loop')
    turn(lab, 5)                        # past the end: stays on Tempo
    assert ui['pages'].page == 3 and ui['mode'].number == 11


def test_shift_loop_and_rec_jump_to_mutes_and_patterns(studio):
    ui, lab, transport, synths = studio
    lab.decode([0xB0, 108, 127])        # Shift + Rec
    assert ui['pages'].page == 2 and ui['mode'].number == 10
    lab.decode([0xB0, 105, 127])        # Shift + Loop
    assert (ui['pages'].page, ui['music'].page, ui['mode'].number) == (0, 8, 8)
    turn(lab, -1)                       # the encoder goes on from there
    assert ui['music'].page == 7


def test_finger_drums_and_the_euclidean_beat(studio):
    ui, lab, transport, synths = studio
    press(lab, 0, 0)
    assert notes(synths) == [(10, 36)]
    synths.sent.clear()
    page(lab, 'Beat')
    press(lab, 3, 0)                    # four kicks in the bar
    press(lab, 7, 1)                    # eight hats in half a bar
    transport.play()
    bars(transport)
    played = notes(synths, 10)
    assert played.count((10, 36)) == 4 and played.count((10, 42)) == 16


def test_snare_steps_follow_swing_and_mutes(studio):
    ui, lab, transport, synths = studio
    page(lab, 'Snare')
    press(lab, 4, 0)
    lab.decode([0xB0, 86, 127])         # knob 1: swing
    ui.surface.update()
    assert ui['snare'].swing == 75.0 and lab._texts['Screen'] == ('Swing', '75%')
    transport.play()
    bars(transport)
    assert notes(synths) == [(10, 38)]
    lab.decode([0xB0, 105, 127])        # Shift + Loop: mutes
    press(lab, 2, 1)                    # snare off
    ui.surface.update()
    assert not ui['snare'].running
    synths.sent.clear()
    bars(transport)
    assert notes(synths) == []


def test_keys_play_the_lead_set_the_bass_and_feed_the_arp(studio):
    ui, lab, transport, synths = studio
    lab.decode([0x90, 60, 100])
    lab.decode([0x80, 60, 0])
    assert notes(synths) == [(1, 60)]
    page(lab, 'Bass')
    press(lab, 0, 0)                    # the first step
    synths.sent.clear()
    lab.decode([0x90, 43, 100])         # heard on the bass channel, and the line follows
    lab.decode([0x80, 43, 0])
    assert notes(synths) == [(2, 43)] and ui['bass'].note == 43
    synths.sent.clear()
    transport.play()
    bars(transport)
    assert notes(synths) == [(2, 43)]
    transport.stop()
    page(lab, 'Arp')
    synths.sent.clear()
    lab.decode([0x90, 60, 100])
    lab.decode([0x90, 63, 100])
    assert notes(synths) == []          # held by the arpeggiator, not played
    transport.play()
    bars(transport)
    assert {note for _, note in notes(synths, 4)} == {60, 63}
    page(lab, 'Lead')
    lab.decode([0x90, 64, 100])         # outside the Arp page the keys don't reach it
    assert 64 not in ui['arp'].held


def test_the_key_knobs_reach_every_melodic_widget(studio):
    ui, lab, transport, synths = studio
    lab.decode([0xB0, 90, round(7 / 11 * 127)])        # knob 4: root G
    lab.decode([0xB0, 110, 127])                       # knob 5: blues
    ui.surface.update()
    for name in ('chords', 'arp', 'lead', 'gen'):
        assert (ui[name].root.name, ui[name].scale.name) == ('G', 'MinorBlues'), name
    assert lab._texts['Screen'] == ('Scale', 'Blues')
    lab.decode([0xB0, 116, 127])                       # knob 7: arp range
    lab.decode([0xB0, 111, 127])                       # knob 6: arp mode
    ui.surface.update()
    assert (ui['arp'].octaves, ui['arp'].mode.name) == (4, 'Played')


def test_chords_lead_pads_and_generative(studio):
    ui, lab, transport, synths = studio
    page(lab, 'Chords')
    press(lab, 0, 0)
    assert len(notes(synths, 3)) == 3
    page(lab, 'Lead')
    press(lab, 0, 0)
    press(lab, 0, 1)
    assert notes(synths, 1)[-2:] == [(1, 60), (1, 72)]
    page(lab, 'Gen')
    assert not ui['gen'].running        # off until switched on in Mutes
    lab.decode([0xB0, 105, 127])
    press(lab, 7, 1)
    ui.surface.update()
    assert ui['gen'].running


def test_faders_strips_and_fx_send_controllers(studio):
    ui, lab, transport, synths = studio
    lab.decode([0xB0, 14, 100])         # fader 1: drums volume
    lab.decode([0xB1, 1, 64])           # mod strip
    assert ccs(synths, 10)[-1] == (7, 100) and ccs(synths, 1)[-1] == (1, 64)
    ui.surface.update()
    assert lab._texts['Screen'] == ('Drums', 'volume 79%')
    lab.decode([0xB0, 117, 127])        # knob 8: space on every channel
    assert {channel for channel in (1, 2, 3, 4, 5, 10) if (91, 127) in ccs(synths, channel)} == {1, 2, 3, 4, 5, 10}
    page(lab, 'FX')
    synths.sent.clear()
    lab.set_button(0, 1, 1.0)           # the filter pad, top left
    assert ccs(synths, 1)[0][0] == 74 and ccs(synths, 1)[0][1] < 64 and (71, 127) in ccs(synths, 4)


def test_patterns_store_and_recall(studio):
    ui, lab, transport, synths = studio
    page(lab, 'Snare')
    press(lab, 0, 0)
    lab.decode([0xB0, 108, 127])        # Shift + Rec
    press(lab, 2, 1)                    # store in slot 3
    ui.surface.update()
    assert lab._texts['Screen'] == ('Pattern 3', 'stored')
    ui['snare'].reset()
    press(lab, 2, 0)                    # recall it
    assert ui['snare'].state[0, 0]
    assert '"presets"' in pathlib.Path(ui.path).read_text()         # kept in the layout file


def test_tempo_from_the_encoder_and_taps(studio):
    ui, lab, transport, synths = studio
    turn(lab, 5, shift = True)
    ui.surface.update()
    assert transport.bpm == pytest.approx(125) and lab._texts['Screen'] == ('Tempo', '125 bpm')
    page(lab, 'Tempo')
    press(lab, 3, 0)                    # +1
    assert transport.bpm == pytest.approx(126)
    clock = iter([0.0, 0.5, 1.0, 1.5])
    ui['tap'].clock = lambda: next(clock)
    for _ in range(4):                  # Shift + Tap, every half second
        lab.decode([0xB0, 109, 127])
    assert transport.bpm == pytest.approx(120) and ui['tempo'].number == 120


def test_pattern_1_is_a_starter_groove(studio):
    ui, lab, transport, synths = studio
    lab.decode([0xB0, 108, 127])        # Shift + Rec
    press(lab, 0, 0)                    # recall pattern 1
    ui.surface.update()
    transport.play()
    bars(transport)
    played = notes(synths)
    assert (played.count((10, 36)), played.count((10, 42)), played.count((10, 38)), played.count((2, 36))) == (4, 10, 3, 7)
