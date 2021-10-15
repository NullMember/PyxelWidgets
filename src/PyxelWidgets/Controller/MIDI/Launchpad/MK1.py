from .Launchpad import Launchpad
from ....Helpers import *
from ....Util.RingBuffer import RingBuffer
from enum import Enum
import numpy

class LaunchpadMK1(Launchpad):

    class layout(Enum):
        Reset   = 0
        XY      = 1
        Drum    = 2
    
    colors = [0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C]

    """ 
    Controller Class for Launchpad, Launchpad S, Launchpad Mini, Launchpad Mini MK2
    """
    def __init__(self, inPort: str, outPort: str, **kwargs):
        super().__init__(inPort=inPort, outPort=outPort, width = 10, height = 10, **kwargs)
        self._header = [0x00, 0x20, 0x29, 0x02, 0x18]
        self._sysexBuffer = RingBuffer(1024)

    def setLayout(self, layout):
        self.sendControlChange(0, layout.value)

    def sendColor(self, x: int, y: int, color: Pixel):
        colorIndex = color.mono // 32
        if y < 8:
            index = (x + (0x70 - (y * 0x10))) & 0x7F
            self.sendNoteOn(index, LaunchpadMK1.colors[colorIndex])
        else:
            index = (0x68 + x) & 0x7F
            self.sendControlChange(index, LaunchpadMK1.colors[colorIndex])

    def connect(self):
        super().connect()
        self.setLayout(LaunchpadMK1.layout.Reset)
        self.setLayout(LaunchpadMK1.layout.XY)

    def disconnect(self):
        self.setLayout(LaunchpadMK1.layout.Reset)
        super().disconnect()

    def processInput(self, message, _):
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

    def updateOne(self, x: int, y: int, pixel: Pixel):
        if self.connected:
            intersect = self.rect.intersect(Rectangle2D(x, y, 1, 1))
            if intersect:
                if pixel == self.buffer[x, y]:
                    pass
                else:
                    self.buffer[x, y] = pixel
                    self.sendColor(x, y, pixel)

    def updateRow(self, y: int, pixel: Pixel):
        if self.connected:
            intersect = self.rect.intersect(Rectangle2D(0, y, self.rect.w, 1))
            if intersect:
                for x in intersect.columns:
                    if pixel == self.buffer[x, y]:
                        pass
                    else:
                        self.buffer[x, y] = pixel
                        self.sendColor(x, y, pixel)

    def updateColumn(self, x: int, pixel: Pixel):
        if self.connected:
            intersect = self.rect.intersect(Rectangle2D(x, 0, 1, self.rect.h))
            if intersect:
                for y in intersect.rows:
                    if pixel == self.buffer[x, y]:
                        pass
                    else:
                        self.buffer[x, y] = pixel
                        self.sendColor(x, y, pixel)

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
                            self.sendColor(x, y, pixel)

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
                            self.sendColor(x, y, self.buffer[x, y])
