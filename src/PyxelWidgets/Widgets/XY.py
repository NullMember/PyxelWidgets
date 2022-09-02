import PyxelWidgets.Widgets
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import enum

class XY(PyxelWidgets.Widgets.Widget):

    class Direction(enum.Enum):
        Vertical    = enum.auto()
        Horizontal  = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'XY_{XY._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.xColor = kwargs.get('xColor', PyxelWidgets.Utils.Pixel.Colors.Cyan)
        self.yColor = kwargs.get('yColor', PyxelWidgets.Utils.Pixel.Colors.Magenta)
        self.delta = [0.0, 0.0]
        self._value = [0.0, 0.0]
        self._heldButton = [-1, -1]
        XY._count += 1
    
    @PyxelWidgets.Widgets.Widget.value.setter
    def value(self, value: list) -> None:
        if value != self._value:
            oldValue = [self._value[0], self._value[1]]
            self._value[0] = round(min(1.0, max(0.0, value[0])), 6)
            self._value[1] = round(min(1.0, max(0.0, value[1])), 6)
            self.delta[0] = self._value[0] - oldValue[0]
            self.delta[1] = self._value[1] - oldValue[1]
            if self._value != oldValue:
                self.updated = True

    def press(self, x: int, y: int, value: float):
        if self._heldButton[0] >= 0 and self._heldButton[1] >= 0:
            self.setValue(self._calcXYValueWithMagnitude(self._heldButton[0], self._heldButton[1], x, y))
        else:
            self.setValue(self._calcXYValue(x, y, value))
    
    def hold(self, x: int, y: int, value: float):
        if self._heldButton[0] == -1 and self._heldButton[1] == -1:
            self._heldButton = [x, y]
            self.setValue(self._calcXYValueWithMagnitude(x, y, x, y))
    
    def release(self, x: int, y: int, value: float):
        if self._heldButton[0] == x and self._heldButton[1] == y:
            self._heldButton = [-1, -1]

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                xPoint = self._findXPoint()
                yPoint = self._findYPoint()
                self.buffer[area.slice] = self.deactiveColor
                self.buffer[xPoint, area.slice[1]] = self.xColor * self._value[0]
                self.buffer[area.slice[0], yPoint] = self.yColor * self._value[1]
                minV = self._minV[xPoint][yPoint]
                coefficientX = ((self.value[0] - minV[0]) * self.rect.w) / 2
                coefficientY = ((self.value[1] - minV[1]) * self.rect.h) / 2
                color = (self.xColor * coefficientX) + (self.yColor * coefficientY)
                self.buffer[xPoint, yPoint] = color
            return intersect, self.buffer[area.slice]
        return None, None

    def _resize(self, width, height) -> bool:
        self._minV = [[self._calcXYValue(x, y, 0.0) for y in range(height)] for x in range(width)]
        self._maxV = [[self._calcXYValue(x, y, 1.0) for y in range(height)] for x in range(width)]
        return True

    def _findXPoint(self):
        point = (self._value[0] * self.rect.w)
        if point > 0.0:
            point = point - 1 if point % 1.0 == 0.0 else point
        return int(point)
    
    def _findYPoint(self):
        point = (self._value[1] * self.rect.h)
        if point > 0.0:
            point = point - 1 if point % 1.0 == 0.0 else point
        return int(point)

    def _calcXValue(self, x: int, value: float) -> float:
        return round(((x / self.rect.w) + (value / self.rect.w)), 6)
    
    def _calcYValue(self, y: int, value: float) -> float:
        return round(((y / self.rect.h) + (value / self.rect.h)), 6)

    def _calcXYValue(self, x: int, y: int, value: float):
        return [self._calcXValue(x, value), self._calcYValue(y, value)]
    
    def _calcXMagnitude(self, x: int) -> float:
        return self._calcXValue(x, (x + 1) / self.rect.w)
    
    def _calcYMagnitude(self, y: int) -> float:
        return self._calcYValue(y, (y + 1) / self.rect.h)

    def _calcXYMagnitude(self, x: int, y: int):
        return [self._calcXMagnitude(x), self._calcYMagnitude(y)]
    
    def _calcXYValueWithMagnitude(self, valX: int, valY: int, magX: int, magY: int):
        return [self._calcXValue(valX, self._calcXMagnitude(magX)), self._calcYValue(valY, self._calcYMagnitude(magY))]