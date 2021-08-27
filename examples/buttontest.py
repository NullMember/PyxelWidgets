from PyxelWidgets.Widgets import *
from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Window import *
from PyxelWidgets.Util.Clock import *

controller = MK3('MIDIIN2', 'MIDIOUT2', Model.Mini)
window = Window('main', 10, 10)
clock = Clock()

def sequencerCallback(name, event, data):
    print(name, event, data)

window.addWidget(Sequencer.Sequencer('seq', 8, 8, clock = clock, callback = sequencerCallback), 1, 1)

controller.setCallback(window.process)
clock.addTarget(Target('update', lambda tick : controller.update(window.x, window.y, window.update())))

controller.connect()
clock.start()

if __name__ == "__main__":
    while True:
        try:
            time.sleep(1)
        except:
            clock.terminate()
            controller.disconnect()
            break
