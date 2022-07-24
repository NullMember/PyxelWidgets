import PyxelWidgets.Widgets
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import PyxelWidgets.Utils.Clock
import numpy

class Sequencer(PyxelWidgets.Widgets.Widget):
    def __init__(self, x: int, y: int, width: int, height: int, clock: PyxelWidgets.Utils.Clock.Clock = None, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Sequencer_{Sequencer._count}')
        self.state = numpy.ndarray((1, 1), dtype = numpy.bool8)
        self._step = kwargs.get('step', width * height)
        self._tick = 0
        self._pageCount = 1
        super().__init__(x, y, width, height, **kwargs)
        self.state.fill(False)
        self.currentPage = 0
        self._page = 0
        self.follow = True
        self.note = kwargs.get('note', 4.0)
        self.beat = kwargs.get('beat', 4.0)
        self.ppq = kwargs.get('ppq', 24)
        self.currentColor = kwargs.get('currentColor', PyxelWidgets.Utils.Pixel.Colors.Lime)
        self.currentActiveColor = kwargs.get('currentActiveColor', PyxelWidgets.Utils.Pixel.Colors.Red)
        self.target = PyxelWidgets.Utils.Clock.Target(self.tick)
        if clock != None:
            self.addToClock(clock)
        Sequencer._count += 1
    
    def addToClock(self, clock: PyxelWidgets.Utils.Clock.Clock):
        self.ppq = clock.ppq
        clock.addTarget(self.target)
    
    @property
    def pages(self) -> int:
        return self._pageCount

    @property
    def page(self) -> int:
        return self._page

    @page.setter
    def page(self, value: int) -> None:
        self._page = value % self._pageCount
        self.updated = True

    @property
    def step(self) -> int:
        return self._step

    @step.setter
    def step(self, value: int) -> None:
        self._step = value
        self._pageCount = int((self._step - 1) / self.rect.area) + 1
        self.state = numpy.zeros((self.rect.w, self.rect.h * self._pageCount), dtype = numpy.bool8)
        self._tick %= self._step
        self.currentPage = int(self._tick / self.rect.area)

    def tick(self, tick):
        oldTick = self._tick
        self._tick = tick / (self.ppq * ((4.0 / self.note) / self.beat))
        self._tick %= self._step
        if int(oldTick) != int(self._tick):
            page = int(self._tick / self.rect.area)
            if page != self.currentPage:
                self.currentPage = page
                self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Page, self.currentPage)
            self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Tick, int(self._tick))
            if self._isTickActive():
                self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Active, int(self._tick))
            self.updated = True

    def press(self, x: int, y: int, value: float):
        if self._calcTickPosition(x, y) < self._step:
            pageY = y + (self.rect.h * self._tickPage())
            self.state[x, pageY] = not self.state[x, pageY]
            self.updated = True

    def reset(self):
        self.state.fill(False)

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        intersect = self.rect.intersect(rect)
        if intersect is not None:
            area = intersect - self.rect
            if self.bufferUpdated:
                self.bufferUpdated = False
                tickP = self._tickPage()
                tickX = self._tickX()
                tickY = self._tickY() % self.rect.h
                stateArea = area + PyxelWidgets.Utils.Rectangle.Rectangle2D(0, self.rect.h * tickP)
                self.buffer[area.slice] = numpy.where(self.state[stateArea.slice] == True, self.activeColor, self.deactiveColor)
                if tickP == self.currentPage:
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
        self._pageCount = int((self._step - 1) / (width * height)) + 1
        self.state.resize((width, height * self._pageCount), refcheck = False)
        self._tick %= self._step
        return True
    
    def _calcTickPosition(self, x, y):
        return (x + (y * self.rect.w)) + (self.rect.area * self._tickPage())
    
    def _tickPage(self):
        return self.currentPage if self.follow else self._page

    def _tickX(self):
        return int(self._tick) % self.rect.w
    
    def _tickY(self):
        return int(self._tick // self.rect.w)
    
    def _isTickActive(self):
        return self.state[self._tickX()][self._tickY()]