from .Widget import *
from ..Util.Clock import *

class Knob(Widget):
    def __init__(self, name: str, width: int, height: int, clock: Clock = None, **kwargs):
        super().__init__(name, width=width, height=height, **kwargs)
        self._coefficient = kwargs.get('coefficient', 0.05)
        self._state = False
        self._held = [-1, -1]
        if self.width > 1 and self.height > 1:
            self._perimeter = ((self.width - 1) * 2) + ((self.height - 1) * 2)
        elif self.width == 1:
            self._perimeter = self.height
        elif self.height == 1:
            self._perimeter = self.width
        self._target = Target(self.name, self.tick)
        if clock != None:
            clock.addTarget(self._target)

    @property
    def coefficient(self) -> float:
        return self._coefficient
    
    @coefficient.setter
    def coefficient(self, value: float) -> None:
        self._coefficient = value

    @property
    def target(self) -> Target:
        return self._target

    def pressed(self, x: int, y: int, value: float):
        self._held = [x, y]
        self._state = True
        return super().pressed(x, y, self.value)
    
    def released(self, x: int, y: int, value: float):
        self._state = False
        return super().released(x, y, self.value)
    
    def tick(self, tick):
        if self._state:
            index = self._calcKnobIndex(self._held[0], self._held[1])
            if index != -1:
                self.value += self._calcKnobWeight(index) * self.coefficient

    def update(self) -> list:
        if self._oldValue != self.value:
            self._oldValue = self.value
            for x in range(self.width):
                for y in range(self.height):
                    index = self._calcKnobIndex(x, y)
                    minV = self._calcKnobValue(index, 0.0)
                    maxV = self._calcKnobValue(index, 1.0)
                    if index == -1:
                        self._pixels[x][y] = [-1, -1, -1]
                    else:
                        if maxV < self.value:
                            self._pixels[x][y] = [self._activeColor[0], self._activeColor[1], self._activeColor[2]]
                        elif minV > self.value:
                            self._pixels[x][y] = [self._deactiveColor[0], self._deactiveColor[1], self._deactiveColor[2]]
                        else:
                            coeff = self._calcPixelCoefficient(self._value - minV)
                            self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
            return self._pixels
        return []
    
    def _calcKnobIndex(self, x: int, y: int) -> float:
        if self.width == 1:
            return y
        elif self.height == 1:
            return x
        halfwidth = int(self.width / 2)
        if y == (self.height - 1):
            return (y + halfwidth + x) - 1
        elif x < halfwidth:
            if y == 0:
                return (halfwidth - x) - 1
            elif x == 0:
                return (y + halfwidth) - 1
        elif x >= halfwidth:
            if y == 0:
                return (self._perimeter - (x - halfwidth)) - 1
            elif x == (self.width - 1):
                return (self._perimeter - (x - halfwidth) - y) - 1
        return -1

    def _calcKnobValue(self, index: int, value: float) -> float:
        if index == -1:
            return 0.0
        return round(((index / self._perimeter) + (value / self._perimeter)), 6)
    
    def _calcKnobWeight(self, index: int) -> float:
        if index == -1:
            return 0.0
        halfperimeter = int(self._perimeter / 2)
        if index < halfperimeter:
            return round(-(0.5 - self._calcKnobValue(index, 0.0)), 6)
        else:
            return round(self._calcKnobValue(index, 1.0) - 0.5, 6)

    def _calcPixelCoefficient(self, value: float) -> float:
        return value * self._perimeter