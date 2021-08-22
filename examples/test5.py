from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Widgets.Fader import *
from PyxelWidgets.Window import *
from PyxelWidgets.WindowManager import *
import time

controller = MK3('Input', 'Input', Model.Mini)
controller2 = MK3('Output', 'Output', Model.Mini)

fader = Fader('fader', 0, 0, 20, 10)

window = Window('mainWindow', 20, 10)
window.addWidget(fader)

manager = WindowManager()

manager.addController(controller, 0, 0)
manager.addController(controller2, 10, 0)

manager.addWindow(window)
manager.addWindowToRenderer('mainWindow', 1, 1, 20, 10)

if __name__ == "__main__":
    manager.run()
    while True:
        try:
            time.sleep(1)
        except:
            manager.stop()
            break