import PyxelWidgets.Controller.MIDI
import PyxelWidgets.Helpers
import PyxelWidgets.Util.RingBuffer
import enum
import numpy

class Launchpad(PyxelWidgets.Controller.MIDI.MIDI):
    """
    Base class for Novation's Launchpad devices
    """
    def __init__(self, inPort: str = None, outPort: str = None, **kwargs):
        super().__init__(inPort, outPort, **kwargs)

class MK1(Launchpad):

    class Layout(enum.Enum):
        Reset   = 0
        XY      = 1
        Drum    = 2
    
    colors = [0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C]

    """ 
    Controller Class for Launchpad, Launchpad S, Launchpad Mini, Launchpad Mini MK2
    """
    def __init__(self, inPort: str, outPort: str, **kwargs):
        kwargs['width'] = kwargs.get('width', 9)
        kwargs['height'] = kwargs.get('height', 9)
        super().__init__(inPort=inPort, outPort=outPort, **kwargs)

    def setLayout(self, layout: Layout):
        self.sendControlChange(0, layout.value)

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        colorIndex = pixel.mono // 32
        if y < 8:
            index = (x + (0x70 - (y * 0x10))) & 0x7F
            self.sendNoteOn(index, MK1.colors[colorIndex])
        else:
            index = (0x68 + x) & 0x7F
            self.sendControlChange(index, MK1.colors[colorIndex])

    def connect(self):
        super().connect()
        self.setLayout(MK1.Layout.Reset)
        self.setLayout(MK1.Layout.XY)

    def disconnect(self):
        self.setLayout(MK1.Layout.Reset)
        super().disconnect()

    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            x = midi[1] % 0x10
            y = 7 - (midi[1] // 0x10)
            self.setButton(x, y, midi[2] / 127.0)
        elif cmd == 0xB0:
            x = midi[1] - 0x68
            y = 8
            self.setButton(x, y, midi[2] / 127.0)

class MK2(Launchpad):
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

    def __init__(self, inPort: str, outPort: str, **kwargs):
        kwargs['width'] = kwargs.get('width', 9)
        kwargs['height'] = kwargs.get('height', 9)
        super().__init__(inPort=inPort, outPort=outPort, **kwargs)
        self._header = [0x00, 0x20, 0x29, 0x02, 0x18]
        self._sysexBuffer = PyxelWidgets.Util.RingBuffer.RingBuffer(1024)
    
    def setLayout(self, layout: Layout):
        self.sendSysex(self._header + [0x22, layout.value])

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        index = (x + (y * 10)) & 0x7F
        pixel = pixel * 0.25
        self._sysexBuffer.write([3, index, pixel.r, pixel.g, pixel.b])

    def connect(self):
        super().connect()
        self.setLayout(MK2.Layout.Session)
    
    def disconnect(self):
        self.setLayout(MK2.Layout.User1)
        super().disconnect()
    
    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            if midi[1] >= 100:
                midi[1] -= 13
            x = midi[1] % 10
            y = midi[1] // 10
            self.setButton(x, y, midi[2] / 127.0)

    def updateOne(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateOne(x, y, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())
    
    def updateRow(self, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateRow(y, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())
    
    def updateColumn(self, x: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateColumn(x, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def updateArea(self, x: int, y: int, width: int, height: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateArea(x, y, width, height, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def update(self, buffer: numpy.ndarray):
        super().update(buffer)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())

class MK3(Launchpad):
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

    def __init__(self, inPort: str, outPort: str, model, **kwargs):
        kwargs['width'] = kwargs.get('width', 10)
        kwargs['height'] = kwargs.get('height', 10)
        super().__init__(inPort=inPort, outPort=outPort, **kwargs)
        self._model = model
        self._header = [0x00, 0x20, 0x29, 0x02, self._model.value]
        self._sysexBuffer = PyxelWidgets.Util.RingBuffer.RingBuffer(1024)
    
    def setLayout(self, layout, page = 0):
        if self._model == MK3.Model.X or self._model == MK3.Model.Mini:
            self.sendSysex(self._header + [0, layout.value])
        else:
            self.sendSysex(self._header + [0, layout.value, page])
    
    def setMode(self, mode: Mode):
        if self._model == MK3.Model.X or self._model == MK3.Model.Mini:
            self.sendSysex(self._header + [14, mode.value])
        else:
            if mode == MK3.Mode.DAW:
                self.setLayout(MK3.ProLayout.Session)
            elif mode == MK3.Mode.Programmer:
                self.setLayout(MK3.ProLayout.Programmer)

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        index = (x + (y * 10)) & 0x7F
        pixel = pixel * 0.5
        self._sysexBuffer.write([3, index, pixel.r, pixel.g, pixel.b])

    def connect(self):
        super().connect()
        self.setMode(MK3.Mode.Programmer)
    
    def disconnect(self):
        self.setMode(MK3.Mode.DAW)
        super().disconnect()

    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            x = midi[1] % 10
            y = midi[1] // 10
            self.setButton(x, y, midi[2] / 127.0)

    def updateOne(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateOne(x, y, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())
    
    def updateRow(self, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateRow(y, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())
    
    def updateColumn(self, x: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateColumn(x, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def updateArea(self, x: int, y: int, width: int, height: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateArea(x, y, width, height, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def update(self, buffer: numpy.ndarray):
        super().update(buffer)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())

class Pro(Launchpad):
    """
    Controller class for Launchpad Pro (first version)
    """
    class Layout(enum.Enum):
        Note        = 0
        Drum        = 1
        Fader       = 2
        Programmer  = 3

    def __init__(self, inPort: str, outPort: str, **kwargs):
        kwargs['width'] = kwargs.get('width', 10)
        kwargs['height'] = kwargs.get('height', 10)
        super().__init__(inPort=inPort, outPort=outPort, **kwargs)
        self._header = [0x00, 0x20, 0x29, 0x02, 0x10]
        self._sysexBuffer = PyxelWidgets.Util.RingBuffer.RingBuffer(1024)
    
    def setLayout(self, layout: Layout):
        self.sendSysex(self._header + [0x2C, layout.value])
    
    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        index = (x + (y * 10)) & 0x7F
        pixel = pixel * 0.25
        self._sysexBuffer.write([3, index, pixel.r, pixel.g, pixel.b])

    def connect(self):
        super().connect()
        self.setLayout(Pro.Layout.Programmer)
    
    def disconnect(self):
        self.setLayout(Pro.Layout.Note)
        super().disconnect()

    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            x = midi[1] % 10
            y = midi[1] // 10
            self.setButton(x, y, midi[2] / 127.0)

    def updateOne(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateOne(x, y, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())
    
    def updateRow(self, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateRow(y, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())
    
    def updateColumn(self, x: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateColumn(x, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def updateArea(self, x: int, y: int, width: int, height: int, pixel: PyxelWidgets.Helpers.Pixel):
        super().updateArea(x, y, width, height, pixel)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def update(self, buffer: numpy.ndarray):
        super().update(buffer)
        if self._sysexBuffer.readable:
            self.sendSysex(self._header + [3] + self._sysexBuffer.read())
