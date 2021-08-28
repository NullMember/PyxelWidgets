from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Window import *
from PyxelWidgets.Widgets import *
from PyxelWidgets.Util.Clock import *

controller = MK3('Input', 'Input', Model.Mini)
window = Window('main', 10, 10)
clock = Clock()

def cb(name, event, value):
    if event == 'pressed':
        if name == 'start':
            life.start()
        if name == 'stop':
            life.stop()

life = Life.Life('life', 8, 8)
window.addWidget(life, 1, 1)
window.addWidget(Button.Button('start', 1, 1, callback = cb), 1, 9)
window.addWidget(Button.Button('stop', 1, 1, callback = cb), 2, 9)
clock.addTarget(Target('life', life.tick, clock.ppq / 2))

controller.setCallback(window.process)
clock.addTarget(Target('update', lambda tick : controller.update(window.x, window.y, window.update())))

if __name__ == '__main__':
    controller.connect()
    clock.start()
    while True:
        try:
            time.sleep(1)
        except:
            clock.terminate()
            controller.disconnect()
            break