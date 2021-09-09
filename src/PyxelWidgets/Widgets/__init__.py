__all__ = ['Button', 'Fader', 'Knob', 'Life', 'Sequencer', 'XY', 'Extra']

from ..Helpers import *
import uuid
from copy import deepcopy

class Widget:

    _count = 0

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, **kwargs):
        """
        Parameters
        ----
        name: str
            Unique widget name, used to find widgets registered on window and
             callbacks returning widget value when changed
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
             Should get 2 parameters, (widget) name and value
        activeColor: [r: int, g: int, b: int] = [255, 255, 255]
            If widget value is non-zero, this color will be used
        deactiveColor: [r: int, g: int, b: int] = [0, 0, 0]
            If widget value is zero, this color will be used
        value: int = 0.0
            Default value of widget
        """
        self.id = uuid.uuid1()
        self.name = kwargs.get('name', 'Widget_' + str(Widget._count))
        self.rect = Rectangle2D(x, y, width, height)
        self.activeColor = kwargs.get('activeColor', [255, 255, 255])
        self.deactiveColor = kwargs.get('deactiveColor', [0, 0, 0])
        self.delta = 0.0
        self.updated = True
        self.buffer = [[[0, 0, 0] for y in range(self.rect.h)] for x in range(self.rect.w)]
        self._value = 0.0
        self._callback = kwargs.get('callback', lambda *_, **__: None)

    @property
    def width(self) -> int:
        return self.rect.w
    
    @width.setter
    def width(self, value: int) -> None:
        if value > 0:
            if self._resize(value, self.rect.h):
                self.rect.w = value
                self.buffer = [[[0, 0, 0] for y in range(self.rect.h)] for x in range(self.rect.w)]
                self.updated = True
                self._callback(self.name, 'resized', (self.rect.w, self.rect.h))

    @property
    def height(self) -> int:
        return self.rect.h
    
    @height.setter
    def height(self, value: int) -> None:
        if value > 0:
            if self._resize(self.rect.w, value):
                self.rect.h = value
                self.buffer = [[[0, 0, 0] for y in range(self.rect.h)] for x in range(self.rect.w)]
                self.updated = True
                self._callback(self.name, 'resized', (self.rect.w, self.rect.h))

    @property
    def value(self) -> float or list:
        return self._value
    
    @value.setter
    def value(self, value: float or list) -> None:
        if value != self._value:
            oldValue = self._value
            self._value = round(min(1.0, max(0.0, value)), 6)
            self.delta = self._value - oldValue
            if self._value != oldValue:
                self.updated = True
                self._callback(self.name, 'changed', self._value)

    def setCallback(self, callback) -> None:
        self._callback = callback

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
        self._callback(self.name, 'pressed', (x, y))
    
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
        self._callback(self.name, 'released', (x, y))
    
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
        self._callback(self.name, 'held', (x, y))
    
    def updateArea(self, sx, sy, sw, sh):
        return []

    def update(self) -> list:
        """
        Description
        ----
        At every Window update
         Window will call this function
          This function must return updated pixel values
           Pixel list should [x][y][r, g, b]
            If nothing is updated return empty list
        """
        return self.updateArea(0, 0, self.rect.w, self.rect.h)
    
    def _resize(self, width, height) -> bool:
        return True