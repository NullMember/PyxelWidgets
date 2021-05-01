from PyxelWidgets.Window.Window import *
from PyxelWidgets import Widgets
from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *

def cb(name, value):
    if name == 'b1':
        print('B1 butonuna basildi')
    print(name, value)

w = Window('w', 20, 10)
ws = [Widgets.Button('b1', 1, 5, 4, 4, callback = cb, mode = Widgets.ButtonMode.Switch),
      Widgets.Fader('f1', 1, 1, 4, 4, callback = cb),
      Widgets.Sequencer('s1', 5, 5, 4, 4, callback = cb),
      Widgets.XY('xy1', 5, 1, 4, 4, callback = cb)]

c = MK3('Output', 'Output', Model.Mini)
w.addWidgets(ws)
w.setCallback(c.update)
c.setCallback(w.setButton)
c.init()
w.run()
