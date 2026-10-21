"""Ableton Push."""

import enum

import numpy

import pyxelwidgets.devices
import pyxelwidgets.devices.midi
import pyxelwidgets.events

__all__ = ['Push2']

class Push2(pyxelwidgets.devices.midi.MIDI):
    """
    Push 2: 8x8 RGB pads, encoders (relative, touch sensitive) and buttons, in
    dual MIDI mode. Buttons light up for their bound widget: the rows above and
    below the display, the time division buttons, Play, Record and Automate in
    color, the others in white.
    """

    class Mode(enum.Enum):
        Live = 0
        User = 1
        Dual = 2
    class Commands(enum.Enum):
        SetLEDColorPaletteEntry = 0x03
        GetLEDColorPaletteEntry = 0x04
        ReapplyColorPalette = 0x05
        SetLEDBrightness = 0x06
        GetLEDBrightness = 0x07
        SetDisplayBrightness = 0x08
        GetDisplayBrightness = 0x09
        SetMIDIMode = 0x0A
        SetLEDPWMFrequencyCorrection = 0x0B
        SamplePedalData = 0x13
        SetLEDWhiteBalance = 0x14
        GetLEDWhiteBalance = 0x15
        SetTouchStripConfiguration = 0x17
        GetTouchStripConfiguration = 0x18
        SetTouchStripLEDs = 0x19
        RequestStatistics = 0x1A
        SetPadParameters = 0x1B
        Read400gPadValuesFromFlash = 0x1D
        SetAftertouchMode = 0x1E
        GetAftertouchMode = 0x1F
        SetPadVelocityCurveEntry = 0x20
        GetPadVelocityCurveEntry = 0x21
        SetTemporary400gPadValues = 0x22
        FlashLEDWhiteBalance = 0x23
        SelectPadSettings = 0x28
        GetSelectedPadSettings = 0x29
        ConfigurePedal = 0x30
        SetPedalCurveLimits = 0x31
        SetPedalCurveEntries = 0x32
    class Controls(enum.Enum):
        Play = 85
        Record = 86
        Automate = 89
        FixedLength = 90
        New = 87
        Duplicate = 88
        Quantize = 116
        DoubleLoop = 117
        Convert = 35
        Undo = 119
        Delete = 118
        TapTempo = 3
        Metronome = 9
        Setup = 30
        User = 59
        AddDevice = 52
        AddTrack = 53
        Device = 110
        Browse = 111
        Mix = 112
        Clip = 113
        Master = 28
        Up = 46
        Down = 47
        Left = 44
        Right = 45
        Repeat = 56
        Accent = 57
        Scale = 58
        Layout = 31
        Note = 50
        Session = 51
        OctaveUp = 55
        OctaveDown = 54
        PageLeft = 62
        PageRight = 63
        Shift = 49
        Select = 48
        Encoder1 = 14
        Encoder2 = 15
        Encoder3 = 71
        Encoder4 = 72
        Encoder5 = 73
        Encoder6 = 74
        Encoder7 = 75
        Encoder8 = 76
        Encoder9 = 77
        Encoder10 = 78
        Encoder11 = 79
        Button01 = 20
        Button02 = 21
        Button03 = 22
        Button04 = 23
        Button05 = 24
        Button06 = 25
        Button07 = 26
        Button08 = 27
        Button11 = 102
        Button12 = 103
        Button13 = 104
        Button14 = 105
        Button15 = 106
        Button16 = 107
        Button17 = 108
        Button18 = 109
        Bar4 = 36
        Bar4t = 37
        Bar8 = 38
        Bar8t = 39
        Bar16 = 40
        Bar16t = 41
        Bar32 = 42
        Bar32t = 43
    class Notes(enum.Enum):
        Encoder1Touch = 10
        Encoder2Touch = 9
        Encoder3Touch = 0
        Encoder4Touch = 1
        Encoder5Touch = 2
        Encoder6Touch = 3
        Encoder7Touch = 4
        Encoder8Touch = 5
        Encoder9Touch = 6
        Encoder10Touch = 7
        Encoder11Touch = 8
        PitchBendTouch = 12
    palette = numpy.array([
            (0, 0, 0), (255, 36, 36), (242, 58, 12), (255, 153, 0), 
            (166, 137, 86), (237, 249, 90), (193, 157, 8), (255, 255, 0), 
            (86, 191, 19), (44, 132, 3), (36, 107, 36), (25, 255, 48), 
            (21, 149, 115), (23, 107, 80), (0, 255, 255), (0, 116, 252), 
            (39, 79, 204), (0, 68, 140), (100, 74, 217), (77, 63, 160), 
            (135, 0, 255), (230, 87, 227), (102, 0, 153), (255, 0, 153), 
            (161, 76, 95), (255, 77, 196), (235, 139, 225), (166, 52, 33), 
            (153, 86, 40), (135, 103, 0), (144, 130, 31), (74, 135, 0), 
            (0, 127, 18), (24, 83, 178), (98, 75, 173), (115, 58, 103), 
            (248, 188, 175), (255, 155, 118), (255, 191, 95), (217, 175, 113), 
            (255, 244, 128), (191, 186, 105), (188, 204, 136), (174, 255, 153), 
            (124, 221, 159), (137, 180, 125), (128, 243, 255), (122, 206, 252), 
            (104, 161, 211), (133, 143, 194), (187, 170, 242), (205, 187, 228), 
            (239, 139, 176), (133, 157, 140), (107, 117, 110), (132, 144, 155), 
            (106, 112, 117), (136, 133, 157), (108, 106, 117), (157, 133, 156), 
            (116, 106, 116), (156, 157, 133), (116, 117, 106), (157, 132, 132), 
            (117, 106, 106), (77, 11, 11), (26, 4, 4), (77, 18, 4), 
            (26, 6, 1), (77, 46, 0), (26, 15, 0), (64, 52, 33), 
            (26, 21, 13), (77, 73, 31), (26, 24, 10), (64, 51, 2), 
            (26, 21, 1), (77, 77, 0), (26, 26, 0), (28, 64, 7), 
            (11, 26, 3), (17, 51, 1), (4, 13, 0), (17, 51, 17), 
            (4, 13, 4), (10, 77, 10), (3, 26, 5), (7, 51, 39), 
            (2, 13, 10), (16, 77, 57), (3, 13, 10), (0, 77, 77), 
            (0, 26, 26), (0, 35, 77), (0, 12, 26), (12, 25, 64), 
            (2, 5, 13), (0, 37, 77), (0, 12, 26), (35, 26, 77), 
            (12, 9, 26), (37, 30, 77), (12, 10, 26), (54, 0, 102), 
            (13, 0, 26), (77, 29, 76), (26, 10, 25), (51, 0, 77), 
            (17, 0, 26), (77, 0, 46), (26, 0, 15), (77, 36, 45), 
            (26, 12, 15), (77, 23, 59), (26, 8, 20), (77, 45, 73), 
            (26, 15, 24), (0, 0, 0), (89, 89, 89), (26, 26, 26), 
            (255, 255, 255), (89, 89, 89), (255, 255, 255), (89, 89, 89), 
            (26, 26, 26), (0, 0, 255), (0, 255, 0), (255, 0, 0)
        ])
    vendor = 'Ableton'
    model = 'Push 2'
    ports = ('Ableton Push 2 Live Port', 'Ableton Push 2', 'Push2')
    grid = (8, 8)
    color_model = pyxelwidgets.devices.Palette(palette)
    controls = tuple(pyxelwidgets.devices.Control(c.name, 'relative' if 'Encoder' in c.name else 'button') for c in Controls) \
             + tuple(pyxelwidgets.devices.Control(n.name, 'touch') for n in Notes)
    lit_controls = tuple(c.name for c in Controls if 'Encoder' not in c.name)
    #: Buttons with RGB lights (the others are white)
    rgb_buttons = frozenset(c.name for c in Controls if c.name.startswith(('Button', 'Bar')) or c.name in ('Play', 'Record', 'Automate'))
    #: White lights: palette indices whose white is 0, 32, 84 and 128 (the default palette, from Ableton's Push 2 interface document)
    white = pyxelwidgets.devices.Brightness([0, 16, 48, 127])

    header = [0x00, 0x21, 0x1D, 0x01, 0x01]
    
    def send_command(self, command: Commands, *args) -> None:
        self.send_sysex(self.header + [command.value] + list(args))
    
    def set_midi_mode(self, mode: Mode) -> None:
        self.send_command(Push2.Commands.SetMIDIMode, mode.value)
    
    def on_connect(self) -> None:
        self.set_midi_mode(Push2.Mode.Dual)
    
    def on_disconnect(self) -> None:
        self.set_midi_mode(Push2.Mode.Live)
    
    def send_pixel(self, x: int, y: int, value) -> None:
        self.send_note_on(x + (y * 8) + 36, value)

    def light_model(self, name: str) -> pyxelwidgets.devices.ColorModel:
        return self.color_model if name in self.rgb_buttons else self.white

    def send_control(self, name: str, value) -> None:
        self.send_control_change(Push2.Controls[name].value, value)
    
    def decode(self, midi: list) -> None:
        if len(midi) == 2 and midi[0] & 0xF0 == 0xD0:
            # Channel pressure: two bytes
            return self.set_channel_pressure(midi[1] / 127.0)
        if len(midi) < 3:
            return
        cmd, number, value = midi[0] & 0xF0, midi[1], midi[2]
        if cmd == 0x80 or cmd == 0x90:
            velocity = value / 127.0 if cmd == 0x90 else 0.0
            if number >= 36:
                if number - 36 < 64:
                    self.set_button((number - 36) % 8, (number - 36) // 8, velocity)
            else:
                touch = Push2.Notes._value2member_map_.get(number)
                if touch is not None:
                    if velocity > 0:
                        self.emit(pyxelwidgets.events.ControlPressed(self, touch.name, velocity))
                    else:
                        self.emit(pyxelwidgets.events.ControlReleased(self, touch.name, 0.0))
        elif cmd == 0xA0 and 36 <= number < 100:
            self.set_pressure((number - 36) % 8, (number - 36) // 8, value / 127.0)
        elif cmd == 0xB0:
            control = Push2.Controls._value2member_map_.get(number)
            if control is None:
                return
            if 'Encoder' in control.name:
                delta = -((value ^ 0x7F) + 1) if value & 0x30 else value
                self.emit(pyxelwidgets.events.ControlTurned(self, control.name, delta))
            elif value > 0:
                self.emit(pyxelwidgets.events.ControlPressed(self, control.name, value / 127.0))
            else:
                self.emit(pyxelwidgets.events.ControlReleased(self, control.name, 0.0))
