from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Widgets import *
from PyxelWidgets.Window import *
from PyxelWidgets.Util.Clock import *

def cb(name, event, value):
    if event == 'pressed':
        if name == 'up':
            window.widgets['fader']['widget'].height += 1
        if name == 'down':
            window.widgets['fader']['widget'].height -= 1
        if name == 'left':
            window.widgets['fader']['widget'].width -= 1
        if name == 'right':
            window.widgets['fader']['widget'].width += 1
    print(name, event, value)

controller = MK3('Input', 'Input', Model.Mini)
window = Window('main', 1000, 1000)
clock = Clock()

window.addWidget(Button.Button('up', 1, 1, callback = cb), 1, 9)
window.addWidget(Button.Button('down', 1, 1, callback = cb), 2, 9)
window.addWidget(Button.Button('left', 1, 1, callback = cb), 3, 9)
window.addWidget(Button.Button('right', 1, 1, callback = cb), 4, 9)
window.addWidget(Fader.Fader('fader', 1000, 1000, grid = Fader.FaderGrid.Matrix, callback = cb), 0, 0)
# window.addWidget(Button.Button('fader', 2, 2, callback = cb), 1, 1)
# window.addWidget(XY.XY('fader', 2, 2, callback = cb), 1, 1)

controller.setCallback(window.process)
clock.addTarget(Target('update', lambda tick : controller.update(window.x, window.y, window.update())))

if __name__ == "__main__":
    controller.connect()
    clock.start()
    while True:
        try:
            time.sleep(1)
        except:
            clock.terminate()
            controller.disconnect()
            break