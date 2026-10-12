"""
A macro board made in the designer (layout.json): the top row of pads sends
editing shortcuts (copy, paste, cut, undo, redo, save, find, select all), the
next one media keys, one pad types a phrase and one holds Shift; the knob
scrolls, the XY pad puts the pointer anywhere on the screen, and two pads
click.

    pip install "pyxelwidgets[desktop]"
    python MacroBoard.py
    pyxelwidgets-designer layout.json     # change it (Connect the output to try it for real)

The shortcuts use cmd (macOS); on Windows or Linux change them to ctrl in the
designer. On macOS, allow the app running this (Terminal, your editor) under
System Settings > Privacy & Security > Accessibility.
"""

import pathlib

from pyxelwidgets import parser

ui = parser.load(pathlib.Path(__file__).with_name('layout.json'))

if __name__ == '__main__':
    desktop = ui.outputs['desktop']
    if desktop.warning:
        print(desktop.warning)
    print('Macro board running. Ctrl+C to stop.')
    ui.app().run()
