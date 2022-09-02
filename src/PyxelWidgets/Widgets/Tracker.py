import PyxelWidgets.Widgets
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import PyxelWidgets.Utils.Clock
import numpy
import enum

class Tracker(PyxelWidgets.Widgets.Widget):

    # class Scroll(enum.Enum):
    #     Continuous = enum.auto()
    #     Page = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, clock: PyxelWidgets.Utils.Clock.Clock = None, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Tracker_{Tracker._count}')
        self.bars = kwargs.get('bars', 64)
        self.bars = self.bars if self.bars >= height else height
        self.pages = kwargs.get('pages', 1)
        self.pages = self.pages if self.pages > 0 else 1
        self.states = numpy.ndarray((1, 1, 1), dtype = numpy.bool8)
        self.currentBar = 0
        self.numerator = kwargs.get('numerator', 1.0)
        self.denominator = kwargs.get('denominator', 4.0)
        self.ppq = kwargs.get('ppq', 24)
        super().__init__(x, y, width, height, **kwargs)
        self.states.fill(False)
        self.currentTop = 0
        self.currentBottom = self.currentTop + self.height - 1
        self.currentPage = 0
        self.currentColor = kwargs.get('currentColor', PyxelWidgets.Utils.Pixel.Colors.Cyan)
        self.currentActiveColor = kwargs.get('currentActiveColor', PyxelWidgets.Utils.Pixel.Colors.Magenta)
        self.target = PyxelWidgets.Utils.Clock.Target(self.tick, name = self.name)
        if clock != None:
            self.addToClock(clock)
        Tracker._count += 1

    def addToClock(self, clock: PyxelWidgets.Utils.Clock.Clock):
        self.ppq = clock.ppq
        clock.addTarget(self.target)

    def press(self, x: int, y: int, value: float):
        self.states[self.currentPage, x, self.rect.h - 1 - y + self.currentTop] = not self.states[self.currentPage, x, self.rect.h - 1 - y + self.currentTop]
        self.updated = True

    def scroll(self, bar):
        self.tick(bar * (self.ppq * (self.numerator / self.denominator)))

    def tick(self, tick):
        oldBar = self.currentBar
        self.currentBar = tick / (self.ppq * (self.numerator / self.denominator))
        self.currentPage = int(self.currentBar / self.bars)
        self.currentPage %= self.pages
        self.currentBar %= self.bars
        if int(oldBar) != int(self.currentBar):
            self.updated = True
            self.currentBar = self.currentBar
            halfHeight = self.height // 2
            # if self.scroll == Tracker.Scroll.Continuous:
            corr = int(not (self.height % 2))
            if self.currentBar < halfHeight:
                self.currentTop = 0
                self.currentBottom = int(self.currentTop + self.height - 1)
            elif self.currentBar >= self.bars - halfHeight:
                self.currentTop = int(self.bars - self.height)
                self.currentBottom = int(self.bars - corr)
            else:
                self.currentTop = int(self.currentBar - (halfHeight - corr))
                self.currentBottom = int(self.currentBar + halfHeight)
            # elif self.scroll == Tracker.Scroll.Page:
            #     pass
            self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Tick, int(self.currentBar))
            for i, state in enumerate(self.states[self.currentPage, :, int(self.currentBar)]):
                if state:
                    self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Active, (int(self.currentBar), i))

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D) -> tuple:
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                self.buffer[area.slice] = numpy.fliplr(numpy.where(self.states[self.currentPage, :, self.currentTop:(self.currentBottom + 1)] == True, self.activeColor, self.deactiveColor))
                self.buffer[:, int(self.currentBottom - self.currentBar)] = numpy.where(self.states[self.currentPage, :, int(self.currentBar)] == True, self.currentActiveColor, self.currentColor)
            return intersect, self.buffer[area.slice]
        return None, None

    def _resize(self, width, height) -> bool:
        self.states.resize((self.pages, width, self.bars), refcheck = False)
        self.tick(0)
        return True