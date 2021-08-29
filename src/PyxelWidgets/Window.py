from threading import Thread
import time

class Window():
    def __init__(self, name: str, width: int, height: int, **kwargs):
        self._name = name
        self._width = max(1, width)
        self._height = max(1, height)
        self._pixels = [[[0, 0, 0] for y in range(self.height)] for x in range(self.width)]
        self._x = 0
        self._y = 0
        self._forceUpdate = False
        self._widgets = {}
        self._hold = {}
        self._callback = lambda *_, **__: None
    
    @property
    def name(self) -> str:
        return self._name

    @property
    def width(self) -> int:
        return self._width
    
    @property
    def height(self) -> int:
        return self._height

    @property
    def x(self) -> int:
        return self._x
    
    @x.setter
    def x(self, scroll: int) -> None:
        self._x = max(0, min(self.width, scroll))
        for hold in self._hold:
            self._widgets[hold].x = self._hold[hold]['x'] + self.x
        self.forceUpdate()

    @property
    def y(self) -> int:
        return self._y
    
    @y.setter
    def y(self, scroll: int) -> None:
        self._y = max(0, min(self.height, scroll))
        for hold in self._hold:
            self._widgets[hold].y = self._hold[hold]['y'] + self.y
        self.forceUpdate()
    
    @property
    def widgets(self) -> dict:
        return self._widgets

    def setCallback(self, callback):
        self._callback = callback

    def getValue(self, name: str) -> float:
        return self._widgets[name]['widget'].value

    def setValue(self, name: str, value: float):
        self._widgets[name]['widget'].value = value
    
    def addWidget(self, widget, x: int, y: int):
        self._widgets[widget.name] = {}
        self._widgets[widget.name]['widget'] = widget
        self._widgets[widget.name]['x'] = x
        self._widgets[widget.name]['y'] = y

    def addWidgets(self, widgets: list):
        for widget in widgets:
            self._widgets[widget.name] = widget

    def setWidgetCallback(self, widget: str, callback) -> None:
        self._widgets[widget].setCallback(callback)

    def setWidgetCallbacks(self, callback) -> None:
        for widget in self._widgets.values():
            widget.setCallback(callback)

    def isCollide(self, sx: int, sy: int, dx: int, dy: int, width: int, height: int) -> bool:
        if sx + self.x >= dx and \
        sx + self.x < dx + width and \
        sy + self.y >= dy and \
        sy + self.y < dy + height:
            return True
        else:
            return False
    
    def forceUpdate(self):
        for widget in self._widgets.values():
            widget.forceUpdate()

    def process(self, event, data):
        x, y, value = data
        for widget in self._widgets.values():
            wx = widget['x']
            wy = widget['y']
            ww = widget['widget'].width
            wh = widget['widget'].height
            if self.isCollide(x, y, wx, wy, ww, wh):
                if event == 'pressed':
                    widget['widget'].pressed(x - wx + self.x, y - wy + self.y, value)
                elif event == 'released':
                    widget['widget'].released(x - wx + self.x, y - wy + self.y, value)
                elif event == 'held':
                    widget['widget'].held(x - wx + self.x, y - wy + self.y, value)

    def update(self):
        for widget in self._widgets.values():
            pixels = widget['widget'].updateArea(0, 0, self.width, self.height)
            if pixels != []:
                for x in range(widget['widget'].width):
                    for y in range(widget['widget'].height):
                        if pixels[x][y] != [-1, -1, -1]:
                            try:
                                self._pixels[x + widget['x']][y + widget['y']] = pixels[x][y]
                            except:
                                break
        return self._pixels