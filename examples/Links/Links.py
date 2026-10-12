"""
A MIDI keyboard made only in the designer (layout.json) whose widgets change
each other with links: the top row moves the octave, steps through scales,
roots and layouts; the switch on the right shows a mod wheel (CC 1) above the
keys, which shrink to make room, and the wheel tints the keys.

    python Links.py                       # play it
    pyxelwidgets-designer layout.json     # change it

Pick "PyxelWidgets Keys" as a MIDI input in your DAW or synth.
"""

import pathlib

from pyxelwidgets import parser

ui = parser.load(pathlib.Path(__file__).with_name('layout.json'))

if __name__ == '__main__':
    print('Sending to the "PyxelWidgets Keys" MIDI port. Ctrl+C to stop.')
    ui.app().run()
