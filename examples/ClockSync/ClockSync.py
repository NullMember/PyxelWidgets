"""
A four track drum sequencer that plays in time with a DAW, showing its tempo.

    python ClockSync.py              # on-screen grid
    python ClockSync.py launchpad    # Launchpad Mini MK3

It opens a virtual MIDI port named "PyxelWidgets Clock". In the DAW, send MIDI
clock (and start/stop) to that port and record from it: steps play kick, snare,
closed and open hi-hat notes on channel 10, with a little swing and short
hi-hats. Pressing play in the DAW starts the sequencer from the DAW's position.
"""

import sys

from pyxelwidgets import App, Colors, Sequencer, StepEnded, StepPlayed, Surface, TempoChanged, Text
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

# Note and gate (in steps) of each track
DRUMS = {'kick': (36, 0.5), 'snare': (38, 0.5), 'closed hat': (42, 0.25), 'open hat': (46, 0.75)}
for row, (name, (note, gate)) in enumerate(DRUMS.items()):
    track = surface.add(Sequencer(0, row, 8, 1, name = name, swing = 58.0, gate = gate))
    app.attach(track)

    @track.on(StepPlayed)
    def hit(e, note = note):
        if e.active:
            clock.send_note_on(note, 100, 9)

    @track.on(StepEnded)
    def release(e, note = note):
        clock.send_note_off(note, 0, 9)

# The measured tempo on the top rows (scrolls when wider than the grid)
tempo = surface.add(Text(0, 4, 9, 5, text = '--', align = Text.Align.Center, active_color = Colors.Cyan))

@app.transport.on(TempoChanged)
def show_tempo(e):
    tempo.text = f'{e.bpm:.0f}'
    print(f'{e.bpm:.1f} bpm')

if __name__ == '__main__':
    print('Send MIDI clock to "PyxelWidgets Clock" and press play in your DAW')
    try:
        app.run()
    finally:
        clock.close()
