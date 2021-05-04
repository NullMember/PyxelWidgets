from PyxelWidgets.Window import *
from PyxelWidgets.WindowManager import *
from PyxelWidgets.Widgets.Fader import *
from PyxelWidgets.Widgets.Extra.ButtonGroup import *
from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Controller.MIDI.MIDI import *
import time

currentWindow = 'window0'

def cb(name, value):
    global currentWindow
    if 'channel' in name:
        if value > 0:
            name, x, y = name.split(',')
            manager.removeWindowFromRenderer(currentWindow)
            currentWindow = 'window' + x
            manager.addWindowToRenderer(currentWindow, 0, 1, 19, 8)
            manager.forceUpdate()
    elif 'page' in name:
        name, x, y = name.split(',')
        if value > 0:
            print(name, x, y)
            manager.getWindow(currentWindow).x = (int(y) * 19)
    elif 'faders' in name:
        print(name, value)
        channel = int(name[6])
        control = int(name[7:9])
        # virtual.sendControlChange(control, int(value * 127), channel)

controller = MK3('Input', 'Input', Model.Mini)
controller2 = MK3('Output', 'Output', Model.Mini)
# virtual = MIDI('Output', 'Input')
manager = WindowManager()

windowTop = Window('windowTop', 8, 1)
windowRight = Window('windowRight', 1, 8)
windowMain = \
        [Window('window0', 16 * 8, 8),
         Window('window1', 16 * 8, 8), 
         Window('window2', 16 * 8, 8),
         Window('window3', 16 * 8, 8),
         Window('window4', 16 * 8, 8), 
         Window('window5', 16 * 8, 8), 
         Window('window6', 16 * 8, 8), 
         Window('window7', 16 * 8, 8)]

widgetsRight = ButtonGroup('page', 0, 0, 1, 8, callback = cb, deactiveColor = [255, 0, 0])
widgetsTop = ButtonGroup('channel', 0, 0, 8, 1, callback = cb, deactiveColor = [0, 255, 0])

faders = [[], [], [], [], [], [], [], []]
for i in range(128):
    faders[0].append(Fader('faders0' + "{:02d}".format(i), i, 0, 1, 8, callback = cb))
    faders[1].append(Fader('faders1' + "{:02d}".format(i), i, 0, 1, 8, callback = cb))
    faders[2].append(Fader('faders2' + "{:02d}".format(i), i, 0, 1, 8, callback = cb))
    faders[3].append(Fader('faders3' + "{:02d}".format(i), i, 0, 1, 8, callback = cb))
    faders[4].append(Fader('faders4' + "{:02d}".format(i), i, 0, 1, 8, callback = cb))
    faders[5].append(Fader('faders5' + "{:02d}".format(i), i, 0, 1, 8, callback = cb))
    faders[6].append(Fader('faders6' + "{:02d}".format(i), i, 0, 1, 8, callback = cb))
    faders[7].append(Fader('faders7' + "{:02d}".format(i), i, 0, 1, 8, callback = cb))

for i in range(8):
    windowMain[i].addWidgets(faders[i])
    manager.addWindow(windowMain[i])

windowRight.addWidgets(widgetsRight.widgets)
manager.addWindow(windowRight)

windowTop.addWidgets(widgetsTop.widgets)
manager.addWindow(windowTop)

manager.addWindowToRenderer(currentWindow, 0, 1, 19, 8)
manager.addWindowToRenderer('windowRight', 19, 1, 1, 8)
manager.addWindowToRenderer('windowTop', 1, 9, 8, 1)

manager.addController(controller, 0, 0, 10, 10)
manager.addController(controller2, 10, 0, 10, 10)

if __name__ == "__main__":
    manager.run()
    while True:
        try:
            time.sleep(1.0)
        except:
            manager.stop()
            controller.deinit()
            break
