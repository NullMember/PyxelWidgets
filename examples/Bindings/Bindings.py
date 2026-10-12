"""
Binds a Launchpad Mini MK3's side buttons to the transport and a widget, with
a sequencer playing on the 8x8 pads.

    python Bindings.py

Top1 plays/stops, Top2 rewinds, Top3 toggles the sequencer's accent (a Button
widget kept off the grid). With a knob controller you would bind knobs the same
way: ``surface.bind(controller, 'Knob_0', fader, takeover = Takeover.Pickup)``.
"""

from pyxelwidgets import App, Button, Changed, Sequencer, StepPlayed, Surface
from pyxelwidgets.devices.novation import LaunchpadMiniMK3

launchpad = LaunchpadMiniMK3.find(side_buttons = False)   # side buttons become controls

surface = Surface(8, 8)
surface.add_device(launchpad)
app = App(surface, bpm = 110)

sequencer = surface.add(Sequencer(0, 0, 8, 8, rate = '1/16'))
app.attach(sequencer)
accent = Button(0, 0, 1, 1, mode = Button.Mode.Switch)   # not on the surface: only the binding changes it

surface.bind(launchpad, 'Top1', app.transport.toggle)
surface.bind(launchpad, 'Top2', lambda: app.transport.locate(0))
surface.bind(launchpad, 'Top3', accent)

accent.on(Changed, lambda e: print('accent', 'on' if e.value else 'off'))
sequencer.on(StepPlayed, lambda e: e.active and print('step', e.step, 'ACCENT' if accent.value else ''))

if __name__ == '__main__':
    print('Top1: play/stop, Top2: rewind, Top3: accent. Press pads to set steps.')
    app.run()
