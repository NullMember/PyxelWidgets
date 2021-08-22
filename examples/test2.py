from PyxelWidgets.Window import *
from PyxelWidgets.Widgets import *
from PyxelWidgets.Widgets.Extra import *
from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Util.Clock import *
import time

def cb(name, event, value):
    print(name, event, value)

w = Window('w', 10, 10)
#ws2 = Keyboard.Keyboard('keyboard', 1, 1, 8, 8, mode = Keyboard.KeyboardMode.DiatonicVertical, callback = cb)
#wb = ButtonGroup.ButtonGroup('bg', 1, 9, 8, 1, callback = cb)

c = MK3('MIDIIN2', 'MIDIOUT2', Model.Mini)
w.addWidget(Button.Button('b1', 4, 4, callback = cb, mode = Button.ButtonMode.Switch), 1, 5)
# w.addWidget(Knob.Knob('k1', 4, 4, callback = cb), 1, 1)
w.addWidget(Fader.Fader('f1', 4, 4, callback = cb, grid = Fader.FaderGrid.Matrix, resolution = 8), 1, 1)
w.addWidget(Sequencer.Sequencer('s1', 4, 4, callback = cb), 5, 5)
w.addWidget(XY.XY('xy1', 4, 4, callback = cb), 5, 1)
#w.addWidgets(wb.widgets)
c.setCallback(w.process)
c.connect()

cl = Clock()
# cl.addTarget(w.getWidget('k1')['widget'].target)

# print()

if __name__ == "__main__":
    cl.start()
    while True:
        try:
            c.update(w.x, w.y, w.update())
            time.sleep(1 / 60)
        except:
            c.disconnect()
            cl.terminate()
            break