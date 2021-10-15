from .Launchpad import Launchpad
from ....Helpers import *
from ....Util.RingBuffer import RingBuffer
from enum import Enum
import numpy



class LaunchpadMK2(Launchpad):

    class layout(Enum):
        Session     = 0
        User1       = 1
        User2       = 2
        Reserved    = 3
        Volume      = 4
        Pan         = 5

    def __init__(self, inPort: str, outPort: str, **kwargs):
        super().__init__(inPort=inPort, outPort=outPort, width = 10, height = 10, **kwargs)
        self._header = [0x00, 0x20, 0x29, 0x02, 0x18]
        self._sysexBuffer = RingBuffer(1024)
    
    def setLayout(self, layout):
        self.sendSysex(self._header + [0x22, layout.value])
    
    def generateRGB(self, x: int, y: int, color: Pixel):
        index = (x + (y * 10)) & 0x7F
        color = color * 0.25
        return [index, color.r, color.g, color.b]

    def sendRGB(self, x: int, y: int, color: Pixel):
        self.sendSysex(self._header + [0x0B] + self.generateRGB(x, y, color))

    def connect(self):
        super().connect()
        self.setLayout(LaunchpadMK2.layout.Session)
    
    def disconnect(self):
        self.setLayout(LaunchpadMK2.layout.User1)
        super().disconnect()
    
    def processInput(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90 or cmd == 0xB0:
            if midi[1] >= 100:
                midi[1] -= 13
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
