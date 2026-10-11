import enum

import pyxelwidgets.devices
import pyxelwidgets.devices.midi
import pyxelwidgets.events

class LaunchControl(pyxelwidgets.devices.midi.MIDI):
    """
    Launch Control (first generation). The grid is LED x template: ``x`` is the
    LED, ``y`` the template (0-15) it is set in.
    """

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
    vendor = 'Novation'
    model = 'Launch Control'
    ports = ('Launch Control',)
    grid = (8, 16)
    color_model = pyxelwidgets.devices.Levels([0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C])
    controls = tuple(pyxelwidgets.devices.Control(c.name, 'absolute' if c.name.startswith('Knob') else 'button') for c in Controls)

    def __init__(self, **kwargs):
        self.current_template = LaunchControl.Templates.User_0
        super().__init__(**kwargs)
    
    def reset(self, template: Templates) -> None:
        self.send_control_change(0, 0, template.value)
    
    def select_template(self, template: Templates) -> None:
        self.send_sysex([0x00, 0x20, 0x29, 0x02, 0x0A, 0x77, template.value])
        self.current_template = template

    def send_pixel(self, x: int, y: int, value) -> None:
        self.send_sysex([0x00, 0x20, 0x29, 0x02, 0x0A, 0x78, y, x, value])

    def on_connect(self) -> None:
        self.reset(LaunchControl.Templates.User_0)

    def on_disconnect(self) -> None:
        self.reset(LaunchControl.Templates.User_0)

    def decode(self, midi: list) -> None:
        cmd = midi[0] & 0xF0
        if cmd == 0x80 or cmd == 0x90:
            self.set_button(midi[1] % 0x10, 7 - (midi[1] // 0x10), midi[2] / 127.0)
        elif cmd == 0xB0:
            self.set_button(midi[1] - 0x68, 8, midi[2] / 127.0)
        elif cmd == 0xF0 and midi[1:7] == [0x00, 0x20, 0x29, 0x02, 0x0A, 0x77]:
            self.current_template = LaunchControl.Templates(midi[7])

class LaunchControlXL(pyxelwidgets.devices.midi.MIDI):
    """
    Launch Control XL: 8x2 buttons as a 8x5 grid (rows 2-4 are the knob LEDs,
    output only), knobs, faders and buttons. Input works in factory template 8
    (``Templates.Factory_7``), which connecting selects.
    """

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
    colors = [0x0C, 0x0D, 0x0E, 0x0F, 0x1E, 0x1F, 0x2F, 0x1D, 
              0x2E, 0x3E, 0x3F, 0x2D, 0x3D, 0x1C, 0x2C, 0x3C]
    leds = [[0x49, 0x29, 0x0F, 0x0E, 0x0D],
            [0x4A, 0x2A, 0x1F, 0x1E, 0x1D],
            [0x4B, 0x2B, 0x2F, 0x2E, 0x2D],
            [0x4C, 0x2C, 0x3F, 0x3E, 0x3D],
            [0x59, 0x39, 0x4F, 0x4E, 0x4D],
            [0x5A, 0x3A, 0x5F, 0x5E, 0x5D],
            [0x5B, 0x3B, 0x6F, 0x6E, 0x6D],
            [0x5C, 0x3C, 0x7F, 0x7E, 0x7D]]
    leds_sysex = [[0x20, 0x18, 0x10, 0x08, 0x00],
                 [0x21, 0x19, 0x11, 0x09, 0x01],
                 [0x22, 0x1A, 0x12, 0x0A, 0x02],
                 [0x23, 0x1B, 0x13, 0x0B, 0x03],
                 [0x24, 0x1C, 0x14, 0x0C, 0x04],
                 [0x25, 0x1D, 0x15, 0x0D, 0x05],
                 [0x26, 0x1E, 0x16, 0x0E, 0x06],
                 [0x27, 0x1F, 0x17, 0x0F, 0x07]]
    vendor = 'Novation'
    model = 'Launch Control XL'
    ports = ('Launch Control XL',)
    grid = (8, 5)
    color_model = pyxelwidgets.devices.Levels(colors, gamma = False)
    controls = tuple(pyxelwidgets.devices.Control(c.name, 'absolute' if c.value < 0x64 else 'button') for c in Controls) \
             + tuple(pyxelwidgets.devices.Control(b.name, 'button') for b in Buttons)

    def __init__(self, **kwargs):
        self.current_template = LaunchControlXL.Templates.User_0
        super().__init__(**kwargs)
    
    def reset(self, template: Templates) -> None:
        self.send_control_change(0, 0, template.value)
        self.current_template = template

    def select_template(self, template: Templates) -> None:
        self.send_sysex([0x00, 0x20, 0x29, 0x02, 0x11, 0x77, template.value])
        self.current_template = template

    def send_pixel(self, x: int, y: int, value) -> None:
        if self.current_template == LaunchControlXL.Templates.Factory_7:
            self.send_note_on(LaunchControlXL.leds[x][y], value, 0xF)
        else:
            self.send_sysex([0x00, 0x20, 0x29, 0x02, 0x11, 0x78, 0xF, LaunchControlXL.leds_sysex[x][y], value])

    def on_connect(self) -> None:
        self.select_template(LaunchControlXL.Templates.Factory_7)
        self.reset(self.current_template)

    def on_disconnect(self) -> None:
        self.reset(LaunchControlXL.Templates.Factory_7)
        self.select_template(LaunchControlXL.Templates.Factory_0)

    def _button(self, name: str, value: int) -> None:
        if value > 0:
            self.emit(pyxelwidgets.events.ControlPressed(self, name, value / 127.0))
        else:
            self.emit(pyxelwidgets.events.ControlReleased(self, name, 0.0))

    def decode(self, midi: list) -> None:
        cmd = midi[0] & 0xF0
        if cmd == 0xF0:
            if midi[1:7] == [0x00, 0x20, 0x29, 0x02, 0x11, 0x77]:
                self.current_template = LaunchControlXL.Templates(midi[7])
            return
        if self.current_template != LaunchControlXL.Templates.Factory_7:
            return
        if cmd == 0x80 or cmd == 0x90:
            note, velocity = midi[1], midi[2] / 127.0
            if note < 0x30:
                self.set_button(note - 0x29, 1, velocity)
            elif note < 0x40:
                self.set_button(note - 0x35, 1, velocity)
            elif note < 0x50:
                self.set_button(note - 0x49, 0, velocity)
            elif note < 0x60:
                self.set_button(note - 0x55, 0, velocity)
            else:
                button = LaunchControlXL.Buttons._value2member_map_.get(note)
                if button is not None:
                    self._button(button.name, midi[2])
        elif cmd == 0xB0:
            control = LaunchControlXL.Controls._value2member_map_.get(midi[1])
            if control is None:
                return
            if midi[1] < 0x64:
                self.emit(pyxelwidgets.events.ControlChanged(self, control.name, midi[2] / 127.0))
            else:
                self._button(control.name, midi[2])
