__all__ = ['ATOM']

import pyxelwidgets.controllers.midi
import pyxelwidgets.enums
import pyxelwidgets.color
import pyxelwidgets.rectangle
import enum

class ATOM(pyxelwidgets.controllers.midi.MIDI):

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

    def set_native_control(self, state):
        self.send_note_off(0, state.value, 15)

    def connect(self, in_port: str = None, out_port: str = None):
        super().connect(in_port=in_port, out_port=out_port)
        self.set_native_control(ATOM.NativeControl.Enable)
        for i in range(36, 52):
            self.send_note_on(i, 127)
    
    def disconnect(self):
        for i in range(36, 52):
            self.send_note_on(i, 0)
        self.set_native_control(ATOM.NativeControl.Disable)
        super().disconnect()
    
    def send_pixel(self, x: int, y: int, pixel: pyxelwidgets.color.Color):
        index = 36 + x + (y * 4)
        rgb = pixel.grgb
        self.send_note_on(index, rgb[0] >> 1, 1)
        self.send_note_on(index, rgb[1] >> 1, 2)
        self.send_note_on(index, rgb[2] >> 1, 3)
    
    def process_midi(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            if midi[1] >= 36 and midi[1] < 52:
                x = (midi[1] - 36) % 4
                y = (midi[1] - 36) // 4
                self.set_button(x, y, midi[2] / 127.0)
        if cmd == 0xB0:
            control = midi[1]
            value = midi[2]
            if control > 17:
                if value > 0.0:
                    self.set_custom(pyxelwidgets.enums.Event.Pressed, ATOM.Controls(control).name, 1.0)
                else:
                    self.set_custom(pyxelwidgets.enums.Event.Released, ATOM.Controls(control).name, 0.0)
            else:
                if value == 1:
                    self.set_custom(pyxelwidgets.enums.Event.Increased, ATOM.Controls(control).name, 1.0)
                elif value == 65:
                    self.set_custom(pyxelwidgets.enums.Event.Decreased, ATOM.Controls(control).name, -1.0)