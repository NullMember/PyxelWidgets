"""
A Mackie Control surface for a DAW: 8 faders, mute buttons and transport,
following what the DAW sends back (fader moves, mute and transport LEDs).

    python DAWControl.py

Uses a Launchpad Mini MK3 if one is connected, else an on-screen grid. In
REAPER: Preferences > Control/OSC/web > Add > Mackie Control Universal, with
"PyxelWidgets MCU" as MIDI input and output.
"""

import random

from pyxelwidgets import App, Button, Changed, Color, Colors, Fader, Pressed, Released, Source, Surface
from pyxelwidgets.devices.mackie import MackieControl
from pyxelwidgets.message import Command

try:
    from pyxelwidgets.devices.novation import LaunchpadMiniMK3
    grid = LaunchpadMiniMK3.find()
except (ImportError, LookupError):
    from pyxelwidgets.devices.virtual import Virtual
    grid = Virtual(9, 9)
    grid.connect()

surface = Surface(9, 9)
surface.add_device(grid)
app = App(surface)

mackie = MackieControl()
mackie.connect_virtual('PyxelWidgets MCU')

# Faders move the DAW's faders and follow them
for channel in range(8):
    color = Color(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    fader = surface.add(Fader(channel, 0, 1, 8, active_color = color))
    surface.map(fader, mackie, Command(f'Fader {channel + 1}', Source('value')), on = Changed, feedback = True)

def button(x, y, name, color):
    """A button pressing ``name`` in the DAW; only the DAW's LED lights it (interactive = False)."""
    widget = surface.add(Button(x, y, 1, 1, active_color = color, inactive_color = color * 0.25, interactive = False))
    surface.map(widget, mackie, Command(name, 1.0), on = Pressed, feedback = True)
    surface.map(widget, mackie, Command(name, 0.0), on = Released)
    return widget

# Mutes on the top row, transport on the right column
for channel in range(8):
    button(channel, 8, f'Mute {channel + 1}', Colors.Red)
for y, (name, color) in enumerate([('Record', Colors.Red), ('Play', Colors.Lime), ('Stop', Colors.Yellow)]):
    button(8, y, name, color)

if __name__ == '__main__':
    print('Pick "PyxelWidgets MCU" as a Mackie Control surface in your DAW.')
    # Runs until Ctrl+C or the grid window is closed; closes the Mackie port too
    app.run()
