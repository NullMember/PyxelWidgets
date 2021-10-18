from . import Widget
from ..Helpers import *
import numpy

class Sprite(Widget):
    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Sprite_{Sprite._count}')
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        self.animate = kwargs.get('animate', False)
        self.frames = kwargs.get('frames', None)
        self.target = kwargs.get('target', 30)
        self.tick = kwargs.get('tick', 0)
        self.currentFrame = 0
        self.nextFrame = 0
        if not isinstance(self.frames, numpy.ndarray):
            self.frames = [numpy.ndarray((self.rect.w, self.rect.h))]
            self.frames[0].fill(Colors.Invisible)
        self.buffer = self.frames[0]

    def updateArea(self, sx: int, sy: int, sw: int, sh: int):
        self.updated = False
        intersect = self.rect.intersect(Rectangle2D(sx, sy, sw, sh))
        if intersect:
            area = intersect - self.rect
            self.buffer = self.frames[self.nextFrame]
            if self.animate:
                self.tick += 1
                if self.tick == self.target:
                    self.tick = 0
                    self.currentFrame = self.nextFrame
                    self.nextFrame += 1
                    if self.nextFrame == len(self.frames):
                        self.nextFrame = 0
                self.updated = True
            return self.buffer[area.l:area.r, area.b:area.t]
        return None