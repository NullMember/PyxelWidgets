import PyxelWidgets.Widgets
import PyxelWidgets.Helpers
import PyxelWidgets.Utils.Clock
import numpy

class Sequencer(PyxelWidgets.Widgets.Widget):
    def __init__(self, x: int, y: int, width: int, height: int, clock: PyxelWidgets.Utils.Clock.Clock = None, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Sequencer_{Sequencer._count}')
        self.state = numpy.ndarray((1, 1), dtype = numpy.bool8)
        self._step = kwargs.get('step', width * height)
        self._tick = 0
        self._page = 1
        super().__init__(x, y, width, height, **kwargs)
        self.state.fill(False)
        self.note = kwargs.get('note', 4.0)
        self.beat = kwargs.get('beat', 4.0)
        self.ppq = kwargs.get('ppq', 24)
        self.currentColor = kwargs.get('currentColor', PyxelWidgets.Helpers.Colors.Lime)
        self.currentActiveColor = kwargs.get('currentActiveColor', PyxelWidgets.Helpers.Colors.Red)
        self.target = PyxelWidgets.Utils.Clock.Target(self.tick)
        if clock != None:
            self.addToClock(clock)
        Sequencer._count += 1
    
    def addToClock(self, clock: PyxelWidgets.Utils.Clock.Clock):
        self.ppq = clock.ppq
        clock.addTarget(self.target)

    @property
    def step(self) -> int:
        return self._step
    
    @step.setter
    def step(self, value: int) -> None:
        self._step = value
        self._page = int(self._step / (self.rect.w * self.rect.h)) + 1
        self.state.resize((self.rect.w, self.rect.h * self._page), refcheck = False)
        self._tick %= self._step

    def tick(self, tick):
        oldTick = self._tick
        self._tick = tick / (self.ppq * ((4.0 / self.note) / self.beat))
        self._tick %= self._step
        if int(oldTick) != int(self._tick):
            self.updated = True
            self._callback(self.name, PyxelWidgets.Helpers.Event.Tick, int(self._tick))
            if self._isTickActive():
                self._callback(self.name, PyxelWidgets.Helpers.Event.Active, int(self._tick))

    def press(self, x: int, y: int, value: float):
        self.state[x, y + (self.rect.h * self._tickPage())] = not self.state[x, y + (self.rect.h * self._tickPage())]
        self.updated = True

    def reset(self):
        self.state.fill(False)

    def updateArea(self, rect: PyxelWidgets.Helpers.Rectangle2D):
        intersect = self.rect.intersect(rect)
        if intersect is not None:
            area = intersect - self.rect
            if self.bufferUpdated:
                self.bufferUpdated = False
                tickP = self._tickPage()
                tickX = self._tickX()
                tickY = self._tickY() % self.rect.h
                stateArea = area + PyxelWidgets.Helpers.Rectangle2D(0, self.rect.h * tickP)
                self.buffer[area.slice] = numpy.where(self.state[stateArea.slice] == True, self.activeColor, self.deactiveColor)
                if self.buffer[tickX, tickY] == self.activeColor:
                    self.buffer[tickX, tickY] = self.currentActiveColor
                else:
                    self.buffer[tickX, tickY] = self.currentColor
                if self.effect is None:
                    return intersect, self.buffer[area.slice]
            if self.effect is not None:
                return intersect, self.effect.apply(self.buffer[area.slice])
        return None, None
    
    def _resize(self, width, height):
        self._page = int(self._step / (width * height)) + 1
        self.state.resize((width, height * self._page), refcheck = False)
        self._tick %= self._step
        return True
    
    def _calcTickPosition(self, x, y):
        return x + ((self.rect.h - y - 1) * self.rect.w)
    
    def _tickPage(self):
        return int((self._tick / self.rect.w) / self.rect.h)

    def _tickX(self):
        return int(self._tick) % self.rect.w
    
    def _tickY(self):
        return (self.rect.h * self._page) - (int(self._tick) // self.rect.w) - 1
    
    def _isTickActive(self):
        return self.state[self._tickX()][self._tickY()]