from pyxelwidgets.controllers.virtual import Virtual
from pyxelwidgets.controllers.midi import MIDI
from pyxelwidgets import App, ButtonGroup, Event, Fader, Keyboard, Manager, Window

def keyboard_callback(name, event, data):
    if event == Event.Changed:
        note, velocity = data
        if velocity > 0.0:
            keyboard_controller.send_note_on(note, int(velocity * volume_fader.value * 127.0))
        else:
            keyboard_controller.send_note_off(note)

def button_callback(name, event, data):
    if event == Event.Pressed:
        x, y = data
        keyboard_widget.octave = x

window = Window(9, 9)

keyboard_widget = Keyboard(
    x = 0, 
    y = 0, 
    width = 8, 
    height = 8, 
    type = Keyboard.Type.DiatonicVertical,
    scale = Keyboard.Scale.Major,
    root = Keyboard.Root.C,
    callback = keyboard_callback)
octave_buttons = ButtonGroup(0, 8, 8, 1, callback = button_callback)
octave_buttons.tapped(5, 0)
volume_fader = Fader(8, 0, 1, 8)
volume_fader.tapped(0, 5)

window.add_widget(keyboard_widget)
window.add_widget(octave_buttons)
window.add_widget(volume_fader)

grid_controller = Virtual(9, 9)
grid_controller.init()
grid_controller.connect()

manager = Manager(9, 9)
manager.add_window(window, 0, 0, 9, 9)
manager.add_controller(grid_controller, 0, 0)

keyboard_controller = MIDI()
keyboard_controller.init()
keyboard_controller.connect_virtual("Keyboard")

# Runs until Ctrl+C or the grid window is closed
App(manager).run()
keyboard_controller.close()
