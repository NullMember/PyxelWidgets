import enum

import pyxelwidgets.devices
import pyxelwidgets.devices.midi
import pyxelwidgets.events

class Launchpad(pyxelwidgets.devices.midi.MIDI):
    """
    Common base of the Launchpads. By default the round side buttons are part of
    the grid (e.g. 9x9 with the top row and right column). With
    ``side_buttons = False`` the grid is only the 8x8 pad area and side buttons
    arrive as ControlPressed / ControlReleased named by position: ``Top1``-``Top8``
    (left to right), ``Right1``-``Right8`` (bottom to top), and on 10x10 models
    also ``Bottom1``-``Bottom8`` and ``Left1``-``Left8``.

    Subclasses decode into physical grid positions with ``_pad`` and receive
    physical positions in ``_send``.
    """

    vendor = 'Novation'
    #: Position of the 8x8 pad area in the physical grid
    main = (0, 0)
    #: Messages to send per LED in one SysEx (keeps messages short)
    sysex_batch = 200

    def __init__(self, *, side_buttons: bool = True, width: int | None = None, height: int | None = None, **kwargs):
        self.side_buttons = side_buttons
        if not side_buttons:
            width = 8 if width is None else width
            height = 8 if height is None else height
        super().__init__(width = width, height = height, **kwargs)

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['main'] = {'x': cls.main[0], 'y': cls.main[1], 'width': 8, 'height': 8}
        info['side_buttons'] = [{'name': name, 'x': x, 'y': y} for (x, y), name in sorted(cls._side_names().items())]
        # Lights with side_buttons = False
        info['lights'] = list(cls._side_names().values())
        return info

    @classmethod
    def _side_names(cls) -> dict:
        mx, my = cls.main
        width, height = cls.grid
        names = {}
        for i in range(8):
            if my + 8 < height:
                names[mx + i, my + 8] = f'Top{i + 1}'
            if mx + 8 < width:
                names[mx + 8, my + i] = f'Right{i + 1}'
            if my > 0:
                names[mx + i, my - 1] = f'Bottom{i + 1}'
            if mx > 0:
                names[mx - 1, my + i] = f'Left{i + 1}'
        return names

    def lights(self) -> tuple:
        # Side buttons outside the grid are controls with a light
        return () if self.side_buttons else tuple(self._side_names().values())

    def send_control(self, name: str, value) -> None:
        position = next(place for place, side in self._side_names().items() if side == name)
        self._send([(*position, value)])

    def _pad(self, x: int, y: int, velocity: float) -> None:
        """Input at physical grid position ``x``, ``y``."""
        if self.side_buttons:
            self.set_button(x, y, velocity)
            return
        mx, my = self.main
        if 0 <= x - mx < 8 and 0 <= y - my < 8:
            self.set_button(x - mx, y - my, velocity)
            return
        name = self._side_names().get((x, y))
        if name is not None:
            event = pyxelwidgets.events.ControlPressed if velocity > 0 else pyxelwidgets.events.ControlReleased
            self.emit(event(self, name, velocity))

    def _pressure(self, x: int, y: int, pressure: float) -> None:
        """Polyphonic aftertouch at physical grid position ``x``, ``y`` (side buttons have none)."""
        if not self.side_buttons:
            x, y = x - self.main[0], y - self.main[1]
        self.set_pressure(x, y, pressure)

    def send_pixels(self, pixels: list) -> None:
        if not self.side_buttons:
            mx, my = self.main
            pixels = [(x + mx, y + my, value) for x, y, value in pixels]
        self._send(pixels)

    def _send(self, pixels: list) -> None:
        """Send ``(x, y, value)`` at physical grid positions."""
        raise NotImplementedError

    def _send_rgb_sysex(self, header: list, index, pixels: list) -> None:
        """LED colors as ``header + [3] + [3, led, r, g, b] ...`` SysEx messages."""
        for start in range(0, len(pixels), self.sysex_batch):
            body = []
            for x, y, (r, g, b) in pixels[start:start + self.sysex_batch]:
                body += [3, index(x, y) & 0x7F, r, g, b]
            self.send_sysex(header + [3] + body)

