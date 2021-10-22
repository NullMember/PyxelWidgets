from . import Widget
from ..Helpers import *
from enum import Enum, auto

class ButtonMode(Enum):
    Button  = auto()
    Switch  = auto()
    Mixed   = auto()

class Button(Widget):
    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Button_{Button._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.mode = kwargs.get('mode', ButtonMode.Button)
        self.hold = False
        self.state = False
        Button._count += 1

    def pressed(self, x: int, y: int, value: float):
        super().pressed(x, y, value)
        if self.mode == ButtonMode.Button:
            self.setValue(value)
        elif self.mode == ButtonMode.Switch:
            if self.state:
                self.setValue(0.0)
                self.state = False
            else:
                self.setValue(value)
                self.state = True
        elif self.mode == ButtonMode.Mixed:
            if self.hold:
                return
            else:
                self.setValue(value)
        
    
    def released(self, x: int, y: int, value: float):
        super().released(x, y, value)
        if self.mode == ButtonMode.Button:
            self.setValue(0.0)
        elif self.mode == ButtonMode.Switch:
            pass
        elif self.mode == ButtonMode.Mixed:
            if self.hold:
                return
            else:
                self.setValue(0.0)
    
    def held(self, x: int, y: int, value: float):
        super().held(x, y, value)
        if self.mode == ButtonMode.Mixed:
            self.hold = not self.hold

    def updateArea(self, sx, sy, sw, sh):
        self.updated = False
        intersect = self.rect.intersect(Rectangle2D(sx, sy, sw, sh))
        if intersect:
            area = intersect - self.rect
            for x in area.columns:
                for y in area.rows:
                    if self.value:
                        self.buffer[x, y] = self.activeColor * self.value
                    else:
                        self.buffer[x, y] = self.deactiveColor
            return self.buffer[area.l:area.r, area.b:area.t]
        return None