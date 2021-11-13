import PyxelWidgets.Widgets
import PyxelWidgets.Helpers
import enum

class Button(PyxelWidgets.Widgets.Widget):

    class ButtonMode(enum.Enum):
        Button  = enum.auto()
        Switch  = enum.auto()
        Mixed   = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Button_{Button._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.mode = kwargs.get('mode', Button.ButtonMode.Button)
        self.hold = False
        self.state = False
        Button._count += 1

    def pressed(self, x: int, y: int, value: float):
        super().pressed(x, y, value)
        if self.mode == Button.ButtonMode.Button:
            self.setValue(value)
        elif self.mode == Button.ButtonMode.Switch:
            if self.state:
                self.setValue(0.0)
                self.state = False
            else:
                self.setValue(value)
                self.state = True
        elif self.mode == Button.ButtonMode.Mixed:
            if self.hold:
                return
            else:
                self.setValue(value)
        
    
    def released(self, x: int, y: int, value: float):
        super().released(x, y, value)
        if self.mode == Button.ButtonMode.Button:
            self.setValue(0.0)
        elif self.mode == Button.ButtonMode.Switch:
            pass
        elif self.mode == Button.ButtonMode.Mixed:
            if self.hold:
                return
            else:
                self.setValue(0.0)
    
    def held(self, x: int, y: int, value: float):
        super().held(x, y, value)
        if self.mode == Button.ButtonMode.Mixed:
            self.hold = not self.hold

    def updateArea(self, rect: PyxelWidgets.Helpers.Rectangle2D):
        self.updated = False
        intersect = self.rect.intersect(rect)
        if intersect:
            area = intersect - self.rect
            for x in area.columns:
                for y in area.rows:
                    if self._value:
                        self.buffer[x, y] = self.activeColor * self._value
                    else:
                        self.buffer[x, y] = self.deactiveColor
            return intersect, self.buffer[area.slice]
        return None