import pytest

from pyxelwidgets import App, Sequencer, StepPlayed, Surface, Transport
from pyxelwidgets.devices.midi_clock import ClockFollower, MidiClockInput, MidiClockOutput


class Port:
    def __init__(self):
        self.sent = []

    def send_message(self, message):
        self.sent.append(list(message))

    def close_port(self):
        pass


def test_input_needs_a_synced_transport():
    with pytest.raises(ValueError, match = 'sync'):
        MidiClockInput(Transport())


def test_input_drives_transport():
    transport = Transport(sync = True)
    clock = MidiClockInput(transport)
    sequencer = Sequencer(0, 0, 8, 1)
    steps = []
    sequencer.on(StepPlayed, lambda e: steps.append(e.step))
    transport.every(sequencer.rate, sequencer.play)

    for _ in range(12):
        clock.decode([0xF8])  # clocks while stopped don't move
    clock.decode([0xFA])
    for _ in range(13):
        clock.decode([0xF8])
    assert steps == [0, 1, 2] and transport.playing
    clock.decode([0xFC])
    assert not transport.playing
    clock.decode([0xF2, 32, 1])  # 16th note 160
    assert transport.beats == 40
    clock.decode([0xFB])
    clock.decode([0xF8])
    assert steps[-1] == 160 % 8
    clock.decode([0xFE])  # active sensing is ignored
    clock.decode([])


def test_follower_listens_to_a_device():
    class Source:
        connected = True
        def __init__(self):
            self.raw_listeners = []
    transport, first, second = Transport(sync = True), Source(), Source()
    follower = ClockFollower(transport, first)
    assert follower.connected and len(first.raw_listeners) == 1
    first.raw_listeners[0]([0xFA])
    assert transport.playing
    follower.attach(second)
    assert first.raw_listeners == [] and len(second.raw_listeners) == 1
    second.raw_listeners[0]([0xFC])
    assert not transport.playing
    follower.close()
    assert second.raw_listeners == [] and not follower.connected
    with pytest.raises(ValueError, match = 'sync'):
        ClockFollower(Transport())


def test_layout_sync_from_an_output():
    from pyxelwidgets import parser
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 1, 'height': 1}, 'widgets': [],
              'outputs': [{'name': 'net', 'type': 'rtp_midi.RtpMidi', 'options': {'announce': False}},
                          {'name': 'osc', 'type': 'osc.OSC'}],
              'transport': {'sync': {'output': 'net'}}}
    ui = parser.load(layout, devices = False)
    follower = ui.sync_input(Transport(sync = True), {'net': None})
    assert isinstance(follower, ClockFollower) and not follower.connected
    for sync, message in (({'output': 'nothing'}, "no output called 'nothing'"), ({'output': 'osc'}, "can't receive MIDI clock")):
        with pytest.raises(parser.LayoutError, match = message):
            parser.load({**layout, 'transport': {'sync': sync}}, devices = False)


def test_input_with_app():
    app = App(Surface(1, 1), sync = True)
    clock = MidiClockInput(app.transport)
    clock.decode([0xFA])
    assert app.transport.playing and app.transport.sync
    app.close()


def test_output_sends_clock_start_stop_and_position():
    transport = Transport(sync = True)  # pulsed by hand for the test
    clock = MidiClockOutput(transport)
    clock._midi_output = port = Port()
    transport.play()
    for _ in range(3):
        transport.pulse()
    transport.stop()
    transport.locate(2)
    transport.play()
    transport.pulse()
    transport.locate(1)
    transport.stop()
    assert port.sent == [
        [0xFA], [0xF8], [0xF8], [0xF8], [0xFC],
        [0xF2, 8, 0],                          # stopped: position only
        [0xF2, 8, 0], [0xFB], [0xF8],          # continue from 16th note 8
        [0xFC], [0xF2, 4, 0], [0xFB],          # moved while playing
        [0xFC],
    ]


def test_output_at_higher_resolution_sends_24_per_quarter():
    transport = Transport(sync = True, ppq = 96)
    clock = MidiClockOutput(transport)
    clock._midi_output = port = Port()
    transport.play()
    for _ in range(24):
        transport.pulse()
    assert port.sent.count([0xF8]) == 24


def test_output_close_unsubscribes():
    transport = Transport(sync = True)
    clock = MidiClockOutput(transport)
    clock._midi_output = port = Port()
    clock.close()
    transport.play()
    transport.pulse()
    assert port.sent == [] and transport.subscriptions == []


def test_output_follows_internal_timer():
    import time
    transport = Transport(1200)
    clock = MidiClockOutput(transport)
    clock._midi_output = port = Port()
    start = time.monotonic()
    transport.play()
    time.sleep(0.2)
    transport.close()
    # 1200 bpm: 480 clocks per second, for however long the sleep really took
    expected = (time.monotonic() - start) * 480
    assert port.sent[0] == [0xFA] and port.sent[-1] == [0xFC]
    assert expected * 0.6 <= port.sent.count([0xF8]) <= expected * 1.1 + 5
