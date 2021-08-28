from PyxelWidgets.Window import *
from PyxelWidgets.Widgets import *
from PyxelWidgets.Widgets.Extra import *
from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Util.Clock import *
from DAWController import *
import time
from random import randint

def controllerCallback(name, event, value):
    print(name, event, value)
    if name[0] == 'k':
        if name == 'k00':
            daw.vpot(0, int(window.widgets[name]['widget'].delta * 127))
        if name == 'k10':
            daw.vpot(1, int(window.widgets[name]['widget'].delta * 127))
        if name == 'k01':
            daw.vpot(2, int(window.widgets[name]['widget'].delta * 127))
        if name == 'k11':
            daw.vpot(3, int(window.widgets[name]['widget'].delta * 127))
        if name == 'b00':
            daw.tap(MCUButton.VSELECT1)
        if name == 'b10':
            daw.tap(MCUButton.VSELECT2)
        if name == 'b01':
            daw.tap(MCUButton.VSELECT3)
        if name == 'b11':
            daw.tap(MCUButton.VSELECT4)
    # pass

def dawCallback(name, data):
    print(name, data)
    if name == 'vpot':
        index, mode, ring, center = data
        if index == 0:
            window.widgets['k00']['widget'].display = ring / 12.0
            window.widgets['b00']['widget'].value = center
        if index == 1:
            window.widgets['k10']['widget'].display = ring / 12.0
            window.widgets['b10']['widget'].value = center
        if index == 2:
            window.widgets['k01']['widget'].display = ring / 12.0
            window.widgets['b01']['widget'].value = center
        if index == 3:
            window.widgets['k11']['widget'].display = ring / 12.0
            window.widgets['b11']['widget'].value = center

window = Window('w', 10, 10)
controller = MK3('Input', 'Input', Model.Mini)
clock = Clock()
daw = DAWController()
daw.connect('DAWO', 'DAWI')
daw.setCallback(dawCallback)

for x in range(2):
    for y in range(2):
        window.addWidget(Knob.Knob('k' + str(x) + str(y), 4, 4, callback = controllerCallback, clock = clock, activeColor = [randint(0, 255), randint(0, 255), randint(0, 255)]), (x * 4) + 1, (y * 4) + 1)
        window.addWidget(Button.Button('b' + str(x) + str(y), 2, 2, callback = controllerCallback, activeColor = [randint(0, 255), randint(0, 255), randint(0, 255)]), (x * 4) + 2, (y * 4) + 2)

# for x in range(4):
#     window.addWidget(Knob.Knob('k' + str(x), 1, 8, callback = controllerCallback, clock = clock, activeColor = [randint(0, 255), randint(0, 255), randint(0, 255)]), 1 + x, 1)

controller.setCallback(window.process)
controller.connect()
clock.addTarget(Target('update', lambda tick : controller.update(window.x, window.y, window.update())))

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