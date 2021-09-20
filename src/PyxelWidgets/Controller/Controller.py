from ..Helpers import *
import numpy
from threading import Timer

class Controller():

    _count = 0

    def __init__(self, **kwargs):
        self.name = kwargs.get('name', f'Controller_{Controller._count}')
        self.rect = Rectangle2D(kwargs.get('x', 0), kwargs.get('y', 0), kwargs.get('width', 1), kwargs.get('height', 1))
        self.heldTime = kwargs.get('heldTime', 1.0)
        self.connected = False
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), Pixel)
        self.buffer.fill(Colors.Invisible)
        self.buttons = numpy.ndarray((self.rect.w, self.rect.h))
        self.buttons.fill(0.0)
        self._timers = numpy.ndarray((self.rect.w, self.rect.h), Timer)
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
        self._timers[x, y] = Timer(interval = self.heldTime, function = self.setHeld, args = (x, y))
        self._timers[x, y].start()
        self._callback('pressed', (x, y, self.buttons[x, y]))
    
    def setReleased(self, x: int, y: int) -> None:
        self._timers[x, y].cancel()
        self._callback('released', (x, y, self.buttons[x, y]))
    
    def setHeld(self, x: int, y: int) -> None:
        self._callback('held', (x, y, self.buttons[x, y]))

    def process(self):
        pass

    def processInput(self):
        pass

    def updateOne(self, x: int, y: int, pixel: Pixel):
        pass

    def updateRow(self, y: int, pixel: Pixel):
        pass

    def updateColumn(self, x: int, pixel: Pixel):
        pass
    
    def updateArea(self, x: int, y: int, width: int, height: int, pixel: Pixel):
        pass

    def update(self, buffer):
        pass