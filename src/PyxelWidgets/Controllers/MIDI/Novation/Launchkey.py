import PyxelWidgets.Controllers.MIDI
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import enum
import numpy

class MK1(PyxelWidgets.Controllers.MIDI.MIDI):
    """ 
    Controller Class for Launchkey MK1 serie controllers
    """
    class Mode(enum.Enum):
        Basic = 0
        Extended = 127
    
    class InControl(enum.Enum):
        Pots = 0x0D
        Slider = 0x0E
        Pads = 0x0F
    
    class Controls(enum.Enum):
        Track_L = 102
        Track_R = 103
        Rewind = 112
        Forward = 113
        Stop = 114
        Play = 115
        Loop = 116
        Record = 117
        Fader_0 = 41
        Fader_1 = 42
        Fader_2 = 43
        Fader_3 = 44
        Fader_4 = 45
        Fader_5 = 46
        Fader_6 = 47
        Fader_7 = 48
        Fader_8 = 7
        Button_0 = 51
        Button_1 = 52
        Button_2 = 53
        Button_3 = 54
        Button_4 = 55
        Button_5 = 56
        Button_6 = 57
        Button_7 = 58
        Button_8 = 59
        Knob_0 = 21
        Knob_1 = 22
        Knob_2 = 23
        Knob_3 = 24
        Knob_4 = 25
        Knob_5 = 26
        Knob_6 = 27
        Knob_7 = 28
    
    colors = [0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C]

    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 9)
        kwargs['height'] = kwargs.get('height', 2)
        super().__init__(**kwargs)

    def setMode(self, mode: Mode):
        self.sendNoteOn(0x0C, mode.value)

    def enableInControl(self, control: InControl):
        self.sendNoteOn(control.value, 0x7F, 0xF)
    
    def disableInControl(self, control: InControl):
        self.sendNoteOn(control.value, 0x00, 0xF)

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        colorIndex = pixel.gmono // 32
        index = 0
        if y == 0:
            index = 0x70 + x
        elif y == 1:
            index = 0x60 + x
        else:
            return
        self.sendNoteOn(index, MK1.colors[colorIndex])

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort=inPort, outPort=outPort)
        self.setMode(MK1.Mode.Extended)
        self.enableInControl(MK1.InControl.Pads)

    def disconnect(self):
        self.setMode(MK1.Mode.Basic)
        super().disconnect()

    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            if midi[1] < 0x80 and midi[1] >= 0x60:
                x = midi[1] % 0x10
                y = 7 - (midi[1] // 0x10)
                self.setButton(x, y, midi[2] / 127.0)
        if cmd == 0xB0:
            if midi[1] > 50:
                if midi[2] > 0:
                    self.setCustom(PyxelWidgets.Utils.Enums.Event.Pressed, MK1.Controls(midi[1]).name, 1.0)
                else:
                    self.setCustom(PyxelWidgets.Utils.Enums.Event.Released, MK1.Controls(midi[1]).name, 0.0)
            else:
                self.setCustom(PyxelWidgets.Utils.Enums.Event.Changed, MK1.Controls(midi[1]).name, midi[2] / 127)

class MK2(PyxelWidgets.Controllers.MIDI.MIDI):

    class Mode(enum.Enum):
        Basic = 0
        Extended = 127
    
    class InControl(enum.Enum):
        pots = 0x0D
        slider = 0x0E
        pads = 0x0F

    palette = numpy.array([(0, 0, 0), (31, 31, 31), (127, 127, 127), (255, 255, 255), 
                           (255, 75, 75), (255, 0, 0), (87, 0, 0), (27, 0, 0), 
                           (255, 187, 107), (255, 83, 0), (87, 31, 0), (39, 27, 0), 
                           (255, 255, 75), (255, 255, 0), (87, 87, 0), (27, 27, 0), 
                           (135, 255, 75), (83, 255, 0), (31, 87, 0), (19, 43, 0), 
                           (75, 255, 75), (0, 255, 0), (0, 87, 0), (0, 27, 0), 
                           (75, 255, 95), (0, 255, 27), (0, 87, 15), (0, 27, 0), 
                           (75, 255, 135), (0, 255, 87), (0, 87, 31), (0, 31, 19), 
                           (75, 255, 183), (0, 255, 151), (0, 87, 55), (0, 27, 19), 
                           (75, 195, 255), (0, 167, 255), (0, 67, 83), (0, 15, 27), 
                           (75, 135, 255), (0, 87, 255), (0, 31, 87), (0, 7, 27), 
                           (75, 75, 255), (0, 0, 255), (0, 0, 87), (0, 0, 27), 
                           (135, 75, 255), (83, 0, 255), (27, 0, 99), (15, 0, 47), 
                           (255, 75, 255), (255, 0, 255), (87, 0, 87), (27, 0, 27), 
                           (255, 75, 135), (255, 0, 83), (87, 0, 31), (35, 0, 19), 
                           (255, 23, 0), (151, 55, 0), (119, 83, 0), (67, 99, 0), 
                           (0, 59, 0), (0, 87, 55), (0, 83, 127), (0, 0, 255), 
                           (0, 71, 79), (39, 0, 203), (127, 127, 127), (31, 31, 31), 
                           (255, 0, 0), (187, 255, 47), (175, 235, 7), (99, 255, 11), 
                           (15, 139, 0), (0, 255, 135), (0, 167, 255), (0, 43, 255), 
                           (63, 0, 255), (123, 0, 255), (175, 27, 123), (63, 35, 0), 
                           (255, 75, 0), (135, 223, 7), (115, 255, 23), (0, 255, 0), 
                           (59, 255, 39), (87, 255, 111), (55, 255, 203), (91, 139, 255), 
                           (51, 83, 195), (135, 127, 231), (211, 31, 255), (255, 0, 91), 
                           (255, 127, 0), (183, 175, 0), (143, 255, 0), (131, 91, 7), 
                           (59, 43, 0), (19, 75, 15), (15, 79, 55), (23, 23, 43), 
                           (23, 31, 91), (103, 59, 27), (167, 0, 11), (219, 83, 63), 
                           (215, 107, 27), (255, 223, 39), (159, 223, 47), (103, 179, 15), 
                           (31, 31, 47), (219, 255, 107), (127, 255, 187), (155, 151, 255), 
                           (143, 103, 255), (63, 63, 63), (115, 115, 115), (223, 255, 255), 
                           (159, 0, 0), (55, 0, 0), (27, 207, 0), (7, 67, 0), 
                           (183, 175, 0), (63, 51, 0), (179, 95, 0), (75, 23, 0)])
    
    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 8)
        kwargs['height'] = kwargs.get('height', 2)
        super().__init__(**kwargs)

    def setMode(self, mode: Mode):
        self.sendNoteOn(0x0C, mode.value, 0xF)

    def enableInControl(self, control: InControl):
        self.sendNoteOn(control.value, 0x7F, 0xF)
    
    def disableInControl(self, control: InControl):
        self.sendNoteOn(control.value, 0x00, 0xF)

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        index = 0
        if y == 0:
            index = 0x70 + x
        elif y == 1:
            index = 0x60 + x
        else:
            return
        self.sendNoteOn(index, pixel.findInPalette(self.palette))

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort=inPort, outPort=outPort)
        self.setMode(MK2.Mode.Extended)
        self.enableInControl(MK2.InControl.pads)

    def disconnect(self):
        self.disableInControl(MK2.InControl.pads)
        self.setMode(MK2.Mode.Basic)
        super().disconnect()

    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            if midi[1] < 0x80 and midi[1] >= 0x60:
                x = midi[1] % 0x10
                y = 7 - (midi[1] // 0x10)
                self.setButton(x, y, midi[2] / 127.0)

class MK3(PyxelWidgets.Controllers.MIDI.MIDI):

    class Mode(enum.Enum):
        Other = 0
        DAW = 127

    class Layout(enum.Enum):
        Drum = 1
        Session = 2
        Custom = 5
        Drum2 = 6
        Toggle = 7
        ProgramChange = 8

    palette = numpy.array([(0, 0, 0), (31, 31, 31), (127, 127, 127), (255, 255, 255), 
                           (255, 75, 75), (255, 0, 0), (87, 0, 0), (27, 0, 0), 
                           (255, 187, 107), (255, 83, 0), (87, 31, 0), (39, 27, 0), 
                           (255, 255, 75), (255, 255, 0), (87, 87, 0), (27, 27, 0), 
                           (135, 255, 75), (83, 255, 0), (31, 87, 0), (19, 43, 0), 
                           (75, 255, 75), (0, 255, 0), (0, 87, 0), (0, 27, 0), 
                           (75, 255, 95), (0, 255, 27), (0, 87, 15), (0, 27, 0), 
                           (75, 255, 135), (0, 255, 87), (0, 87, 31), (0, 31, 19), 
                           (75, 255, 183), (0, 255, 151), (0, 87, 55), (0, 27, 19), 
                           (75, 195, 255), (0, 167, 255), (0, 67, 83), (0, 15, 27), 
                           (75, 135, 255), (0, 87, 255), (0, 31, 87), (0, 7, 27), 
                           (75, 75, 255), (0, 0, 255), (0, 0, 87), (0, 0, 27), 
                           (135, 75, 255), (83, 0, 255), (27, 0, 99), (15, 0, 47), 
                           (255, 75, 255), (255, 0, 255), (87, 0, 87), (27, 0, 27), 
                           (255, 75, 135), (255, 0, 83), (87, 0, 31), (35, 0, 19), 
                           (255, 23, 0), (151, 55, 0), (119, 83, 0), (67, 99, 0), 
                           (0, 59, 0), (0, 87, 55), (0, 83, 127), (0, 0, 255), 
                           (0, 71, 79), (39, 0, 203), (127, 127, 127), (31, 31, 31), 
                           (255, 0, 0), (187, 255, 47), (175, 235, 7), (99, 255, 11), 
                           (15, 139, 0), (0, 255, 135), (0, 167, 255), (0, 43, 255), 
                           (63, 0, 255), (123, 0, 255), (175, 27, 123), (63, 35, 0), 
                           (255, 75, 0), (135, 223, 7), (115, 255, 23), (0, 255, 0), 
                           (59, 255, 39), (87, 255, 111), (55, 255, 203), (91, 139, 255), 
                           (51, 83, 195), (135, 127, 231), (211, 31, 255), (255, 0, 91), 
                           (255, 127, 0), (183, 175, 0), (143, 255, 0), (131, 91, 7), 
                           (59, 43, 0), (19, 75, 15), (15, 79, 55), (23, 23, 43), 
                           (23, 31, 91), (103, 59, 27), (167, 0, 11), (219, 83, 63), 
                           (215, 107, 27), (255, 223, 39), (159, 223, 47), (103, 179, 15), 
                           (31, 31, 47), (219, 255, 107), (127, 255, 187), (155, 151, 255), 
                           (143, 103, 255), (63, 63, 63), (115, 115, 115), (223, 255, 255), 
                           (159, 0, 0), (55, 0, 0), (27, 207, 0), (7, 67, 0), 
                           (183, 175, 0), (63, 51, 0), (179, 95, 0), (75, 23, 0)])
    
    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 8)
        kwargs['height'] = kwargs.get('height', 2)
        super().__init__(**kwargs)

    def setMode(self, mode: Mode):
        self.sendNoteOn(12, mode.value, 15)

    def setLayout(self, layout: Layout):
        self.sendControlChange(3, layout.value, 15)

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        index = 0
        if y == 0:
            index = 0x70 + x
        elif y == 1:
            index = 0x60 + x
        else:
            return
        self.sendNoteOn(index, pixel.findInPalette(self.palette))

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort=inPort, outPort=outPort)
        self.setMode(MK3.Mode.DAW)
        self.setLayout(MK3.Layout.Session)

    def disconnect(self):
        self.setMode(MK3.Mode.Other)
        self.setLayout(MK3.Layout.Drum)
        super().disconnect()

    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            if midi[1] < 0x80 and midi[1] >= 0x60:
                x = midi[1] % 0x10
                y = 7 - (midi[1] // 0x10)
                self.setButton(x, y, midi[2] / 127.0)