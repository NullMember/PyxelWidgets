from . import Widget
from ..Helpers import *
from ..Util.Clock import *
from copy import deepcopy

class Life(Widget):
    def __init__(self, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', 'Life_' + str(Life._count))
        super().__init__(width, height, **kwargs)
        self._running = False
        self._grid = [[False for y in range(self.rect.h)] for x in range(self.rect.w)]
        Life._count += 1
    
    def pressed(self, x: int, y: int, value: float):
        if not self._running:
            self._grid[x][y] = not self._grid[x][y]
            self.updated = True
        super().pressed(x, y, value)

    def start(self):
        self._running = True
    
    def stop(self):
        self._running = False

    def tick(self, tick):
        if self._running:
            self.updated = True

    def updateArea(self, sx, sy, sw, sh):
        self.updated = False
        newGrid = deepcopy(self._grid)
        area = Rectangle2D(sx, sy, sw, sh)
        for x in area.columns:
            for y in area.rows:
                if self._running:
                    total = int(self._grid[(x - 1) % self.rect.w][(y - 1) % self.rect.h]) + \
                            int(self._grid[(x + 0) % self.rect.w][(y - 1) % self.rect.h]) + \
                            int(self._grid[(x + 1) % self.rect.w][(y - 1) % self.rect.h]) + \
                            int(self._grid[(x - 1) % self.rect.w][(y + 0) % self.rect.h]) + \
                            int(self._grid[(x + 1) % self.rect.w][(y + 0) % self.rect.h]) + \
                            int(self._grid[(x - 1) % self.rect.w][(y + 1) % self.rect.h]) + \
                            int(self._grid[(x + 0) % self.rect.w][(y + 1) % self.rect.h]) + \
                            int(self._grid[(x + 1) % self.rect.w][(y + 1) % self.rect.h])
                    if self._grid[x][y]:
                        if (total < 2) or (total > 3):
                            newGrid[x][y] = False
                    else:
                        if total == 3:
                            newGrid[x][y] = True
                if newGrid[x][y]:
                    self.buffer[x, y] = self.activeColor
                else:
                    self.buffer[x, y] = self.deactiveColor
        self._grid = newGrid
        return self.buffer[area.l:area.r, area.b:area.t]