from . import Widget
from ..Util.Clock import *

class Sequencer(Widget):
    def __init__(self, width: int, height: int, clock: Clock = None, **kwargs):
        name = kwargs.get('name', 'Sequencer_' + str(Sequencer._count))
        super().__init__(name, width, height, **kwargs)
        self._active = [[False for y in range(self.height)] for x in range(self.width)]
        self._numerator = kwargs.get('numerator', 1.0)
        self._denominator = kwargs.get('denominator', 4.0)
        self._ppq = kwargs.get('ppq', 24)
        self._currentColor = kwargs.get('currentColor', [0, 255, 0])
        self._tickTarget = self.width * self.height
        self._tick = 0
        self._target = Target(self.name, self.tick)
        if clock != None:
            self.addToClock(clock)
        Sequencer._count += 1
    
    @property
    def numerator(self):
        return self._numerator
    
    @numerator.setter
    def numerator(self, numerator: int):
        self._numerator = numerator

    @property
    def denominator(self):
        return self._denominator
    
    @denominator.setter
    def denominator(self, denominator: int):
        self._denominator = denominator
    
    @property
    def ppq(self):
        return self._ppq

    @ppq.setter
    def ppq(self, ppq: int):
        self._ppq = ppq

    @property
    def target(self):
        return self._target
    
    def addToClock(self, clock: Clock):
        self.ppq = clock.ppq
        clock.addTarget(self.target)

    def tick(self, tick):
        oldTick = self._tick
        self._tick = tick / (self._ppq * (self._numerator / self._denominator))
        self._tick %= self._tickTarget
        if int(oldTick) != int(self._tick):
            self._updated = True
            self._callback(self.name, 'tick', int(self._tick))
            if self._isTickActive():
                self._callback(self.name, 'active', int(self._tick))

    def pressed(self, x: int, y: int, value: float):
        self._active[x][y] = not self._active[x][y]
        self._updated = True
        super().pressed(x, y, value)

    def updateArea(self, sx, sy, sw, sh):
        if self._updated:
            self._updated = False
            ex = sx + sw
            ex = ex if ex < self.width else self.width
            ey = sy + sh
            ey = ey if ey < self.height else self.height
            for x in range(sx, ex):
                for y in range(sy, ey):
                    if self._active[x][y]:
                        self._pixels[x][y] = self._activeColor
                    else:
                        self._pixels[x][y] = self._deactiveColor
            self._pixels[self._tickX()][self._tickY()] = self._currentColor
            return self._pixels
        return []
    
    def _resize(self, width, height):
        self._tickTarget = width * height
        return True
    
    def _calcTickPosition(self, x, y):
        return x + ((self.height - y - 1) * self.width)
    
    def _tickX(self):
        return int(self._tick) % self.width
    
    def _tickY(self):
        return self.height - (int(self._tick) // self.width) - 1
    
    def _isTickActive(self):
        return self._active[self._tickX()][self._tickY()]