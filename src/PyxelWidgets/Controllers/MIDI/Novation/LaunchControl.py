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
        Encoder_0 = 0
        Encoder_1 = 1
        Encoder_2 = 2
        Encoder_3 = 3
        Encoder_4 = 4
        Encoder_5 = 5
        Encoder_6 = 6
        Encoder_7 = 7
        Encoder_8 = 8
        Encoder_9 = 9
        Encoder_10 = 10
        Encoder_11 = 11
        Encoder_12 = 12
        Encoder_13 = 13
        Encoder_14 = 14
        Encoder_15 = 15
        Encoder_16 = 16
        Encoder_17 = 17
        Encoder_18 = 18
        Encoder_19 = 19
        Encoder_20 = 20
        Encoder_21 = 21
        Encoder_22 = 22
        Encoder_23 = 23
        Fader_0 = 24
        Fader_1 = 25
        Fader_2 = 26
        Fader_3 = 27
        Fader_4 = 28
        Fader_5 = 29
        Fader_6 = 30
        Fader_7 = 31
        Up = 32
        Down = 33
        Left = 34
        Right = 35
        Device = 36
        Mute = 37
        Solo = 38
        RecordArm = 39
    
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
        self.currentTemplate = XL.Templates.User_0
        super().__init__(**kwargs)
    
    def reset(self, template):
        self.sendControlChange(0, 0, template.value)
        self.currentTemplate = template

    def selectTemplate(self, template):
        self.sendSysex([0x00, 0x20, 0x29, 0x02, 0x0A, 0x77, template.value])
        self.currentTemplate = template

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        colorIndex = pixel.gmono // 32
        self.sendSysex([0x00, 0x20, 0x29, 0x02, 0x0A, 0x78, y, x, XL.colors[colorIndex]])

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort=inPort, outPort=outPort)
        self.reset(XL.Templates.User_0)

    def disconnect(self):
        self.reset(XL.Templates.User_0)
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
                self.currentTemplate = XL.Templates(midi[7])