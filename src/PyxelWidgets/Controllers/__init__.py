__all__ = ['OSC', 'MIDI']

import PyxelWidgets.Helpers
import PyxelWidgets.Utils.Clock
import numpy
import threading

class Controller():

    _count = 0

    def __init__(self, **kwargs):
        self.name = kwargs.get('name', f'Controller_{Controller._count}')
        self.rect = PyxelWidgets.Helpers.Rectangle2D(kwargs.get('x', 0), kwargs.get('y', 0), kwargs.get('width', 1), kwargs.get('height', 1))
        self.heldTime = kwargs.get('heldTime', 1.0)
        self.initialized = False
        self.connected = False
        self.terminated = False
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), PyxelWidgets.Helpers.Pixel)
        self.buffer.fill(PyxelWidgets.Helpers.Colors.Invisible)
        self.buttons = numpy.ndarray((self.rect.w, self.rect.h))
        self.buttons.fill(0.0)
        self.clock = PyxelWidgets.Utils.Clock.Clock()
        self._held = numpy.ndarray((self.rect.w, self.rect.h), threading.Timer)
        self._callback = lambda *_, **__ : None
        Controller._count += 1

    def setCallback(self, callback):
        self._callback = callback

    def init(self):
        if self.initialized:
            raise Exception(f'{self.name} already initialized')
        self.clock.start()
        self.initialized = True
    
    def close(self):
        if self.connected:
            self.disconnect()
        self.clock.terminate()
        self.terminated = True

    def connect(self):
        if self.connected:
            self.disconnect()
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
        self._held[x, y] = threading.Timer(interval = self.heldTime, function = self.setHeld, args = (x, y))
        self._held[x, y].start()
        self._callback(self.name, 'pressed', (x, y, self.buttons[x, y]))
    
    def setReleased(self, x: int, y: int) -> None:
        self._held[x, y].cancel()
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
            if intersect is not None:
                if pixel != self.buffer[x, y]:
                    self.buffer[x, y] = pixel
                    self.sendPixel(x, y, pixel)

    def updateRow(self, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        if self.connected:
            intersect = self.rect.intersect(PyxelWidgets.Helpers.Rectangle2D(0, y, self.rect.w, 1))
            if intersect is not None:
                for x in intersect.columns:
                    if pixel != self.buffer[x, y]:
                        self.buffer[x, y] = pixel
                        self.sendPixel(x, y, pixel)

    def updateColumn(self, x: int, pixel: PyxelWidgets.Helpers.Pixel):
        if self.connected:
            intersect = self.rect.intersect(PyxelWidgets.Helpers.Rectangle2D(x, 0, 1, self.rect.h))
            if intersect is not None:
                for y in intersect.rows:
                    if pixel != self.buffer[x, y]:
                        self.buffer[x, y] = pixel
                        self.sendPixel(x, y, pixel)
    
    def updateArea(self, rect: PyxelWidgets.Helpers.Rectangle2D, pixel: PyxelWidgets.Helpers.Pixel):
        if self.connected:
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                for x in intersect.columns:
                    for y in intersect.rows:
                        if pixel != self.buffer[x, y]:
                            self.buffer[x, y] = pixel
                            self.sendPixel(x, y, pixel)

    def update(self, data: tuple):
        rect, buffer = data
        if self.connected:
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                updated = numpy.where(buffer[(intersect - rect).slice] != self.buffer[intersect.slice], True, False)
                self.buffer[intersect.slice] = numpy.where(updated, buffer[(intersect - rect).slice], self.buffer[intersect.slice])
                for x in intersect.columns:
                    for y in intersect.rows:
                        if updated[x, y]:
                            self.sendPixel(x, y, self.buffer[x, y])