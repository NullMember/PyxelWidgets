from .Launchpad import Launchpad
from ....Helpers import *
from ....Util.RingBuffer import RingBuffer
from enum import Enum

class Model(Enum):
    X = 12
    Mini = 13
    Pro = 14

class ProLayout(Enum):
    Session = 0
    Fader = 1
    Chord = 2
    CustomLayout = 3
    NoteDrum = 4
    ScaleSettings = 5
    SequencerSettings = 6
    SequencerSteps = 7
    SequencerVelocity = 8
    SequencerPatternSettings = 9
    SequencerProbability = 10
    SequencerMutation = 11
    SequencerMicroStep = 12
    SequencerProjects = 13
    SequencerPatterns = 14
    SequencerTempo = 15
    SequencerSwing = 16
    Programmer = 17
    Settings = 18
    CustomLayoutSettings = 19

class XLayout(Enum):
    Session = 0
    Note = 1
    Custom1 = 4
    Custom2 = 5
    Custom3 = 6
    Custom4 = 7
    Fader = 13
    Programmer = 127

class MiniLayout(Enum):
    Session = 0
    Custom1 = 4
    Custom2 = 5
    Custom3 = 6
    Fader = 13
    Programmer = 127

class Mode(Enum):
    DAW = 0
    Programmer = 1

class MK3(Launchpad):
    def __init__(self, inPort: str, outPort: str, model: Model, **kwargs):
        super().__init__(inPort=inPort, outPort=outPort, width = 10, height = 10, **kwargs)
        self._model = model
        self._header = [0x00, 0x20, 0x29, 0x02, self._model.value]
        self._sysexBuffer = RingBuffer(1024)
    
    def setLayout(self, layout, page = 0):
        if self._model == Model.X or self._model == Model.Mini:
            self.sendSysex(self._header + [0, layout.value])
        else:
            self.sendSysex(self._header + [0, layout.value, page])
    
    def setMode(self, mode: Mode):
        if self._model == Model.X or self._model == Model.Mini:
            self.sendSysex(self._header + [14, mode.value])
        else:
            if mode == Mode.DAW:
                self.setLayout(ProLayout.Session)
            elif mode == Mode.Programmer:
                self.setLayout(ProLayout.Programmer)
    
    def generateRGB(self, x: int, y: int, color: Pixel):
        index = x + (y * 10)
        color = (color * 0.5) <= 127
        return [3, index, color.r, color.g, color.b]

    def sendRGB(self, x: int, y: int, color: Pixel):
        self.sendSysex(self._header + [3] + self.generateRGB(x, y, color))

    def displayText(self, text: str, loop: bool = False, speed: int = 10, color: Pixel = Colors.White):
        if speed < 0:
            speed += 0x80
        self.sendSysex(self._header + [7, int(loop), speed, 1] + color.rgb + list(bytes(text, 'ascii')))

    def connect(self):
        super().connect()
        self.setMode(Mode.Programmer)
    
    def disconnect(self):
        super().disconnect()
        self.setMode(Mode.DAW)

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
            try:
                if pixel == self.buffer[x, y]:
                    pass
                else:
                    self.buffer[x, y] = pixel
                    self.sendRGB(x, y, pixel)
            except:
                pass
    
    def updateRow(self, y: int, pixel: Pixel):
        if self.connected:
            for x in self.rect.columns:
                try:
                    if pixel == self.buffer[x, y]:
                        pass
                    else:
                        self.buffer[x, y] = pixel
                        self._sysexBuffer.write(self.generateRGB(x, y, self.buffer[x, y]))
                except:
                    break
            if self._sysexBuffer.readable:
                self.sendSysex(self._header + [3] + self._sysexBuffer.read())
    
    def updateColumn(self, x: int, pixel: Pixel):
        if self.connected:
            for y in self.rect.rows:
                try:
                    if pixel == self.buffer[x, y]:
                        pass
                    else:
                        self.buffer[x, y] = pixel
                        self._sysexBuffer.write(self.generateRGB(x, y, self.buffer[x, y]))
                except:
                    break
            if self._sysexBuffer.readable:
                self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def updateArea(self, x: int, y: int, width: int, height: int, pixel: Pixel):
        if self.connected:
            for _x in range(width):
                for _y in range(height):
                    try:
                        if pixel == self.buffer[x + _x, y + _y]:
                            pass
                        else:
                            self.buffer[x + _x, y + _y] = pixel
                            self._sysexBuffer.write(self.generateRGB(x + _x, y + _y, self.buffer[x + _x, y + _y]))
                    except:
                        break
            if self._sysexBuffer.readable:
                self.sendSysex(self._header + [3] + self._sysexBuffer.read())

    def update(self, buffer):
        if self.connected:
            for x in self.rect.columns:
                for y in self.rect.rows:
                    try:
                        if buffer[x, y] == self.buffer[x, y]:
                            pass
                        else:
                            self.buffer[x, y] = buffer[x, y]
                            self._sysexBuffer.write(self.generateRGB(x, y, self.buffer[x, y]))
                    except:
                        break
            if self._sysexBuffer.readable:
                self.sendSysex(self._header + [3] + self._sysexBuffer.read())
