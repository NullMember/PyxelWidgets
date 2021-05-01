class Controller():
    def __init__(self, **kwargs):
        self._width = kwargs.get('width', 1)
        self._height = kwargs.get('height', 1)
        self._connected = False
        self._pixels = [[[-1, -1, -1] for y in range(self.height)] for x in range(self.width)]
        self._callback = lambda *_, **__ : None
    
    @property
    def width(self):
        return self._width
    
    @property
    def height(self):
        return self._height

    def setCallback(self, callback):
        self._callback = callback

    def init(self):
        self._connected = True

    def deinit(self):
        self._connected = False

    def process(self):
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