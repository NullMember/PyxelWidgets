from PyxelWidgets import Window
from PyxelWidgets.Widgets import Knob
from PyxelWidgets.Controller.MIDI.Launchpad import MK3
from PyxelWidgets.Util import Clock
import time
from random import randint

def controllerCallback(name, event, value):
    print(name, event, value)
    # pass

window = Window.Window(10, 10)
controller = MK3.MK3('MIDIIN2', 'MIDIOUT2', MK3.Model.Mini)
clock = Clock.Clock()

for x in range(2):
    for y in range(2):
        window.addWidget(Knob.Knob(4, 4, callback = controllerCallback, clock = clock, type = Knob.KnobType.BoostCut, activeColor = [randint(0, 255), randint(0, 255), randint(0, 255)]), (x * 4) + 1, (y * 4) + 1)
        window.addWidget(Knob.Knob(2, 2, callback = controllerCallback, clock = clock, type = Knob.KnobType.BoostCut, activeColor = [randint(0, 255), randint(0, 255), randint(0, 255)]), (x * 4) + 2, (y * 4) + 2)

# for x in range(4):
#     window.addWidget(Knob.Knob('k' + str(x), 1, 8, callback = controllerCallback, clock = clock, activeColor = [randint(0, 255), randint(0, 255), randint(0, 255)]), 1 + x, 1)

controller.setCallback(window.process)
controller.connect()
clock.addTarget(Clock.Target('update', lambda tick : controller.update(window.x, window.y, window.update())))

if __name__ == "__main__":
    clock.start()
    while True:
        try:
            # c.update(w.x, w.y, w.update())
            # time.sleep(1 / 60)
            time.sleep(1)
        except:
            controller.disconnect()
            clock.terminate()
            break