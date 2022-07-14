from DAWController import DAWController
from DAWController.enums import MCUButton
from PyxelWidgets.Controllers.Virtual import Virtual
from PyxelWidgets.Controllers.MIDI import MIDI
from PyxelWidgets.Utils.Enums import Event
from PyxelWidgets.Utils.Pixel import Pixel, Colors
from PyxelWidgets.Window import Window
from PyxelWidgets.Widgets import *
import time
import random

def fader_callback(name, event, data):
    name, index = name.split("_")
    index = int(index)
    if event == Event.Changed:
        daw_controller.fader(index, int(data * 16383.0))

def button_callback(name, event, data):
    if event == Event.Pressed:
        if "Mute" in name:
            name, index = name.split("_")
            index = int(index)
            daw_controller.tap(MCUButton.MUTE1.value + index)

def daw_callback(name, data):
    if name == "fader":
        index, value = data
        index = int(index)
        if index < 8:
            window.widgets[f"Fader_{index}"].value = value / 16383.0
    if name == "led":
        button, value = data
        if button.value >= MCUButton.MUTE1.value and button.value <= MCUButton.MUTE8.value:
            index = button.value - MCUButton.MUTE1.value
            window.widgets[f"Mute_{index}"].value = 1.0 if value else 0.0

window = Window(9, 9)
for i in range(8):
    window.addWidget(
        Fader.Fader(
            x = i, 
            y = 0, 
            width = 1, 
            height = 8, 
            name = f"Fader_{i}", 
            activeColor = Pixel(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
            callback = fader_callback
        )
    )

for i in range(8):
    window.addWidget(
        Button.Button(
            x = i, 
            y = 8, 
            width = 1, 
            height = 1, 
            name = f"Mute_{i}", 
            mode = Button.Button.Mode.Switch,
            activeColor = Colors.Red,
            deactiveColor = Colors.DarkRed,
            lock = True,
            callback = button_callback
        )
    )

window.addWidget(Button.Button(8, 0, 1, 1, name = "Record", callback = button_callback, activeColor = Colors.Red, deactiveColor = Colors.Red * 0.5))
window.addWidget(Button.Button(8, 1, 1, 1, name = "Play", callback = button_callback, activeColor = Colors.Green, deactiveColor = Colors.Green * 0.5))
window.addWidget(Button.Button(8, 2, 1, 1, name = "Stop", callback = button_callback, activeColor = Colors.Yellow, deactiveColor = Colors.Yellow * 0.5))

grid_controller = Virtual(9, 9)
grid_controller.init()
grid_controller.connect()
grid_controller.setCallback(window.process)

daw_controller = DAWController()
daw_controller.connect("DAWOut", "DAWIn")
daw_controller.setCallback(daw_callback)

while True:
    try:
        grid_controller.update(window.update())
        time.sleep(1 / 60)
    except:
        grid_controller.close()
        daw_controller.disconnect()
        break