from PyxelWidgets.Controllers.Virtual import Virtual
from PyxelWidgets.Controllers.MIDI import MIDI
from PyxelWidgets.Utils.Window import Window, Manager
from PyxelWidgets.Utils.Enums import *
from PyxelWidgets.Utils.Rectangle import *
from PyxelWidgets.Utils.Pixel import *
from PyxelWidgets.Widgets import *
import time
import random

def buttonCallback(name: str, event: str, data):
    global currentWindow
    x, y = data
    if event == Event.Pressed:
        if windows[currentWindow] == sequencerWindow:
            sequencerWindow.removeWidget(sequencerWidgets[currentSequencer].name)
        if windows[currentWindow] == keyboardWindow:
            manager.removeWindow(keyboardConfigWindow.name)
        manager.removeWindow(windows[currentWindow].name)
        currentWindow = x
        manager.addWindow(windows[currentWindow], 0, 0, 9, 8)
        if windows[currentWindow] == sequencerWindow:
            sequencerWindow.addWidget(sequencerWidgets[currentSequencer])

def faderCallback(name: str, event: str, data):
    if event == Event.Changed:
        index = name.split("_")[1]
        index = int(index)
        keyboard.sendControlChange(index + 8, int(data * 127.0))

def knobCallback(name: str, event: str, data):
    if event == Event.Changed:
        index = name.split("_")[1]
        index = int(index)
        keyboard.sendControlChange(index + 16, int(data * 127.0))

def keyboardCallback(name: str, event: str, data):
    if name == "Keyboard":
        if event == Event.Changed:
            note, velocity = data
            keyboard.sendNoteOn(note, int(velocity * 127.0))
    if name == "switch":
        if event == Event.Released:
            manager.removeWindow(keyboardWindow.name)
            manager.addWindow(keyboardConfigWindow, 0, 0, 9, 8)

def keyboardConfigCallback(name: str, event: str, data):
    keyboard = keyboardWindow.widgets['Keyboard']
    if name == "Type":
        if event == Event.Pressed:
            x, y = data
            keyboard.type = Keyboard.Keyboard.Type(x)
    if name == "Root":
        if event == Event.Changed:
            note, velocity = data
            note %= 12
            if note < len(Keyboard.Keyboard.Root):
                keyboard.root = Keyboard.Keyboard.Root(note)
    elif name == "Octave":
        if event == Event.Pressed:
            x, y = data
            keyboard.octave = x
    elif name == "Scale":
        if event == Event.Pressed:
            scale = keyboardConfigWindow.widgets['Scale']
            x, y = data
            scale = x + (y * scale.width)
            if scale < len(Keyboard.Keyboard.Scale):
                keyboard.scale = Keyboard.Keyboard.Scale(scale)
    elif name == "switch":
        if event == Event.Released:
            manager.removeWindow(keyboardConfigWindow.name)
            manager.addWindow(keyboardWindow, 0, 0, 9, 8)

def sequencerCallback(name: str, event: str, data):
    global currentSequencer
    if "Sequencer" in name:
        prefix, index = name.split("_")
        index = int(index)
        if event == Event.Tick:
            keyboard.sendNoteOn(36 + index, 0, 1)
        if event == Event.Active:
            keyboard.sendNoteOn(36 + index, 100 + random.randint(-10, 10), 1)
    elif "sample" in name:
        if event == Event.Pressed:
            x, y = data
            sequencerWindow.removeWidget(sequencerWidgets[currentSequencer].name)
            currentSequencer = x + (y * 4)
            keyboard.sendNoteOn(36 + currentSequencer, 100, 1)
            keyboard.sendNoteOn(36 + currentSequencer, 0, 1)
            sequencerWindow.addWidget(sequencerWidgets[currentSequencer])
        if event == Event.Held:
            x, y = data
            sequencerWidgets[x + (y * 4)].reset()
    elif "height" in name:
        if event == Event.Pressed:
            x, y = data
            for sequencer in sequencerWidgets:
                sequencer.step = (y + 1) * 8
            sequencerWindow.forceUpdate()

controller = Virtual(9, 9)
controller.init(True)
controller.connect()

keyboard = MIDI()
keyboard.init()
keyboard.connectVirtual('Keyboard')

