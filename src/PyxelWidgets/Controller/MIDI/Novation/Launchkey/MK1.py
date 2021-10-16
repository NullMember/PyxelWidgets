from PyxelWidgets.Controller.MIDI.Novation.Launchkey.Launchkey import Launchkey
from PyxelWidgets.Helpers import *
from enum import Enum
import numpy

class LaunchkeyMK1(Launchkey):
    """ 
    Controller Class for Launchkey MK1 serie controllers
    """
    class mode(Enum):
        Basic = 0
        Extended = 127
    
    class inControl(Enum):
        pots = 0x0D
        slider = 0x0E
        pads = 0x0F
    
    colors = [0x0C, 0x0D, 0x0F, 0x1D, 0x3F, 0x3E, 0x1C, 0x3C]

    def __init__(self, inPort: str, outPort: str, **kwargs):
        super().__init__(inPort=inPort, outPort=outPort, width = 10, height = 10, **kwargs)

    def setMode(self, mode: mode):
        self.sendNoteOn(0x0C, mode.value, 0xF)

    def enableInControl(self, control: inControl):
        self.sendNoteOn(control.value, 0x7F, 0xF)
    
    def disableInControl(self, control: inControl):
        self.sendNoteOn(control.value, 0x00, 0xF)

    def sendColor(self, x: int, y: int, color: Pixel):
        colorIndex = color.mono // 32
        index = 0
        if y == 0:
            index = 0x70 + x
        elif y == 1:
            index = 0x60 + x
        else:
            return
        self.sendNoteOn(index, LaunchkeyMK1.colors[colorIndex])

    def connect(self):
        super().connect()
        self.setMode(LaunchkeyMK1.mode.Extended)
        self.enableInControl(LaunchkeyMK1.inControl.pads)

    def disconnect(self):
        self.disableInControl(LaunchkeyMK1.inControl.pads)
        self.setMode(LaunchkeyMK1.mode.Basic)
        super().disconnect()

    def processInput(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80 or cmd == 0x90:
            if midi[1] < 0x80 and midi[1] >= 0x60:
                x = midi[1] % 0x10
                y = 7 - (midi[1] // 0x10)
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
