"""
Arturia controllers. Both MiniLabs have 8 pads in two banks (the Pad button
switches them), shown as an 8x2 grid: the bottom row is the first bank, the
top row the second, so a frame lights both banks and the pads show the bank
selected on the device.

Written from the messages Ableton Live's own MiniLab scripts send. The
MiniLab 3 was tried on the author's (2026-10-22); the mkII hasn't been.
"""

import enum

import pyxelwidgets.devices
import pyxelwidgets.devices.midi
import pyxelwidgets.events

__all__ = ['MiniLabMK2', 'MiniLab3']

# Arturia's SysEx header (after F0)
_HEADER = [0x00, 0x20, 0x6B, 0x7F, 0x42]
_PAD_CHANNEL = 9
_FIRST_PAD = 36
# MiniLab 3 control numbers that aren't absolute
_RELATIVE = (28, 29)
_BUTTONS = (27, 118, 119, 105, 106, 107, 108, 109)

class _MiniLab(pyxelwidgets.devices.midi.MIDI):
    """Pads send notes 36-51 on channel 10: bank 1 is the bottom row, bank 2 the top."""

    vendor = 'Arturia'
    grid = (8, 2)

    def decode(self, midi: list) -> None:
        status, channel = midi[0] & 0xF0, midi[0] & 0x0F
        if channel == _PAD_CHANNEL:
            if status == 0xD0:
                self.set_channel_pressure(midi[1] / 127.0)
                return
            pad = midi[1] - _FIRST_PAD
            if not 0 <= pad < 16:
                return
            if status == 0x90 or status == 0x80:
                self.set_button(pad % 8, pad // 8, midi[2] / 127.0 if status == 0x90 else 0.0)
            elif status == 0xA0:
                self.set_pressure(pad % 8, pad // 8, midi[2] / 127.0)
        elif status == 0xB0:
            self.decode_control(channel, midi[1], midi[2])

    def decode_control(self, channel: int, number: int, value: int) -> None:
        """Turn a control change into control events."""

    def _button(self, name: str, value: int) -> None:
        # The Shift + pad buttons are pads: they send how hard they're hit
        if value > 0:
            self.emit(pyxelwidgets.events.ControlPressed(self, name, value / 127))
        else:
            self.emit(pyxelwidgets.events.ControlReleased(self, name, 0.0))

class MiniLabMK2(_MiniLab):
    """
    MiniLab mkII: 16 pads (two banks of 8) in 8 colors and 16 endless encoders.
    Connecting sets up the working memory: pads play notes 36-51 on channel 10,
    encoders send relative CCs on channel 2. Select a memory on the device to
    get its own settings back.
    """

    class Controls(enum.Enum):
        Encoder_0 = 22
        Encoder_1 = 23
        Encoder_2 = 24
        Encoder_3 = 25
        Encoder_4 = 26
        Encoder_5 = 27
        Encoder_6 = 28
        Encoder_7 = 29
        Encoder_8 = 30
        Encoder_9 = 31
        Encoder_10 = 33
        Encoder_11 = 34
        Encoder_12 = 52
        Encoder_13 = 53
        Encoder_14 = 54
        Encoder_15 = 55
    #: The device's own ids of encoders 1-16 (top row left to right, then the bottom row)
    encoder_ids = (48, 1, 2, 9, 11, 12, 13, 14, 51, 3, 4, 10, 5, 6, 7, 8)
    #: The device's own ids of pads 1-16, which are also their LEDs
    pad_ids = tuple(range(0x70, 0x80))
    encoder_channel = 1
    #: LED values of the palette colors: one bit each for red, green and blue
    led_values = (0x00, 0x01, 0x04, 0x05, 0x10, 0x11, 0x14, 0x7F)
    model = 'MiniLab mkII'
    ports = ('MiniLab mkII',)
    color_model = pyxelwidgets.devices.Palette([(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0),
                                                (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)])
    controls = tuple(pyxelwidgets.devices.Control(c.name, 'relative') for c in Controls)

    def set_property(self, setting: int, control: int, value: int) -> None:
        """Write one setting (mode 1, channel 2, number 3, option 6, color 16) of a control to the working memory."""
        self.send_sysex(_HEADER + [0x02, 0x00, setting, control, value])

    def on_connect(self) -> None:
        for encoder, control in zip(self.encoder_ids, MiniLabMK2.Controls):
            self.set_property(1, encoder, 1)                     # control change
            self.set_property(3, encoder, control.value)
            self.set_property(2, encoder, self.encoder_channel)
            self.set_property(6, encoder, 2)                     # relative, two's complement
        for index, pad in enumerate(self.pad_ids):
            self.set_property(1, pad, 9)                         # note
            self.set_property(3, pad, _FIRST_PAD + index)
            self.set_property(2, pad, _PAD_CHANNEL)
            self.set_property(6, pad, 1)                         # momentary

    def on_disconnect(self) -> None:
        for pad in self.pad_ids:
            self.set_property(16, pad, 0)

    def send_pixel(self, x: int, y: int, value) -> None:
        self.set_property(16, self.pad_ids[x + y * 8], self.led_values[value])

    def decode_control(self, channel: int, number: int, value: int) -> None:
        control = MiniLabMK2.Controls._value2member_map_.get(number)
        if channel != self.encoder_channel or control is None or value in (0, 64):
            return
        self.emit(pyxelwidgets.events.ControlTurned(self, control.name, value if value < 64 else value - 128))

class MiniLab3(_MiniLab):
    """
    MiniLab 3 in its DAW program: 16 RGB pads (two banks of 8), 8 knobs, 4
    faders and the clickable display encoder. Pick the DAW program on the
    device (``daw`` tells whether it's on; ``warning`` says so while it isn't):
    the pads' lights, the screen and the Shift buttons only work there, and
    loading it shows everything again. Shift with pads 4-8 are the Loop, Stop,
    Play, Record and Tap buttons, lit while Shift is held. ``Screen`` shows two
    lines (``set_screen``, or ``show_text``) until the device draws over them
    (e.g. when its own controls move). The knobs are endless: ``set_ring``
    sets the value they go on from, so a bound knob turns from its widget's value.
    """

    class Controls(enum.Enum):
        Knob_0 = 86
        Knob_1 = 87
        Knob_2 = 89
        Knob_3 = 90
        Knob_4 = 110
        Knob_5 = 111
        Knob_6 = 116
        Knob_7 = 117
        Fader_0 = 14
        Fader_1 = 15
        Fader_2 = 30
        Fader_3 = 31
        Display = 28
        Shift_Display = 29
        Shift = 27
        Display_Press = 118
        Shift_Display_Press = 119
        Loop = 105
        Stop = 106
        Play = 107
        Record = 108
        Tap = 109
    #: LED ids of pads 1-8 in bank A, then bank B
    pad_leds = tuple(range(0x34, 0x3C)) + tuple(range(0x44, 0x4C))
    #: LED ids of the Shift + pad buttons
    button_leds = {'Loop': 87, 'Stop': 88, 'Play': 89, 'Record': 90, 'Tap': 91}
    #: The knobs' ids for setting the value they go on from
    knob_ids = {f'Knob_{i}': 7 + i for i in range(8)}
    model = 'MiniLab 3'
    ports = ('Minilab3 MIDI', 'Minilab3', 'MiniLab 3')
    color_model = pyxelwidgets.devices.RGB(bits = 7)
    controls = tuple(pyxelwidgets.devices.Control(c.name, 'relative' if c.value in _RELATIVE else 'button' if c.value in _BUTTONS else 'absolute')
                     for c in Controls)
    screens = {'Screen': (10, 18)}
    lit_controls = tuple(button_leds)
    ring_controls = tuple(knob_ids)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        #: Whether the DAW program is on (None: not known yet)
        self.daw = None
        self.warning = None
        # The screen's lines, shown again after Shift (the device draws its own page while it's held)
        self._screen = None

    def set_daw_mode(self, enabled: bool) -> None:
        """Tell the DAW program a host is there (or gone); the program itself is picked on the device."""
        self.send_sysex(_HEADER + [0x02, 0x00, 0x40, 0x6A, 0x21 if enabled else 0x20])

    def request_program(self) -> None:
        """Ask which program is on: the answer sets ``daw``."""
        self.send_sysex(_HEADER + [0x01, 0x00, 0x40, 0x01])

    def show_text(self, top: str, bottom: str = '') -> None:
        """Show two lines (10 and 18 characters) on the screen until the device draws over them."""
        def line(text, width):
            return [ord(c) if 32 <= ord(c) < 127 else ord('?') for c in text[:width].strip()]
        self.send_sysex(_HEADER + [0x04, 0x02, 0x60, 0x1F, 0x07, 0x01, 0, 0, 0, 0]
                        + [0x01] + line(top, 10) + [0, 0x02] + line(bottom, 18) + [0])

    def send_screen(self, name: str, lines: tuple) -> None:
        self._screen = lines
        self.show_text(*lines)

    def send_control(self, name: str, value) -> None:
        self.send_sysex(_HEADER + [0x02, 0x02, 0x16, self.button_leds[name], *value])

    def send_ring(self, name: str, value: float) -> None:
        self.send_sysex(_HEADER + [0x21, 0x10, 0x00, self.knob_ids[name], 0x00, round(value * 127)])

    def on_connect(self) -> None:
        self.set_daw_mode(True)
        self.request_program()

    def on_disconnect(self) -> None:
        for led in self.pad_leds:
            self.send_sysex(_HEADER + [0x02, 0x02, 0x16, led, 0, 0, 0])
        self.set_daw_mode(False)

    def send_pixel(self, x: int, y: int, value) -> None:
        self.send_sysex(_HEADER + [0x02, 0x02, 0x16, self.pad_leds[x + y * 8], *value])

    def decode(self, midi: list) -> None:
        # The program: asked for (01, the DAW program is 1) or just loaded (62, it's 2)
        if midi[:9] == [0xF0, *_HEADER, 0x02, 0x00, 0x40] and len(midi) == 12 and midi[9] in (0x01, 0x62):
            self._program(midi[10] == (1 if midi[9] == 0x01 else 2))
            return
        super().decode(midi)

    def _program(self, daw: bool) -> None:
        loaded = daw and self.daw is False
        self.daw = daw
        self.warning = None if daw else 'pick the DAW program on the MiniLab 3: its pads, Shift buttons and screen only follow PyxelWidgets there'
        if loaded and self.connected:
            # Tell it again, and show everything again
            self.set_daw_mode(True)
            self.invalidate()

    def decode_control(self, channel: int, number: int, value: int) -> None:
        control = MiniLab3.Controls._value2member_map_.get(number)
        if channel != 0 or control is None:
            return
        if number in _BUTTONS:
            self._button(control.name, value)
            if control is MiniLab3.Controls.Shift and value == 0 and self._screen is not None:
                self.show_text(*self._screen)
        elif number in _RELATIVE:
            # One click is 65 one way and 62 the other (seen on the author's; 63 counts as one too)
            if value > 64:
                self.emit(pyxelwidgets.events.ControlTurned(self, control.name, value - 64))
            elif value < 64:
                self.emit(pyxelwidgets.events.ControlTurned(self, control.name, min(-1, value - 63)))
        else:
            self.emit(pyxelwidgets.events.ControlChanged(self, control.name, value / 127))
