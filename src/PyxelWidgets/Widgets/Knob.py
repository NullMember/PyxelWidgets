from . import Widget
from ..Helpers import *
from enum import Enum

class KnobType(Enum):
    Single = 0
    BoostCut = 1
    Wrap = 2
    Spread = 3
    Collapse = 4

class Knob(Widget):
    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Knob_{Knob._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.coefficient = kwargs.get('coefficient', 0.05)
        self.type = kwargs.get('type', KnobType.Wrap)
        self.state = False
        self.perimeter = self._calcPerimeter(self.rect.w, self.rect.h)
        self._held = [-1, -1]
        Knob._count += 1

    def pressed(self, x: int, y: int, value: float):
        if self._held == [-1, -1]:
            if self._calcKnobIndex(x, y) != -1:
                self._held = [x, y]
                self.state = True
                self.updated = True
        else:
            heldIndex = self._calcKnobIndex(self._held[0], self._held[1])
            curIndex = self._calcKnobIndex(x, y)
            halfPerimeter = self.perimeter // 2
            if heldIndex != -1 and curIndex != -1:
                if (heldIndex < halfPerimeter and curIndex >= halfPerimeter) or (curIndex < halfPerimeter and heldIndex >= halfPerimeter):
                    self.state = False
                    self.value = 0.5
        return super().pressed(x, y, self.value)
    
    def released(self, x: int, y: int, value: float):
        self._held = [-1, -1]
        self.state = False
        return super().released(x, y, self.value)
    
    def tick(self):
        if self.state:
            index = self._calcKnobIndex(self._held[0], self._held[1])
            if index != -1:
                self.value += self._calcKnobWeight(index) * self.coefficient

    def updateArea(self, sx, sy, sw, sh):
        if self.state:
            self.tick()
        else:
            self.updated = False
        halfval = self.value / 2.0
        halfvalpluspointfive = halfval + 0.5
        area = Rectangle2D(sx, sy, sw, sh)
        for x in area.columns:
            for y in area.rows:
                index = self._calcKnobIndex(x, y)
                minV = self._calcKnobValue(index, 0.0)
                maxV = self._calcKnobValue(index, 1.0)
                if index == -1:
                    self.buffer[x, y] = [-1, -1, -1]
                else:
                    if self.type == KnobType.Single:
                        if maxV <= self.value:
                            self.buffer[x, y] = self.deactiveColor
                        elif minV > self.value:
                            self.buffer[x, y] = self.deactiveColor
                        else:
                            coefficient = self._calcPixelCoefficient(self.value - minV)
                            self.buffer[x, y] = self.activeColor * coefficient
                    elif self.type == KnobType.BoostCut:
                        if self.value > 0.5:
                            if minV < 0.5:
                                self.buffer[x, y] = self.deactiveColor
                            else:
                                if maxV <= self.value:
                                    self.buffer[x, y] = self.activeColor
                                elif minV > self.value:
                                    self.buffer[x, y] = self.deactiveColor
                                else:
                                    coefficient = self._calcPixelCoefficient(self.value - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                        elif self.value < 0.5:
                            if maxV > 0.5:
                                self.buffer[x, y] = self.deactiveColor
                            else:
                                if minV >= self.value:
                                    self.buffer[x, y] = self.activeColor
                                elif maxV < self.value:
                                    self.buffer[x, y] = self.deactiveColor
                                else:
                                    coefficient = 1.0 - self._calcPixelCoefficient(self.value - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                        else:
                            if minV == 0.5 or maxV == 0.5:
                                self.buffer[x, y] = self.activeColor
                            else:
                                self.buffer[x, y] = self.deactiveColor
                    elif self.type == KnobType.Wrap:
                        if maxV <= self.value:
                            self.buffer[x, y] = self.activeColor
                        elif minV > self.value:
                            self.buffer[x, y] = self.deactiveColor
                        else:
                            coefficient = self._calcPixelCoefficient(self.value - minV)
                            self.buffer[x, y] = self.activeColor * coefficient
                    elif self.type == KnobType.Spread:
                        if minV >= 0.5:
                            if minV > halfvalpluspointfive:
                                self.buffer[x, y] = self.deactiveColor
                            elif maxV <= halfvalpluspointfive:
                                self.buffer[x, y] = self.activeColor
                            else:
                                coefficient = self._calcPixelCoefficient(halfvalpluspointfive - minV)
                                self.buffer[x, y] = self.activeColor * coefficient
                        elif maxV <= 0.5:
                            if minV >= (1.0 - halfvalpluspointfive):
                                self.buffer[x, y] = self.activeColor
                            elif maxV < (1.0 - halfvalpluspointfive):
                                self.buffer[x, y] = self.deactiveColor
                            else:
                                coefficient = 1.0 - self._calcPixelCoefficient((1.0 - halfvalpluspointfive) - minV)
                                self.buffer[x, y] = self.activeColor * coefficient
                    elif self.type == KnobType.Collapse:
                        if halfval < 0.5:
                            if maxV <= 0.5:
                                if minV > halfval:
                                    self.buffer[x, y] = self.activeColor
                                elif maxV <= halfval:
                                    self.buffer[x, y] = self.deactiveColor
                                else:
                                    coefficient = 1.0 - self._calcPixelCoefficient(halfval - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                            elif minV >= 0.5:
                                if minV >= (1.0 - halfval):
                                    self.buffer[x, y] = self.deactiveColor
                                elif maxV < (1.0 - halfval):
                                    self.buffer[x, y] = self.activeColor
                                else:
                                    coefficient = self._calcPixelCoefficient((1.0 - halfval) - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                        else:
                            self.buffer[x, y] = self.deactiveColor
        return self.buffer[area.l:area.r, area.b:area.t]
    
    def _resize(self, width, height):
        self.perimeter = self._calcPerimeter(width, height)
        return True

    def _calcKnobIndex(self, x: int, y: int) -> float:
        if self.rect.w == 1:
            return y
        elif self.rect.h == 1:
            return x
        halfwidth = int(self.rect.w / 2)
        if y == (self.rect.h - 1):
            return (y + halfwidth + x) - 1
        elif x < halfwidth:
            if y == 0:
                return (halfwidth - x) - 1
            elif x == 0:
                return (y + halfwidth) - 1
        elif x >= halfwidth:
            if y == 0:
                return (self.perimeter - (x - halfwidth)) - 1
            elif x == (self.rect.w - 1):
                return (self.perimeter - (x - halfwidth) - y) - 1
        return -1

    def _calcKnobValue(self, index: int, value: float) -> float:
        if index == -1:
            return 0.0
        return round(((index / self.perimeter) + (value / self.perimeter)), 6)
    
    def _calcKnobWeight(self, index: int) -> float:
        if index == -1:
            return 0.0
        halfperimeter = int(self.perimeter / 2)
        if index < halfperimeter:
            return round(-(0.5 - self._calcKnobValue(index, 0.0)), 6)
        else:
            return round(self._calcKnobValue(index, 1.0) - 0.5, 6)

    def _calcPixelCoefficient(self, value: float) -> float:
        return value * self.perimeter
    
    def _calcPerimeter(self, width, height) -> float:    
        if width == 1:
            return height
        elif height == 1:
            return width
        return ((width - 1) * 2) + ((height - 1) * 2)