import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import PyxelWidgets.Utils.Effect
import uuid
import numpy
import enum

class Widget:
    """
    Base class for all Widgets.
    """
    _count = 0

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, **kwargs):
        """
        Widget Constructor
        ------------------
        
        Parameters
        ----------
        x: int
            x axis where widget will be placed on window, from left to right.
            x value should be positive.
        y: int
            y axis where widget will be placed on window, from bottom to top.
            y value should be positive.
        width: int
            Widget width, should >= 1
        height: int
            Widget height, should >= 1
        name: str, optional
            Unique widget name, used to find widgets registered on window and
            callbacks returning widget value when changed.
        callback: function, optional
            If widget value is changed this function will be called.
            Should get 3 parameters, (widget) name, event and value
        activeColor: Pixel = Pixel(255, 255, 255, 1.0), optional
            If widget value is non-zero, this color will be used.
        deactiveColor: Pixel = Pixel(0, 0, 0, 0.0), optional
            If widget value is zero, this color will be used.
        value: float = 0.0, optional
            Default value of widget.
        
        Returns
        -------
        Widget
            new Widget instance
        """    
        self.id = uuid.uuid1()
        self.name = kwargs.get('name', f'Widget_{Widget._count}')
        self.rect = PyxelWidgets.Utils.Rectangle.Rectangle2D(x, y, width, height)
        self.activeColor = kwargs.get('activeColor', PyxelWidgets.Utils.Pixel.Colors.White)
        self.deactiveColor = kwargs.get('deactiveColor', PyxelWidgets.Utils.Pixel.Colors.Black)
        self.delta = 0.0
        self.updated = True
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), PyxelWidgets.Utils.Pixel.Pixel)
        self.buffer.fill(self.deactiveColor)
        self.lock = kwargs.get('lock', False)
        self._value = kwargs.get('value', 0.0)
        self._oldValue = self._value
        self.callback = kwargs.get('callback', lambda *_, **__: None)
        self._resize(self.rect.w, self.rect.h)

    @property
    def width(self) -> int:
        return self.rect.w
    
    @width.setter
    def width(self, value: int) -> None:
        if value > 0:
            if self._resize(value, self.rect.h):
                self.rect.w = value
                self.buffer.resize((self.rect.w, self.rect.h), refcheck = False)
                self.buffer = numpy.where(self.buffer == 0, self.deactiveColor, self.buffer)
                self.updated = True
                self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Resized, (self.rect.w, self.rect.h))

    @property
    def height(self) -> int:
        return self.rect.h
    
    @height.setter
    def height(self, value: int) -> None:
        if value > 0:
            if self._resize(self.rect.w, value):
                self.rect.h = value
                self.buffer.resize((self.rect.w, self.rect.h), refcheck = False)
                self.buffer = numpy.where(self.buffer == 0, self.deactiveColor, self.buffer)
                self.updated = True
                self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Resized, (self.rect.w, self.rect.h))

    @property
    def value(self) -> float:
        return self._value
    
    @value.setter
    def value(self, value: float) -> None:
        if value != self._value:
            self._oldValue = self._value
            self._value = round(min(1.0, max(0.0, value)), 6)
            self.delta = self._value - self._oldValue
            if self._value != self._oldValue:
                self.updated = True
    
    def setValue(self, value: float):
        if not self.lock:
            self.value = value
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Changed, round(min(1.0, max(0.0, value)), 6))

    def setCallback(self, callback) -> None:
        self.callback = callback

    def process(self, name, event, data):
        if event != PyxelWidgets.Utils.Enums.Event.Custom:
            x, y, value = data
            btn = PyxelWidgets.Utils.Rectangle.Rectangle2D(x, y)
            if btn.collide(self.rect):
                btn = btn - self.rect
                if event == PyxelWidgets.Utils.Enums.Event.Pressed:
                    self.pressed(btn.x, btn.y, value)
                elif event == PyxelWidgets.Utils.Enums.Event.Released:
                    self.released(btn.x, btn.y, value)
                elif event == PyxelWidgets.Utils.Enums.Event.Held:
                    self.held(btn.x, btn.y, value)
                elif event == PyxelWidgets.Utils.Enums.Event.DoublePressed:
                    self.doublePressed(btn.x, btn.y, value)

    def press(self, x: int, y: int, value: float):
        return
    
    def pressed(self, x: int, y: int, value: float):
        """
        Description
        ----
        If last pressed button was on this Widget
         Window will call this function
        
        Parameters
        ----
        x: int
            x axis of button location on Widget
        y: int
            y axis of button location on Widget
        value: float
            Value of the pressed button, useful for velocity sensitive pads
             Could be 1 for non velocity sensitive pads
        """
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Pressed, (x, y))
        self.press(x, y, value)
    
    def release(self, x: int, y: int, value: float):
        return
    
    def released(self, x: int, y: int, value: float):
        """
        Description
        ----
        If last released button was on this Widget
         Window will call this function
        
        Parameters
        ----
        x: int
            x axis of button location on Widget
        y: int
            y axis of button location on Widget
        value: float
            Value of the released button, useful for velocity sensitive pads
             Could be 0 for non velocity sensitive pads
        """
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Released, (x, y))
        self.release(x, y, value)
    
    def hold(self, x: int, y: int, value: float):
        return
    
    def held(self, x: int, y: int, value: float):
        """
        Description
        ----
        If last held button was on this Widget
         Window will call this function
        
        Parameters
        ----
        x: int
            x axis of button location on Widget
        y: int
            y axis of button location on Widget
        """
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Held, (x, y))
        self.hold(x, y, value)
    
    def doublePress(self, x: int, y: int, value: float):
        return
    
    def doublePressed(self, x: int, y: int, value: float):
        """
        Description
        ----
        If last double pressed button was on this Widget
         Window will call this function
        
        Parameters
        ----
        x: int
            x axis of button location on Widget
        y: int
            y axis of button location on Widget
        value: float
            Value of the double pressed button, useful for velocity sensitive pads
            Could be 1 for non velocity sensitive pads
        """
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.DoublePressed, (x, y))
        self.doublePress(x, y, value)
    
    def tap(self, x: int, y: int, pressValue: float = 1.0, releaseValue: float = 0.0):
        self.press(x, y, pressValue)
        self.release(x, y, releaseValue)
    
    def tapped(self, x: int, y: int, pressValue: float = 1.0, releaseValue: float = 0.0):
        self.pressed(x, y, pressValue)
        self.released(x, y, releaseValue)

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D) -> tuple:
        return rect, self.buffer[rect.slice]

    def update(self) -> tuple:
        """
        Description
        ----
        At every Window update
         Window will call this function
          This function must return updated pixel values
           Pixel list should [x][y][r, g, b]
            If nothing is updated return empty list
        """
        return self.updateArea(self.rect)
    
    def _resize(self, width, height) -> bool:
        return True

