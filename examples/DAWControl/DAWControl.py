from pyxelwidgets.controllers.virtual import Virtual
from pyxelwidgets.controllers.midi import MIDI
from pyxelwidgets import Button, Colors, Event, Fader, Pixel, Window
import time
import random
import enum

class DAW(MIDI):

    class Buttons(enum.Enum):
        MUTE_0 = 16
        MUTE_1 = 17
        MUTE_2 = 18
        MUTE_3 = 19
        MUTE_4 = 20
        MUTE_5 = 21
        MUTE_6 = 22
        MUTE_7 = 23
        STOP = 93
        PLAY = 94
        RECORD = 95

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def process_midi(self, message, _):
        data, delta = message
        cmd = data[0] & 0xF0
        chn = data[0] & 0x0F
        if cmd == 0x90: # MCU Leds
            button = data[1]
            value = data[2]
            if button >= DAW.Buttons.MUTE_0.value and button < DAW.Buttons.MUTE_7.value: # MUTE1-8
                window.widgets[f"Mute_{button - 16}"].value = 1.0 if value else 0.0
            elif button == DAW.Buttons.STOP.value: # STOP
                window.widgets["Stop"].value = 1.0 if value else 0.0
            elif button == DAW.Buttons.PLAY.value: # PLAY
                window.widgets["Play"].value = 1.0 if value else 0.0
            elif button == DAW.Buttons.RECORD.value: # RECORD
                window.widgets["Record"].value = 1.0 if value else 0.0
        if cmd == 0xE0: # MCU Faders
            if chn >= 0 and chn < 8: # Channel Faders
                value = ((data[2] << 7) | data[1]) / (1 << 14)
                window.widgets[f"Fader_{chn}"].value = value

def fader_callback(name, event, data):
    name, index = name.split("_")
    index = int(index)
    if event == Event.Changed:
        daw_controller.send_pitch_bend(int(data * 16383.0), index)

def button_callback(name, event, data):
    if event == Event.Changed:
        if "Mute" in name:
            name, index = name.split("_")
            index = int(index)
            daw_controller.send_note_on(DAW.Buttons.MUTE_0.value + index, 127)
            daw_controller.send_note_off(DAW.Buttons.MUTE_0.value + index, 0)
        if name == "Stop":
            daw_controller.send_note_on(DAW.Buttons.STOP.value, 127)
            daw_controller.send_note_off(DAW.Buttons.STOP.value, 0)
        if name == "Play":
            daw_controller.send_note_on(DAW.Buttons.PLAY.value, 127 if data else 0)
            daw_controller.send_note_off(DAW.Buttons.PLAY.value, 0)
        if name == "Record":
            daw_controller.send_note_on(DAW.Buttons.RECORD.value, 127 if data else 0)
            daw_controller.send_note_off(DAW.Buttons.RECORD.value, 0)

window = Window(9, 9)
for i in range(8):
    window.add_widget(
        Fader(
            x = i, y = 0, width = 1, height = 8, 
            name = f"Fader_{i}", 
            active_color = Pixel(
                r = random.randint(0, 255), 
                g = random.randint(0, 255), 
                b = random.randint(0, 255)
            ),
            lock = True, callback = fader_callback
        )
    )

for i in range(8):
    window.add_widget(
        Button(
            x = i, y = 8, width = 1, height = 1, 
            name = f"Mute_{i}", mode = Button.Mode.Switch,
            active_color = Colors.Red,
            inactive_color = Colors.DarkRed,
            lock = True, callback = button_callback)
    )

window.add_widget(Button(
    x = 8, y = 0, width = 1, height = 1, 
    name = "Record", callback = button_callback, lock = True, 
    active_color = Colors.Red, inactive_color = Colors.Red * 0.5)
)
window.add_widget(Button(
    x = 8, y = 1, width = 1, height = 1, 
    name = "Play", callback = button_callback, lock = True, 
    active_color = Colors.Green, inactive_color = Colors.Green * 0.5)
)
window.add_widget(Button(
    x = 8, y = 2, width = 1, height = 1, 
    name = "Stop", callback = button_callback, lock = True, 
    active_color = Colors.Yellow, inactive_color = Colors.Yellow * 0.5)
)

grid_controller = Virtual(9, 9)
grid_controller.init()
grid_controller.connect()
grid_controller.set_callback(window.process)

daw_controller = DAW()
daw_controller.init()
daw_controller.connect_virtual("DAW")

while True:
    try:
        grid_controller.update(window.update())
        time.sleep(1 / 60)
    except KeyboardInterrupt:
        grid_controller.close()
        daw_controller.close()
        break