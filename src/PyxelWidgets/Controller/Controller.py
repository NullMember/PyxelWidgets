from threading import Timer

class Controller():

    _count = 0

    def __init__(self, **kwargs):
        self._name = kwargs.get('name', 'Controller_' + str(Controller._count))
        self._width = kwargs.get('width', 1)
        self._height = kwargs.get('height', 1)
        self._heldTime = kwargs.get('heldTime', 1.0)
        self._connected = False
        self._pixels = [[[-1, -1, -1] for y in range(self.height)] for x in range(self.width)]
        self._buttons = [[0.0 for y in range(self.height)] for x in range(self.width)]
        self._timers = [[None for y in range(self.height)] for x in range(self.width)]
        self._callback = lambda *_, **__ : None
        Controller._count += 1
    
    @property
    def width(self):
        return self._width
    
    @property
    def height(self):
        return self._height

    def setCallback(self, callback):
        self._callback = callback

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False
    
    def getButton(self, x: int, y: int) -> float:
        return self._buttons[x][y]

    def setButton(self, x: int, y: int, value: float) -> None:
        self._buttons[x][y] = min(1.0, max(0.0, value))
        self.setState(x, y, bool(self._buttons[x][y]))
    
    def setState(self, x: int, y: int, state: bool) -> None:
        if state:
            self.setPressed(x, y)
        else:
            self.setReleased(x, y)
        return
    
    def setPressed(self, x: int, y: int) -> None:
        self._timers[x][y] = Timer(interval = self._heldTime, function = self.setHeld, args = (x, y))
        self._timers[x][y].start()
        self._callback('pressed', (x, y, self._buttons[x][y]))
    
    def setReleased(self, x: int, y: int) -> None:
        self._timers[x][y].cancel()
        self._callback('released', (x, y, self._buttons[x][y]))
    
    def setHeld(self, x: int, y: int) -> None:
        self._callback('held', (x, y, self._buttons[x][y]))

    def process(self):
        pass

    def processInput(self):
        pass

    def updateOne(self, pixel, x, y):
        pass

    def updateRow(self, pixels, y):
        pass

    def updateColumn(self, pixels, x):
        pass
    
    def updateArea(self, pixels, x, y, width, height):
        pass

    def updateAreaByArea(self, sx, sy, dx, dy, width, height, pixels):
        pass

    def update(self, x, y, width, height, pixels):
        pass