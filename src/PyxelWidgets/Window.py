from .Helpers import *

class Window():

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', 'Window_' + str(Window._count))
        self.rect = Rectangle2D(0, 0, width, height)
        self.widgets = {}
        self.buffer = [[[0, 0, 0] for y in range(self.rect.h)] for x in range(self.rect.w)]
        self._callback = lambda *_, **__: None
        Window._count += 1

    @property
    def x(self) -> int:
        return self.rect.x
    
    @x.setter
    def x(self, scroll: int) -> None:
        self.rect.x = max(0, min(self.rect.w, scroll))
        self.forceUpdate()

    @property
    def y(self) -> int:
        return self.rect.y
    
    @y.setter
    def y(self, scroll: int) -> None:
        self.rect.y = max(0, min(self.rect.h, scroll))
        self.forceUpdate()

    def addWidget(self, widget, x: int, y: int):
        self.widgets[widget.name] = {}
        self.widgets[widget.name]['widget'] = widget
        self.widgets[widget.name]['x'] = x
        self.widgets[widget.name]['y'] = y
    
    def forceUpdate(self):
        for widget in self.widgets.values():
            widget['widget']._updated = True

    def process(self, event, data):
        x, y, value = data
        for widget in self.widgets.values():
            b = Rectangle2D(x, y)
            w = Rectangle2D(widget['x'], widget['y'], widget['widget'].width, widget['widget'].height) - self.rect
            if b.collide(w):
                if event == 'pressed':
                    widget['widget'].pressed(b.x - w.x, b.y - w.y, value)
                elif event == 'released':
                    widget['widget'].released(b.x - w.x, b.y - w.y, value)
                elif event == 'held':
                    widget['widget'].held(b.x - w.x, b.y - w.y, value)

    def update(self):
        for widget in self.widgets.values():
            if widget.updated:
                pixels = widget['widget'].updateArea(0, 0, self.rect.w, self.rect.h)
                if pixels != []:
                    for x in range(widget['widget'].width):
                        for y in range(widget['widget'].height):
                            if pixels[x][y] != [-1, -1, -1]:
                                try:
                                    self.buffer[x + widget['x']][y + widget['y']] = pixels[x][y]
                                except:
                                    break
        return self.buffer