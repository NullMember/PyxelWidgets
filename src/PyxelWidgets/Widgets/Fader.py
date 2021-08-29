from .Widget import Widget
from enum import Enum

class FaderDirection(Enum):
    """
    Description
    ----
    Fader direction class\n
    Determines fader direction
    
    Options
    ----
    Vertical\n
    Horizontal
    """
    Vertical = 0
    Horizontal = 1

class FaderGrid(Enum):
    """
    Description
    ----
    Fader grid class\n
    Determines how multi-width vertical faders\n 
    or multi-height horizontal faders will work
    
    Options
    ----
    Simple\n
    Matrix
    """
    Simple = 0
    Matrix = 1

class FaderType(Enum):
    Single = 0
    BoostCut = 1
    Wrap = 2
    Spread = 3
    Collapse = 4

class FaderMode(Enum):
    Simple = 0
    Multi = 1
    Magnitude = 2
    Sensitive = 3
    Relative = 4

class Fader(Widget):
    def __init__(self, name: str, width: int, height: int, **kwargs):
        """
        Description
        ----
        Fader class implements Widget class

        Parameters
        ----
        name: str
            Unique widget name, used to find widgets registered on window
        x: int
            x axis where widget will be placed on window, from left to right
             x value should be positive
        y: int
            y axis where widget will be placed on window, from bottom to top
             y value should be positive
        width: int
            Widget width, should >= 1
        height: int
            Widget height, should >= 1
        
        Optional Parameters
        ----
        callback: function
            If widget value is changed this function will be called
             Should accept 2 parameters, (widget) name and value
        activeColor: [r: int, g: int, b: int] = [255, 255, 255]
            If widget value is non-zero, this color will be used
        deactiveColor: [r: int, g: int, b: int] = [0, 0, 0]
            If widget value is zero, this color will be used
        value: int = 0.0
            Default value of widget
        direction: FaderDirection = FaderDirection.Vertical
            Can be FaderDirection.Vertical or FaderDirection.Horizontal
             This will affect how widget rendered and value is calculated
              Vertical faders from bottom to top, horizontal faders from left to right
        grid: FaderGrid = FaderGrid.Simple
            Can be FaderGrid.Simple or FaderGrid.Matrix
             Simple faders will use only one axis
              Matrix faders will use both x and y axis
        type: FaderType = FaderType.Wrap
            Single: Only corresponding pad will active
             BoostCut: Corresponding pads from middle active
              Wrap: Corresponding pads from bottom active
               Spread: Corresponding pads from middle active symmetrically
        """
        super().__init__(name, width, height, **kwargs)
        self._direction = kwargs.get('direction', FaderDirection.Vertical)
        self._grid = kwargs.get('grid', FaderGrid.Simple)
        self._type = kwargs.get('type', FaderType.Wrap)
        self._mode = kwargs.get('mode', FaderMode.Multi)
        self._resolution = kwargs.get('resolution', 4)
        self._multiStep = 0
        self._oldButton = [-1, -1]
        self._heldButton = [-1, -1]

    def pressed(self, x: int, y: int, value: float):
        if self._mode == FaderMode.Simple:
            self.value = self._pressedSimple(x, y, value)
        elif self._mode == FaderMode.Multi:
            self.value = self._pressedMulti(x, y, value)
        elif self._mode == FaderMode.Magnitude:
            self.value = self._pressedMagnitude(x, y, value)
        elif self._mode == FaderMode.Sensitive:
            self.value = self._pressedSensitive(x, y, value)
        elif self._mode == FaderMode.Relative:
            self.value = self._pressedRelative(x, y, value)
        super().pressed(x, y, value)
    
    def _pressedSimple(self, x, y, value):
        if self._type == FaderType.BoostCut:
            if self._calcFaderValue(x, y, 0.0) < 0.5:
                return self._calcFaderValue(x, y, 0.0)
            else:
                return self._calcFaderValue(x, y, 1.0)
        else:
            return self._calcFaderValue(x, y, 0.0)

    def _pressedMulti(self, x, y, value):
        if self._type == FaderType.BoostCut:
            if self._calcFaderValue(x, y, 0.0) < 0.5:
                if self._oldButton[0] == x and self._oldButton[1] == y:
                    self._multiStep = (self._multiStep - 1) % self._resolution
                else:
                    self._oldButton = [x, y]
                    self._multiStep = self._resolution - 1
                return self._calcFaderValue(x, y, self._multiStep / self._resolution)
            else:
                if self._oldButton[0] == x and self._oldButton[1] == y:
                    self._multiStep = (self._multiStep + 1) % self._resolution
                else:
                    self._oldButton = [x, y]
                    self._multiStep = 0
                return self._calcFaderValue(x, y, self._multiStep / self._resolution)
        elif self._type == FaderType.Collapse:
            if self._oldButton[0] == x and self._oldButton[1] == y:
                self._multiStep = (self._multiStep - 1) % self._resolution
            else:
                self._oldButton = [x, y]
                self._multiStep = self._resolution - 1
            return self._calcFaderValue(x, y, self._multiStep / self._resolution)
        else:
            if self._oldButton[0] == x and self._oldButton[1] == y:
                self._multiStep = (self._multiStep + 1) % self._resolution
            else:
                self._oldButton = [x, y]
                self._multiStep = 0
            return self._calcFaderValue(x, y, self._multiStep / self._resolution)

    def _pressedMagnitude(self, x, y, value):
        return self._calcFaderValue(x, y, self._calcFaderMagnitude(x, y))

    def _pressedSensitive(self, x, y, value):
        if self._type == FaderType.BoostCut:
            if self._calcFaderValue(x, y, 0.0) < 0.5:
                return self._calcFaderValue(x, y, 1.0 - value)
            else:
                return self._calcFaderValue(x, y, value)
        elif self._type == FaderType.Collapse:
            return self._calcFaderValue(x, y, 1.0 - value)
        else:
            return self._calcFaderValue(x, y, value)

    def _pressedRelative(self, x, y, value):
        if self._heldButton[0] >= 0 and self._heldButton[1] >= 0:
            return self._calcFaderValue(self._heldButton[0], self._heldButton[1], self._calcFaderMagnitude(x, y))
        else:
            self._heldButton = [x, y]
            return self._calcFaderValue(x, y, self._calcFaderMagnitude(x, y))

    def held(self, x: int, y: int, value: float):
        if self._mode != FaderMode.Relative:
            if x == 0 and y == 0:
                self.value = 0.0
            elif x == self.width - 1 and y == self.height - 1:
                self.value = 1.0
            else:
                self.value = 0.5
        super().held(x, y, value)
    
    def released(self, x: int, y: int, value: float):
        if self._heldButton[0] == x and self._heldButton[1] == y:
            self._heldButton = [-1, -1]
        super().released(x, y, value)

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
                    minV = self._calcFaderValue(x, y, 0.0)
                    maxV = self._calcFaderValue(x, y, 1.0)
                    if self._type == FaderType.Single:
                        # if current pad lower than last pressed pad
                        if maxV <= self.value:
                            self._pixels[x][y] = self._deactiveColor
                        # if current pad higher than last pressed pad
                        elif minV > self.value:
                            self._pixels[x][y] = self._deactiveColor
                        # if current pad is last pressed pad
                        else:
                            coefficient = min(self._calcPixelCoefficient(self.value - minV) + self._calcPixelStep(), 1.0)
                            self._pixels[x][y] = [int(self._activeColor[0] * coefficient), int(self._activeColor[1] * coefficient), int(self._activeColor[2] * coefficient)]
                    elif self._type == FaderType.BoostCut:
                        # if last pressed pad in upper half
                        if self.value > 0.5:
                            # if current pad in lower half
                            if minV < 0.5:
                                self._pixels[x][y] = self._deactiveColor
                            # if current pad in upper half
                            else:
                                # if current pad is lower than last pressed pad
                                if maxV <= self.value:
                                    self._pixels[x][y] = self._activeColor
                                # if current pad is higher than last pressed pad
                                elif minV > self.value:
                                    self._pixels[x][y] = self._deactiveColor
                                # if current pad is last pressed pad
                                else:
                                    coefficient = min(self._calcPixelCoefficient(self.value - minV) + self._calcPixelStep(), 1.0)
                                    self._pixels[x][y] = [int(self._activeColor[0] * coefficient), int(self._activeColor[1] * coefficient), int(self._activeColor[2] * coefficient)]
                        # if last pressed pad in lower half
                        elif self.value < 0.5:
                            # if current pad in upper half
                            if maxV > 0.5:
                                self._pixels[x][y] = self._deactiveColor
                            # if current pad in lower half
                            else:
                                # if current pad is higher than last pressed pad
                                if minV >= self.value:
                                    self._pixels[x][y] = self._activeColor
                                # if current pad is lower than last pressed pad
                                elif maxV < self.value:
                                    self._pixels[x][y] = self._deactiveColor
                                # if current pad is last pressed pad
                                else:
                                    # reverse brightness to match type
                                    coefficient = 1.0 - self._calcPixelCoefficient(self.value - minV)
                                    self._pixels[x][y] = [int(self._activeColor[0] * coefficient), int(self._activeColor[1] * coefficient), int(self._activeColor[2] * coefficient)]
                        # if current value is 0.5
                        else:
                            # lit middle pad(s)
                            if minV == 0.5 or maxV == 0.5:
                                self._pixels[x][y] = self._activeColor
                            # unlit every other pad
                            else:
                                self._pixels[x][y] = self._deactiveColor
                    elif self._type == FaderType.Wrap:
                        # if current pad lower than last pressed pad
                        if maxV <= self.value:
                            self._pixels[x][y] = self._activeColor
                        # if current pad higher than last pressed pad
                        elif minV > self.value:
                            self._pixels[x][y] = self._deactiveColor
                        # if current pad is last pressed pad
                        else:
                            coefficient = min(self._calcPixelCoefficient(self.value - minV) + self._calcPixelStep(), 1.0)
                            self._pixels[x][y] = [int(self._activeColor[0] * coefficient), int(self._activeColor[1] * coefficient), int(self._activeColor[2] * coefficient)]
                    elif self._type == FaderType.Spread:
                        # if current pad in upper half
                        if minV >= 0.5:
                            # if current pad higher than current value
                            if minV > halfvalpluspointfive:
                                self._pixels[x][y] = self._deactiveColor
                            # if current pad lower than current value
                            elif maxV <= halfvalpluspointfive:
                                self._pixels[x][y] = self._activeColor
                            # if current value is in current pad's boundary
                            else:
                                coeff = self._calcPixelCoefficient(halfvalpluspointfive - minV)
                                self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                        # if current pad in lower half
                        elif maxV <= 0.5:
                            # if current pad higher than current value
                            if minV >= (1.0 - halfvalpluspointfive):
                                self._pixels[x][y] = self._activeColor
                            # if current pad lower than current value
                            elif maxV < (1.0 - halfvalpluspointfive):
                                self._pixels[x][y] = self._deactiveColor
                            # if current value is in current pad's boundary
                            else:
                                coeff = 1.0 - self._calcPixelCoefficient((1.0 - halfvalpluspointfive) - minV)
                                self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                    elif self._type == FaderType.Collapse:
                        # if current pad in upper half
                        if minV >= 0.5:
                            # if current pad lower than current value
                            if minV >= (1.0 - halfval):
                                self._pixels[x][y] = self._deactiveColor
                            # if current pad higher than current value
                            elif maxV < (1.0 - halfval):
                                self._pixels[x][y] = self._activeColor
                            # if current value is in current pad's boundary
                            else:
                                coeff = self._calcPixelCoefficient((1.0 - halfval) - minV)
                                self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                        # if current pad in lower half
                        elif maxV <= 0.5:
                            # if current pad lower than current value
                            if minV > halfval:
                                self._pixels[x][y] = self._activeColor
                            # if current pad higher than current value
                            elif maxV <= halfval:
                                self._pixels[x][y] = self._deactiveColor
                            # if current value is in current pad's boundary
                            else:
                                coeff = 1.0 - self._calcPixelCoefficient(halfval - minV)
                                self._pixels[x][y] = [int(self._activeColor[0] * coeff), int(self._activeColor[1] * coeff), int(self._activeColor[2] * coeff)]
                        # # if last pressed pad in upper half
                        # if self.value > 0.5:
                        #     # if current pad in upper half
                        #     if minV >= 0.5:
                        #         # if current pad higher than last pressed pad
                        #         if minV > self.value:
                        #             self._pixels[x][y] = self._deactiveColor
                        #         # if current pad lower than last pressed pad
                        #         elif maxV <= self.value:
                        #             self._pixels[x][y] = self._activeColor
                        #         # if current pad is last pressed pad
                        #         else:
                        #             coefficient = min(self._calcPixelCoefficient(self.value - minV) + self._calcPixelStep(), 1.0)
                        #             self._pixels[x][y] = [int(self._activeColor[0] * coefficient), int(self._activeColor[1] * coefficient), int(self._activeColor[2] * coefficient)]
                        #     # if current pad in lower half
                        #     elif maxV <= 0.5:
                        #         # if current pad higher than last pressed pads symmetrical equivalent
                        #         if minV >= (1.0 - self.value):
                        #             self._pixels[x][y] = self._activeColor
                        #         # if current pad lower than last pressed pads symmetrical equivalent
                        #         elif maxV < (1.0 - self.value):
                        #             self._pixels[x][y] = self._deactiveColor
                        #         # if current pad is last pressed pads symmetrical equivalent
                        #         else:
                        #             coefficient = 1.0 - max(self._calcPixelCoefficient((1.0 - self.value) - minV) - self._calcPixelStep(), 0.0)
                        #             self._pixels[x][y] = [int(self._activeColor[0] * coefficient), int(self._activeColor[1] * coefficient), int(self._activeColor[2] * coefficient)]
                        # # if last pressed pad in lower half
                        # elif self.value < 0.5:
                        #     # if current pad in lower half
                        #     if maxV <= 0.5:
                        #         # if current pad higher than last pressed pad
                        #         if minV > self.value:
                        #             self._pixels[x][y] = self._activeColor
                        #         # if current pad lower than last pressed pad
                        #         elif maxV <= self.value:
                        #             self._pixels[x][y] = self._deactiveColor
                        #         # if current pad is last pressed pad
                        #         else:
                        #             coefficient = 1.0 - self._calcPixelCoefficient(self.value - minV)
                        #             self._pixels[x][y] = [int(self._activeColor[0] * coefficient), int(self._activeColor[1] * coefficient), int(self._activeColor[2] * coefficient)]
                        #     # if current pad in upper half
                        #     elif minV >= 0.5:
                        #         # if current pad higher than last pressed pads symmetrical equivalent
                        #         if minV >= (1.0 - self.value):
                        #             self._pixels[x][y] = self._deactiveColor
                        #         # if current pad lower than last pressed pads symmetrical equivalent
                        #         elif maxV < (1.0 - self.value):
                        #             self._pixels[x][y] = self._activeColor
                        #         # if current pad is last pressed pads symmetrical equivalent
                        #         else:
                        #             coefficient = self._calcPixelCoefficient((1.0 - self.value) - minV)
                        #             self._pixels[x][y] = [int(self._activeColor[0] * coefficient), int(self._activeColor[1] * coefficient), int(self._activeColor[2] * coefficient)]
                        # # if current value is 0.5
                        # else:
                        #     # lit middle pad(s)
                        #     if minV == 0.5 or maxV == 0.5:
                        #         self._pixels[x][y] = self._activeColor
                        #     # unlit every other pad
                        #     else:
                        #         self._pixels[x][y] = self._deactiveColor
            return self._pixels
        return []

    # Calculate fader value from pad location
    def _calcFaderValue(self, x: int, y: int, value: float) -> float:
        # For 2-d widgets, where output values are single float,
        # we must calculate single float from 2-d area.
        # Calculation done from left to right, bottom to up in order
        # to get final value for vertical faders. its basically (y * step) + x
        # vertical matrix faders are left to right, bottom to up in order
        # horizontal matrix faders are bottom to up, left to right in order
        # Simple faders are bottom to up for vertical, left to right for horizontal
        if self._grid == FaderGrid.Simple:
            if self._direction == FaderDirection.Vertical:
                return round(((y / self.height) + (value / self.height)), 6)
            elif self._direction == FaderDirection.Horizontal:
                return round(((x / self.width) + (value / self.width)), 6)
        elif self._grid == FaderGrid.Matrix:
            if self._direction == FaderDirection.Vertical:
                base = (x / (self.height * self.width)) + (y / self.height)
            elif self._direction == FaderDirection.Horizontal:
                base = (y / (self.height * self.width)) + (x / self.width)
            return round(base + (value / (self.width * self.height)), 6)
    
    # Calculate pad magnitude from pad location
    def _calcFaderMagnitude(self, x: int, y: int) -> float:
        if self._grid == FaderGrid.Simple:
            if self._direction == FaderDirection.Vertical:
                return self._calcFaderValue(x, y, y / (self.height - 1))
            elif self._direction == FaderDirection.Horizontal:
                return self._calcFaderValue(x, y, x / (self.width - 1))
        elif self._grid == FaderGrid.Matrix:
            if self._direction == FaderDirection.Vertical:
                base = (x / ((self.height * self.width) - 1)) + (y / (self.height - 1))
            elif self._direction == FaderDirection.Horizontal:
                base = (y / ((self.height * self.width) - 1)) + (x / (self.width - 1))
            return self._calcFaderValue(x, y, base)
    
    # Calculate pixel coefficient for different fader options
    def _calcPixelCoefficient(self, value: float) -> float:
        if self._grid == FaderGrid.Simple:
            if self._direction == FaderDirection.Vertical:
                return (value * self.height)
            elif self._direction == FaderDirection.Horizontal:
                return (value * self.width)
        elif self._grid == FaderGrid.Matrix:
            return (value * (self.height * self.width))
    
    def _calcPixelStep(self):
        if self._mode == FaderMode.Simple:
            return 0.5
        elif self._mode == FaderMode.Multi:
            return 1.0 / self._resolution
        elif self._mode == FaderMode.Magnitude:
            return 1.0 / 255
        elif self._mode == FaderMode.Sensitive:
            return 1.0 / 255
        elif self._mode == FaderMode.Relative:
            if self._grid == FaderGrid.Simple:
                if self._direction == FaderDirection.Vertical:
                    return 1.0/ self.height
                elif self._direction == FaderDirection.Horizontal:
                    return 1.0 / self.width
            elif self._grid == FaderGrid.Matrix:
                return 1.0 / (self.width * self.height)