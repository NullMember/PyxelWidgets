import PyxelWidgets.Controllers.MIDI
import PyxelWidgets.Helpers
import collections
import enum
import numpy

class MK1(PyxelWidgets.Controllers.MIDI.MIDI):

    class Controls(enum.Enum):
        Knob_1 = 0
        Knob_2 = 1
        Knob_3 = 2
        Knob_4 = 3
        Knob_5 = 4
        Knob_6 = 5
        Knob_7 = 6
        Knob_8 = 7
        Knob_9 = 8
        Knob_10 = 9
        Knob_11 = 10
        Knob_12 = 11
        Knob_13 = 12
        Knob_14 = 13
        Knob_15 = 14
        Knob_16 = 15
        Up = 16
        Down = 17
        Left = 18
        Right = 19
        User = 20
        Factory = 21
    
    class Templates(enum.Enum):
        User_0 = 0
        User_1 = 1
        User_2 = 2
        User_3 = 3
        User_4 = 4
        User_5 = 5
        User_6 = 6
        User_7 = 7
        Factory_0 = 8
        Factory_1 = 9
        Factory_2 = 10
        Factory_3 = 11
        Factory_4 = 12
        Factory_5 = 13
        Factory_6 = 14
        Factory_7 = 15
    
    colors = [0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C]

    """ 
    Controller Class for Launchpad, Launchpad S, Launchpad Mini, Launchpad Mini MK2
    """
    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 8)
        kwargs['height'] = kwargs.get('height', 16)
        self.currentTemplate = MK1.Templates.User_0
        super().__init__(**kwargs)
    
    def reset(self, template):
        self.sendControlChange(0, 0, template.value)
    
    def selectTemplate(self, template):
        self.sendSysex([0x00, 0x20, 0x29, 0x02, 0x0A, 0x77, template.value])
        self.currentTemplate = template

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        colorIndex = pixel.gmono // 32
        self.sendSysex([0x00, 0x20, 0x29, 0x02, 0x0A, 0x78, y, x, MK1.colors[colorIndex]])

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort=inPort, outPort=outPort)
        self.reset(MK1.Templates.User_0)

    def disconnect(self):
        self.reset(MK1.Templates.User_0)
        super().disconnect()

    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            x = midi[1] % 0x10
            y = 7 - (midi[1] // 0x10)
            self.setButton(x, y, midi[2] / 127.0)
        elif cmd == 0xB0:
            x = midi[1] - 0x68
            y = 8
            self.setButton(x, y, midi[2] / 127.0)
        elif cmd == 0xF0:
            if midi[1:7] == [0x00, 0x20, 0x29, 0x02, 0x0A, 0x77]:
                self.currentTemplate = MK1.Templates(midi[7])

class XL(PyxelWidgets.Controllers.MIDI.MIDI):

    class Controls(enum.Enum):
        Knob_0 = 49
        Knob_1 = 50
        Knob_2 = 51
        Knob_3 = 52
        Knob_4 = 53
        Knob_5 = 54
        Knob_6 = 55
        Knob_7 = 56
        Knob_8 = 29
        Knob_9 = 30
        Knob_10 = 31
        Knob_11 = 32
        Knob_12 = 33
        Knob_13 = 34
        Knob_14 = 35
        Knob_15 = 36
        Knob_16 = 13
        Knob_17 = 14
        Knob_18 = 15
        Knob_19 = 16
        Knob_20 = 17
        Knob_21 = 18
        Knob_22 = 19
        Knob_23 = 20
        Fader_0 = 77
        Fader_1 = 78
        Fader_2 = 79
        Fader_3 = 80
        Fader_4 = 81
        Fader_5 = 82
        Fader_6 = 83
        Fader_7 = 84
        Up = 104
        Down = 105
        Left = 106
        Right = 107
    
    class Buttons(enum.Enum):
        Device = 105
        Mute = 106
        Solo = 107
        RecordArm = 108
    
    class Templates(enum.Enum):
        User_0 = 0
        User_1 = 1
        User_2 = 2
        User_3 = 3
        User_4 = 4
        User_5 = 5
        User_6 = 6
        User_7 = 7
        Factory_0 = 8
        Factory_1 = 9
        Factory_2 = 10
        Factory_3 = 11
        Factory_4 = 12
        Factory_5 = 13
        Factory_6 = 14
        Factory_7 = 15
    
    colors = [0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C]
    leds = [[0x49, 0x29, 0x0F, 0x0E, 0x0D],
            [0x4A, 0x2A, 0x1F, 0x1E, 0x1D],
            [0x4B, 0x2B, 0x2F, 0x2E, 0x2D],
            [0x4C, 0x2C, 0x3F, 0x3E, 0x3D],
            [0x59, 0x39, 0x4F, 0x4E, 0x4D],
            [0x5A, 0x3A, 0x5F, 0x5E, 0x5D],
            [0x5B, 0x3B, 0x6F, 0x6E, 0x6D],
            [0x5C, 0x3C, 0x7F, 0x7E, 0x7D]]
    ledsSysex = [[0x20, 0x18, 0x10, 0x08, 0x00],
                 [0x21, 0x19, 0x11, 0x09, 0x01],
                 [0x22, 0x1A, 0x12, 0x0A, 0x02],
                 [0x23, 0x1B, 0x13, 0x0B, 0x03],
                 [0x24, 0x1C, 0x14, 0x0C, 0x04],
                 [0x25, 0x1D, 0x15, 0x0D, 0x05],
                 [0x26, 0x1E, 0x16, 0x0E, 0x06],
                 [0x27, 0x1F, 0x17, 0x0F, 0x07]]

    """ 
    Controller Class for Launchpad, Launchpad S, Launchpad Mini, Launchpad Mini MK2
    """
    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 8)
        kwargs['height'] = kwargs.get('height', 5)
        self.currentTemplate = XL.Templates.User_0
        super().__init__(**kwargs)
    
    def reset(self, template):
        self.sendControlChange(0, 0, template.value)
        self.currentTemplate = template

    def selectTemplate(self, template):
        self.sendSysex([0x00, 0x20, 0x29, 0x02, 0x11, 0x77, template.value])
        self.currentTemplate = template

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        colorIndex = pixel.mono // 32
        if self.currentTemplate == XL.Templates.Factory_7:
            self.sendNoteOn(XL.leds[x][y], XL.colors[colorIndex], 0xF)
        else:
            self.sendSysex([0x00, 0x20, 0x29, 0x02, 0x11, 0x78, 0xF, XL.ledsSysex[x][y], XL.colors[colorIndex]])

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort=inPort, outPort=outPort)
        self.selectTemplate(XL.Templates.Factory_7)
        self.reset(self.currentTemplate)

    def disconnect(self):
        self.reset(XL.Templates.Factory_7)
        self.selectTemplate(XL.Templates.Factory_0)
        super().disconnect()

    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0xF0:
            if midi[1:7] == [0x00, 0x20, 0x29, 0x02, 0x11, 0x77]:
                self.currentTemplate = XL.Templates(midi[7])
        if self.currentTemplate == XL.Templates.Factory_7:
            if cmd == 0x80 or cmd == 0x90:
                if midi[1] < 0x30:
                    x = midi[1] - 0x29
                    y = 1
                    self.setButton(x, y, midi[2] / 127.0)
                elif midi[1] < 0x40:
                    x = midi[1] - 0x35
                    y = 1
                    self.setButton(x, y, midi[2] / 127.0)
                elif midi[1] < 0x50:
                    x = midi[1] - 0x49
                    y = 0
                    self.setButton(x, y, midi[2] / 127.0)
                elif midi[1] < 0x60:
                    x = midi[1] - 0x55
                    y = 0
                    self.setButton(x, y, midi[2] / 127.0)
                else:
                    button = XL.Buttons(midi[1])
                    if midi[2] > 0:
                        self.setCustom(PyxelWidgets.Helpers.Event.Pressed, button.name, midi[2] / 127.0)
                    else:
                        self.setCustom(PyxelWidgets.Helpers.Event.Released, button.name, 0.0)
            elif cmd == 0xB0:
                control = XL.Controls(midi[1])
                if midi[1] < 0x64:
                    self.setCustom(PyxelWidgets.Helpers.Event.Changed, control.name, midi[2] / 128.0)
                else:
                    if midi[2] > 0:
                        self.setCustom(PyxelWidgets.Helpers.Event.Pressed, control.name, midi[2] / 127.0)
                    else:
                        self.setCustom(PyxelWidgets.Helpers.Event.Released, control.name, midi[2] / 127.0)