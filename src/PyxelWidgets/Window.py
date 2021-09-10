from .Helpers import *
import numpy
class Window():

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', 'Window_' + str(Window._count))
        self.rect = Rectangle2D(0, 0, width, height)
        self.widgets = {}
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), Pixel)
        self.buffer.fill(Colors.Invisible)
        self._callback = lambda *_, **__: None
        Window._count += 1

    @property
    def x(self) -> int:
        return self.rect.x
    
    @x.setter
    def x(self, value: int) -> None:
        self.rect.x = min(self.rect.w, max(0, value))
        self.buffer[self.rect.l:self.rect.r, self.rect.b:self.rect.t].fill(Colors.Invisible)
        self.forceUpdate()

    @property
    def y(self) -> int:
        return self.rect.y
    
    @y.setter
    def y(self, value: int) -> None:
        self.rect.y = min(self.rect.h, max(0, value))
        self.buffer[self.rect.l:self.rect.r, self.rect.b:self.rect.t].fill(Colors.Invisible)
        self.forceUpdate()

    def addWidget(self, widget):
        self.widgets[widget.name] = widget
    
    def forceUpdate(self):
        for widget in self.widgets.values():
            widget.updated = True

    def process(self, event, data):
        x, y, value = data
        for widget in self.widgets.values():
            b = Rectangle2D(x, y)
            w = widget.rect - self.rect
            if b.collide(w):
                if event == 'pressed':
                    widget.pressed(b.x - w.x, b.y - w.y, value)
                elif event == 'released':
                    widget.released(b.x - w.x, b.y - w.y, value)
                elif event == 'held':
                    widget.held(b.x - w.x, b.y - w.y, value)

    def update(self):
        for widget in self.widgets.values():
            if widget.updated:
                intersect = self.rect.intersect(widget.rect)
                if intersect:
                    update = intersect - widget.rect
                    buffer = widget.updateArea(update.x, update.y, update.w, update.h)
                    copy = intersect - self.rect
                    view = self.buffer[copy.l:copy.r, copy.b:copy.t]
                    view[:] = numpy.where(buffer == False, view, buffer)
        return self.buffer