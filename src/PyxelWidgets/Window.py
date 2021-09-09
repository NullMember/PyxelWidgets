class Window():

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', 'Window_' + str(Window._count))
        self.x = 0
        self.y = 0
        self.width = max(1, width)
        self.height = max(1, height)
        self.widgets = {}
        self.buffer = [[[0, 0, 0] for y in range(self.height)] for x in range(self.width)]
        self._callback = lambda *_, **__: None
        Window._count += 1

    @property
    def x(self) -> int:
        return self.x
    
    @x.setter
    def x(self, scroll: int) -> None:
        self.x = max(0, min(self.width, scroll))
        self.forceUpdate()

    @property
    def y(self) -> int:
        return self.y
    
    @y.setter
    def y(self, scroll: int) -> None:
        self.y = max(0, min(self.height, scroll))
        self.forceUpdate()
    
    def addWidget(self, widget, x: int, y: int):
        self.widgets[widget.name] = {}
        self.widgets[widget.name]['widget'] = widget
        self.widgets[widget.name]['x'] = x
        self.widgets[widget.name]['y'] = y

    def _isCollide(self, sx: int, sy: int, dx: int, dy: int, width: int, height: int) -> bool:
        if sx + self.x >= dx and \
        sx + self.x < dx + width and \
        sy + self.y >= dy and \
        sy + self.y < dy + height:
            return True
        else:
            return False
    
    def forceUpdate(self):
        for widget in self.widgets.values():
            widget['widget']._updated = True

    def process(self, event, data):
        x, y, value = data
        for widget in self.widgets.values():
            wx = widget['x']
            wy = widget['y']
            ww = widget['widget'].width
            wh = widget['widget'].height
            if self._isCollide(x, y, wx, wy, ww, wh):
                if event == 'pressed':
                    widget['widget'].pressed(x - wx + self.x, y - wy + self.y, value)
                elif event == 'released':
                    widget['widget'].released(x - wx + self.x, y - wy + self.y, value)
                elif event == 'held':
                    widget['widget'].held(x - wx + self.x, y - wy + self.y, value)

    def update(self):
        for widget in self.widgets.values():
            pixels = widget['widget'].updateArea(0, 0, self.width, self.height)
            if pixels != []:
                for x in range(widget['widget'].width):
                    for y in range(widget['widget'].height):
                        if pixels[x][y] != [-1, -1, -1]:
                            try:
                                self.buffer[x + widget['x']][y + widget['y']] = pixels[x][y]
                            except:
                                break
        return self.buffer