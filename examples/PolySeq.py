from PyxelWidgets.Window import *
from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Widgets.Sequencer import *
from PyxelWidgets.Util.Clock import *

controller = MK3('Input', 'Input', Model.Mini)
window = Window('main', 10, 10)
clock = Clock(120, 480)
controller.setCallback(window.process)

def cb(name, event, value):
    pass

for i in range(8):
    window.addWidget(Sequencer('s' + str(i), 8, 1, clock = clock, callback = cb), 1, 1 + i)

# clock.addTarget(Target('update', lambda tick : controller.update(window.x, window.y, window.update())))

if __name__ == "__main__":
    controller.connect()
    clock.start()
    while True:
        try:
            controller.update(window.x, window.y, window.update())
            time.sleep(1 / 60)
        except:
            clock.terminate()
            controller.disconnect()
            break