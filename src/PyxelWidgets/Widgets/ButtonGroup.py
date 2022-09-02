import PyxelWidgets.Widgets
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import numpy
import enum

class ButtonGroup(PyxelWidgets.Widgets.Widget):

    class Mode(enum.Enum):
        Button = enum.auto()
        Switch = enum.auto()
        Multi = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, **kwargs):
        kwargs['name'] = kwargs.get('name', f'ButtonGroup_{ButtonGroup._count}')
        self.state = numpy.ndarray((1, 1), dtype = numpy.bool8)
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        self.mode = kwargs.get('mode', ButtonGroup.Mode.Switch)
        self.state.fill(False)
        self._oldButton = [-1, -1]
        if self.mode == ButtonGroup.Mode.Switch:
            self.state[0, 0] = True
            self._oldButton = [0, 0]
        ButtonGroup._count += 1

    def press(self, x: int, y: int, value: float):
        if self.mode == ButtonGroup.Mode.Button:
            self.state[x, y] = True
        if self.mode == ButtonGroup.Mode.Switch:
            self.state[self._oldButton[0], self._oldButton[1]] = False
            self._oldButton = [x, y]
            self.state[self._oldButton[0], self._oldButton[1]] = True
        if self.mode == ButtonGroup.Mode.Multi:
            self.state[x, y] = not self.state[x, y]
        self.updated = True
    
    def release(self, x: int, y: int, value: float):
        if self.mode == ButtonGroup.Mode.Button:
            self.state[x, y] = False
            self.updated = True

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D) -> tuple:
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                self.buffer[area.slice] = numpy.where(self.state[area.slice] == True, self.activeColor, self.deactiveColor)
                return intersect, self.buffer[area.slice]
        return None, None

    def _resize(self, width, height):
        self.state.resize((width, height), refcheck = False)
        return True