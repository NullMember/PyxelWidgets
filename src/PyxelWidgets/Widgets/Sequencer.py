import PyxelWidgets.Widgets
import PyxelWidgets.Helpers
import PyxelWidgets.Util.Clock

class Sequencer(PyxelWidgets.Widgets.Widget):
    def __init__(self, x: int, y: int, width: int, height: int, clock: PyxelWidgets.Util.Clock.Clock = None, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Sequencer_{Sequencer._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.active = [[False for y in range(self.rect.h)] for x in range(self.rect.w)]
        self.numerator = kwargs.get('numerator', 1.0)
        self.denominator = kwargs.get('denominator', 4.0)
        self.ppq = kwargs.get('ppq', 24)
        self.currentColor = kwargs.get('currentColor', PyxelWidgets.Helpers.Colors.Lime)
        self._tickTarget = self.rect.w * self.rect.h
        self._tick = 0
        self.target = PyxelWidgets.Util.Clock.Target(self.tick)
        if clock != None:
            self.addToClock(clock)
        Sequencer._count += 1
    
    def addToClock(self, clock: PyxelWidgets.Util.Clock.Clock):
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

    def updateArea(self, rect: PyxelWidgets.Helpers.Rectangle2D):
        self.updated = False
        intersect = self.rect.intersect(rect)
        if intersect:
            area = intersect - self.rect
            for x in area.columns:
                for y in area.rows:
                    if self.active[x][y]:
                        self.buffer[x, y] = self.activeColor
                    else:
                        self.buffer[x, y] = self.deactiveColor
            self.buffer[self._tickX()][self._tickY()] = self.currentColor
            return intersect, self.buffer[area.l:area.r, area.b:area.t]
        return None
    
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