"""The Android MIDI backend's parts that don't need Android: the framer."""

from pyxelwidgets.devices.android_midi import MidiFramer

def test_messages_and_running_status():
    framer = MidiFramer()
    assert framer.feed([0x90, 60, 100, 62, 0, 0xC1, 5, 6]) == [[0x90, 60, 100], [0x90, 62, 0], [0xC1, 5], [0xC1, 6]]
    # Split across runs
    assert framer.feed([0xB0, 7]) == []
    assert framer.feed([127]) == [[0xB0, 7, 127]]

def test_realtime_inside_a_message():
    framer = MidiFramer()
    assert framer.feed([0x90, 60, 0xF8, 100, 0xFA]) == [[0xF8], [0x90, 60, 100], [0xFA]]

def test_sysex_over_runs_and_system_common():
    framer = MidiFramer()
    assert framer.feed([0xF0, 0x00, 0x20]) == []
    assert framer.feed([0x29, 0xF8, 0x02, 0xF7, 0xF2, 1, 2, 3]) == [[0xF8], [0xF0, 0x00, 0x20, 0x29, 0x02, 0xF7], [0xF2, 1, 2]]
    # No running status after system common: the stray 3 is dropped
    assert framer.feed([0xF6, 0x80, 1, 2]) == [[0xF6], [0x80, 1, 2]]
