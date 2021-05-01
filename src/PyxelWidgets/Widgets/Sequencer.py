from .Widget import Widget
from threading import Thread
import time

class Sequencer(Widget):
    def __init__(self, name: str, x: int, y: int, width: int, height: int, **kwargs):
        super().__init__(name, x=x, y=y, width=width, height=height, **kwargs)
        self._active = [[False for y in range(self.height)] for x in range(self.width)]
        self._bpm = kwargs.get('bpm', 60)
        self._numerator = kwargs.get('numerator', 1)
        self._denominator = kwargs.get('denominator', 4)
        self._duration = kwargs.get('duration', 4)
        self._currentColor = kwargs.get('currentColor', [0, 255, 0])
        self._tickPeriod = self._calcTickPeriod()
        self._tickTarget = self.width * self.height
        self._tick = 0

    @property
    def bpm(self):
        return self._bpm
    
    @bpm.setter
    def bpm(self, bpm):
        self._bpm = bpm
        self._tickPeriod = self._calcTickPeriod()
    
    @property
    def numerator(self):
        return self._numerator
    
    @numerator.setter
    def numerator(self, numerator):
        self._numerator = numerator
        self._tickPeriod = self._calcTickPeriod()

    @property
    def denominator(self):
        return self._denominator
    
    @denominator.setter
    def denominator(self, denominator):
        self._denominator = denominator
        self._tickPeriod = self._calcTickPeriod()

    @property
    def duration(self):
        return self._duration
    
    @duration.setter
    def duration(self, duration):
        self._duration = duration
        self._tickPeriod = self._calcTickPeriod()
    
    @property
    def period(self):
        return self._tickPeriod
    
    def stop(self):
        self._tick = 0

    def tick(self):
        self._tick += 1
        if self._tick == self._tickTarget:
            self.stop()
        if self._isTickActive():
            self._callback(self.name, self._tick)

    def pressed(self, x: int, y: int, value: float):
        self._active[x][y] = not self._active[x][y]

    def update(self) -> list:
        for x in range(self.width):
            for y in range(self.height):
                if self._active[x][y]:
                    self._pixels[x][y] = self._activeColor
                else:
                    self._pixels[x][y] = self._deactiveColor
        self._pixels[self._tickX()][self._tickY()] = self._currentColor
        return self._pixels

    def _calcTickPeriod(self):
        return (60.0 / self.bpm) / ((self.numerator / self.denominator) * 4.0) / self.duration
    
    def _calcTickPosition(self, x, y):
        return x + ((self.height - y - 1) * self.width)
    
    def _tickX(self):
        return self._tick % self.width
    
    def _tickY(self):
        return self.height - (self._tick // self.width) - 1
    
    def _isTickActive(self):
        return self._active[self._tickX()][self._tickY()]