from PyxelWidgets.Window import *
from PyxelWidgets.Widgets import *
from PyxelWidgets.Widgets.Extra import *
from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
import time

def cb(name: str, value):
    if 'bg' in name:
        name, x, y = name.split(',')
        if value > 0:
            if x == 0:
                ws2.tone = Keyboard.KeyboardTone.C
                ws2.octave = 0
            elif x == 1:
                ws2.tone = Keyboard.KeyboardTone.D
                ws2.octave = 0
            elif x == 2:
                ws2.tone = Keyboard.KeyboardTone.E
                ws2.octave = 0
            elif x == 3:
                ws2.tone = Keyboard.KeyboardTone.F
                ws2.octave = 0
            elif x == 4:
                ws2.tone = Keyboard.KeyboardTone.G
                ws2.octave = 0
            elif x == 5:
                ws2.tone = Keyboard.KeyboardTone.A
                ws2.octave = 0
            elif x == 6:
                ws2.tone = Keyboard.KeyboardTone.B
                ws2.octave = 0
            elif x == 7:
                ws2.tone = Keyboard.KeyboardTone.C
                ws2.octave = 1
    print(name, value)

w = Window('w', 20, 10)
ws = [Button.Button('b1', 1, 5, 4, 4, callback = cb, mode = Button.ButtonMode.Switch),
      Fader.Fader('f1', 1, 1, 4, 4, callback = cb, grid = Fader.FaderGrid.Matrix, resolution = 8),
      Sequencer.Sequencer('s1', 5, 5, 4, 4, callback = cb),
      XY.XY('xy1', 5, 1, 4, 4, callback = cb)]
ws2 = Keyboard.Keyboard('keyboard', 1, 1, 8, 8, mode = Keyboard.KeyboardMode.DiatonicVertical, callback = cb)
wb = ButtonGroup.ButtonGroup('bg', 1, 9, 8, 1, callback = cb)

c = MK3('Input', 'Input', Model.Mini)
w.addWidgets(ws2.widgets)
w.addWidgets(wb.widgets)
w.setCallback(c.updateArea)
c.setCallback(w.setButton)
c.init()

if __name__ == "__main__":
    w.run()
    while True:
        try:
            time.sleep(1)
        except:
            c.deinit()
            w.stop()
            break