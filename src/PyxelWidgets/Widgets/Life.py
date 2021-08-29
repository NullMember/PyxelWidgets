from .Widget import *
from ..Util.Clock import *
from copy import deepcopy

class Life(Widget):
    def __init__(self, width: int, height: int, **kwargs):
        name = kwargs.get('name', 'Life' + str(Life._count))
        super().__init__(name, width=width, height=height, **kwargs)
        self._running = False
        self._grid = [[False for y in range(self.height)] for x in range(self.width)]
        Life._count += 1
    
    def pressed(self, x: int, y: int, value: float):
        if not self._running:
            self._grid[x][y] = not self._grid[x][y]
            self._updated = True
        super().pressed(x, y, value)

    def start(self):
        self._running = True
    
    def stop(self):
        self._running = False

    def tick(self, tick):
        if self._running:
            self._updated = True

    def updateArea(self, sx, sy, sw, sh):
        if self._updated:
            self._updated = False
            ex = sx + sw
            ex = ex if ex < self.width else self.width
            ey = sy + sh
            ey = ey if ey < self.height else self.height
            newGrid = deepcopy(self._grid)
            for x in range(sx, ex):
                for y in range(sy, ey):
                    if self._running:
                        total = int(self._grid[(x - 1) % self.width][(y - 1) % self.height]) + \
                                int(self._grid[(x + 0) % self.width][(y - 1) % self.height]) + \
                                int(self._grid[(x + 1) % self.width][(y - 1) % self.height]) + \
                                int(self._grid[(x - 1) % self.width][(y + 0) % self.height]) + \
                                int(self._grid[(x + 1) % self.width][(y + 0) % self.height]) + \
                                int(self._grid[(x - 1) % self.width][(y + 1) % self.height]) + \
                                int(self._grid[(x + 0) % self.width][(y + 1) % self.height]) + \
                                int(self._grid[(x + 1) % self.width][(y + 1) % self.height])
                        if self._grid[x][y]:
                            if (total < 2) or (total > 3):
                                newGrid[x][y] = False
                        else:
                            if total == 3:
                                newGrid[x][y] = True
                    if newGrid[x][y]:
                        self._pixels[x][y] = self._activeColor
                    else:
                        self._pixels[x][y] = self._deactiveColor
            self._grid = newGrid
            return self._pixels
        return []