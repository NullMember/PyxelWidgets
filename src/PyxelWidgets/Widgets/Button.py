from . import Widget
from enum import Enum

class ButtonMode(Enum):
    Button = 0
    Switch = 1
    Mixed = 2

class Button(Widget):
    def __init__(self, width: int, height: int, **kwargs):
        name = kwargs.get('name', 'Button_' + str(Button._count))
        super().__init__(name, width, height, **kwargs)
        self.mode = kwargs.get('mode', ButtonMode.Button)
        self.hold = False
        self.state = False
        Button._count += 1

    def pressed(self, x: int, y: int, value: float):
        if self.mode == ButtonMode.Button:
            self.value = value
        elif self.mode == ButtonMode.Switch:
            if self.state:
                self.value = 0.0
                self.state = False
            else:
                self.value = value
                self.state = True
        elif self.mode == ButtonMode.Mixed:
            if self.hold:
                return
            else:
                self.value = value
        super().pressed(x, y, self.value)
    
    def released(self, x: int, y: int, value: float):
        if self.mode == ButtonMode.Button:
            self.value = 0.0
        elif self.mode == ButtonMode.Switch:
            pass
        elif self.mode == ButtonMode.Mixed:
            if self.hold:
                return
            else:
                self.value = 0.0
        super().released(x, y, self.value)
    
    def held(self, x: int, y: int, value: float):
        if self.mode == ButtonMode.Mixed:
            self.hold = not self.hold
        super().held(x, y, self.value)

    def updateArea(self, sx, sy, sw, sh):
        if self._updated:
            self._updated = False
            ex = sx + sw
            ex = ex if ex < self.width else self.width
            ey = sy + sh
            ey = ey if ey < self.height else self.height
            for x in range(sx, ex):
                for y in range(sy, ey):
                    if self.value:
                        self._pixels[x][y] = [int(self._activeColor[0] * self.value), int(self._activeColor[1] * self.value), int(self._activeColor[2] * self.value)]
                    else:
                        self._pixels[x][y] = self._deactiveColor
            return self._pixels
        return []