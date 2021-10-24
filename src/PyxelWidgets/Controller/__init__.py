__all__ = ['OSC', 'MIDI']

import PyxelWidgets.Helpers
import numpy
import threading

class Controller():

    _count = 0

    def __init__(self, **kwargs):
        self.name = kwargs.get('name', f'Controller_{Controller._count}')
        self.rect = PyxelWidgets.Helpers.Rectangle2D(kwargs.get('x', 0), kwargs.get('y', 0), kwargs.get('width', 1), kwargs.get('height', 1))
        self.heldTime = kwargs.get('heldTime', 1.0)
        self.connected = False
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), PyxelWidgets.Helpers.Pixel)
        self.buffer.fill(PyxelWidgets.Helpers.Colors.Invisible)
        self.buttons = numpy.ndarray((self.rect.w, self.rect.h))
        self.buttons.fill(0.0)
        self._timers = numpy.ndarray((self.rect.w, self.rect.h), threading.Timer)
        self._callback = lambda *_, **__ : None
        Controller._count += 1

    def setCallback(self, callback):
        self._callback = callback

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False
    
    def getButton(self, x: int, y: int) -> float:
        return self.buttons[x, y]

    def setButton(self, x: int, y: int, value: float) -> None:
        self.buttons[x, y] = min(1.0, max(0.0, value))
        self.setState(x, y, bool(self.buttons[x, y]))
    
    def setState(self, x: int, y: int, state: bool) -> None:
        if state:
            self.setPressed(x, y)
        else:
            self.setReleased(x, y)
        return
    
    def setPressed(self, x: int, y: int) -> None:
        self._timers[x, y] = threading.Timer(interval = self.heldTime, function = self.setHeld, args = (x, y))
        self._timers[x, y].start()
        self._callback(self.name, 'pressed', (x, y, self.buttons[x, y]))
    
    def setReleased(self, x: int, y: int) -> None:
        self._timers[x, y].cancel()
        self._callback(self.name, 'released', (x, y, self.buttons[x, y]))
    
    def setHeld(self, x: int, y: int) -> None:
        self._callback(self.name, 'held', (x, y, self.buttons[x, y]))
    
    def setCustom(self, event, name, value):
        self._callback(self.name, 'custom', (name, event, value))

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        raise NotImplementedError("sendPixel method must be implemented")

    def updateOne(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        if self.connected:
            intersect = self.rect.intersect(PyxelWidgets.Helpers.Rectangle2D(x, y, 1, 1))
            if intersect:
                if pixel == self.buffer[x, y]:
                    pass
                else:
                    self.buffer[x, y] = pixel
                    self.sendPixel(x, y, pixel)

    def updateRow(self, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        if self.connected:
            intersect = self.rect.intersect(PyxelWidgets.Helpers.Rectangle2D(0, y, self.rect.w, 1))
            if intersect:
                for x in intersect.columns:
                    if pixel == self.buffer[x, y]:
                        pass
                    else:
                        self.buffer[x, y] = pixel
                        self.sendPixel(x, y, pixel)

    def updateColumn(self, x: int, pixel: PyxelWidgets.Helpers.Pixel):
        if self.connected:
            intersect = self.rect.intersect(PyxelWidgets.Helpers.Rectangle2D(x, 0, 1, self.rect.h))
            if intersect:
                for y in intersect.rows:
                    if pixel == self.buffer[x, y]:
                        pass
                    else:
                        self.buffer[x, y] = pixel
                        self.sendPixel(x, y, pixel)
    
    def updateArea(self, x: int, y: int, width: int, height: int, pixel: PyxelWidgets.Helpers.Pixel):
        if self.connected:
            intersect = self.rect.intersect(PyxelWidgets.Helpers.Rectangle2D(x, y, width, height))
            if intersect:
                for _x in intersect.columns:
                    for _y in intersect.rows:
                        if pixel == self.buffer[_x, _y]:
                            pass
                        else:
                            self.buffer[_x, _y] = pixel
                            self.sendPixel(x, y, pixel)

    def update(self, buffer):
        if self.connected:
            intersect = self.rect.intersect(PyxelWidgets.Helpers.Rectangle2D(0, 0, buffer.shape[0], buffer.shape[1]))
            if intersect:
                for x in intersect.columns:
                    for y in intersect.rows:
                        if buffer[x, y] == self.buffer[x, y]:
                            pass
                        else:
                            self.buffer[x, y] = buffer[x, y]
                            self.sendPixel(x, y, self.buffer[x, y])