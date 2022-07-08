__all__ = []

import PyxelWidgets.Controllers.MIDI
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import enum

class ATOM(PyxelWidgets.Controllers.MIDI.MIDI):

    class Controls(enum.Enum):
        Encoder_0 = 14
        Encoder_1 = 15
        Encoder_2 = 16
        Encoder_3 = 17
        NoteRepeat = 24
        FullLevel = 25
        Bank = 26
        Preset = 27
        Show = 29
        Nudge = 30
        Editor = 31
        Shift = 32
        SetLoop = 85
        Setup = 86
        Up = 87
        Down = 89
        Left = 90
        Right = 102
        Select = 103
        Zoom = 104
        Click = 105
        Record = 107
        Play = 109
        Stop = 111

    class NativeControl(enum.Enum):
        Enable = 127
        Disable = 0

    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 4)
        kwargs['height'] = kwargs.get('height', 4)
        super().__init__(**kwargs)

    def setNativeControl(self, state):
        self.sendNoteOff(0, state.value, 15)

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect(inPort=inPort, outPort=outPort)
        self.setNativeControl(ATOM.NativeControl.Enable)
        for i in range(36, 52):
            self.sendNoteOn(i, 127)
    
    def disconnect(self):
        for i in range(36, 52):
            self.sendNoteOn(i, 0)
        self.setNativeControl(ATOM.NativeControl.Disable)
        super().disconnect()
    
    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        index = 36 + x + (y * 4)
        rgb = pixel.grgb
        self.sendNoteOn(index, rgb[0] >> 1, 1)
        self.sendNoteOn(index, rgb[1] >> 1, 2)
        self.sendNoteOn(index, rgb[2] >> 1, 3)
    
    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            if midi[1] >= 36 and midi[1] < 52:
                x = (midi[1] - 36) % 4
                y = (midi[1] - 36) // 4
                self.setButton(x, y, midi[2] / 127.0)
        if cmd == 0xB0:
            control = midi[1]
            value = midi[2]
            if control > 17:
                if value > 0.0:
                    self.setCustom(PyxelWidgets.Utils.Enums.Event.Pressed, ATOM.Controls(control).name, 1.0)
                else:
                    self.setCustom(PyxelWidgets.Utils.Enums.Event.Released, ATOM.Controls(control).name, 0.0)
            else:
                if value == 1:
                    self.setCustom(PyxelWidgets.Utils.Enums.Event.Increased, ATOM.Controls(control).name, 1.0)
                elif value == 65:
                    self.setCustom(PyxelWidgets.Utils.Enums.Event.Decreased, ATOM.Controls(control).name, -1.0)