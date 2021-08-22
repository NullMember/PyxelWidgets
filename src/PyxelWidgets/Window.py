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

    def setCallback(self, callback):
        self._callback = callback

    def getValue(self, name: str) -> float:
        return self._widgets[name]['widget'].value

    def setValue(self, name: str, value: float):
        self._widgets[name]['widget'].value = value
    
    def addWidget(self, widget, x: int, y: int, priority = 1):
        self._widgets[widget.name] = {}
        self._widgets[widget.name]['widget'] = widget
        self._widgets[widget.name]['x'] = x
        self._widgets[widget.name]['y'] = y
        self._widgets[widget.name]['priority'] = priority
    
    def addWidgets(self, widgets: list):
        for widget in widgets:
            self._widgets[widget.name] = widget

    def getWidget(self, name):
        return self._widgets[name]
    
    def getWidgets(self):
        return list(self._widgets.values())

    def getWidgetNames(self) -> list:
        return list(self._widgets.keys())

    def setWidgetCallback(self, widget: str, callback) -> None:
        self._widgets[widget].setCallback(callback)

    def setWidgetCallbacks(self, callback) -> None:
        for widget in self._widgets.values():
            widget.setCallback(callback)

    def isCollide(self, x: int, y: int, widget):
        if x + self.x >= widget['x'] and \
           x + self.x < widget['x'] + widget['widget'].width and \
           y + self.y >= widget['y'] and \
           y + self.y < widget['y'] + widget['widget'].height:
            return True
        else:
            return False
    
    def forceUpdate(self):
        for widget in self._widgets.values():
            widget.forceUpdate()

    def process(self, event, data):
        x, y, value = data
        for widget in self._widgets.values():
            if self.isCollide(x, y, widget):
                if event == 'pressed':
                    widget['widget'].pressed(x - widget['x'] + self.x, y - widget['y'] + self.y, value)
                elif event == 'released':
                    widget['widget'].released(x - widget['x'] + self.x, y - widget['y'] + self.y, value)
                elif event == 'held':
                    widget['widget'].held(x - widget['x'] + self.x, y - widget['y'] + self.y, value)

    def update(self):
        for priority in range(4):
            for widget in self._widgets.values():
                if widget['priority'] == priority:
                    pixels = widget['widget'].update()
                    if pixels != []:
                        for y in range(widget['widget'].height):
                            for x in range(widget['widget'].width):
                                if pixels[x][y] != [-1, -1, -1]:
                                    self._pixels[x + widget['x']][y + widget['y']] = pixels[x][y]
        return self._pixels