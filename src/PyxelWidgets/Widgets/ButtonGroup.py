import PyxelWidgets.Widgets
import PyxelWidgets.Helpers
import numpy
import enum

class ButtonGroup(PyxelWidgets.Widgets.Widget):

    _count = 0

    class Type(enum.Enum):
        Button = enum.auto()
        Switch = enum.auto()
        Multi = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, **kwargs):
        kwargs['name'] = kwargs.get('name', f'ButtonGroup_{ButtonGroup._count}')
        self.state = numpy.ndarray((1, 1), dtype = numpy.bool8)
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        self.type = kwargs.get('type', ButtonGroup.Type.Switch)
        self.state.fill(False)
        self._oldButton = [-1, -1]
        if self.type == ButtonGroup.Type.Switch:
            self.state[0, 0] = True
            self._oldButton = [0, 0]
        ButtonGroup._count += 1
    
    def pressed(self, x: int, y: int, value: float):
        if self.type == ButtonGroup.Type.Button:
            self.state[x, y] = True
        if self.type == ButtonGroup.Type.Switch:
            self.state[self._oldButton[0], self._oldButton[1]] = False
            self._oldButton = [x, y]
            self.state[self._oldButton[0], self._oldButton[1]] = True
        if self.type == ButtonGroup.Type.Multi:
            self.state[x, y] = not self.state[x, y]
        self.updated = True
        super().pressed(x, y, value)
    
    def released(self, x: int, y: int, value: float):
        if self.type == ButtonGroup.Type.Button:
            self.state[x, y] = False
            self.updated = True
        super().released(x, y, value)

    def updateArea(self, rect: PyxelWidgets.Helpers.Rectangle2D) -> tuple:
        intersect = self.rect.intersect(rect)
        if intersect is not None:
            area = intersect - self.rect
            if self.bufferUpdated:
                self.bufferUpdated = False
                self.buffer[area.slice] = numpy.where(self.state[area.slice] == True, self.activeColor, self.deactiveColor)
                if self.effect is None:
                    return intersect, self.buffer[area.slice]
            if self.effect is not None:
                return intersect, self.effect.apply(self.buffer[area.slice])
        return None, None

    def _resize(self, width, height):
        self.state.resize((width, height), refcheck = False)
        return True