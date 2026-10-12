"""
A MIDI drum controller made only in the designer (layout.json): 4x4 pads
play notes 36-51 on channel 10, the top row sends program changes, and four
faders send CC 21-24 and follow them back.

    python MidiDrums.py                               # play it
    pyxelwidgets-designer layout.json --hardware      # change it

Pick "PyxelWidgets Drums" as a MIDI input in your DAW or synth.
"""

import pathlib

from pyxelwidgets import parser

ui = parser.load(pathlib.Path(__file__).with_name('layout.json'))

if __name__ == '__main__':
    print('Sending to the "PyxelWidgets Drums" MIDI port. Ctrl+C to stop.')
    ui.app().run()
