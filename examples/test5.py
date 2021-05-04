from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Widgets.Extra.Keyboard import *
from PyxelWidgets.Window import *
from PyxelWidgets.WindowManager import *
import time

controller = MK3('Input', 'Input', Model.Mini)
controller2 = MK3('Output', 'Output', Model.Mini)

keyboard = Keyboard('keyboard', 0, 0, 8, 16)

window = Window('mainWindow', 8, 16)
window.addWidgets(keyboard.widgets)

manager = WindowManager()

manager.addController(controller, 0, 0)
manager.addController(controller2, 0, 10)

manager.addWindow(window)
manager.addWindowToRenderer('mainWindow', 1, 1, 8, 16)

if __name__ == "__main__":
    manager.run()
    while True:
        try:
            time.sleep(1)
        except:
            manager.stop()
            break