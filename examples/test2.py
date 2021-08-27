from PyxelWidgets.Window import *
from PyxelWidgets.Widgets import *
from PyxelWidgets.Widgets.Extra import *
from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Util.Clock import *
import time

def cb(name, event, value):
    print(name, event, value)

window = Window('w', 10, 10)
#ws2 = Keyboard.Keyboard('keyboard', 1, 1, 8, 8, mode = Keyboard.KeyboardMode.DiatonicVertical, callback = cb)
#wb = ButtonGroup.ButtonGroup('bg', 1, 9, 8, 1, callback = cb)

controller = MK3('MIDIIN2', 'MIDIOUT2', Model.Mini)
window.addWidget(Button.Button('b1', 4, 4, callback = cb, mode = Button.ButtonMode.Switch), 1, 5)
# w.addWidget(Knob.Knob('k1', 4, 4, callback = cb), 1, 1)
window.addWidget(Fader.Fader('f1', 4, 4, callback = cb, grid = Fader.FaderGrid.Matrix, resolution = 8), 1, 1)
window.addWidget(Sequencer.Sequencer('s1', 4, 4, callback = cb), 5, 5)
window.addWidget(XY.XY('xy1', 4, 4, callback = cb), 5, 1)
#w.addWidgets(wb.widgets)
controller.setCallback(window.process)
controller.connect()

clock = Clock()
clock.addTarget(window.widgets['s1']['widget'].target)
clock.addTarget(Target('update', lambda tick : controller.update(window.x, window.y, window.update())))
# cl.addTarget(w.widgets['k1']['widget'].target)

# print()

if __name__ == "__main__":
    clock.start()
    while True:
        try:
            # controller.update(window.x, window.y, window.update())
            # time.sleep(1 / 60)
            time.sleep(1)
        except:
            controller.disconnect()
            clock.terminate()
            break