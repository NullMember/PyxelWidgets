from threading import Thread
import time

class Window():
    
    def __init__(self, name: str, width: int, height: int, **kwargs):
        self._name = name
        self._width = max(1, width)
        self._height = max(1, height)
        self._heldTime = kwargs.get('heldTime', 1.0)
        self._frameTarget = kwargs.get('frameTarget', 60)
        self._run = False
        self._pixels = [[[0, 0, 0] for y in range(self.height * 2)] for x in range(self.width * 2)]
        self._buttons = [[0.0 for y in range(self.height)] for x in range(self.width)]
        self._states = [[False for y in range(self.height)] for x in range(self.width)]
        self._pressed = [[False for y in range(self.height)] for x in range(self.width)]
        self._released = [[False for y in range(self.height)] for x in range(self.width)]
        self._held = [[False for y in range(self.height)] for x in range(self.width)]
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

    def run(self):
        self._run = True
        self._updateRunner = Thread(None, self.update)
        self._updateRunner.start()
    
    def stop(self):
        self._run = False

    def setCallback(self, callback):
        self._callback = callback

    def getPixel(self, x: int, y: int) -> list:
        return self._pixels[x][y]

    def setPixel(self, x: int, y: int, color: list) -> None:
        self._pixels[x][y] = color
        return
    
    def getPixels(self, x: int, y: int, width: int, height: int) -> list:
        result = self._pixels[x:x+width]
        for _x in range(len(result)):
            result[_x] = result[_x][y:y+height]
        return result
    
    def setPixels(self, x: int, y: int, width: int, height: int, colors: list) -> None:
        for _x in range(width):
            for _y in range(height):
                self._pixels[_x+x][_y+y] = colors[_x][_y]
        return
    
    def getScreen(self):
        return self._pixels

    def resetPixels(self):
        self._pixels = [[[0, 0, 0] for y in range(self.height * 2)] for x in range(self.width * 2)]
    
    def getButton(self, x: int, y: int) -> float:
        return self._buttons[x][y]

    def setButton(self, x: int, y: int, value: float) -> None:
        if value < 0.0:
            self._buttons[x][y] = 0.0
        elif value > 1.0:
            self._buttons[x][y] = 1.0
        else:
            self._buttons[x][y] = value
        if self._buttons[x][y]:
            self.setState(x, y, True)
        else:
            self.setState(x, y, False)
        return
    
    def getState(self, x: int, y: int) -> bool:
        return self._states[x][y]
    
    def setState(self, x: int, y: int, state: bool) -> None:
        self._states[x][y] = state
        if state:
            self.setPressed(x, y)
        else:
            self.setReleased(x, y)
        return
    
    def getPressed(self, x: int, y: int) -> bool:
        if self._pressed[x][y]:
            self._pressed[x][y] = False
            return True
        else:
            return False
    
    def setPressed(self, x: int, y: int) -> None:
        self._pressed[x][y] = True
        return
    
    def getReleased(self, x: int, y: int) -> bool:
        if self._released[x][y]:
            self._released[x][y] = False
            return True
        else:
            return False
    
    def setReleased(self, x: int, y: int) -> None:
        self._released[x][y] = True
        return
    
    def getHeld(self, x: int, y: int) -> bool:
        if self._held[x][y]:
            self._held[x][y] = False
            return True
        else:
            return False
    
    def setHeld(self, x: int, y: int) -> None:
        self._held[x][y] = True
        return

    def getValue(self, name: str) -> float:
        return self._widgets[name].value

    def setValue(self, name: str, value: float):
        self._widgets[name].value = value
    
    def addWidget(self, widget):
        self._widgets[widget.name] = widget
    
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

    def is_collide(self, x: int, y: int, widget):
        if x + self.x >= widget.x and \
           x + self.x < widget.x + widget.width and \
           y + self.y >= widget.y and \
           y + self.y < widget.y + widget.height:
            return True
        else:
            return False
    
    def forceUpdate(self):
        for widget in self._widgets.values():
            widget.forceUpdate()
        self.resetPixels()

    def update(self):
        pressedTime = [[0 for y in range(self.height)] for x in range(self.width)]
        oldState = [[False for y in range(self.height)] for x in range(self.width)]
        while self._run:
            currentTime = time.time()
            for y in range(self.height):
                for x in range(self.width):
                    # Update held state
                    if self._states[x][y] != oldState[x][y]:
                        if self._states[x][y]:
                            pressedTime[x][y] = currentTime
                            oldState[x][y] = self._states[x][y]
                        else:
                            pressedTime[x][y] = 0
                            oldState[x][y] = self._states[x][y]
                    if pressedTime[x][y] > 0:
                        if currentTime >= pressedTime[x][y] + self._heldTime:
                            self.setHeld(x, y)
                            pressedTime[x][y] = 0
                    # Button was pressed
                    if self.getPressed(x, y):
                        for widget in self._widgets.values():
                            if self.is_collide(x, y, widget):
                                widget.pressed(x - widget.x + self.x, y - widget.y + self.y, self._buttons[x][y])
                    # Button was released
                    if self.getReleased(x, y):
                        for widget in self._widgets.values():
                            if self.is_collide(x, y, widget):
                                widget.released(x - widget.x + self.x, y - widget.y + self.y)
                    # Button was held
                    if self.getHeld(x, y):
                        for widget in self._widgets.values():
                            if self.is_collide(x, y, widget):
                                widget.held(x - widget.x + self.x, y - widget.y + self.y)
            # Update pixels from updated widgets
            for widget in self._widgets.values():
                pixels = widget.update()
                if pixels != []:
                    self.setPixels(widget.x, widget.y, widget.width, widget.height, pixels)
            # Send pixels to controller
            # self._callback([[self._pixels\
            #                [x + self.x]\
            #                [y + self.y]\
            #                for y in range(self.height)]\
            #                for x in range(self.width)])
            self._callback(self._pixels)
            time.sleep(1.0 / self._frameTarget)
