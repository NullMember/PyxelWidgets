import PyxelWidgets.Widgets
import PyxelWidgets.Helpers
import enum

class Fader(PyxelWidgets.Widgets.Widget):

    class Direction(enum.Enum):
        """
        Description
        ----
        Vertical faders are bottom to top,
        Horizontal faders are left to right.
        
        Enums
        ----
        Vertical\n
        Horizontal
        """
        Vertical    = enum.auto()
        Horizontal  = enum.auto()

    class Grid(enum.Enum):
        """
        Description
        ----
        Determines how multi-width vertical faders
        or multi-height horizontal faders will work
        
        Enums
        ----
        Simple\n
        Matrix
        """
        Simple      = enum.auto()
        Matrix      = enum.auto()

    class Type(enum.Enum):
        Single      = enum.auto()
        BoostCut    = enum.auto()
        Wrap        = enum.auto()
        Spread      = enum.auto()
        Collapse    = enum.auto()

    class Mode(enum.Enum):
        Simple      = enum.auto()
        Multi       = enum.auto()
        Magnitude   = enum.auto()
        Sensitive   = enum.auto()
        Relative    = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        """
        Description
        ----
        Fader class implements Widget class

        Parameters
        ----
        name: str
            Unique widget name, used to find widgets registered on window.
        x: int
            x axis where widget will be placed on window, from left to right.
            x value should be positive
        y: int
            y axis where widget will be placed on window, from bottom to top.
            y value should be positive.
        width: int
            Widget width, should >= 1
        height: int
            Widget height, should >= 1
        
        Optional Parameters
        ----
        callback: function
            If widget value is changed this function will be called.  
            Should accept 2 parameters, (widget) name and value
        activeColor: [r: int, g: int, b: int] = [255, 255, 255]
            If widget value is non-zero, this color will be used.
        deactiveColor: [r: int, g: int, b: int] = [0, 0, 0]
            If widget value is zero, this color will be used.
        value: int = 0.0
            Default value of widget.
        direction: FaderDirection = Fader.FaderDirection.Vertical
            Can be Fader.FaderDirection.Vertical or Fader.FaderDirection.Horizontal.  
            This will affect how widget rendered and value is calculated.  
            Vertical faders from bottom to top, horizontal faders from left to right.
        grid: FaderGrid = Fader.FaderGrid.Simple
            Can be Fader.FaderGrid.Simple or Fader.FaderGrid.Matrix.  
            Simple faders will use only one axis.  
            Matrix faders will use both x and y axis.
        type: FaderType = Fader.FaderType.Wrap
            Single: Only corresponding pad will active.  
            BoostCut: Corresponding pads from middle active.  
            Wrap: Corresponding pads from bottom active.  
            Spread: Corresponding pads from middle active symmetrically.  
        """
        kwargs['name'] = kwargs.get('name', f'Fader_{Fader._count}')
        self.direction = kwargs.get('direction', Fader.Direction.Vertical)
        self.grid = kwargs.get('grid', Fader.Grid.Simple)
        self.type = kwargs.get('type', Fader.Type.Wrap)
        self.mode = kwargs.get('mode', Fader.Mode.Multi)
        self.resolution = kwargs.get('resolution', 4)
        super().__init__(x, y, width, height, **kwargs)
        self._multiStep = 0
        self._oldButton = [-1, -1]
        self._heldButton = [-1, -1]
        Fader._count += 1

    def pressed(self, x: int, y: int, value: float):
        super().pressed(x, y, value)
        if self.mode == Fader.Mode.Simple:
            self.setValue(self._pressedSimple(x, y, value))
        elif self.mode == Fader.Mode.Multi:
            self.setValue(self._pressedMulti(x, y, value))
        elif self.mode == Fader.Mode.Magnitude:
            self.setValue(self._pressedMagnitude(x, y, value))
        elif self.mode == Fader.Mode.Sensitive:
            self.setValue(self._pressedSensitive(x, y, value))
        elif self.mode == Fader.Mode.Relative:
            self.setValue(self._pressedRelative(x, y, value))
        self.updated = True
    
    def _pressedSimple(self, x, y, value):
        if self.type == Fader.Type.BoostCut:
            if self._minV[x][y] < 0.5:
                return self._minV[x][y]
            else:
                return self._maxV[x][y]
        else:
            return self._minV[x][y]

    def _pressedMulti(self, x, y, value):
        if self.type == Fader.Type.BoostCut:
            if self._minV[x][y] < 0.5:
                if self._oldButton[0] == x and self._oldButton[1] == y:
                    self._multiStep = (self._multiStep - 1) % self.resolution
                else:
                    self._oldButton = [x, y]
                    self._multiStep = self.resolution - 1
                return self._calcFaderValue(x, y, self._multiStep / self.resolution)
            else:
                if self._oldButton[0] == x and self._oldButton[1] == y:
                    self._multiStep = (self._multiStep + 1) % self.resolution
                else:
                    self._oldButton = [x, y]
                    self._multiStep = 0
                return self._calcFaderValue(x, y, self._multiStep / self.resolution)
        elif self.type == Fader.Type.Collapse:
            if self._oldButton[0] == x and self._oldButton[1] == y:
                self._multiStep = (self._multiStep - 1) % self.resolution
            else:
                self._oldButton = [x, y]
                self._multiStep = self.resolution - 1
            return self._calcFaderValue(x, y, self._multiStep / self.resolution)
        else:
            if self._oldButton[0] == x and self._oldButton[1] == y:
                self._multiStep = (self._multiStep + 1) % self.resolution
            else:
                self._oldButton = [x, y]
                self._multiStep = 0
            return self._calcFaderValue(x, y, self._multiStep / self.resolution)

    def _pressedMagnitude(self, x, y, value):
        return self._calcFaderValue(x, y, self._calcFaderMagnitude(x, y))

    def _pressedSensitive(self, x, y, value):
        if self.type == Fader.Type.BoostCut:
            if self._minV[x][y] < 0.5:
                return self._calcFaderValue(x, y, 1.0 - value)
            else:
                return self._calcFaderValue(x, y, value)
        elif self.type == Fader.Type.Collapse:
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
        super().held(x, y, value)
        if self.mode != Fader.Mode.Relative:
            if x == 0 and y == 0:
                self.setValue(0.0)
            elif x == self.rect.w - 1 and y == self.rect.h - 1:
                self.setValue(1.0)
            else:
                self.setValue(0.5)
        self.updated = True
    
    def released(self, x: int, y: int, value: float):
        super().released(x, y, value)
        if self._heldButton[0] == x and self._heldButton[1] == y:
            self._heldButton = [-1, -1]

    def updateArea(self, rect: PyxelWidgets.Helpers.Rectangle2D):
        halfval = self._value / 2.0
        halfvalpluspointfive = halfval + 0.5
        intersect = self.rect.intersect(rect)
        if intersect is not None:
            area = intersect - self.rect
            if self.bufferUpdated:
                self.bufferUpdated = False
                for x in area.columns:
                    for y in area.rows:
                        minV = self._minV[x][y]
                        maxV = self._maxV[x][y]
                        if self.type == Fader.Type.Single:
                            # if current pad lower than last pressed pad
                            if maxV <= self._value:
                                self.buffer[x, y] = self.deactiveColor
                            # if current pad higher than last pressed pad
                            elif minV > self._value:
                                self.buffer[x, y] = self.deactiveColor
                            # if current pad is last pressed pad
                            else:
                                coefficient = min(self._calcPixelCoefficient(self._value - minV) + self._calcPixelStep(), 1.0)
                                self.buffer[x, y] = self.activeColor * coefficient
                        elif self.type == Fader.Type.BoostCut:
                            # if last pressed pad in upper half
                            if self._value > 0.5:
                                # if current pad in lower half
                                if minV < 0.5:
                                    self.buffer[x, y] = self.deactiveColor
                                # if current pad in upper half
                                else:
                                    # if current pad is lower than last pressed pad
                                    if maxV <= self._value:
                                        self.buffer[x, y] = self.activeColor
                                    # if current pad is higher than last pressed pad
                                    elif minV > self._value:
                                        self.buffer[x, y] = self.deactiveColor
                                    # if current pad is last pressed pad
                                    else:
                                        coefficient = min(self._calcPixelCoefficient(self._value - minV) + self._calcPixelStep(), 1.0)
                                        self.buffer[x, y] = self.activeColor * coefficient
                            # if last pressed pad in lower half
                            elif self._value < 0.5:
                                # if current pad in upper half
                                if maxV > 0.5:
                                    self.buffer[x, y] = self.deactiveColor
                                # if current pad in lower half
                                else:
                                    # if current pad is higher than last pressed pad
                                    if minV >= self._value:
                                        self.buffer[x, y] = self.activeColor
                                    # if current pad is lower than last pressed pad
                                    elif maxV < self._value:
                                        self.buffer[x, y] = self.deactiveColor
                                    # if current pad is last pressed pad
                                    else:
                                        # reverse brightness to match type
                                        coefficient = 1.0 - self._calcPixelCoefficient(self._value - minV)
                                        self.buffer[x, y] = self.activeColor * coefficient
                            # if current value is 0.5
                            else:
                                # lit middle pad(s)
                                if minV == 0.5 or maxV == 0.5:
                                    self.buffer[x, y] = self.activeColor
                                # unlit every other pad
                                else:
                                    self.buffer[x, y] = self.deactiveColor
                        elif self.type == Fader.Type.Wrap:
                            # if current pad lower than last pressed pad
                            if maxV <= self._value:
                                self.buffer[x, y] = self.activeColor
                            # if current pad higher than last pressed pad
                            elif minV > self._value:
                                self.buffer[x, y] = self.deactiveColor
                            # if current pad is last pressed pad
                            else:
                                coefficient = min(self._calcPixelCoefficient(self._value - minV) + self._calcPixelStep(), 1.0)
                                self.buffer[x, y] = self.activeColor * coefficient
                        elif self.type == Fader.Type.Spread:
                            # if current pad in upper half
                            if minV >= 0.5:
                                # if current pad higher than current value
                                if minV > halfvalpluspointfive:
                                    self.buffer[x, y] = self.deactiveColor
                                # if current pad lower than current value
                                elif maxV <= halfvalpluspointfive:
                                    self.buffer[x, y] = self.activeColor
                                # if current value is in current pad's boundary
                                else:
                                    coefficient = self._calcPixelCoefficient(halfvalpluspointfive - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                            # if current pad in lower half
                            elif maxV <= 0.5:
                                # if current pad higher than current value
                                if minV >= (1.0 - halfvalpluspointfive):
                                    self.buffer[x, y] = self.activeColor
                                # if current pad lower than current value
                                elif maxV < (1.0 - halfvalpluspointfive):
                                    self.buffer[x, y] = self.deactiveColor
                                # if current value is in current pad's boundary
                                else:
                                    coefficient = 1.0 - self._calcPixelCoefficient((1.0 - halfvalpluspointfive) - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                        elif self.type == Fader.Type.Collapse:
                            # if current pad in upper half
                            if minV >= 0.5:
                                # if current pad lower than current value
                                if minV >= (1.0 - halfval):
                                    self.buffer[x, y] = self.deactiveColor
                                # if current pad higher than current value
                                elif maxV < (1.0 - halfval):
                                    self.buffer[x, y] = self.activeColor
                                # if current value is in current pad's boundary
                                else:
                                    coefficient = self._calcPixelCoefficient((1.0 - halfval) - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                            # if current pad in lower half
                            elif maxV <= 0.5:
                                # if current pad lower than current value
                                if minV > halfval:
                                    self.buffer[x, y] = self.activeColor
                                # if current pad higher than current value
                                elif maxV <= halfval:
                                    self.buffer[x, y] = self.deactiveColor
                                # if current value is in current pad's boundary
                                else:
                                    coefficient = 1.0 - self._calcPixelCoefficient(halfval - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                if self.effect is None:
                    return intersect, self.buffer[area.slice]
            if self.effect is not None:
                return intersect, self.effect.apply(self.buffer[area.slice])
        return None, None

    def _resize(self, width, height):
        self._minV = [[self._calcFaderValue(x, y, 0.0) for y in range(height)] for x in range(width)]
        self._maxV = [[self._calcFaderValue(x, y, 1.0) for y in range(height)] for x in range(width)]
        return True

    """
        For 2-d widgets, where output values are single float,
        we must calculate single float from 2-d area.
        Calculation done from left to right, bottom to top in order
        to get final value for vertical faders. its basically (y * step) + x.
        Vertical matrix faders are left to right, bottom to up in order.
        Horizontal matrix faders are bottom to up, left to right in order.
        Simple faders are bottom to up for vertical, left to right for horizontal.
    """
    def _calcFaderValue(self, x: int, y: int, value: float) -> float:
        """Calculate fader value from pad location"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return round(((y / self.rect.h) + (value / self.rect.h)), 6)
            elif self.direction == Fader.Direction.Horizontal:
                return round(((x / self.rect.w) + (value / self.rect.w)), 6)
        elif self.grid == Fader.Grid.Matrix:
            if self.direction == Fader.Direction.Vertical:
                base = (x / (self.rect.h * self.rect.w)) + (y / self.rect.h)
            elif self.direction == Fader.Direction.Horizontal:
                base = (y / (self.rect.h * self.rect.w)) + (x / self.rect.w)
            return round(base + (value / (self.rect.w * self.rect.h)), 6)
    
    def _calcFaderMagnitude(self, x: int, y: int) -> float:
        """Calculate pad magnitude from pad location"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return self._calcFaderValue(x, y, y / (self.rect.h - 1))
            elif self.direction == Fader.Direction.Horizontal:
                return self._calcFaderValue(x, y, x / (self.rect.w - 1))
        elif self.grid == Fader.Grid.Matrix:
            if self.direction == Fader.Direction.Vertical:
                base = (x / ((self.rect.h * self.rect.w) - 1)) + (y / (self.rect.h - 1))
            elif self.direction == Fader.Direction.Horizontal:
                base = (y / ((self.rect.h * self.rect.w) - 1)) + (x / (self.rect.w - 1))
            return self._calcFaderValue(x, y, base)
    
    def _calcPixelCoefficient(self, value: float) -> float:
        """Calculate pixel coefficient for different fader options"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return (value * self.rect.h)
            elif self.direction == Fader.Direction.Horizontal:
                return (value * self.rect.w)
        elif self.grid == Fader.Grid.Matrix:
            return (value * (self.rect.h * self.rect.w))
    
    def _calcPixelStep(self):
        if self.mode == Fader.Mode.Simple:
            return 0.5
        elif self.mode == Fader.Mode.Multi:
            return 1.0 / self.resolution
        elif self.mode == Fader.Mode.Magnitude:
            return 1.0 / 256
        elif self.mode == Fader.Mode.Sensitive:
            return 1.0 / 256
        elif self.mode == Fader.Mode.Relative:
            if self.grid == Fader.Grid.Simple:
                if self.direction == Fader.Direction.Vertical:
                    return 1.0/ self.rect.h
                elif self.direction == Fader.Direction.Horizontal:
                    return 1.0 / self.rect.w
            elif self.grid == Fader.Grid.Matrix:
                return 1.0 / (self.rect.w * self.rect.h)