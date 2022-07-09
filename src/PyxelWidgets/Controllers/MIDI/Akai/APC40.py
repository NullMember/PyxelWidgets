import PyxelWidgets.Controllers.MIDI
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import numpy
import enum

class MK2(PyxelWidgets.Controllers.MIDI.MIDI):
    """
    Akai APC40 MK2 Controller class
    """

    class Modes(enum.Enum):
        Generic = 0x40
        Ableton = 0x41
        Alternative = 0x42
    
    class Controls(enum.Enum):
        Fader_0 = (0, 7)
        Fader_1 = (1, 7)
        Fader_2 = (2, 7)
        Fader_3 = (3, 7)
        Fader_4 = (4, 7)
        Fader_5 = (5, 7)
        Fader_6 = (6, 7)
        Fader_7 = (7, 7)
        Fader_8 = (0, 14)
        CrossFader = (0, 15)
        DeviceKnob_0 = (0, 16)
        DeviceKnob_1 = (0, 17)
        DeviceKnob_2 = (0, 18)
        DeviceKnob_3 = (0, 19)
        DeviceKnob_4 = (0, 20)
        DeviceKnob_5 = (0, 21)
        DeviceKnob_6 = (0, 22)
        DeviceKnob_7 = (0, 23)
        SceneKnob_0 = (0, 48)
        SceneKnob_1 = (0, 49)
        SceneKnob_2 = (0, 50)
        SceneKnob_3 = (0, 51)
        SceneKnob_4 = (0, 52)
        SceneKnob_5 = (0, 53)
        SceneKnob_6 = (0, 54)
        SceneKnob_7 = (0, 55)
        Cue = (0, 47) #relative
        Tempo = (0, 13) #relative

    class Buttons(enum.Enum):
        Select_0 = (0, 50)
        Select_1 = (1, 50)
        Select_2 = (2, 50)
        Select_3 = (3, 50)
        Select_4 = (4, 50)
        Select_5 = (5, 50)
        Select_6 = (6, 50)
        Select_7 = (7, 50)
        Solo_0 = (0, 49)
        Solo_1 = (1, 49)
        Solo_2 = (2, 49)
        Solo_3 = (3, 49)
        Solo_4 = (4, 49)
        Solo_5 = (5, 49)
        Solo_6 = (6, 49)
        Solo_7 = (7, 49)
        Record_0 = (0, 48)
        Record_1 = (1, 48)
        Record_2 = (2, 48)
        Record_3 = (3, 48)
        Record_4 = (4, 48)
        Record_5 = (5, 48)
        Record_6 = (6, 48)
        Record_7 = (7, 48)
        Beat_0 = (0, 51)
        Beat_1 = (1, 51)
        Beat_2 = (2, 51)
        Beat_3 = (3, 51)
        Beat_4 = (4, 51)
        Beat_5 = (5, 51)
        Beat_6 = (6, 51)
        Beat_7 = (7, 51)
        Beat_8 = (0, 80)
        Stop_0 = (0, 52)
        Stop_1 = (1, 52)
        Stop_2 = (2, 52)
        Stop_3 = (3, 52)
        Stop_4 = (4, 52)
        Stop_5 = (5, 52)
        Stop_6 = (6, 52)
        Stop_7 = (7, 52)
        Stop_8 = (0, 81)
        Scene_0 = (0, 82)
        Scene_1 = (0, 83)
        Scene_2 = (0, 84)
        Scene_3 = (0, 85)
        Scene_4 = (0, 86)
        Pan = (0, 87)
        Sends = (0, 88)
        User = (0, 89)
        Metronome = (0, 90)
        Tap = (0, 99)
        Nudge_N = (0, 100)
        Nudge_P = (0, 101)
        Play = (0, 91)
        Record = (0, 93)
        Session = (0, 102)
        Control_0 = (0, 58)
        Control_1 = (0, 59)
        Control_2 = (0, 60)
        Control_3 = (0, 61)
        Control_4 = (0, 62)
        Control_5 = (0, 63)
        Control_6 = (0, 64)
        Control_7 = (0, 65)
        Shift = (0, 98)
        Bank = (0, 103)
        Up = (0, 94)
        Down = (0, 95)
        Right = (0, 96)
        Left = (0, 97)

    palette = numpy.array([
        (0, 0, 0), (30, 30, 30), (127, 127, 127), (255, 255, 255), 
        (255, 76, 76), (255, 0, 0), (89, 0, 0), (25, 0, 0), 
        (255, 189, 108), (255, 84, 0), (89, 29, 0), (39, 27, 0), 
        (255, 255, 76), (255, 255, 0), (89, 89, 0), (25, 25, 0), 
        (136, 255, 76), (84, 255, 0), (29, 89, 0), (20, 43, 0), 
        (76, 255, 76), (0, 255, 0), (0, 89, 0), (0, 25, 0), 
        (76, 255, 94), (0, 255, 25), (0, 89, 13), (0, 25, 2), 
        (76, 255, 136), (0, 255, 85), (0, 89, 29), (0, 31, 18), 
        (76, 255, 183), (0, 255, 153), (0, 89, 53), (0, 25, 18), 
        (76, 195, 255), (0, 169, 255), (0, 65, 82), (0, 16, 25), 
        (76, 136, 255), (0, 85, 255), (0, 29, 89), (0, 8, 25), 
        (76, 76, 255), (0, 0, 255), (0, 0, 89), (0, 0, 25), 
        (135, 76, 255), (84, 0, 255), (25, 0, 100), (15, 0, 48), 
        (255, 76, 255), (255, 0, 255), (89, 0, 89), (25, 0, 25), 
        (255, 76, 135), (255, 0, 84), (89, 0, 29), (34, 0, 19), 
        (255, 21, 0), (153, 53, 0), (121, 81, 0), (67, 100, 0), 
        (3, 57, 0), (0, 87, 53), (0, 84, 127), (0, 0, 255), 
        (0, 69, 79), (37, 0, 204), (127, 127, 127), (32, 32, 32), 
        (255, 0, 0), (189, 255, 45), (175, 237, 6), (100, 255, 9), 
        (16, 139, 0), (0, 255, 135), (0, 169, 255), (0, 42, 255), 
        (63, 0, 255), (122, 0, 255), (178, 26, 125), (64, 33, 0), 
        (255, 74, 0), (136, 225, 6), (114, 255, 21), (0, 255, 0), 
        (59, 255, 38), (89, 255, 113), (56, 255, 204), (91, 138, 255), 
        (49, 81, 198), (135, 127, 233), (211, 29, 255), (255, 0, 93), 
        (255, 127, 0), (185, 176, 0), (144, 255, 0), (131, 93, 7), 
        (57, 43, 0), (20, 76, 16), (13, 80, 56), (21, 21, 42), 
        (22, 32, 90), (105, 60, 28), (168, 0, 10), (222, 81, 61), 
        (216, 106, 28), (255, 225, 38), (158, 225, 47), (103, 181, 15), 
        (30, 30, 48), (220, 255, 107), (128, 255, 189), (154, 153, 255), 
        (142, 102, 255), (64, 64, 64), (117, 117, 117), (224, 255, 255), 
        (160, 0, 0), (53, 0, 0), (26, 208, 0), (7, 66, 0), 
        (185, 176, 0), (63, 49, 0), (179, 95, 0), (75, 21, 2)
    ])

    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 8)
        kwargs['height'] = kwargs.get('height', 5)
        super().__init__(**kwargs)
        self.deviceID = 0x7F
    
    def changeMode(self, mode):
        self.sendSysex([0x47, self.deviceID, 0x29, 0x60, 0x00, 0x04, mode.value, 0x00, 0x00, 0x00])

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort, outPort)
        self.changeMode(MK2.Modes.Ableton)
    
    def disconnect(self):
        self.changeMode(MK2.Modes.Generic)
        super().disconnect()

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        index = x + (y * 8)
        self.sendNoteOn(index, pixel.findInPalette(MK2.palette))
    
    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80:
            if midi[1] < 40:
                x = midi[1] % 8
                y = midi[1] // 8
                self.setButton(x, y, 0.0)
            else:
                control = MK2.Buttons(chn, midi[1])
                self.setCustom(PyxelWidgets.Utils.Enums.Event.Released, control.name, 0.0)
        elif cmd == 0x90:
            if midi[1] < 40:
                if midi[2] == 0:
                    x = midi[1] % 8
                    y = midi[1] // 8
                    self.setButton(x, y, 0.0)
                else:
                    x = midi[1] % 8
                    y = midi[1] // 8
                    self.setButton(x, y, 1.0)
            else:
                control = MK2.Buttons(chn, midi[1])
                self.setCustom(PyxelWidgets.Utils.Enums.Event.Pressed, control.name, 1.0)
        elif cmd == 0xB0:
            control = MK2.Controls(chn, midi[1])
            if control != MK2.Controls.Cue and control != MK2.Controls.Tempo:
                self.setCustom(PyxelWidgets.Utils.Enums.Event.Changed, control.name, midi[2] / 127)
            else:
                if midi[2] >= 64:
                    self.setCustom(PyxelWidgets.Utils.Enums.Event.Increased, control.name, midi[2] - 64)
                else:
                    self.setCustom(PyxelWidgets.Utils.Enums.Event.Decreased, control.name, 64 - midi[2])