faderWindow = Window(9, 8)
knobWindow = Window(9, 8)
keyboardWindow = Window(9, 8)
keyboardConfigWindow = Window(9, 8)
sequencerWindow = Window(9, 8)

topButtonWindow = Window(8, 1)

windows = [faderWindow, knobWindow, keyboardWindow, sequencerWindow]
currentWindow = 0

manager = Manager(9, 9)
manager.addWindow(topButtonWindow, 0, 8, 8, 1)
manager.addWindow(windows[currentWindow], 0, 0, 9, 8)
manager.addController(controller, 0, 0)

topButtonWindow.addWidget(
    ButtonGroup.ButtonGroup(
        x = 0, y = 0, width = len(windows), height = 1, 
        deactiveColor = Colors.Blue, 
        callback = buttonCallback)
)

for i in range(8):
    faderWindow.addWidget(
        Fader.Fader(
            x = i, y = 0, width = 1, height = 8, 
            name = f"DAWFader_{i}", 
            callback = faderCallback, 
            activeColor = Pixel(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    )

for i in range(8):
    knobWindow.addWidget(
        Knob.Knob(
            x = 0, y = 7 - i, width = 8, height = 1, 
            name = f"DAWKnob_{i}", 
            callback = knobCallback, 
            type = Knob.Knob.Type.BoostCut,
            activeColor = Pixel(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    )

keyboardWindow.addWidget(
    Keyboard.Keyboard(
        x = 0, y = 0, width = 8, height = 8,
        name = "Keyboard",
        type = Keyboard.Keyboard.Type.DiatonicVertical, 
        scale = Keyboard.Keyboard.Scale.Major, 
        root = Keyboard.Keyboard.Root.C, 
        fold = 4, octave = 4,
        callback = keyboardCallback)
)
keyboardWindow.addWidget(
    Button.Button(
        8, 0, 1, 1, 
        name = "switch", 
        callback = keyboardCallback, 
        deactiveColor = Colors.Red)
)
keyboardConfigWindow.addWidget(
    ButtonGroup.ButtonGroup(
        x = 0, y = 7, width = len(Keyboard.Keyboard.Type), height = 1,
        name = "Type",
        callback = keyboardConfigCallback)
)
keyboardConfigWindow.addWidget(
    Keyboard.Keyboard(
        x = 0, y = 5, width = 8, height = 2,
        name = "Root",
        type = Keyboard.Keyboard.Type.Keyboard,
        callback = keyboardConfigCallback)
)
keyboardConfigWindow.addWidget(
    ButtonGroup.ButtonGroup(
        x = 0, y = 4, width = 8, height = 1,
        name = "Octave",
        deactiveColor = Colors.PaleVioletRed,
        callback = keyboardConfigCallback)
)
keyboardConfigWindow.addWidget(
    ButtonGroup.ButtonGroup(
        x = 0, y = 0, width = 8, height = 2,
        name = "Scale",
        deactiveColor = Colors.SkyBlue,
        callback = keyboardConfigCallback)
)
keyboardConfigWindow.addWidget(
    Button.Button(
        8, 0, 1, 1, 
        name = "switch", 
        callback = keyboardConfigCallback, 
        deactiveColor = Colors.Red)
)

sequencerWidgets = []
for i in range(16):
    sequencerWidgets.append(
        Sequencer.Sequencer(
            x = 0, y = 4, width = 8, height = 4, 
            clock = controller.clock, 
            callback = sequencerCallback)
    )

sequencerWindow.addWidget(
    ButtonGroup.ButtonGroup(
        x = 0, y = 0, width = 4, height = 4, 
        deactiveColor = Pixel(255, 255, 0), 
        callback = sequencerCallback,
        name = "sample")
)
sequencerWindow.addWidget(
    ButtonGroup.ButtonGroup(
        x = 4, y = 0, width = 1, height = 4,
        deactiveColor = Pixel(255, 0, 255),
        callback = sequencerCallback,
        name = "height")
)
currentSequencer = 0

if __name__ == "__main__":
    while True:
        try:
            manager.update()
            time.sleep(1 / 60)
        except KeyboardInterrupt:
            manager.destroy()
            break