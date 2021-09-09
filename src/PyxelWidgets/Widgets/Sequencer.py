from . import Widget
from ..Helpers import *
from ..Util.Clock import *

class Sequencer(Widget):
    def __init__(self, width: int, height: int, clock: Clock = None, **kwargs):
        kwargs['name'] = kwargs.get('name', 'Sequencer_' + str(Sequencer._count))
        super().__init__(width, height, **kwargs)
        self.active = [[False for y in range(self.rect.h)] for x in range(self.rect.w)]
        self.numerator = kwargs.get('numerator', 1.0)
        self.denominator = kwargs.get('denominator', 4.0)
        self.ppq = kwargs.get('ppq', 24)
        self.currentColor = kwargs.get('currentColor', [0, 255, 0])
        self._tickTarget = self.rect.w * self.rect.h
        self._tick = 0
        self.target = Target(self.name, self.tick)
        if clock != None:
            self.addToClock(clock)
        Sequencer._count += 1
    
    def addToClock(self, clock: Clock):
        self.ppq = clock.ppq
        clock.addTarget(self.target)

    def tick(self, tick):
        oldTick = self._tick
        self._tick = tick / (self.ppq * (self.numerator / self.denominator))
        self._tick %= self._tickTarget
        if int(oldTick) != int(self._tick):
            self.updated = True
            self._callback(self.name, 'tick', int(self._tick))
            if self._isTickActive():
                self._callback(self.name, 'active', int(self._tick))

    def pressed(self, x: int, y: int, value: float):
        self.active[x][y] = not self.active[x][y]
        self.updated = True
        super().pressed(x, y, value)

    def updateArea(self, sx, sy, sw, sh):
        self.updated = False
        area = Rectangle2D(sx, sy, sw, sh)
        for x in area.columns:
            for y in area.rows:
                if self.active[x][y]:
                    self.buffer[x, y] = self.activeColor
                else:
                    self.buffer[x, y] = self.deactiveColor
        self.buffer[self._tickX()][self._tickY()] = self.currentColor
        return self.buffer[area.l:area.r, area.b:area.t]
    
    def _resize(self, width, height):
        self._tickTarget = width * height
        return True
    
    def _calcTickPosition(self, x, y):
        return x + ((self.rect.h - y - 1) * self.rect.w)
    
    def _tickX(self):
        return int(self._tick) % self.rect.w
    
    def _tickY(self):
        return self.rect.h - (int(self._tick) // self.rect.w) - 1
    
    def _isTickActive(self):
        return self.active[self._tickX()][self._tickY()]