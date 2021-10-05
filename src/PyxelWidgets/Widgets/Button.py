from . import Widget
from ..Helpers import *
from enum import Enum

class ButtonMode(Enum):
    Button = 0
    Switch = 1
    Mixed = 2

class Button(Widget):
    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Button_{Button._count}')
        super().__init__(x, y, width, height, **kwargs)
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
        self.updated = False
        area = self.rect.origin.intersect(Rectangle2D(sx, sy, sw, sh))
        for x in area.columns:
            for y in area.rows:
                if self.value:
                    self.buffer[x, y] = self.activeColor * self.value
                else:
                    self.buffer[x, y] = self.deactiveColor
        return self.buffer[area.l:area.r, area.b:area.t]