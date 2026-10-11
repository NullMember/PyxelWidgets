from pyxelwidgets.controllers.virtual import Virtual
from pyxelwidgets.controllers.midi import MIDI
from pyxelwidgets import (App, Button, ButtonGroup, Colors, Event, Fader, Keyboard, Knob,
                          Manager, Pixel, Sequencer, Window)
import random

def button_callback(name: str, event: str, data):
    global current_window
    x, y = data
    if event == Event.Pressed:
        if windows[current_window] == sequencer_window:
            sequencer_window.remove_widget(sequencer_widgets[current_sequencer].name)
        if windows[current_window] == keyboard_window:
            manager.remove_window(keyboard_config_window.name)
        manager.remove_window(windows[current_window].name)
        current_window = x
        manager.add_window(windows[current_window], 0, 0, 9, 8)
        if windows[current_window] == sequencer_window:
            sequencer_window.add_widget(sequencer_widgets[current_sequencer])

def fader_callback(name: str, event: str, data):
    if event == Event.Changed:
        index = name.split("_")[1]
        index = int(index)
        keyboard.send_control_change(index + 8, int(data * 127.0))

def knob_callback(name: str, event: str, data):
    if event == Event.Changed:
        index = name.split("_")[1]
        index = int(index)
        keyboard.send_control_change(index + 16, int(data * 127.0))

def keyboard_callback(name: str, event: str, data):
    if name == "Keyboard":
        if event == Event.Changed:
            note, velocity = data
            keyboard.send_note_on(note, int(velocity * 127.0))
    if name == "switch":
        if event == Event.Released:
            manager.remove_window(keyboard_window.name)
            manager.add_window(keyboard_config_window, 0, 0, 9, 8)

def keyboard_config_callback(name: str, event: str, data):
    keyboard = keyboard_window.widgets['Keyboard']
    if name == "Type":
        if event == Event.Pressed:
            x, y = data
            keyboard.type = Keyboard.Type(x)
    if name == "Root":
        if event == Event.Changed:
            note, velocity = data
            note %= 12
            if note < len(Keyboard.Root):
                keyboard.root = Keyboard.Root(note)
    elif name == "Octave":
        if event == Event.Pressed:
            x, y = data
            keyboard.octave = x
    elif name == "Scale":
        if event == Event.Pressed:
            scale = keyboard_config_window.widgets['Scale']
            x, y = data
            scale = x + (y * scale.width)
            if scale < len(Keyboard.Scale):
                keyboard.scale = Keyboard.Scale(scale)
    elif name == "switch":
        if event == Event.Released:
            manager.remove_window(keyboard_config_window.name)
            manager.add_window(keyboard_window, 0, 0, 9, 8)

def sequencer_callback(name: str, event: str, data):
    global current_sequencer
    if "Sequencer" in name:
        prefix, index = name.split("_")
        index = int(index)
        if event == Event.Tick:
            keyboard.send_note_on(36 + index, 0, 1)
        if event == Event.Active:
            keyboard.send_note_on(36 + index, 100 + random.randint(-10, 10), 1)
    elif "sample" in name:
        if event == Event.Pressed:
            x, y = data
            sequencer_window.remove_widget(sequencer_widgets[current_sequencer].name)
            current_sequencer = x + (y * 4)
            keyboard.send_note_on(36 + current_sequencer, 100, 1)
            keyboard.send_note_on(36 + current_sequencer, 0, 1)
            sequencer_window.add_widget(sequencer_widgets[current_sequencer])
        if event == Event.Held:
            x, y = data
            sequencer_widgets[x + (y * 4)].reset()
    elif "height" in name:
        if event == Event.Pressed:
            x, y = data
            for sequencer in sequencer_widgets:
                sequencer.steps = (y + 1) * 8
            sequencer_window.force_update()

controller = Virtual(9, 9)
controller.init()
controller.connect()

keyboard = MIDI()
keyboard.init()
keyboard.connect_virtual('Keyboard')

fader_window = Window(9, 8)
knob_window = Window(9, 8)
keyboard_window = Window(9, 8)
keyboard_config_window = Window(9, 8)
sequencer_window = Window(9, 8)

top_button_window = Window(8, 1)

windows = [fader_window, knob_window, keyboard_window, sequencer_window]
current_window = 0

manager = Manager(9, 9)
manager.add_window(top_button_window, 0, 8, 8, 1)
manager.add_window(windows[current_window], 0, 0, 9, 8)
manager.add_controller(controller, 0, 0)
app = App(manager, bpm = 60)

top_button_window.add_widget(
    ButtonGroup(
        x = 0, y = 0, width = len(windows), height = 1, 
        inactive_color = Colors.Blue, 
        callback = button_callback)
)

for i in range(8):
    fader_window.add_widget(
        Fader(
            x = i, y = 0, width = 1, height = 8, 
            name = f"DAWFader_{i}", 
            callback = fader_callback, 
            active_color = Pixel(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    )

for i in range(8):
    knob_window.add_widget(
        Knob(
            x = 0, y = 7 - i, width = 8, height = 1, 
            name = f"DAWKnob_{i}", 
            callback = knob_callback, 
            type = Knob.Type.BoostCut,
            active_color = Pixel(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    )

keyboard_window.add_widget(
    Keyboard(
        x = 0, y = 0, width = 8, height = 8,
        name = "Keyboard",
        type = Keyboard.Type.DiatonicVertical, 
        scale = Keyboard.Scale.Major, 
        root = Keyboard.Root.C, 
        fold = 4, octave = 4,
        callback = keyboard_callback)
)
keyboard_window.add_widget(
    Button(
        8, 0, 1, 1, 
        name = "switch", 
        callback = keyboard_callback, 
        inactive_color = Colors.Red)
)
keyboard_config_window.add_widget(
    ButtonGroup(
        x = 0, y = 7, width = len(Keyboard.Type), height = 1,
        name = "Type",
        callback = keyboard_config_callback)
)
keyboard_config_window.add_widget(
    Keyboard(
        x = 0, y = 5, width = 8, height = 2,
        name = "Root",
        type = Keyboard.Type.Keyboard,
        callback = keyboard_config_callback)
)
keyboard_config_window.add_widget(
    ButtonGroup(
        x = 0, y = 4, width = 8, height = 1,
        name = "Octave",
        inactive_color = Colors.PaleVioletRed,
        callback = keyboard_config_callback)
)
keyboard_config_window.add_widget(
    ButtonGroup(
        x = 0, y = 0, width = 8, height = 2,
        name = "Scale",
        inactive_color = Colors.SkyBlue,
        callback = keyboard_config_callback)
)
keyboard_config_window.add_widget(
    Button(
        8, 0, 1, 1, 
        name = "switch", 
        callback = keyboard_config_callback, 
        inactive_color = Colors.Red)
)

sequencer_widgets = []
for i in range(16):
    sequencer_widgets.append(
        Sequencer(
            x = 0, y = 4, width = 8, height = 4, 
            clock = app.clock, 
            callback = sequencer_callback)
    )

sequencer_window.add_widget(
    ButtonGroup(
        x = 0, y = 0, width = 4, height = 4, 
        inactive_color = Pixel(255, 255, 0), 
        callback = sequencer_callback,
        name = "sample")
)
sequencer_window.add_widget(
    ButtonGroup(
        x = 4, y = 0, width = 1, height = 4,
        inactive_color = Pixel(255, 0, 255),
        callback = sequencer_callback,
        name = "height")
)
current_sequencer = 0

if __name__ == "__main__":
    # Runs until Ctrl+C or the grid window is closed
    app.run()
    keyboard.close()
