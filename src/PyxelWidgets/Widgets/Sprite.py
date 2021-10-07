from . import Widget, WidgetAreaNotValid
from ..Helpers import *
import numpy

class Sprite(Widget):
    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Sprite_{Sprite._count}')
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        self.animate = kwargs.get('animate', False)
        self.frames = kwargs.get('frames', None)
        self.currentFrame = 0
        if not isinstance(self.frames, numpy.ndarray):
            self.frames = [numpy.ndarray((self.rect.w, self.rect.h))]
            self.frames[0].fill(Colors.Invisible)
        self.buffer = self.frames[0]
    
    def updateArea(self, sx: int, sy: int, sw: int, sh: int):
        self.updated = False
        area = self.rect.origin.intersect(Rectangle2D(sx, sy, sw, sh))
        if area:
            self.buffer = self.frames[self.currentFrame]
            if self.animate:
                self.currentFrame += 1
                if self.currentFrame >= len(self.frames):
                    self.currentFrame = 0
                self.updated = True
            return self.buffer[area.l:area.r, area.b:area.t]
        raise WidgetAreaNotValid(self.rect, (sx, sy, sw, sh))