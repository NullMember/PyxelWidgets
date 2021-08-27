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
        self._widgets[widget.name]['coordinates'] = []
        self._widgets[widget.name]['coordinates'].append((x, y))
    
    def cloneWidget(self, name: str, x: int, y: int):
        if name in self._widgets:
            if (x, y) not in self._widgets[name]['coordinates']:
                self._widgets[name]['coordinates'].append((x, y))
    
    def killWidget(self, name: str, x: int, y: int):
        if name in self._widgets:
            if len(self._widgets[name]['coordinates']) > 1:
                if (x, y) in self._widgets[name]['coordinates']:
                    self._widgets[name]['coordinates'].pop(self._widgets[name]['coordinates'].index((x, y)))

    def addWidgets(self, widgets: list):
        for widget in widgets:
            self._widgets[widget.name] = widget

    def setWidgetCallback(self, widget: str, callback) -> None:
        self._widgets[widget].setCallback(callback)

    def setWidgetCallbacks(self, callback) -> None:
        for widget in self._widgets.values():
            widget.setCallback(callback)

    def isCollide(self, sx: int, sy: int, dx, dy, width, height):
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
            for coordinate in widget['coordinates']:
                if self.isCollide(x, y, coordinate[0], coordinate[1], widget['widget'].width, widget['widget'].height):
                    if event == 'pressed':
                        widget['widget'].pressed(x - coordinate[0] + self.x, y - coordinate[1] + self.y, value)
                    elif event == 'released':
                        widget['widget'].released(x - coordinate[0] + self.x, y - coordinate[1] + self.y, value)
                    elif event == 'held':
                        widget['widget'].held(x - coordinate[0] + self.x, y - coordinate[1] + self.y, value)

    def update(self):
        for widget in self._widgets.values():
            pixels = widget['widget'].update()
            if pixels != []:
                for y in range(widget['widget'].height):
                    for x in range(widget['widget'].width):
                        if pixels[x][y] != [-1, -1, -1]:
                            for coordinate in widget['coordinates']:
                                self._pixels[x + coordinate[0]][y + coordinate[1]] = pixels[x][y]
        return self._pixels