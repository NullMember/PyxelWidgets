import time
import Window
import Widgets
import Widgets.Extra
from Controller.MIDI.Launchpad.MK3 import *
from Controller.OSC import *

def clb(name, value):
    if name == 'previous':
        if value == 0:
            manager.previousWindow()
            controller.setCallback(manager.window.setButton)
    elif name == 'next':
        if value == 0:
            manager.nextWindow()
            controller.setCallback(manager.window.setButton)
    else:
        print(name, value)

manager = Window.WindowManager()
windows = [Window.Window('a', 20, 12), Window.Window('b', 20, 12), Window.Window('c', 20, 12), Window.Window('d', 20, 12)]
manager.addWindows(windows)

# controller = OSC("192.168.0.21", width = 20, height = 12)
# controller = MK3(10, 10, 'MIDIIN2', 'MIDIOUT2', Model.Mini)
controller = MK3('MK3 MIDI 2', 'MK3 MIDI 2', Model.Mini)
controller.init()
controller.setCallback(manager.window.setButton)

widgets = [Widgets.Fader('f1', 1, 1, 1, 8, type = Widgets.FaderType.Single, direction = Widgets.FaderDirection.Vertical, callback = clb),
           Widgets.Fader('f2', 2, 1, 1, 8, type = Widgets.FaderType.BoostCut, direction = Widgets.FaderDirection.Vertical, callback = clb),
           Widgets.Fader('f3', 3, 1, 1, 8, type = Widgets.FaderType.Wrap, direction = Widgets.FaderDirection.Vertical, callback = clb),
           Widgets.Fader('f4', 4, 1, 1, 8, type = Widgets.FaderType.Spread, direction = Widgets.FaderDirection.Vertical, callback = clb),
           Widgets.Fader('f5', 5, 1, 4, 2, type = Widgets.FaderType.Single, direction = Widgets.FaderDirection.Horizontal, grid = Widgets.FaderGrid.Matrix, callback = clb),
           Widgets.Fader('f6', 5, 3, 4, 2, type = Widgets.FaderType.BoostCut, direction = Widgets.FaderDirection.Horizontal, grid = Widgets.FaderGrid.Matrix, callback = clb),
           Widgets.Fader('f7', 5, 5, 4, 2, type = Widgets.FaderType.Wrap, direction = Widgets.FaderDirection.Horizontal, grid = Widgets.FaderGrid.Matrix, callback = clb),
           Widgets.Fader('f8', 5, 7, 4, 2, type = Widgets.FaderType.Spread, direction = Widgets.FaderDirection.Horizontal, grid = Widgets.FaderGrid.Matrix, callback = clb)
           ]
buttons = [Widgets.Button('previous', 1, 9, 1, 1, callback = clb),
           Widgets.Button('next', 2, 9, 1, 1, callback = clb)]

manager.addWidgets(widgets)
manager.addWidgets(buttons)

manager.setCallback(controller.update)
manager.run()

while True:
    try:
        time.sleep(1)
    except:
        manager.stop()
        controller.deinit()
        break

# widgets = [Fader('f1', 1, 1, 1, 8, mode = FaderMode.Simple, callback = clb, resolution = 40),
#            Fader('f2', 2, 1, 1, 8, mode = FaderMode.Multi, callback = clb),
#            Fader('f3', 3, 1, 1, 8, mode = FaderMode.Magnitude, callback = clb),
#            Fader('f4', 4, 1, 1, 8, mode = FaderMode.Relative, callback = clb),
#            Fader('f5', 5, 1, 1, 8, mode = FaderMode.Sensitive, callback = clb),
#            Fader('f6', 6, 1, 1, 8, type = FaderType.Wrap, callback = clb),
#            Fader('f7', 7, 1, 1, 8, type = FaderType.BoostCut, callback = clb),
#            Fader('f8', 8, 1, 1, 8, type = FaderType.Spread, callback = clb)
#            ]
#widgets = [XY('xy1', 1, 1, 4, 4), XY('xy2', 5, 1, 4, 4), XY('xy3', 1, 5, 4, 4), XY('xy4', 5, 5, 4, 4)]
# btn = ButtonGroup('btn', 1, 1, 1, 1, 8, callback = clb)
#widgets = [Widgets.Fader('f', 1, 1, 8, 8, mode = Widgets.FaderMode.Relative, grid = Widgets.FaderGrid.Matrix)]
# widgets = [Widgets.Sequencer('s1', 1, 8, 8, 1, deactiveColor = [255, 0, 255], callback = clb),
#            Widgets.Sequencer('s2', 1, 7, 7, 1, deactiveColor = [255, 0, 255], callback = clb),
#            Widgets.Sequencer('s3', 1, 6, 6, 1, deactiveColor = [255, 0, 255], callback = clb),
#            Widgets.Sequencer('s4', 1, 5, 5, 1, deactiveColor = [255, 0, 255], callback = clb),
#            Widgets.Sequencer('s5', 1, 4, 4, 1, deactiveColor = [255, 0, 255], callback = clb),
#            Widgets.Sequencer('s6', 1, 3, 3, 1, deactiveColor = [255, 0, 255], callback = clb),
#            Widgets.Sequencer('s7', 1, 2, 2, 1, deactiveColor = [255, 0, 255], callback = clb),
#            Widgets.Sequencer('s8', 1, 1, 1, 1, deactiveColor = [255, 0, 255], callback = clb)]



# keyboard = Widgets.Extra.Keyboard('k1', 0, 0, 8, 8, mode = Widgets.Extra.KeyboardMode.DiatonicVertical, callback = clb)
# keyboard2 = Widgets.Extra.Keyboard('k2', 8, 0, 8, 8, mode = Widgets.Extra.KeyboardMode.DiatonicHorizontal, callback = clb)
# buttons = [Widgets.Button('previous', 1, 9, 1, 1, callback = clb),
#            Widgets.Button('next', 2, 9, 1, 1, callback = clb)]

# window.addWidgets(keyboard.widgets)
# window.addWidgets(keyboard2.widgets)
# # window.addWidgets(buttons)

# window2.addWidgets(keyboard2.widgets)
# window2.addWidgets(buttons)

# manager.setCallback(controller.update)
# manager.run()

# for mode in range(2):
#     keyboard.mode = Widgets.Extra.KeyboardMode(Widgets.Extra.KeyboardMode.ChromaticVertical.value + mode)
#     for scale in range(len(Widgets.Extra.KeyboardScales.values()) - 2):
#         keyboard.scale = Widgets.Extra.KeyboardScale(scale)
#         for fold in range(len(Widgets.Extra.KeyboardScales[keyboard.scale.name]) + 1):
#             keyboard.fold = fold + 1
#             print("{:16s}, {:16s}, Fold:{:02d}".format(keyboard.mode.name, keyboard.scale.name, keyboard.fold))
#             time.sleep(0.25)