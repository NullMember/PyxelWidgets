from . import Widget
from ..Helpers import *
from enum import Enum

class XYDirection(Enum):
    Vertical = 0
    Horizontal = 1

class XY(Widget):
    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'XY_{XY._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.xColor = kwargs.get('xColor', Colors.Cyan)
        self.yColor = kwargs.get('yColor', Colors.Magenta)
        self.delta = [0.0, 0.0]
        self._value = [0.0, 0.0]
        self._heldButton = [-1, -1]
        XY._count += 1
    
    @Widget.value.setter
    def value(self, value: list) -> None:
        if value != self._value:
            oldValue = [self._value[0], self._value[1]]
            self._value[0] = round(min(1.0, max(0.0, value[0])), 6)
            self._value[1] = round(min(1.0, max(0.0, value[1])), 6)
            self.delta[0] = self._value[0] - oldValue[0]
            self.delta[1] = self._value[1] - oldValue[1]
            if self._value != oldValue:
                self.updated = True
                self._callback(self.name, 'changed', self._value)

    def pressed(self, x: int, y: int, value: float):
        if self._heldButton[0] >= 0 and self._heldButton[1] >= 0:
            self.value = self._calcXYValueWithMagnitude(self._heldButton[0], self._heldButton[1], x, y)
        else:
            self.value = self._calcXYValue(x, y, value)
        super().pressed(x, y, value)
    
    def held(self, x: int, y: int, value: float):
        if self._heldButton[0] == -1 and self._heldButton[1] == -1:
            self._heldButton = [x, y]
            self.value = self._calcXYValueWithMagnitude(x, y, x, y)
        super().held(x, y, value)
    
    def released(self, x: int, y: int, value: float):
        if self._heldButton[0] == x and self._heldButton[1] == y:
            self._heldButton = [-1, -1]
        super().released(x, y, value)

    def updateArea(self, sx, sy, sw, sh):
        self.updated = False
        area = self.rect.origin.intersect(Rectangle2D(sx, sy, sw, sh))
        for x in area.columns:
            for y in area.rows:
                minV = self._calcXYValue(x, y, 0.0)
                maxV = self._calcXYValue(x, y, 1.0)
                # junction point
                # if current padx is last pressed pad and current pady is last pressed pad
                if minV[0] < self.value[0] and maxV[0] >= self.value[0] and minV[1] < self.value[1] and maxV[1] >= self.value[1]:
                    coefficientX = ((self.value[0] - minV[0]) * self.rect.w) / 2
                    coefficientY = ((self.value[1] - minV[1]) * self.rect.h) / 2
                    color = (self.xColor * coefficientX) + (self.yColor * coefficientY)
                    self.buffer[x, y] = color
                # x axis
                # if current padx is in same column of last pressed pad
                elif minV[0] < self.value[0] and maxV[0] >= self.value[0]:
                    self.buffer[x, y] = self.xColor * self.value[0]
                # y axis
                # if current pady is in same row of last pressed pad
                elif minV[1] < self.value[1] and maxV[1] >= self.value[1]:
                    self.buffer[x, y] = self.yColor * self.value[1]
                # unlit every other pad
                else:
                    self.buffer[x, y] = self.deactiveColor
        return self.buffer[area.l:area.r, area.b:area.t]

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