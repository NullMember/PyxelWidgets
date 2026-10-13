"""
Melodic tools on a Launchpad Mini MK3, one page each (top row switches):

1. melody: a piano roll in A minor (right column: scroll up/down, tap tempo, play),
2. chords: chord pads feeding an arpeggiator below them (right column: its
   mode from the bottom: up, down, up and down, random, as played; top: latch),
3. rhythm: Euclidean drums over a hi-hat sequencer; hold hat steps and touch
   the fader to set their velocity,
4. life: notes from Conway's Life (top right: start again at random).

    python Melodic.py
    pyxelwidgets-designer layout.json     # change it

Notes go to the "PyxelWidgets Melodic" MIDI port: melody on channel 1,
chords 2, arpeggio 3, life 4, drums 10.
"""

import pathlib

from pyxelwidgets import parser

ui = parser.load(pathlib.Path(__file__).with_name('layout.json'))

if __name__ == '__main__':
    print('Ctrl+C to stop.')
    ui.app().run()
