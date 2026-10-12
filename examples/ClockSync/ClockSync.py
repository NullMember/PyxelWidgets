"""
A four track drum sequencer that plays in time with a DAW.

    python ClockSync.py              # on-screen grid
    python ClockSync.py launchpad    # Launchpad Mini MK3

It opens a virtual MIDI port named "PyxelWidgets Clock". In the DAW, send MIDI
clock (and start/stop) to that port and record from it: steps play kick, snare,
closed and open hi-hat notes on channel 10. Pressing play in the DAW starts the
sequencer from the DAW's position.
"""

import sys

from pyxelwidgets import App, Sequencer, StepPlayed, Surface, TempoChanged
from pyxelwidgets.devices.midi_clock import MidiClockInput

if len(sys.argv) > 1 and sys.argv[1] == 'launchpad':
    from pyxelwidgets.devices.novation import LaunchpadMiniMK3
    device = LaunchpadMiniMK3.find()
else:
    from pyxelwidgets.devices.virtual import Virtual
    device = Virtual(9, 9)
    device.connect()

surface = Surface(9, 9)
surface.add_device(device)
app = App(surface, sync = True)

clock = MidiClockInput(app.transport)
clock.connect_virtual('PyxelWidgets Clock')

DRUMS = {'kick': 36, 'snare': 38, 'closed hat': 42, 'open hat': 46}
for row, (name, note) in enumerate(DRUMS.items()):
    track = surface.add(Sequencer(0, row, 8, 1, name = name))
    app.transport.every(track.rate, track.play)

    @track.on(StepPlayed)
    def hit(e, note = note):
        if e.active:
            clock.send_note_on(note, 100, 9)
            clock.send_note_off(note, 0, 9)

app.transport.on(TempoChanged, lambda e: print(f'{e.bpm:.1f} bpm'))

if __name__ == '__main__':
    print('Send MIDI clock to "PyxelWidgets Clock" and press play in your DAW')
    try:
        app.run()
    finally:
        clock.close()
