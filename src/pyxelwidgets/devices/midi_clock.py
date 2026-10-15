"""
MIDI clock: follow another program's clock (e.g. a DAW) or send one.

    transport = Transport(sync = True)            # or App(surface, sync = True)
    clock = MidiClockInput(transport)
    clock.connect_virtual('PyxelWidgets Clock')    # or clock.connect('IAC Driver Bus 1')

    clock = MidiClockOutput(app.transport)
    clock.connect(out_port = 'IAC Driver Bus 1')

A Bluetooth or network MIDI output the DAW connects to (``BleMidi``,
``RtpMidi``, or any device with ``raw_listeners``) can carry the clock too::

    clock = ClockFollower(transport, bluetooth)

Any object with the Transport's ``pulse``, ``play``, ``stop`` and ``locate``
(input) or ``every``, ``on``, ``tick`` and ``ppq`` (output) works; devices don't
import the transport.
"""

import pyxelwidgets.devices.midi
import pyxelwidgets.events

__all__ = ['ClockFollower', 'MidiClockInput', 'MidiClockOutput', 'follow']

CLOCK = 0xF8
START = 0xFA
CONTINUE = 0xFB
STOP = 0xFC
SONG_POSITION = 0xF2

class MidiClockInput(pyxelwidgets.devices.midi.MIDI):
    """Drives a ``Transport(sync = True)`` from incoming MIDI clock, start, continue, stop and song position."""

    model = 'MIDI Clock Input'

    def __init__(self, transport, **kwargs):
        if not getattr(transport, 'sync', False):
            raise ValueError('MidiClockInput needs a transport created with sync = True')
        super().__init__(**kwargs)
        self.transport = transport

    def decode(self, midi: list) -> None:
        follow(self.transport, midi)

class ClockFollower:
    """
    Drives a ``Transport(sync = True)`` from the MIDI clock another device
    receives (its ``raw_listeners``), e.g. a Bluetooth or network MIDI output
    a DAW sends its clock to. ``attach`` moves it to another device (None:
    waits for one).
    """

    model = 'MIDI Clock Follower'

    def __init__(self, transport, source = None):
        if not getattr(transport, 'sync', False):
            raise ValueError('ClockFollower needs a transport created with sync = True')
        self.transport = transport
        self.source = None
        self.attach(source)

    @property
    def connected(self) -> bool:
        """Whether the device it follows is connected."""
        return self.source is not None and bool(getattr(self.source, 'connected', True))

    def attach(self, source) -> None:
        if source is self.source:
            return
        if self.source is not None and self._received in self.source.raw_listeners:
            self.source.raw_listeners.remove(self._received)
        self.source = source
        if source is not None:
            source.raw_listeners.append(self._received)

    def close(self) -> None:
        self.attach(None)

    def _received(self, midi: list) -> None:
        follow(self.transport, midi)

def follow(transport, midi: list) -> None:
    """Apply one received MIDI message to ``transport``: clock, start, continue, stop and song position (others are ignored)."""
    status = midi[0] if midi else None
    if status == CLOCK:
        transport.pulse()
    elif status == START:
        transport.locate(0)
        transport.play()
    elif status == CONTINUE:
        transport.play()
    elif status == STOP:
        transport.stop()
    elif status == SONG_POSITION and len(midi) == 3:
        # Position in 16th notes
        transport.locate(((midi[2] << 7) | midi[1]) / 4)

class MidiClockOutput(pyxelwidgets.devices.midi.MIDI):
    """Sends a Transport's tempo and position as MIDI clock (24 per quarter note) with start, continue, stop and song position."""

    model = 'MIDI Clock Output'

    def __init__(self, transport, **kwargs):
        super().__init__(**kwargs)
        self.transport = transport
        # A 96th note: 24 clocks per quarter note
        self._subscription = transport.every('1/96', self._clock)
        transport.on(pyxelwidgets.events.TransportStarted, self._started)
        transport.on(pyxelwidgets.events.TransportStopped, self._stopped)
        transport.on(pyxelwidgets.events.TransportLocated, self._located)

    def close(self) -> None:
        self._subscription.cancel()
        self.transport.off(pyxelwidgets.events.TransportStarted, self._started)
        self.transport.off(pyxelwidgets.events.TransportStopped, self._stopped)
        self.transport.off(pyxelwidgets.events.TransportLocated, self._located)
        super().close()

    def _send(self, message: list) -> None:
        if self._midi_output is not None:
            self._midi_output.send_message(message)

    def _clock(self, count: int) -> None:
        self._send([CLOCK])

    def _song_position(self, tick: int) -> None:
        sixteenths = min(tick * 4 // self.transport.ppq, 0x3FFF)
        self._send([SONG_POSITION, sixteenths & 0x7F, sixteenths >> 7])

    def _started(self, event) -> None:
        if event.tick == 0:
            self._send([START])
        else:
            self._song_position(event.tick)
            self._send([CONTINUE])

    def _stopped(self, event) -> None:
        self._send([STOP])

    def _located(self, event) -> None:
        # Receivers only accept song position while stopped
        if self.transport.playing:
            self._send([STOP])
            self._song_position(event.tick)
            self._send([CONTINUE])
        else:
            self._song_position(event.tick)
