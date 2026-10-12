"""
A performance layout made in the designer (layout.json), on a Launchpad Mini
MK3 and, mirrored, in any web browser on the network (a tablet, a phone):

- the top four rows launch clips on the next bar (scenes on the right column),
- bottom-left drum pads (bank buttons on the top row), whose hits drive the meter,
- a beat sequencer with its own clock, started and stopped from the top row,
- the top-left button plays the transport.

    python Performance.py
    pyxelwidgets-designer layout.json     # change it

Everything is sent to the "PyxelWidgets Performance" MIDI port. Unplugging the
Launchpad and plugging it back in reconnects it.
"""

import pathlib

from pyxelwidgets import parser

ui = parser.load(pathlib.Path(__file__).with_name('layout.json'))

if __name__ == '__main__':
    web = next(device for device in ui.devices if hasattr(device, 'url'))
    print('Open', web.url, 'in a browser. Ctrl+C to stop.')
    ui.app().run()
