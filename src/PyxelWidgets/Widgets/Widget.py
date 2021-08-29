import uuid
from copy import deepcopy

class Widget:
    def __init__(self, name: str, width: int = 1, height: int = 1, **kwargs):
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
        self._id = uuid.uuid1()
        self._name = name
        self._width = 1 if width < 1 else width
        self._height = 1 if height < 1 else height
        self._callback = kwargs.get('callback', lambda *_, **__: None)
        self._activeColor = kwargs.get('activeColor', [255, 255, 255])
        self._deactiveColor = kwargs.get('deactiveColor', [0, 0, 0])
        self._value = 0.0
        self._delta = 0.0
        self._updated = True
        self._pixels = [[[0, 0, 0] for y in range(self.height)] for x in range(self.width)]

    @property
    def id(self) -> str:
        return self._id.hex

    @property
    def name(self) -> str:
        return self._name

    @property
    def width(self) -> int:
        return self._width
    
    @width.setter
    def width(self, value: int) -> None:
        if value > 0:
            if self._resize(value, self.height):
                self._width = value
                self._pixels = [[[0, 0, 0] for y in range(self.height)] for x in range(self.width)]
                self._updated = True
                self._callback(self.name, 'resized', (self.width, self.height))

    @property
    def height(self) -> int:
        return self._height
    
    @height.setter
    def height(self, value: int) -> None:
        if value > 0:
            if self._resize(self.width, value):
                self._height = value
                self._pixels = [[[0, 0, 0] for y in range(self.height)] for x in range(self.width)]
                self._updated = True
                self._callback(self.name, 'resized', (self.width, self.height))

    @property
    def value(self) -> float or list:
        return self._value
    
    @value.setter
    def value(self, value: float or list) -> None:
        if value != self._value:
            if isinstance(self._value, list):
                oldValue = deepcopy(self._value)
                for i, val in enumerate(value):
                    self._value[i] = round(min(1.0, max(0.0, val)), 6)
            else:
                oldValue = self._value
                self._value = round(min(1.0, max(0.0, value)), 6)
            if self._value != oldValue:
                self._updated = True
                self._callback(self.name, 'changed', self._value)
    
    @property
    def delta(self) -> float or list:
        if isinstance(self._value, list):
            deltas = deepcopy(self._value)
            for i in range(len(self._value)):
                deltas[i] = round(deltas[i] - self._delta[i], 6)
            return deltas
        return round(self._value - self._delta, 6)

    @property
    def activeColor(self) -> list:
        return self._activeColor
    
    @activeColor.setter
    def activeColor(self, color: list):
        self._activeColor = color
    
    @property
    def deactiveColor(self) -> list:
        return self._deactiveColor
    
    @deactiveColor.setter
    def deactiveColor(self, color: list):
        self._deactiveColor = color

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
        return self.updateArea(0, 0, self.width, self.height)
    
    def _resize(self, width, height) -> bool:
        return True