from PyxelWidgets.Controller.MIDI.Novation.Launchkey.Launchkey import Launchkey
from PyxelWidgets.Helpers import *
from enum import Enum
import numpy

class LaunchkeyMK3(Launchkey):

    class mode(Enum):
        Other = 0
        DAW = 127

    class layout(Enum):
        Drum = 1
        Session = 2
        Custom = 5
        Drum2 = 6
        Toggle = 7
        ProgramChange = 8

    palette = numpy.array([(0, 0, 0), (31, 31, 31), (127, 127, 127), (255, 255, 255), 
                           (255, 75, 75), (255, 0, 0), (87, 0, 0), (27, 0, 0), 
                           (255, 187, 107), (255, 83, 0), (87, 31, 0), (39, 27, 0), 
                           (255, 255, 75), (255, 255, 0), (87, 87, 0), (27, 27, 0), 
                           (135, 255, 75), (83, 255, 0), (31, 87, 0), (19, 43, 0), 
                           (75, 255, 75), (0, 255, 0), (0, 87, 0), (0, 27, 0), 
                           (75, 255, 95), (0, 255, 27), (0, 87, 15), (0, 27, 0), 
                           (75, 255, 135), (0, 255, 87), (0, 87, 31), (0, 31, 19), 
                           (75, 255, 183), (0, 255, 151), (0, 87, 55), (0, 27, 19), 
                           (75, 195, 255), (0, 167, 255), (0, 67, 83), (0, 15, 27), 
                           (75, 135, 255), (0, 87, 255), (0, 31, 87), (0, 7, 27), 
                           (75, 75, 255), (0, 0, 255), (0, 0, 87), (0, 0, 27), 
                           (135, 75, 255), (83, 0, 255), (27, 0, 99), (15, 0, 47), 
                           (255, 75, 255), (255, 0, 255), (87, 0, 87), (27, 0, 27), 
                           (255, 75, 135), (255, 0, 83), (87, 0, 31), (35, 0, 19), 
                           (255, 23, 0), (151, 55, 0), (119, 83, 0), (67, 99, 0), 
                           (0, 59, 0), (0, 87, 55), (0, 83, 127), (0, 0, 255), 
                           (0, 71, 79), (39, 0, 203), (127, 127, 127), (31, 31, 31), 
                           (255, 0, 0), (187, 255, 47), (175, 235, 7), (99, 255, 11), 
                           (15, 139, 0), (0, 255, 135), (0, 167, 255), (0, 43, 255), 
                           (63, 0, 255), (123, 0, 255), (175, 27, 123), (63, 35, 0), 
                           (255, 75, 0), (135, 223, 7), (115, 255, 23), (0, 255, 0), 
                           (59, 255, 39), (87, 255, 111), (55, 255, 203), (91, 139, 255), 
                           (51, 83, 195), (135, 127, 231), (211, 31, 255), (255, 0, 91), 
                           (255, 127, 0), (183, 175, 0), (143, 255, 0), (131, 91, 7), 
                           (59, 43, 0), (19, 75, 15), (15, 79, 55), (23, 23, 43), 
                           (23, 31, 91), (103, 59, 27), (167, 0, 11), (219, 83, 63), 
                           (215, 107, 27), (255, 223, 39), (159, 223, 47), (103, 179, 15), 
                           (31, 31, 47), (219, 255, 107), (127, 255, 187), (155, 151, 255), 
                           (143, 103, 255), (63, 63, 63), (115, 115, 115), (223, 255, 255), 
                           (159, 0, 0), (55, 0, 0), (27, 207, 0), (7, 67, 0), 
                           (183, 175, 0), (63, 51, 0), (179, 95, 0), (75, 23, 0)])
    
    def __init__(self, inPort: str = None, outPort: str = None, **kwargs):
        super().__init__(inPort=inPort, outPort=outPort, width = 8, height = 2, **kwargs)

    def setMode(self, mode: mode):
        self.sendNoteOn(12, mode.value, 15)

    def setLayout(self, layout: layout):
        self.sendControlChange(3, layout.value, 15)

    def sendColor(self, x: int, y: int, color: Pixel):
        index = 0
        if y == 0:
            index = 0x70 + x
        elif y == 1:
            index = 0x60 + x
        else:
            return
        self.sendNoteOn(index, color.findInPalette(self.palette))

    def connect(self):
        super().connect()
        self.setMode(LaunchkeyMK3.mode.DAW)
        self.setLayout(LaunchkeyMK3.layout.Session)

    def disconnect(self):
        self.setMode(LaunchkeyMK3.mode.Other)
        self.setLayout(LaunchkeyMK3.layout.Drum)
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