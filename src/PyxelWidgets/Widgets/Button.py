import PyxelWidgets.Widgets
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import enum

class Button(PyxelWidgets.Widgets.Widget):

    class Type(enum.Enum):
        Button  = enum.auto()
        Switch  = enum.auto()
        Mixed   = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Button_{Button._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.mode = kwargs.get('mode', Button.Type.Button)
        self.state = False
        self.isHold = False
        Button._count += 1

    def press(self, x: int, y: int, value: float):
        if self.mode == Button.Type.Button:
            self.setValue(value)
        elif self.mode == Button.Type.Switch:
            if self.state:
                self.setValue(0.0)
                self.state = False
            else:
                self.setValue(value)
                self.state = True
        elif self.mode == Button.Type.Mixed:
            if self.isHold:
                return
            else:
                self.setValue(value)
    
    def release(self, x: int, y: int, value: float):
        if self.mode == Button.Type.Button:
            self.setValue(0.0)
        elif self.mode == Button.Type.Switch:
            pass
        elif self.mode == Button.Type.Mixed:
            if self.isHold:
                return
            else:
                self.setValue(0.0)
    
    def hold(self, x: int, y: int, value: float):
        if self.mode == Button.Type.Mixed:
            self.isHold = not self.isHold

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        intersect = self.rect.intersect(rect)
        if intersect is not None:
            area = intersect - self.rect
            if self.bufferUpdated:
                self.bufferUpdated = False
                self.buffer[area.slice].fill(self.activeColor * self._value if self._value else self.deactiveColor)
                if self.effect is None:
                    return intersect, self.buffer[area.slice]
            if self.effect is not None:
                return intersect, self.effect.apply(self.buffer[area.slice])
        return None, None