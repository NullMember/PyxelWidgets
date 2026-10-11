"""Presonus controllers."""

import enum

import pyxelwidgets.devices
import pyxelwidgets.devices.midi
import pyxelwidgets.events

__all__ = ['ATOM']

class ATOM(pyxelwidgets.devices.midi.MIDI):
    """ATOM: 4x4 RGB pads, encoders and buttons, in native control mode."""

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
    vendor = 'Presonus'
    model = 'ATOM'
    ports = ('ATOM',)
    grid = (4, 4)
    color_model = pyxelwidgets.devices.RGB(bits = 7)
    controls = tuple(pyxelwidgets.devices.Control(c.name, 'button' if c.value > 17 else 'relative') for c in Controls)

    def set_native_control(self, state: NativeControl) -> None:
        self.send_note_off(0, state.value, 15)

    def on_connect(self) -> None:
        self.set_native_control(ATOM.NativeControl.Enable)
        for i in range(36, 52):
            self.send_note_on(i, 127)
    
    def on_disconnect(self) -> None:
        for i in range(36, 52):
            self.send_note_on(i, 0)
        self.set_native_control(ATOM.NativeControl.Disable)
    
    def send_pixel(self, x: int, y: int, value) -> None:
        index = 36 + x + (y * 4)
        red, green, blue = value
        self.send_note_on(index, red, 1)
        self.send_note_on(index, green, 2)
        self.send_note_on(index, blue, 3)
    
    def decode(self, midi: list) -> None:
        cmd, number, value = midi[0] & 0xF0, midi[1], midi[2]
        if (cmd == 0x80 or cmd == 0x90) and 36 <= number < 52:
            self.set_button((number - 36) % 4, (number - 36) // 4, value / 127.0)
        elif cmd == 0xB0:
            control = ATOM.Controls._value2member_map_.get(number)
            if control is None:
                return
            if number > 17:
                if value > 0:
                    self.emit(pyxelwidgets.events.ControlPressed(self, control.name, 1.0))
                else:
                    self.emit(pyxelwidgets.events.ControlReleased(self, control.name, 0.0))
            elif value == 1:
                self.emit(pyxelwidgets.events.ControlTurned(self, control.name, 1))
            elif value == 65:
                self.emit(pyxelwidgets.events.ControlTurned(self, control.name, -1))
