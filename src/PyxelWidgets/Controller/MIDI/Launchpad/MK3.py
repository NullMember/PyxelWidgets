from .Launchpad import Launchpad
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
        self._buffer = RingBuffer(1024)
    
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
    
    def sendRGB(self, x: int, y: int, color: list):
        self.sendSysex(self._header + [3] + self.generateRGB(x, y, color))
    
    def generateRGB(self, x: int, y: int, color: list):
        index = x + (y * 10)
        return [3, index, int(color[0] / 2.), int(color[1] / 2.), int(color[2] / 2.)]

    def displayText(self, text: str, loop: bool = False, speed: int = 10, color: list = [255, 255, 255]):
        if speed < 0:
            speed += 0x80
        self.sendSysex(self._header + [7, int(loop), speed, 1] + color + list(bytes(text, 'ascii')))

    def init(self):
        self._connected = True
        self.setMode(Mode.Programmer)
        self._midiInput.set_callback(self.process)
    
    def deinit(self):
        self._connected = False
        self.setMode(Mode.DAW)
        self._midiInput.set_callback(lambda *_, **__: None)

    def process(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            x = midi[1] % 10
            y = midi[1] // 10
            self._callback(x, y, midi[2] / 127.0)

    def updateOne(self, x, y, pixel):
        if self._connected:
            try:
                if pixel == self._pixels[x][y]:
                    pass
                else:
                    self._pixels[x][y] = pixel
                    self.sendRGB(x, y, pixel)
            except:
                pass
    
    def updateRow(self, y, pixels):
        if self._connected:
            for x in range(self.width):
                try:
                    if pixels[x] == self._pixels[x][y]:
                        pass
                    else:
                        self._pixels[x][y] = pixels[x]
                        self._buffer.write(self.generateRGB(x, y, self._pixels[x][y]))
                except:
                    pass
            if self._buffer.readable:
                self.sendSysex(self._header + [3] + self._buffer.read())
    
    def updateColumn(self, x, pixels):
        if self._connected:
            for y in range(self.height):
                try:
                    if pixels[y] == self._pixels[x][y]:
                        pass
                    else:
                        self._pixels[x][y] = pixels[y]
                        self._buffer.write(self.generateRGB(x, y, self._pixels[x][y]))
                except:
                    pass
            if self._buffer.readable:
                self.sendSysex(self._header + [3] + self._buffer.read())

    def updateArea(self, x, y, width, height, pixels):
        if self._connected:
            for _x in range(width):
                for _y in range(height):
                    try:
                        if pixels[_x][_y] == self._pixels[x + _x][y + _y]:
                            pass
                        else:
                            self._pixels[x + _x][y + _y] = pixels[_x][_y]
                            self._buffer.write(self.generateRGB(x + _x, y + _y, self._pixels[x + _x][y + _y]))
                    except:
                        pass
            if self._buffer.readable:
                self.sendSysex(self._header + [3] + self._buffer.read())

    def updateAreaByArea(self, sx, sy, dx, dy, width, height, pixels):
        if self._connected:
            for x in range(width):
                for y in range(height):
                    try:
                        if pixels[x + sx][y + sy] == self._pixels[x + dx][y + dy]:
                            pass
                        else:
                            self._pixels[x + dx][y + dy] = pixels[x + sx][y + sy]
                            self._buffer.write(self.generateRGB(x + dx, y + dy, self._pixels[x + dx][y + dy]))
                    except:
                        pass
            if self._buffer.readable:
                self.sendSysex(self._header + [3] + self._buffer.read())

    def update(self, pixels):
        if self._connected:
            for x in range(self.width):
                for y in range(self.height):
                    try:
                        if pixels[x][y] == self._pixels[x][y]:
                            pass
                        else:
                            self._pixels[x][y] = pixels[x][y]
                            self._buffer.write(self.generateRGB(x, y, self._pixels[x][y]))
                    except:
                        pass
            if self._buffer.readable:
                self.sendSysex(self._header + [3] + self._buffer.read())
