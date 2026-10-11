from pyxelwidgets.devices.virtual import Virtual
from pyxelwidgets.devices.midi import MIDI
from pyxelwidgets import App, Button, Changed, Color, Colors, Fader, Surface
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

    def process_midi(self, message, _):
        # Called on rtmidi's thread: hold the app lock while changing widgets
        with app.lock:
            self.update_widgets(message[0])

    def update_widgets(self, data):
        cmd = data[0] & 0xF0
        chn = data[0] & 0x0F
        if cmd == 0x90: # MCU Leds
            button = data[1]
            value = 1.0 if data[2] else 0.0
            if button >= DAW.Buttons.MUTE_0.value and button <= DAW.Buttons.MUTE_7.value: # MUTE1-8
                mutes[button - DAW.Buttons.MUTE_0.value].value = value
            elif button in transport:
                transport[button].value = value
        if cmd == 0xE0: # MCU Faders
            if chn >= 0 and chn < 8: # Channel Faders
                faders[chn].value = ((data[2] << 7) | data[1]) / (1 << 14)

def send_button(note, pressed):
    daw_controller.send_note_on(note, 127 if pressed else 0)
    daw_controller.send_note_off(note, 0)

surface = Surface(9, 9)

# Widgets only show what the DAW sends back (interactive = False); input is forwarded to the DAW
faders = []
mutes = []
for i in range(8):
    fader = surface.add(Fader(
        x = i, y = 0, width = 1, height = 8,
        active_color = Color(
            r = random.randint(0, 255),
            g = random.randint(0, 255),
            b = random.randint(0, 255)
        ),
        interactive = False))
    fader.on(Changed, lambda e, channel = i: daw_controller.send_pitch_bend(int(e.value * 16383.0), channel))
    faders.append(fader)

    mute = surface.add(Button(
        x = i, y = 8, width = 1, height = 1,
        mode = Button.Mode.Switch,
        active_color = Colors.Red,
        inactive_color = Colors.DarkRed,
        interactive = False))
    # Mutes toggle in the DAW, so every press sends a full note
    mute.on(Changed, lambda e, note = DAW.Buttons.MUTE_0.value + i: send_button(note, True))
    mutes.append(mute)

transport = {}
for y, (button, color) in enumerate([(DAW.Buttons.RECORD, Colors.Red), (DAW.Buttons.PLAY, Colors.Green), (DAW.Buttons.STOP, Colors.Yellow)]):
    widget = surface.add(Button(
        x = 8, y = y, width = 1, height = 1,
        interactive = False,
        active_color = color, inactive_color = color * 0.5))
    widget.on(Changed, lambda e, note = button.value: send_button(note, e.value))
    transport[button.value] = widget

grid_controller = Virtual(9, 9)
grid_controller.connect()
surface.add_device(grid_controller)
app = App(surface)

daw_controller = DAW()
daw_controller.connect_virtual("DAW")

# Runs until Ctrl+C or the grid window is closed
app.run()
daw_controller.close()
