from pyxelwidgets.devices.virtual import Virtual
from pyxelwidgets.devices.midi import MIDI
from pyxelwidgets import App, ButtonGroup, Fader, Keyboard, NoteOff, NoteOn, Surface, Toggled

surface = Surface(9, 9)

keyboard_widget = surface.add(Keyboard(
    x = 0,
    y = 0,
    width = 8,
    height = 8,
    type = Keyboard.Type.DiatonicVertical,
    scale = Keyboard.Scale.Major,
    root = Keyboard.Root.C))
octave_buttons = surface.add(ButtonGroup(0, 8, 8, 1))
volume_fader = surface.add(Fader(8, 0, 1, 8))

@keyboard_widget.on(NoteOn)
def note_on(e):
    keyboard_controller.send_note_on(e.note, int(e.velocity * volume_fader.value * 127.0))

@keyboard_widget.on(NoteOff)
def note_off(e):
    keyboard_controller.send_note_off(e.note)

@octave_buttons.on(Toggled)
def select_octave(e):
    if e.state:
        keyboard_widget.octave = e.x

octave_buttons.tap(5, 0)
volume_fader.tap(0, 5)

grid_controller = Virtual(9, 9)
grid_controller.connect()
surface.add_device(grid_controller)

keyboard_controller = MIDI()
keyboard_controller.connect_virtual("Keyboard")

# Runs until Ctrl+C or the grid window is closed
App(surface).run()
keyboard_controller.close()
