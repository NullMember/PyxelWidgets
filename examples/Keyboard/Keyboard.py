from PyxelWidgets.Controllers.Virtual import Virtual
from PyxelWidgets.Controllers.MIDI import MIDI
from PyxelWidgets.Utils.Enums import Event
from PyxelWidgets.Window import Window
from PyxelWidgets.Widgets import *
import time

def keyboard_callback(name, event, data):
    if event == Event.Changed:
        note, velocity = data
        if velocity > 0.0:
            keyboard_controller.sendNoteOn(note, int(velocity * volume_fader.value * 127.0))
        else:
            keyboard_controller.sendNoteOff(note)

def button_callback(name, event, data):
    if event == Event.Pressed:
        x, y = data
        keyboard_widget.octave = x

# 9 hucre genislige ve 9 hucre yukseklige sahip bir pencere olusturuluyor 
window = Window(9, 9)

# Kullanilacak araclar olusturuluyor
keyboard_widget = Keyboard.Keyboard(
    x = 0, 
    y = 0, 
    width = 8, 
    height = 8, 
    type = Keyboard.Keyboard.Type.DiatonicVertical,
    scale = Keyboard.Keyboard.Scale.Major,
    root = Keyboard.Keyboard.Root.C,
    callback = keyboard_callback)
octave_buttons = ButtonGroup.ButtonGroup(0, 8, 8, 1, callback = button_callback)
octave_buttons.tapped(5, 0)
volume_fader = Fader.Fader(8, 0, 1, 8)
volume_fader.tapped(0, 5)

# Olusturulan araclar pencere icerisine ekleniyor
window.addWidget(keyboard_widget)
window.addWidget(octave_buttons)
window.addWidget(volume_fader)

# 9 hucre genislige ve 9 hucre yukseklige sahip
# sanal bir grid kontrolcu olusturuluyor
grid_controller = Virtual(9, 9)
grid_controller.init()
grid_controller.connect()
# Grid kontrolcuden gelen kullanici girisleri Window'a aktariliyor
grid_controller.setCallback(window.process)

# Sanal bir MIDI baglanti noktasi olusturuluyor
keyboard_controller = MIDI()
keyboard_controller.init()
keyboard_controller.connectVirtual("Keyboard")

while True:
    try:
        grid_controller.update(window.update())
        time.sleep(1 / 60)
    except KeyboardInterrupt:
        grid_controller.close()
        break