class LaunchpadMK1(Launchpad):
    """Launchpad, Launchpad S, Launchpad Mini (MK1 and MK2): red/green LEDs, 9x9 with side buttons."""

    class Layout(enum.Enum):
        Reset   = 0
        XY      = 1
        Drum    = 2

    model = 'Launchpad / Launchpad S / Launchpad Mini'
    ports = ('Launchpad S', 'Launchpad Mini', 'Launchpad')
    grid = (9, 9)
    color_model = pyxelwidgets.devices.Levels([0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C])

    def set_layout(self, layout: Layout) -> None:
        self.send_control_change(0, layout.value)

    def on_connect(self) -> None:
        self.set_layout(LaunchpadMK1.Layout.Reset)
        self.set_layout(LaunchpadMK1.Layout.XY)

    def on_disconnect(self) -> None:
        self.set_layout(LaunchpadMK1.Layout.Reset)

    def _send(self, pixels: list) -> None:
        for x, y, value in pixels:
            if y < 8:
                self.send_note_on((x + (0x70 - (y * 0x10))) & 0x7F, value)
            else:
                self.send_control_change((0x68 + x) & 0x7F, value)

    def decode(self, midi: list) -> None:
        cmd = midi[0] & 0xF0
        if cmd == 0x80 or cmd == 0x90:
            self._pad(midi[1] % 0x10, 7 - (midi[1] // 0x10), midi[2] / 127.0)
        elif cmd == 0xB0:
            self._pad(midi[1] - 0x68, 8, midi[2] / 127.0)

class _ProgrammerLayout(Launchpad):
    """Launchpads numbering LEDs ``11``-``89`` by row and column (``x + 10 * y``)."""

    #: Physical grid position of LED index 0
    origin = (0, 0)

    def _index(self, x: int, y: int) -> int:
        return (x + self.origin[0]) + ((y + self.origin[1]) * 10)

    def _decode_index(self, index: int, velocity: float) -> None:
        self._pad((index % 10) - self.origin[0], (index // 10) - self.origin[1], velocity)

    def _decode_pressure(self, midi: list) -> None:
        """Polyphonic (``A0 index pressure``) or channel (``D0 pressure``) aftertouch, on models with it."""
        cmd = midi[0] & 0xF0
        if cmd == 0xA0 and len(midi) == 3:
            self._pressure((midi[1] % 10) - self.origin[0], (midi[1] // 10) - self.origin[1], midi[2] / 127.0)
        elif cmd == 0xD0 and len(midi) >= 2:
            self.set_channel_pressure(midi[1] / 127.0)

class LaunchpadMK2(_ProgrammerLayout):
    """Launchpad MK2: RGB, 9x9 with the top row and right column."""

    class Layout(enum.Enum):
        Session     = 0
        User1       = 1
        User2       = 2
        Reserved    = 3
        Volume      = 4
        Pan         = 5

    model = 'Launchpad MK2'
    ports = ('Launchpad MK2',)
    grid = (9, 9)
    origin = (1, 1)
    color_model = pyxelwidgets.devices.RGB(bits = 6)
    header = [0x00, 0x20, 0x29, 0x02, 0x18]

    def set_layout(self, layout: Layout) -> None:
        self.send_sysex(self.header + [0x22, layout.value])

    def on_connect(self) -> None:
        self.set_layout(LaunchpadMK2.Layout.Session)

    def on_disconnect(self) -> None:
        self.set_layout(LaunchpadMK2.Layout.User1)

    def _send(self, pixels: list) -> None:
        self._send_rgb_sysex(self.header, self._index, pixels)

    def decode(self, midi: list) -> None:
        cmd = midi[0] & 0xF0
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            index = midi[1]
            # Top row buttons are CC 104-111; fold them onto row 9 (91-98)
            if index >= 100:
                index -= 13
            self._decode_index(index, midi[2] / 127.0)

class LaunchpadPro(_ProgrammerLayout):
    """Launchpad Pro (first generation): RGB, 10x10 with side buttons on all four sides."""

    class Layout(enum.Enum):
        Note        = 0
        Drum        = 1
        Fader       = 2
        Programmer  = 3

    model = 'Launchpad Pro'
    ports = ('Launchpad Pro',)
    grid = (10, 10)
    main = (1, 1)
    color_model = pyxelwidgets.devices.RGB(bits = 6)
    header = [0x00, 0x20, 0x29, 0x02, 0x10]

    def set_layout(self, layout: Layout) -> None:
        self.send_sysex(self.header + [0x2C, layout.value])

    def on_connect(self) -> None:
        self.set_layout(LaunchpadPro.Layout.Programmer)

    def on_disconnect(self) -> None:
        self.set_layout(LaunchpadPro.Layout.Note)

    def _send(self, pixels: list) -> None:
        self._send_rgb_sysex(self.header, self._index, pixels)

    def decode(self, midi: list) -> None:
        cmd = midi[0] & 0xF0
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            self._decode_index(midi[1], midi[2] / 127.0)
        else:
            self._decode_pressure(midi)

class _MK3(_ProgrammerLayout):
    """Launchpad X, Mini MK3 and Pro MK3 (programmer mode)."""

    class Mode(enum.Enum):
        DAW         = 0
        Programmer  = 1

    color_model = pyxelwidgets.devices.RGB(bits = 7)
    device_id = 0

    @property
    def header(self) -> list:
        return [0x00, 0x20, 0x29, 0x02, self.device_id]

    def set_mode(self, mode: Mode) -> None:
        self.send_sysex(self.header + [14, mode.value])

    def on_connect(self) -> None:
        self.set_mode(_MK3.Mode.Programmer)

    def on_disconnect(self) -> None:
        self.set_mode(_MK3.Mode.DAW)

    def _send(self, pixels: list) -> None:
        self._send_rgb_sysex(self.header, self._index, pixels)

    def decode(self, midi: list) -> None:
        cmd = midi[0] & 0xF0
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            self._decode_index(midi[1], midi[2] / 127.0)
        else:
            # Launchpad X and Pro MK3 (the Mini MK3 sends none)
            self._decode_pressure(midi)

class LaunchpadX(_MK3):
    """Launchpad X: RGB, 9x9 with the top row and right column."""

    class Layout(enum.Enum):
        Session     = 0
        Note        = 1
        Custom1     = 4
        Custom2     = 5
        Custom3     = 6
        Custom4     = 7
        Fader       = 13
        Programmer  = 127

    model = 'Launchpad X'
    ports = ('LPX MIDI', 'Launchpad X MIDI')
    grid = (9, 9)
    origin = (1, 1)
    device_id = 12

    def set_layout(self, layout: Layout) -> None:
        self.send_sysex(self.header + [0, layout.value])

class LaunchpadMiniMK3(_MK3):
    """Launchpad Mini MK3: RGB, 9x9 with the top row and right column."""

    class Layout(enum.Enum):
        Session     = 0
        Custom1     = 4
        Custom2     = 5
        Custom3     = 6
        Fader       = 13
        Programmer  = 127

    model = 'Launchpad Mini MK3'
    # Android has no port names: its second port (the first is DAW) is the MIDI one
    ports = ('LPMiniMK3 MIDI', 'Launchpad Mini MK3 MIDI', 'Launchpad Mini MK3 2')
    grid = (9, 9)
    origin = (1, 1)
    device_id = 13

    def set_layout(self, layout: Layout) -> None:
        self.send_sysex(self.header + [0, layout.value])

class LaunchpadProMK3(_MK3):
    """Launchpad Pro MK3: RGB, 10x10 with side buttons on all four sides."""

    class Layout(enum.Enum):
        Session                     = 0
        Fader                       = 1
        Chord                       = 2
        CustomLayout                = 3
        NoteDrum                    = 4
        ScaleSettings               = 5
        SequencerSettings           = 6
        SequencerSteps              = 7
        SequencerVelocity           = 8
        SequencerPatternSettings    = 9
        SequencerProbability        = 10
        SequencerMutation           = 11
        SequencerMicroStep          = 12
        SequencerProjects           = 13
        SequencerPatterns           = 14
        SequencerTempo              = 15
        SequencerSwing              = 16
        Programmer                  = 17
        Settings                    = 18
        CustomLayoutSettings        = 19

    model = 'Launchpad Pro MK3'
    ports = ('LPProMK3 MIDI', 'Launchpad Pro MK3 MIDI')
    grid = (10, 10)
    main = (1, 1)
    device_id = 14

    def set_layout(self, layout: Layout, page: int = 0) -> None:
        self.send_sysex(self.header + [0, layout.value, page])

    def set_mode(self, mode: _MK3.Mode) -> None:
        # The Pro MK3 has no mode command: programmer mode is a layout
        if mode == _MK3.Mode.Programmer:
            self.set_layout(LaunchpadProMK3.Layout.Programmer)
        else:
            self.set_layout(LaunchpadProMK3.Layout.Session)