# Button class
class Button(Widget):
    class Mode(enum.Enum):
        Button  = enum.auto()
        Switch  = enum.auto()
        Mixed   = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Button_{Button._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.mode = kwargs.get('mode', Button.Mode.Button)
        self.state = False
        self.isHold = False
        Button._count += 1

    def press(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Button:
            self.setValue(value)
        elif self.mode == Button.Mode.Switch:
            if self.state:
                self.setValue(0.0)
                self.state = False
            else:
                self.setValue(value)
                self.state = True
        elif self.mode == Button.Mode.Mixed:
            if self.isHold:
                return
            else:
                self.setValue(value)
    
    def release(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Button:
            self.setValue(0.0)
        elif self.mode == Button.Mode.Switch:
            pass
        elif self.mode == Button.Mode.Mixed:
            if self.isHold:
                return
            else:
                self.setValue(0.0)
    
    def hold(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Mixed:
            self.isHold = not self.isHold

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                self.buffer[area.slice].fill(self.activeColor * self._value if self._value else self.deactiveColor)
                return intersect, self.buffer[area.slice]
        return None, None

# ButtonGroup class
class ButtonGroup(Widget):

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

# Fader class
class Fader(Widget):

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

    def press(self, x: int, y: int, value: float):
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

    def hold(self, x: int, y: int, value: float):
        if self.mode != Fader.Mode.Relative:
            if x == 0 and y == 0:
                self.setValue(0.0)
            elif x == self.rect.w - 1 and y == self.rect.h - 1:
                self.setValue(1.0)
            else:
                self.setValue(0.5)
        self.updated = True
    
    def release(self, x: int, y: int, value: float):
        if self._heldButton[0] == x and self._heldButton[1] == y:
            self._heldButton = [-1, -1]

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        if self.updated:
            self.updated = False
            halfval = self._value / 2.0
            halfvalpluspointfive = halfval + 0.5
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
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
                return intersect, self.buffer[area.slice]
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
                base = (x / self.rect.area) + (y / self.rect.h)
            elif self.direction == Fader.Direction.Horizontal:
                base = (y / self.rect.area) + (x / self.rect.w)
            return round(base + (value / self.rect.area), 6)
    
    def _calcFaderMagnitude(self, x: int, y: int) -> float:
        """Calculate pad magnitude from pad location"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return self._calcFaderValue(x, y, y / (self.rect.h - 1))
            elif self.direction == Fader.Direction.Horizontal:
                return self._calcFaderValue(x, y, x / (self.rect.w - 1))
        elif self.grid == Fader.Grid.Matrix:
            if self.direction == Fader.Direction.Vertical:
                base = (x / (self.rect.area - 1)) + (y / (self.rect.h - 1))
            elif self.direction == Fader.Direction.Horizontal:
                base = (y / (self.rect.area - 1)) + (x / (self.rect.w - 1))
            return self._calcFaderValue(x, y, base)
    
    def _calcPixelCoefficient(self, value: float) -> float:
        """Calculate pixel coefficient for different fader options"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return (value * self.rect.h)
            elif self.direction == Fader.Direction.Horizontal:
                return (value * self.rect.w)
        elif self.grid == Fader.Grid.Matrix:
            return (value * self.rect.area)
    
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
                return 1.0 / self.rect.area

# Keyboard class
class Keyboard(Widget):

    class Type(enum.Enum):
        Keyboard            = 0
        ChromaticVertical   = 1
        ChromaticHorizontal = 2
        Diatonic            = 3
        DiatonicVertical    = 4
        DiatonicHorizontal  = 5

    class Scale(enum.Enum):
        Major           = 0
        Minor           = 1
        Dorian          = 2
        Mixolydian      = 3
        Lydian          = 4
        Phrygian        = 5
        Locrian         = 6
        Diminished      = 7
        WholeHalf       = 8
        WholeTone       = 9
        MinorBlues      = 10
        MinorPentatonic = 11
        MajorPentatonic = 12
        MinorHarmonic   = 13
        MinorMelodic    = 14

    class Root(enum.Enum):
        C   = 0
        CS  = 1
        D   = 2
        DS  = 3
        E   = 4
        F   = 5
        FS  = 6
        G   = 7
        GS  = 8
        A   = 9
        AS  = 10
        B   = 11

    Scales = {
        'Major': [0, 2, 4, 5, 7, 9, 11],
        'Minor': [0, 2, 3, 5, 7, 8, 10],
        'Dorian': [0, 2, 3, 5, 7, 9, 10],
        'Mixolydian': [0, 2, 4, 5, 7, 9, 10],
        'Lydian': [0, 2, 4, 6, 7, 9, 11],
        'Phrygian': [0, 1, 3, 5, 7, 8, 10],
        'Locrian': [0, 1, 3, 5, 6, 8, 10],
        'Diminished': [0, 1, 3, 4, 6, 7, 9, 10],
        'WholeHalf': [0, 2, 3, 5, 6, 8, 9, 11],
        'WholeTone': [0, 2, 4, 6, 8, 10],
        'MinorBlues': [0, 3, 5, 6, 7, 10],
        'MinorPentatonic': [0, 3, 5, 7, 10],
        'MajorPentatonic': [0, 2, 4, 7, 9],
        'MinorHarmonic': [0, 2, 3, 5, 7, 8, 11],
        'MinorMelodic': [0, 2, 3, 5, 7, 9, 11],

        'Keyboard': [0, 2, 4, 5, 7, 9, 11],
        'KeyboardUpper': [-1, 1, 3, -1, 6, 8, 10]
    }

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Keyboard_{Keyboard._count}')
        self._octave = kwargs.get('octave', 0)
        self._fold = kwargs.get('fold', 4)
        self._type: Keyboard.Type = kwargs.get('type', Keyboard.Type.Diatonic)
        self._scale: Keyboard.Scale = kwargs.get('scale', Keyboard.Scale.Major)
        self._root: Keyboard.Root = kwargs.get('root', Keyboard.Root.C)
        self._rootColor: PyxelWidgets.Utils.Pixel.Pixel = kwargs.get('rootColor', PyxelWidgets.Utils.Pixel.Colors.Magenta)
        self._keyboardColor: PyxelWidgets.Utils.Pixel.Pixel = kwargs.get('keyboardColor', PyxelWidgets.Utils.Pixel.Colors.Cyan)
        self._nonScaleColor: PyxelWidgets.Utils.Pixel.Pixel = kwargs.get('nonScaleColor', PyxelWidgets.Utils.Pixel.Colors.Yellow)
        kwargs['activeColor'] = kwargs.get('activeColor', PyxelWidgets.Utils.Pixel.Colors.Green)
        self.buttons = None
        self.notes = None
        self.colors = None
        self.states = None
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        Keyboard._count += 1

    @property
    def octave(self):
        return self._octave
    
    @octave.setter
    def octave(self, octave: int):
        self._octave = octave
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def fold(self):
        return self._fold
    
    @fold.setter
    def fold(self, fold: int):
        self._fold = fold
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def type(self):
        return self._type
    
    @type.setter
    def type(self, mode: Type):
        self._type = mode
        self._resize(self.width, self.height)
        self.updated = True
    
    @property
    def scale(self):
        return self._scale
    
    @scale.setter
    def scale(self, scale: Scale):
        self._scale = scale
        self._resize(self.width, self.height)
        self.updated = True
    
    @property
    def root(self):
        return self._root
    
    @root.setter
    def root(self, root: Root):
        self._root = root
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def rootColor(self):
        return self._rootColor
    
    @rootColor.setter
    def rootColor(self, rootColor: PyxelWidgets.Utils.Pixel.Pixel):
        self._rootColor = rootColor
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def keyboardColor(self):
        return self._keyboardColor
    
    @keyboardColor.setter
    def keyboardColor(self, keyboardColor: PyxelWidgets.Utils.Pixel.Pixel):
        self._keyboardColor = keyboardColor
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def nonScaleColor(self):
        return self._nonScaleColor
    
    @nonScaleColor.setter
    def nonScaleColor(self, nonScaleColor: PyxelWidgets.Utils.Pixel.Pixel):
        self._nonScaleColor = nonScaleColor
        self._resize(self.width, self.height)
        self.updated = True

    def press(self, x: int, y: int, value: float):
        if self.notes[x, y] >= 0:
            for button in self.buttons[self.notes[x, y]]:
                self.states[button[0], button[1]] = True
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Changed, (self.notes[x, y], 1.0))
        self.updated = True
    
    def release(self, x: int, y: int, value: float):
        if self.notes[x, y] >= 0:
            for button in self.buttons[self.notes[x, y]]:
                self.states[button[0], button[1]] = False
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Changed, (self.notes[x, y], 0.0))
        self.updated = True
    
    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D) -> tuple:
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                for x in area.columns:
                    for y in area.rows:
                        note = self.notes[x, y]
                        if note >= 0:
                            if self.states[x, y]:
                                self.buffer[x, y] = self.activeColor
                            else:
                                self.buffer[x, y] = self.colors[note]
                        else:
                            self.buffer[x, y] = self.deactiveColor
                return intersect, self.buffer[area.slice]
        return None, None

    def _resize(self, width, height) -> bool:
        self.notes = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.states = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.colors = [PyxelWidgets.Utils.Pixel.Colors.Invisible for i in range(128)]
        self.buttons = [[] for i in range(128)]
        self._calcNotes()

    def _calcNotes(self):
        base = self._root.value + (self._octave * 12)
        scale = Keyboard.Scales[self._scale.name]
        precalc = []
        #precalculate scale values
        for i in range(self.rect.area):
            precalc.append(scale[i % len(scale)] + base + ((i // len(scale)) * 12))
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                #calculate notes
                if self._type == Keyboard.Type.Keyboard:
                    base = Keyboard.Root.C.value + (self._octave * 12)
                    length = 7 if 7 < self.rect.w else self.rect.w
                    if y % 2 == 0:
                        scale = Keyboard.Scales['Keyboard']
                    else:
                        scale = Keyboard.Scales['KeyboardUpper']
                    if scale[x % length] == -1:
                        self.notes[x, y] = -1
                    else:
                        self.notes[x, y] = scale[x % length] + base + ((y // 2) * 12) + ((x // length) * 12)
                elif self._type == Keyboard.Type.ChromaticVertical:
                    index = x + (y * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._type == Keyboard.Type.ChromaticHorizontal:
                    index = y + (x * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._type == Keyboard.Type.Diatonic:
                    self.notes[x, y] = precalc[x + (y * len(scale))]
                elif self._type == Keyboard.Type.DiatonicVertical:
                    self.notes[x, y] = precalc[x + (y * len(scale)) - (y * (len(scale) - self._fold + 1))]
                elif self._type == Keyboard.Type.DiatonicHorizontal:
                    self.notes[x, y] = precalc[y + (x * len(scale)) - (x * (len(scale) - self._fold + 1))]
                #clear notes 128 or higher
                if self.notes[x, y] > 127:
                    self.notes[x, y] = -1
                #make array from same buttons
                if self.notes[x, y] != -1:
                    self.buttons[self.notes[x, y]].append([x, y])
                #change colors
                if self.notes[x, y] != -1:
                    if (self.notes[x, y] - self._root.value) % 12 == 0:
                        self.colors[self.notes[x, y]] = self._rootColor
                    elif (self.notes[x, y] - self._root.value) % 12 in Keyboard.Scales[self._scale.name]:
                        self.colors[self.notes[x, y]] = self._keyboardColor
                    else:
                        self.colors[self.notes[x, y]] = self._nonScaleColor

# Knob class
class Knob(Widget):

    class Type(enum.Enum):
        Single      = enum.auto()
        BoostCut    = enum.auto()
        Wrap        = enum.auto()
        Spread      = enum.auto()
        Collapse    = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Knob_{Knob._count}')
        super().__init__(x, y, width, height, **kwargs)
        self.coefficient = kwargs.get('coefficient', 0.05)
        self.type = kwargs.get('type', Knob.Type.Wrap)
        self.state = False
        self._held = [-1, -1]
        Knob._count += 1

    def press(self, x: int, y: int, value: float):
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
                    self.setValue(0.5)
    
    def release(self, x: int, y: int, value: float):
        self._held = [-1, -1]
        self.state = False
    
    def tick(self):
        if self.state:
            index = self._calcKnobIndex(self._held[0], self._held[1])
            if index != -1:
                self.setValue(self._value + (self._calcKnobWeight(index) * self.coefficient))

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        if self.updated:
            if not self.state:
                self.updated = False
            else:
                self.tick()
            halfval = self._value / 2.0
            halfvalpluspointfive = halfval + 0.5
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                for x in area.columns:
                    for y in area.rows:
                        index = self.indexes[x][y]
                        minV = self._minV[index]
                        maxV = self._maxV[index]
                        if index == -1:
                            self.buffer[x, y] = PyxelWidgets.Utils.Pixel.Colors.Invisible
                        else:
                            if self.type == Knob.Type.Single:
                                if maxV < self._value:
                                    self.buffer[x, y] = self.deactiveColor
                                elif minV > self._value:
                                    self.buffer[x, y] = self.deactiveColor
                                else:
                                    coefficient = self._calcPixelCoefficient(self._value - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                            elif self.type == Knob.Type.BoostCut:
                                if self._value > 0.5:
                                    if minV < 0.5:
                                        self.buffer[x, y] = self.deactiveColor
                                    else:
                                        if maxV <= self._value:
                                            self.buffer[x, y] = self.activeColor
                                        elif minV > self._value:
                                            self.buffer[x, y] = self.deactiveColor
                                        else:
                                            coefficient = self._calcPixelCoefficient(self._value - minV)
                                            self.buffer[x, y] = self.activeColor * coefficient
                                elif self._value < 0.5:
                                    if maxV > 0.5:
                                        self.buffer[x, y] = self.deactiveColor
                                    else:
                                        if minV >= self._value:
                                            self.buffer[x, y] = self.activeColor
                                        elif maxV < self._value:
                                            self.buffer[x, y] = self.deactiveColor
                                        else:
                                            coefficient = 1.0 - self._calcPixelCoefficient(self._value - minV)
                                            self.buffer[x, y] = self.activeColor * coefficient
                                else:
                                    if minV == 0.5 or maxV == 0.5:
                                        self.buffer[x, y] = self.activeColor
                                    else:
                                        self.buffer[x, y] = self.deactiveColor
                            elif self.type == Knob.Type.Wrap:
                                if maxV <= self._value:
                                    self.buffer[x, y] = self.activeColor
                                elif minV > self._value:
                                    self.buffer[x, y] = self.deactiveColor
                                else:
                                    coefficient = self._calcPixelCoefficient(self._value - minV)
                                    self.buffer[x, y] = self.activeColor * coefficient
                            elif self.type == Knob.Type.Spread:
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
                            elif self.type == Knob.Type.Collapse:
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
            return intersect, self.buffer[area.slice]
        return None, None
    
    def _resize(self, width, height):
        self.perimeter = self._calcPerimeter(width, height)
        self.indexes = [[self._calcKnobIndex(x, y) for y in range(height)] for x in range(width)]
        self._minV = [self._calcKnobValue(index, 0.0) for index in range(self.perimeter)]
        self._maxV = [self._calcKnobValue(index, 1.0) for index in range(self.perimeter)]
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
            return round(-(0.5 - self._minV[index]), 6)
        else:
            return round(self._maxV[index] - 0.5, 6)

    def _calcPixelCoefficient(self, value: float) -> float:
        return value * self.perimeter
    
    def _calcPerimeter(self, width, height) -> float:    
        if width == 1:
            return height
        elif height == 1:
            return width
        return ((width - 1) * 2) + ((height - 1) * 2)

# Sequencer class
class Sequencer(Widget):
    def __init__(self, x: int, y: int, width: int, height: int, clock: PyxelWidgets.Utils.Clock.Clock = None, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Sequencer_{Sequencer._count}')
        self.state = numpy.ndarray((1, 1), dtype = numpy.bool8)
        self._steps = kwargs.get('steps', width * height)
        self._tick = 0
        self._pageCount = 1
        super().__init__(x, y, width, height, **kwargs)
        self.state.fill(False)
        self.currentPage = 0
        self._page = 0
        self.follow = True
        self.active = True
        self.note = kwargs.get('note', 4.0)
        self.beat = kwargs.get('beat', 4.0)
        self.ppq = kwargs.get('ppq', 24)
        self.currentColor = kwargs.get('currentColor', PyxelWidgets.Utils.Pixel.Colors.Lime)
        self.currentActiveColor = kwargs.get('currentActiveColor', PyxelWidgets.Utils.Pixel.Colors.Red)
        self.target = PyxelWidgets.Utils.Clock.Target(self.tick)
        if clock != None:
            self.addToClock(clock)
        Sequencer._count += 1
    
    def addToClock(self, clock: PyxelWidgets.Utils.Clock.Clock):
        self.ppq = clock.ppq
        clock.addTarget(self.target)
    
    @property
    def pages(self) -> int:
        return self._pageCount

    @property
    def page(self) -> int:
        return self._page

    @page.setter
    def page(self, value: int) -> None:
        self._page = value % self._pageCount
        self.updated = True

    @property
    def step(self) -> int:
        return self._tick
    
    @step.setter
    def step(self, value: int) -> None:
        self._tick = value % self._steps
        self.updated = True

    @property
    def steps(self) -> int:
        return self._steps

    @steps.setter
    def steps(self, value: int) -> None:
        self._steps = value
        self._pageCount = int((self._steps - 1) / self.rect.area) + 1
        self.state = numpy.zeros((self.rect.w, self.rect.h * self._pageCount), dtype = numpy.bool8)
        self._tick %= self._steps
        self.currentPage = int(self._tick / self.rect.area)

    @property
    def current(self) -> bool:
        self._tick
    
    @current.setter
    def current(self, state: bool) -> None:
        self.state[self._tickX(), self._tickY()] = state
        self.updated = True

    def tick(self, tick):
        if self.active:
            oldTick = self._tick
            self._tick = tick / (self.ppq * ((4.0 / self.note) / self.beat))
            self._tick %= self._steps
            if int(oldTick) != int(self._tick):
                page = int(self._tick / self.rect.area)
                if page != self.currentPage:
                    self.currentPage = page
                    self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Page, self.currentPage)
                self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Tick, int(self._tick))
                if self._isTickActive():
                    self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Active, int(self._tick))
                self.updated = True

    def press(self, x: int, y: int, value: float):
        if self._calcTickPosition(x, y) < self._steps:
            pageY = y + (self.rect.h * self._tickPage())
            self.state[x, pageY] = not self.state[x, pageY]
            self.updated = True

    def reset(self):
        self.state.fill(False)
        self.updated = True

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                tickP = self._tickPage()
                tickX = self._tickX()
                tickY = self._tickY() % self.rect.h
                stateArea = area + PyxelWidgets.Utils.Rectangle.Rectangle2D(0, self.rect.h * tickP)
                self.buffer[area.slice] = numpy.where(self.state[stateArea.slice] == True, self.activeColor, self.deactiveColor)
                if tickP == self.currentPage:
                    if self.buffer[tickX, tickY] == self.activeColor:
                        self.buffer[tickX, tickY] = self.currentActiveColor
                    else:
                        self.buffer[tickX, tickY] = self.currentColor
            return intersect, self.buffer[area.slice]
        return None, None
    
    def _resize(self, width, height):
        self._pageCount = int((self._steps - 1) / (width * height)) + 1
        self.state.resize((width, height * self._pageCount), refcheck = False)
        self._tick %= self._steps
        return True
    
    def _calcTickPosition(self, x, y):
        return (x + (y * self.rect.w)) + (self.rect.area * self._tickPage())
    
    def _tickPage(self):
        return self.currentPage if self.follow else self._page

    def _tickX(self):
        return int(self._tick) % self.rect.w
    
    def _tickY(self):
        return int(self._tick // self.rect.w)
    
    def _isTickActive(self):
        return self.state[self._tickX()][self._tickY()]
    
# Sprite class
class Sprite(Widget):
    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Sprite_{Sprite._count}')
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        self.animate = kwargs.get('animate', False)
        self.frames = kwargs.get('frames', None)
        self.target = kwargs.get('target', 30)
        self.tick = kwargs.get('tick', 0)
        self.currentFrame = 0
        self.nextFrame = 0
        if not isinstance(self.frames, numpy.ndarray):
            self.frames = [numpy.ndarray((self.rect.w, self.rect.h))]
            self.frames[0].fill(PyxelWidgets.Utils.Pixel.Colors.Invisible)
        self.buffer = self.frames[0]

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D):
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                self.buffer = self.frames[self.nextFrame]
                if self.animate:
                    self.tick += 1
                    if self.tick == self.target:
                        self.tick = 0
                        self.currentFrame = self.nextFrame
                        self.nextFrame += 1
                        if self.nextFrame == len(self.frames):
                            self.nextFrame = 0
                    self.updated = True
            return intersect, self.buffer[area.slice]
        return None, None

# Tracker class
class Tracker(Widget):

    # class Scroll(enum.Enum):
    #     Continuous = enum.auto()
    #     Page = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, clock: PyxelWidgets.Utils.Clock.Clock = None, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Tracker_{Tracker._count}')
        self.bars = kwargs.get('bars', 64)
        self.bars = self.bars if self.bars >= height else height
        self.pages = kwargs.get('pages', 1)
        self.pages = self.pages if self.pages > 0 else 1
        self.states = numpy.ndarray((1, 1, 1), dtype = numpy.bool8)
        self.currentBar = 0
        self.numerator = kwargs.get('numerator', 1.0)
        self.denominator = kwargs.get('denominator', 4.0)
        self.ppq = kwargs.get('ppq', 24)
        super().__init__(x, y, width, height, **kwargs)
        self.states.fill(False)
        self.currentTop = 0
        self.currentBottom = self.currentTop + self.height - 1
        self.currentPage = 0
        self.currentColor = kwargs.get('currentColor', PyxelWidgets.Utils.Pixel.Colors.Cyan)
        self.currentActiveColor = kwargs.get('currentActiveColor', PyxelWidgets.Utils.Pixel.Colors.Magenta)
        self.target = PyxelWidgets.Utils.Clock.Target(self.tick, name = self.name)
        if clock != None:
            self.addToClock(clock)
        Tracker._count += 1

    def addToClock(self, clock: PyxelWidgets.Utils.Clock.Clock):
        self.ppq = clock.ppq
        clock.addTarget(self.target)

    def press(self, x: int, y: int, value: float):
        self.states[self.currentPage, x, self.rect.h - 1 - y + self.currentTop] = not self.states[self.currentPage, x, self.rect.h - 1 - y + self.currentTop]
        self.updated = True

    def scroll(self, bar):
        self.tick(bar * (self.ppq * (self.numerator / self.denominator)))

    def tick(self, tick):
        oldBar = self.currentBar
        self.currentBar = tick / (self.ppq * (self.numerator / self.denominator))
        self.currentPage = int(self.currentBar / self.bars)
        self.currentPage %= self.pages
        self.currentBar %= self.bars
        if int(oldBar) != int(self.currentBar):
            self.updated = True
            self.currentBar = self.currentBar
            halfHeight = self.height // 2
            # if self.scroll == Tracker.Scroll.Continuous:
            corr = int(not (self.height % 2))
            if self.currentBar < halfHeight:
                self.currentTop = 0
                self.currentBottom = int(self.currentTop + self.height - 1)
            elif self.currentBar >= self.bars - halfHeight:
                self.currentTop = int(self.bars - self.height)
                self.currentBottom = int(self.bars - corr)
            else:
                self.currentTop = int(self.currentBar - (halfHeight - corr))
                self.currentBottom = int(self.currentBar + halfHeight)
            # elif self.scroll == Tracker.Scroll.Page:
            #     pass
            self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Tick, int(self.currentBar))
            for i, state in enumerate(self.states[self.currentPage, :, int(self.currentBar)]):
                if state:
                    self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Active, (int(self.currentBar), i))

    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D) -> tuple:
        if self.updated:
            self.updated = False
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                area = intersect - self.rect
                self.buffer[area.slice] = numpy.fliplr(numpy.where(self.states[self.currentPage, :, self.currentTop:(self.currentBottom + 1)] == True, self.activeColor, self.deactiveColor))
                self.buffer[:, int(self.currentBottom - self.currentBar)] = numpy.where(self.states[self.currentPage, :, int(self.currentBar)] == True, self.currentActiveColor, self.currentColor)
            return intersect, self.buffer[area.slice]
        return None, None

    def _resize(self, width, height) -> bool:
        self.states.resize((self.pages, width, self.bars), refcheck = False)
        self.tick(0)
        return True

# XY class
class XY(Widget):

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