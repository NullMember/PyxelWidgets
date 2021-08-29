from .Widget import Widget
from enum import Enum

class XYDirection(Enum):
    Vertical = 0
    Horizontal = 1

class XY(Widget):
    def __init__(self, width: int, height: int, **kwargs):
        name = kwargs.get('name', 'Fader_' + str(XY._count))
        super().__init__(name, width, height, **kwargs)
        self._value = [0.0, 0.0]
        self._xColor = kwargs.get('xColor', [0, 255, 255])
        self._yColor = kwargs.get('yColor', [255, 0, 255])
        self._heldButton = [-1, -1]
        XY._count += 1
    
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
        if self._updated:
            self._updated = False
            ex = sx + sw
            ex = ex if ex < self.width else self.width
            ey = sy + sh
            ey = ey if ey < self.height else self.height
            for x in range(sx, ex):
                for y in range(sy, ey):
                    minV = self._calcXYValue(x, y, 0.0)
                    maxV = self._calcXYValue(x, y, 1.0)
                    # junction point
                    # if current padx is last pressed pad and current pady is last pressed pad
                    if minV[0] < self.value[0] and maxV[0] >= self.value[0] and minV[1] < self.value[1] and maxV[1] >= self.value[1]:
                        coefficientX = (self.value[0] - minV[0]) * self.width
                        coefficientY = (self.value[1] - minV[1]) * self.height
                        r = ((self._xColor[0] * coefficientX) + (self._yColor[0] * coefficientY)) / 2
                        g = ((self._xColor[1] * coefficientX) + (self._yColor[1] * coefficientY)) / 2
                        b = ((self._xColor[2] * coefficientX) + (self._yColor[2] * coefficientY)) / 2
                        self._pixels[x][y] = [int(r), int(g), int(b)]
                    # x axis
                    # if current padx is in same column of last pressed pad
                    elif minV[0] < self.value[0] and maxV[0] >= self.value[0]:
                        self._pixels[x][y] = [int(self._xColor[0] * self.value[0]), int(self._xColor[1] * self.value[0]), int(self._xColor[2] * self.value[0])]
                    # y axis
                    # if current pady is in same row of last pressed pad
                    elif minV[1] < self.value[1] and maxV[1] >= self.value[1]:
                        self._pixels[x][y] = [int(self._yColor[0] * self.value[1]), int(self._yColor[1] * self.value[1]), int(self._yColor[2] * self.value[1])]
                    # unlit every other pad
                    else:
                        self._pixels[x][y] = self._deactiveColor
            return self._pixels
        return []

    def _calcXValue(self, x: int, value: float) -> float:
        return round(((x / self.width) + (value / self.width)), 6)
    
    def _calcYValue(self, y: int, value: float) -> float:
        return round(((y / self.height) + (value / self.height)), 6)

    def _calcXYValue(self, x: int, y: int, value: float):
        return [self._calcXValue(x, value), self._calcYValue(y, value)]
    
    def _calcXMagnitude(self, x: int) -> float:
        return self._calcXValue(x, (x + 1) / self.width)
    
    def _calcYMagnitude(self, y: int) -> float:
        return self._calcYValue(y, (y + 1) / self.height)

    def _calcXYMagnitude(self, x: int, y: int):
        return [self._calcXMagnitude(x), self._calcYMagnitude(y)]
    
    def _calcXYValueWithMagnitude(self, valX: int, valY: int, magX: int, magY: int):
        return [self._calcXValue(valX, self._calcXMagnitude(magX)), self._calcYValue(valY, self._calcYMagnitude(magY))]