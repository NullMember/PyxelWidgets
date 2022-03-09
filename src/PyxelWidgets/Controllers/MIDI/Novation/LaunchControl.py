import PyxelWidgets.Controllers.MIDI
import PyxelWidgets.Helpers
import collections
import enum
import numpy

class MK1(PyxelWidgets.Controllers.MIDI.MIDI):

    class Controls(enum.Enum):
        Encoder_1 = 0
        Encoder_2 = 1
        Encoder_3 = 2
        Encoder_4 = 3
        Encoder_5 = 4
        Encoder_6 = 5
        Encoder_7 = 6
        Encoder_8 = 7
        Encoder_9 = 8
        Encoder_10 = 9
        Encoder_11 = 10
        Encoder_12 = 11
        Encoder_13 = 12
        Encoder_14 = 13
        Encoder_15 = 14
        Encoder_16 = 15
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
        Encoder_0 = 13
        Encoder_1 = 14
        Encoder_2 = 15
        Encoder_3 = 16
        Encoder_4 = 17
        Encoder_5 = 18
        Encoder_6 = 19
        Encoder_7 = 20
        Encoder_8 = 29
        Encoder_9 = 30
        Encoder_10 = 31
        Encoder_11 = 32
        Encoder_12 = 33
        Encoder_13 = 34
        Encoder_14 = 35
        Encoder_15 = 36
        Encoder_16 = 49
        Encoder_17 = 50
        Encoder_18 = 51
        Encoder_19 = 52
        Encoder_20 = 53
        Encoder_21 = 54
        Encoder_22 = 55
        Encoder_23 = 56
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
    pads = [[0x49, 0x29],
            [0x4A, 0x2A],
            [0x4B, 0x2B],
            [0x4C, 0x2C],
            [0x59, 0x39],
            [0x5A, 0x3A],
            [0x5B, 0x3B],
            [0x5C, 0x3C]]
    knobs = [[0x0F, 0x0E, 0x0D],
             [0x1F, 0x1E, 0x1D],
             [0x2F, 0x2E, 0x2D],
             [0x3F, 0x3E, 0x3D],
             [0x4F, 0x4E, 0x4D],
             [0x5F, 0x5E, 0x5D],
             [0x6F, 0x6E, 0x6D],
             [0x7F, 0x7E, 0x7D]]

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
        if self.currentTemplate == XL.Templates.Factory_7:
            colorIndex = pixel.gmono // 32
            if y < 2:
                self.sendNoteOn(XL.pads[x][y], XL.colors[colorIndex], 0xF)
            else:
                self.sendNoteOn(XL.knobs[x][y - 2], XL.colors[colorIndex], 0xF)
            #self.sendSysex([0x00, 0x20, 0x29, 0x02, 0x11, 0x78, y, x, XL.colors[colorIndex]])

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort=inPort, outPort=outPort)
        self.selectTemplate(XL.Templates.Factory_7)
        self.reset(self.currentTemplate)

    def disconnect(self):
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
                    y = 0
                    self.setButton(x, y, midi[2] / 127.0)
                elif midi[1] < 0x40:
                    x = midi[1] - 0x35
                    y = 0
                    self.setButton(x, y, midi[2] / 127.0)
                elif midi[1] < 0x50:
                    x = midi[1] - 0x49
                    y = 1
                    self.setButton(x, y, midi[2] / 127.0)
                elif midi[1] < 0x60:
                    x = midi[1] - 0x55
                    y = 1
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
                    self.setCustom(PyxelWidgets.Helpers.Event.Changed, control.name, midi[2] / 127.0)
                else:
                    if midi[2] > 0:
                        self.setCustom(PyxelWidgets.Helpers.Event.Pressed, control.name, midi[2] / 127.0)
                    else:
                        self.setCustom(PyxelWidgets.Helpers.Event.Released, control.name, midi[2] / 127.0)