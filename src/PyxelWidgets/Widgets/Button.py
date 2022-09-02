import PyxelWidgets.Widgets
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import enum

class Button(PyxelWidgets.Widgets.Widget):

    class Mode(enum.Enum):
        Button  = enum.auto()
        Switch  = enum.auto()
        Mixed   = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Button_{Button._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.mode = kwargs.get('mode', Button.Mode.Button)
        self.state = False
        self.isHold = False
        Button._count += 1

    def press(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Button:
            self.setValue(value)
        elif self.mode == Button.Mode.Switch:
            if self.state:
                self.setValue(0.0)
                self.state = False
            else:
                self.setValue(value)
                self.state = True
        elif self.mode == Button.Mode.Mixed:
            if self.isHold:
                return
            else:
                self.setValue(value)
    
    def release(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Button:
            self.setValue(0.0)
        elif self.mode == Button.Mode.Switch:
            pass
        elif self.mode == Button.Mode.Mixed:
            if self.isHold:
                return
            else:
                self.setValue(0.0)
    
    def hold(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Mixed:
            self.isHold = not self.isHold

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                self.buffer[area.slice].fill(self.activeColor * self._value if self._value else self.deactiveColor)
                return intersect, self.buffer[area.slice]
        return None, None