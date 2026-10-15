import pytest

from pyxelwidgets.message import (ChannelPressure, Command, ControlChange, MidiMessage, NoteOff, NoteOn, OscMessage,
                                  PitchBend, PolyPressure, ProgramChange, Source)


def test_constants_and_sources():
    message = NoteOn(36, Source('velocity'), channel = 10)
    assert message.resolve({'velocity': 1.0}).to_midi() == [0x99, 36, 127]
    assert NoteOn(Source('cell', offset = 36)).resolve({'cell': 5, 'velocity': 0.5}).to_midi() == [0x90, 41, 64]


def test_ranges_clamp_and_narrow():
    assert ControlChange(7, Source('value', min = 64, max = 127)).resolve({'value': 0.0}).value == 64
    assert NoteOn(Source('cell', offset = 120)).resolve({'cell': 20, 'velocity': 1.0}).note == 127
    assert PitchBend().resolve({'value': 0.5}).to_midi() == [0xE0, 0x00, 0x40]


@pytest.mark.parametrize('midi, message', [
    ([0x91, 60, 100], NoteOn(60, 100, 2)),
    ([0x80, 60, 0], NoteOff(60, 0, 1)),
    ([0xB0, 7, 127], ControlChange(7, 127, 1)),
    ([0xC3, 5], ProgramChange(5, 4)),
    ([0xE0, 0x7F, 0x7F], PitchBend(16383, 1)),
    ([0xA0, 60, 10], PolyPressure(60, 10, 1)),
    ([0xD0, 10], ChannelPressure(10, 1)),
])
def test_midi_round_trip(midi, message):
    assert MidiMessage.from_midi(midi) == message
    assert message.to_midi() == midi


def test_no_message_for_system_messages():
    assert MidiMessage.from_midi([0xF8]) is None and MidiMessage.from_midi([]) is None


def test_match_recovers_values():
    template = ControlChange(7, Source('value'), channel = 2)
    assert template.match(ControlChange(7, 127, 2)) == {'value': 1.0}
    assert template.match(ControlChange(7, 127, 1)) is None
    assert template.match(NoteOn(7, 127, 2)) is None
    assert NoteOn(Source('cell', offset = 36)).match(NoteOn(40, 0, 1)) == {'cell': 4, 'velocity': 0.0}


def test_osc_addresses_with_placeholders():
    template = OscMessage('/track/{x+1}/volume', Source('value'))
    assert template.resolve({'x': 2, 'value': 0.25}) == OscMessage('/track/3/volume', 0.25)
    assert template.match(OscMessage('/track/8/volume', 0.5)) == {'x': 7, 'value': 0.5}
    assert template.match(OscMessage('/track/8/pan', 0.5)) is None
    assert OscMessage('/play', 1.0).match(OscMessage('/play', 1)) == {}
    assert OscMessage('/track/1/name', Source('text')).match(OscMessage('/track/1/name', 'Drums')) == {'text': 'Drums'}


def test_commands():
    assert Command('Mute {cell+1}').resolve({'cell': 2}) == Command('Mute 3', 1.0)
    assert Command('Play').match(Command('Play', 1.0, True)) == {'state': 1.0, 'flash': True}
    assert Command('Fader 1', Source('value')).match(Command('Fader 1', 0.5)) == {'value': 0.5, 'flash': False}
    assert Command('Timecode', Source('text')).match(Command('Timecode', '1.1.1')) == {'text': '1.1.1', 'flash': False}
    assert Command('Play').match(Command('Stop', 1.0)) is None
