from PyxelWidgets.Controller.MIDI.Novation.Launchpad.Launchpad import Launchpad
from PyxelWidgets.Helpers import *
from PyxelWidgets.Util.RingBuffer import RingBuffer
from enum import Enum
import numpy

class LaunchpadMK3(Launchpad):

    class model(Enum):
        X                           = 12
        Mini                        = 13
        Pro                         = 14

    class proLayout(Enum):
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

    class xLayout(Enum):
        Session                     = 0
        Note                        = 1
        Custom1                     = 4
        Custom2                     = 5
        Custom3                     = 6
        Custom4                     = 7
        Fader                       = 13
        Programmer                  = 127

    class miniLayout(Enum):
        Session                     = 0
        Custom1                     = 4
        Custom2                     = 5
        Custom3                     = 6
        Fader                       = 13
        Programmer                  = 127

    class mode(Enum):
        DAW                         = 0
        Programmer                  = 1

    def __init__(self, inPort: str, outPort: str, model, **kwargs):
        super().__init__(inPort=inPort, outPort=outPort, width = 10, height = 10, **kwargs)
        self._model = model
        self._header = [0x00, 0x20, 0x29, 0x02, self._model.value]
        self._sysexBuffer = RingBuffer(1024)
    
    def setLayout(self, layout, page = 0):
        if self._model == LaunchpadMK3.model.X or self._model == LaunchpadMK3.model.Mini:
            self.sendSysex(self._header + [0, layout.value])
        else:
            self.sendSysex(self._header + [0, layout.value, page])
    
    def setMode(self, mode: mode):
        if self._model == LaunchpadMK3.model.X or self._model == LaunchpadMK3.model.Mini:
            self.sendSysex(self._header + [14, mode.value])
        else:
            if mode == LaunchpadMK3.mode.DAW:
                self.setLayout(LaunchpadMK3.proLayout.Session)
            elif mode == LaunchpadMK3.mode.Programmer:
                self.setLayout(LaunchpadMK3.proLayout.Programmer)
    
    def generateRGB(self, x: int, y: int, color: Pixel):
        index = (x + (y * 10)) & 0x7F
        color = color * 0.5
        return [3, index, color.r, color.g, color.b]

    def sendRGB(self, x: int, y: int, color: Pixel):
        self.sendSysex(self._header + [3] + self.generateRGB(x, y, color))

    def connect(self):
        super().connect()
        self.setMode(LaunchpadMK3.mode.Programmer)
    
    def disconnect(self):
        self.setMode(LaunchpadMK3.mode.DAW)
        super().disconnect()

    def processInput(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            x = midi[1] % 10
            y = midi[1] // 10
            self.setButton(x, y, midi[2] / 127.0)

    def updateOne(self, x: int, y: int, pixel: Pixel):
        if self.connected:
            intersect = self.rect.intersect(Rectangle2D(x, y, 1, 1))
            if intersect:
                if pixel == self.buffer[x, y]:
                    pass
                else:
                    self.buffer[x, y] = pixel
                    self.sendRGB(x, y, pixel)
    
    def updateRow(self, y: int, pixel: Pixel):
        if self.connected:
            intersect = self.rect.intersect(Rectangle2D(0, y, self.rect.w, 1))
            if intersect:
                for x in intersect.columns:
                    if pixel == self.buffer[x, y]:
                        pass
                    else:
                        self.buffer[x, y] = pixel
                        self._sysexBuffer.write(self.generateRGB(x, y, self.buffer[x, y]))
                if self._sysexBuffer.readable:
                    self.sendSysex(self._header + [3] + self._sysexBuffer.read())
    
    def updateColumn(self, x: int, pixel: Pixel):
        if self.connected:
            intersect = self.rect.intersect(Rectangle2D(x, 0, 1, self.rect.h))
            if intersect:
                for y in intersect.rows:
                    if pixel == self.buffer[x, y]:
                        pass
                    else:
                        self.buffer[x, y] = pixel
                        self._sysexBuffer.write(self.generateRGB(x, y, self.buffer[x, y]))
                if self._sysexBuffer.readable:
                    self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def updateArea(self, x: int, y: int, width: int, height: int, pixel: Pixel):
        if self.connected:
            intersect = self.rect.intersect(Rectangle2D(x, y, width, height))
            if intersect:
                for _x in intersect.columns:
                    for _y in intersect.rows:
                        if pixel == self.buffer[_x, _y]:
                            pass
                        else:
                            self.buffer[_x, _y] = pixel
                            self._sysexBuffer.write(self.generateRGB(_x, _y, self.buffer[_x, _y]))
                if self._sysexBuffer.readable:
                    self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def update(self, buffer: numpy.ndarray):
        if self.connected:
            intersect = self.rect.intersect(Rectangle2D(0, 0, buffer.shape[0], buffer.shape[1]))
            if intersect:
                for x in intersect.columns:
                    for y in intersect.rows:
                        if buffer[x, y] == self.buffer[x, y]:
                            pass
                        else:
                            self.buffer[x, y] = buffer[x, y]
                            self._sysexBuffer.write(self.generateRGB(x, y, self.buffer[x, y]))
                if self._sysexBuffer.readable:
                    self.sendSysex(self._header + [3] + self._sysexBuffer.read())
