import pyxelwidgets.controllers.midi
import pyxelwidgets.enums
import pyxelwidgets.pixel
import pyxelwidgets.rectangle
import collections
import enum
import numpy

class MK1(pyxelwidgets.controllers.midi.MIDI):

    class Layout(enum.Enum):
        Reset   = 0
        XY      = 1
        Drum    = 2
    
    colors = [0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C]

    """ 
    Controller Class for Launchpad, Launchpad S, Launchpad Mini, Launchpad Mini MK2
    """
    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 9)
        kwargs['height'] = kwargs.get('height', 9)
        super().__init__(**kwargs)

    def set_layout(self, layout: Layout):
        self.send_control_change(0, layout.value)

    def send_pixel(self, x: int, y: int, pixel: pyxelwidgets.pixel.Pixel):
        color_index = pixel.gmono // 32
        if y < 8:
            index = (x + (0x70 - (y * 0x10))) & 0x7F
            self.send_note_on(index, MK1.colors[color_index])
        else:
            index = (0x68 + x) & 0x7F
            self.send_control_change(index, MK1.colors[color_index])

    def connect(self, in_port: str = None, out_port: str = None):
        super().connect(in_port=in_port, out_port=out_port)
        self.set_layout(MK1.Layout.Reset)
        self.set_layout(MK1.Layout.XY)

    def disconnect(self):
        self.set_layout(MK1.Layout.Reset)
        super().disconnect()

    def process_midi(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            x = midi[1] % 0x10
            y = 7 - (midi[1] // 0x10)
            self.set_button(x, y, midi[2] / 127.0)
        elif cmd == 0xB0:
            x = midi[1] - 0x68
            y = 8
            self.set_button(x, y, midi[2] / 127.0)

class MK2(pyxelwidgets.controllers.midi.MIDI):
    """
    Controller class for Launchpad MK2
    """
    class Layout(enum.Enum):
        Session     = 0
        User1       = 1
        User2       = 2
        Reserved    = 3
        Volume      = 4
        Pan         = 5

    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 9)
        kwargs['height'] = kwargs.get('height', 9)
        super().__init__(**kwargs)
        self._header = [0x00, 0x20, 0x29, 0x02, 0x18]
        self._sysex_buffer = collections.deque(maxlen = 1024)
    
    def set_layout(self, layout: Layout):
        self.send_sysex(self._header + [0x22, layout.value])

    def send_pixel(self, x: int, y: int, pixel: pyxelwidgets.pixel.Pixel):
        index = (x + (y * 10)) & 0x7F
        rgb = pixel.grgb
        self._sysex_buffer.extend([3, index, rgb[0] >> 2, rgb[1] >> 2, rgb[2] >> 2])

    def connect(self, in_port: str = None, out_port: str = None):
        super().connect(in_port=in_port, out_port=out_port)
        self.set_layout(MK2.Layout.Session)
    
    def disconnect(self):
        self.set_layout(MK2.Layout.User1)
        super().disconnect()
    
    def process_midi(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            if midi[1] >= 100:
                midi[1] -= 13
            x = midi[1] % 10
            y = midi[1] // 10
            self.set_button(x, y, midi[2] / 127.0)

    def update_one(self, x: int, y: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_one(x, y, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()
    
    def update_row(self, y: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_row(y, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()
    
    def update_column(self, x: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_column(x, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()

    def update_area(self, rect: pyxelwidgets.rectangle.Rectangle2D, pixel: pyxelwidgets.pixel.Pixel):
        super().update_area(rect, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()

    def update(self, data: tuple):
        super().update(data)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()

class MK3(pyxelwidgets.controllers.midi.MIDI):
    """
    Controller class for Launchpad Mini MK3, Launchpad X, Launchpad Pro MK3
    """
    class Model(enum.Enum):
        X                           = 12
        Mini                        = 13
        Pro                         = 14

    class ProLayout(enum.Enum):
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

    class XLayout(enum.Enum):
        Session                     = 0
        Note                        = 1
        Custom1                     = 4
        Custom2                     = 5
        Custom3                     = 6
        Custom4                     = 7
        Fader                       = 13
        Programmer                  = 127

    class MiniLayout(enum.Enum):
        Session                     = 0
        Custom1                     = 4
        Custom2                     = 5
        Custom3                     = 6
        Fader                       = 13
        Programmer                  = 127

    class Mode(enum.Enum):
        DAW                         = 0
        Programmer                  = 1

    def __init__(self, model, **kwargs):
        kwargs['width'] = kwargs.get('width', 10)
        kwargs['height'] = kwargs.get('height', 10)
        super().__init__(**kwargs)
        self._model = model
        self._header = [0x00, 0x20, 0x29, 0x02, self._model.value]
        self._sysex_buffer = collections.deque(maxlen = 1024)
    
    def set_layout(self, layout, page = 0):
        if self._model == MK3.Model.X or self._model == MK3.Model.Mini:
            self.send_sysex(self._header + [0, layout.value])
        else:
            self.send_sysex(self._header + [0, layout.value, page])
    
    def set_mode(self, mode: Mode):
        if self._model == MK3.Model.X or self._model == MK3.Model.Mini:
            self.send_sysex(self._header + [14, mode.value])
        else:
            if mode == MK3.Mode.DAW:
                self.set_layout(MK3.ProLayout.Session)
            elif mode == MK3.Mode.Programmer:
                self.set_layout(MK3.ProLayout.Programmer)

    def send_pixel(self, x: int, y: int, pixel: pyxelwidgets.pixel.Pixel):
        index = (x + (y * 10)) & 0x7F
        rgb = pixel.grgb
        self._sysex_buffer.extend([3, index, rgb[0] >> 1, rgb[1] >> 1, rgb[2] >> 1])

    def connect(self, in_port: str = None, out_port: str = None):
        super().connect(in_port=in_port, out_port=out_port)
        self.set_mode(MK3.Mode.Programmer)
    
    def disconnect(self):
        self.set_mode(MK3.Mode.DAW)
        super().disconnect()

    def process_midi(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            x = midi[1] % 10
            y = midi[1] // 10
            self.set_button(x, y, midi[2] / 127.0)

    def update_one(self, x: int, y: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_one(x, y, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()
    
    def update_row(self, y: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_row(y, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()
    
    def update_column(self, x: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_column(x, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()

    def update_area(self, rect: pyxelwidgets.rectangle.Rectangle2D, pixel: pyxelwidgets.pixel.Pixel):
        super().update_area(rect, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()

    def update(self, data: tuple):
        super().update(data)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()

class Pro(pyxelwidgets.controllers.midi.MIDI):
    """
    Controller class for Launchpad Pro (first version)
    """
    class Layout(enum.Enum):
        Note        = 0
        Drum        = 1
        Fader       = 2
        Programmer  = 3

    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 10)
        kwargs['height'] = kwargs.get('height', 10)
        super().__init__(**kwargs)
        self._header = [0x00, 0x20, 0x29, 0x02, 0x10]
        self._sysex_buffer = collections.deque(maxlen = 1024)
    
    def set_layout(self, layout: Layout):
        self.send_sysex(self._header + [0x2C, layout.value])
    
    def send_pixel(self, x: int, y: int, pixel: pyxelwidgets.pixel.Pixel):
        index = (x + (y * 10)) & 0x7F
        rgb = pixel.grgb
        self._sysex_buffer.extend([3, index, rgb[0] >> 2, rgb[1] >> 2, rgb[2] >> 2])

    def connect(self, in_port: str = None, out_port: str = None):
        super().connect(in_port=in_port, out_port=out_port)
        self.set_layout(Pro.Layout.Programmer)
    
    def disconnect(self):
        self.set_layout(Pro.Layout.Note)
        super().disconnect()

    def process_midi(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            x = midi[1] % 10
            y = midi[1] // 10
            self.set_button(x, y, midi[2] / 127.0)

    def update_one(self, x: int, y: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_one(x, y, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()
    
    def update_row(self, y: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_row(y, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()
    
    def update_column(self, x: int, pixel: pyxelwidgets.pixel.Pixel):
        super().update_column(x, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()

    def update_area(self, rect: pyxelwidgets.rectangle.Rectangle2D, pixel: pyxelwidgets.pixel.Pixel):
        super().update_area(rect, pixel)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()

    def update(self, data: tuple):
        super().update(data)
        if len(self._sysex_buffer):
            self.send_sysex(self._header + [3] + list(self._sysex_buffer))
            self._sysex_buffer.clear()
