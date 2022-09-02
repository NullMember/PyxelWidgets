__all__ = ['Button', 'ButtonGroup', 'Fader', 'Keyboard', 'Knob', 'Sequencer', 'Sprite', 'Tracker', 'XY']

import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import PyxelWidgets.Utils.Effect
import uuid
import numpy

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