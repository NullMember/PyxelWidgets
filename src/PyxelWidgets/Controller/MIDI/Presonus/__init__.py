__all__ = []

import PyxelWidgets.Controller.MIDI
import PyxelWidgets.Helpers
import enum

class ATOM(PyxelWidgets.Controller.MIDI.MIDI):

    class buttons(enum.Enum):
        Encoder1 = 14
        Encoder2 = 15
        Encoder3 = 16
        Encoder4 = 17
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

    class nativeControl(enum.Enum):
        Enable = 127
        Disable = 0

    def __init__(self, inPort: str, outPort: str, **kwargs):
        kwargs['width'] = kwargs.get('width', 4)
        kwargs['height'] = kwargs.get('height', 4)
        super().__init__(inPort, outPort, **kwargs)

    def setNativeControl(self, state):
        self.sendNoteOff(0, state.value, 15)

    def connect(self):
        super().connect()
        self.setNativeControl(ATOM.nativeControl.Enable)
        for i in range(36, 52):
            self.sendNoteOn(i, 127)
    
    def disconnect(self):
        for i in range(36, 52):
            self.sendNoteOn(i, 0)
        self.setNativeControl(ATOM.nativeControl.Disable)
        super().disconnect()
    
    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        index = 36 + x + (y * 4)
        pixel = pixel * 0.5
        self.sendNoteOn(index, pixel.r, 1)
        self.sendNoteOn(index, pixel.g, 2)
        self.sendNoteOn(index, pixel.b, 3)
    
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
                    self.setCustom('pressed', ATOM.buttons(control).name, 0, 0, 1.0)
                else:
                    self.setCustom('released', ATOM.buttons(control).name, 0, 0, 0.0)
            else:
                if value == 1:
                    self.setCustom('incremented', ATOM.buttons(control).name, 0, 0, 1.0)
                elif value == 65:
                    self.setCustom('decremented', ATOM.buttons(control).name, 0, 0, 0.0)