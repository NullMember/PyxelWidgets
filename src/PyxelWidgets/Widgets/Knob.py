from enum import Enum
from .Widget import *
from ..Util.Clock import *


class KnobType(Enum):
    Single = 0
    BoostCut = 1
    Wrap = 2
    Spread = 3
    Collapse = 4

class Knob(Widget):
    def __init__(self, width: int, height: int, **kwargs):
        name = kwargs.get('name', 'Knob_' + str(Knob._count))
        super().__init__(name, width=width, height=height, **kwargs)
        self._ppq = kwargs.get('ppq', 24)
        self._type = kwargs.get('type', KnobType.Wrap)
        self._coefficient = 0.05#1.0 / self._ppq
        self._state = False
        self._held = [-1, -1]
        self._perimeter = self._calcPerimeter(self.width, self.height)
        self._target = Target(self.name, self.tick)
        self._target.active = False
        clock = kwargs.get('clock', None)
        if clock != None:
            self.addToClock(clock)
        Knob._count += 1

    @property
    def ppq(self) -> int:
        return self._ppq
    
    @ppq.setter
    def ppq(self, value: int) -> None:
        self._ppq = value
        self._coefficient = 1.0 / self.ppq

    @property
    def target(self) -> Target:
        return self._target

    def addToClock(self, clock: Clock):
        # self.ppq = clock.ppq
        clock.addTarget(self._target)

    def pressed(self, x: int, y: int, value: float):
        self._state = True
        if self._held == [-1, -1]:
            if self._calcKnobIndex(x, y) != -1:
                self._held = [x, y]
                self._target.active = True
        else:
            heldIndex = self._calcKnobIndex(self._held[0], self._held[1])
            curIndex = self._calcKnobIndex(x, y)
            halfPerimeter = self._perimeter // 2
            if heldIndex != -1 and curIndex != -1:
                if (heldIndex < halfPerimeter and curIndex >= halfPerimeter) or (curIndex < halfPerimeter and heldIndex >= halfPerimeter):
                    self._target.active = False
                    self.value = 0.5
        return super().pressed(x, y, self.value)
    
    def released(self, x: int, y: int, value: float):
        self._held = [-1, -1]
        self._state = False
        self._target.active = False
        return super().released(x, y, self.value)
    
    def tick(self, tick):
        if self._state:
            index = self._calcKnobIndex(self._held[0], self._held[1])
            if index != -1:
                self.value += self._calcKnobWeight(index) * self._coefficient

    def updateArea(self, sx, sy, sw, sh):
        if self._updated:
            self._updated = False
            halfval = self.value / 2.0
            halfvalpluspointfive = halfval + 0.5
            ex = sx + sw
            ex = ex if ex < self.width else self.width
            ey = sy + sh
            ey = ey if ey < self.height else self.height
            for x in range(sx, ex):
                for y in range(sy, ey):
                    index = self._calcKnobIndex(x, y)
                    minV = self._calcKnobValue(index, 0.0)
                    maxV = self._calcKnobValue(index, 1.0)
                    if index == -1:
                        self._pixels[x][y] = [-1, -1, -1]
                    else:
                        if self._type == KnobType.Single:
                            if maxV <= self.value:
                                self._pixels[x][y] = self._deactiveColor
                            elif minV > self.value:
                                self._pixels[x][y] = self._deactiveColor
                            else:
                                coeff = self._calcPixelCoefficient(self.value - minV)
                                self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                        elif self._type == KnobType.BoostCut:
                            if self.value > 0.5:
                                if minV < 0.5:
                                    self._pixels[x][y] = self._deactiveColor
                                else:
                                    if maxV <= self.value:
                                        self._pixels[x][y] = self._activeColor
                                    elif minV > self.value:
                                        self._pixels[x][y] = self._deactiveColor
                                    else:
                                        coeff = self._calcPixelCoefficient(self.value - minV)
                                        self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                            elif self.value < 0.5:
                                if maxV > 0.5:
                                    self._pixels[x][y] = self._deactiveColor
                                else:
                                    if minV >= self.value:
                                        self._pixels[x][y] = self._activeColor
                                    elif maxV < self.value:
                                        self._pixels[x][y] = self._deactiveColor
                                    else:
                                        coeff = 1.0 - self._calcPixelCoefficient(self.value - minV)
                                        self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                            else:
                                if minV == 0.5 or maxV == 0.5:
                                    self._pixels[x][y] = self._activeColor
                                else:
                                    self._pixels[x][y] = self._deactiveColor
                        elif self._type == KnobType.Wrap:
                            if maxV <= self.value:
                                self._pixels[x][y] = self._activeColor
                            elif minV > self.value:
                                self._pixels[x][y] = self._deactiveColor
                            else:
                                coeff = self._calcPixelCoefficient(self.value - minV)
                                self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                        elif self._type == KnobType.Spread:
                            if minV >= 0.5:
                                if minV > halfvalpluspointfive:
                                    self._pixels[x][y] = self._deactiveColor
                                elif maxV <= halfvalpluspointfive:
                                    self._pixels[x][y] = self._activeColor
                                else:
                                    coeff = self._calcPixelCoefficient(halfvalpluspointfive - minV)
                                    self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                            elif maxV <= 0.5:
                                if minV >= (1.0 - halfvalpluspointfive):
                                    self._pixels[x][y] = self._activeColor
                                elif maxV < (1.0 - halfvalpluspointfive):
                                    self._pixels[x][y] = self._deactiveColor
                                else:
                                    coeff = 1.0 - self._calcPixelCoefficient((1.0 - halfvalpluspointfive) - minV)
                                    self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                        elif self._type == KnobType.Collapse:
                            if halfval < 0.5:
                                if maxV <= 0.5:
                                    if minV > halfval:
                                        self._pixels[x][y] = self._activeColor
                                    elif maxV <= halfval:
                                        self._pixels[x][y] = self._deactiveColor
                                    else:
                                        coeff = 1.0 - self._calcPixelCoefficient(halfval - minV)
                                        self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                                elif minV >= 0.5:
                                    if minV >= (1.0 - halfval):
                                        self._pixels[x][y] = self._deactiveColor
                                    elif maxV < (1.0 - halfval):
                                        self._pixels[x][y] = self._activeColor
                                    else:
                                        coeff = self._calcPixelCoefficient((1.0 - halfval) - minV)
                                        self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                            else:
                                self._pixels[x][y] = self._deactiveColor

                            # if self.value > 0.5:
                            #     if minV >= 0.5:
                            #         if minV > self.value:
                            #             self._pixels[x][y] = self._deactiveColor
                            #         elif maxV <= self.value:
                            #             self._pixels[x][y] = self._activeColor
                            #         else:
                            #             coeff = self._calcPixelCoefficient(self.value - minV)
                            #             self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                            #     elif maxV <= 0.5:
                            #         if minV >= (1.0 - self.value):
                            #             self._pixels[x][y] = self._activeColor
                            #         elif maxV < (1.0 - self.value):
                            #             self._pixels[x][y] = self._deactiveColor
                            #         else:
                            #             coeff = 1.0 - self._calcPixelCoefficient((1.0 - self.value) - minV)
                            #             self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                            # elif self.value < 0.5:
                            #     if maxV <= 0.5:
                            #         if minV > self.value:
                            #             self._pixels[x][y] = self._activeColor
                            #         elif maxV <= self.value:
                            #             self._pixels[x][y] = self._deactiveColor
                            #         else:
                            #             coeff = 1.0 - self._calcPixelCoefficient(self.value - minV)
                            #             self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                            #     elif minV >= 0.5:
                            #         if minV >= (1.0 - self.value):
                            #             self._pixels[x][y] = self._deactiveColor
                            #         elif maxV < (1.0 - self.value):
                            #             self._pixels[x][y] = self._activeColor
                            #         else:
                            #             coeff = self._calcPixelCoefficient((1.0 - self.value) - minV)
                            #             self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                            # else:
                            #     if minV == 0.5 or maxV == 0.5:
                            #         self._pixels[x][y] = self._activeColor
                            #     else:
                            #         self._pixels[x][y] = self._deactiveColor
            return self._pixels
        return []
    
    def _resize(self, width, height):
        self._perimeter = self._calcPerimeter(width, height)
        return True

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
    
    def _calcPerimeter(self, width, height) -> float:    
        if width == 1:
            return height
        elif height == 1:
            return width
        return ((width - 1) * 2) + ((height - 1) * 2)