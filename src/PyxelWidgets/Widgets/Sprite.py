import PyxelWidgets.Widgets
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import numpy

class Sprite(PyxelWidgets.Widgets.Widget):
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
            self.frames[0].fill(PyxelWidgets.Utils.Pixel.Colors.Invisible)
        self.buffer = self.frames[0]

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        self.updated = False
        intersect = self.rect.intersect(rect)
        if intersect is not None:
            area = intersect - self.rect
            if self.bufferUpdated:
                self.bufferUpdated = False
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
                if self.effect is None:
                    return intersect, self.buffer[area.slice]
            if self.effect is not None:
                return intersect, self.effect.apply(self.buffer[area.slice])
        return None, None