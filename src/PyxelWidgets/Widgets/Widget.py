import uuid

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
        self._oldValue = -1
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

    @property
    def height(self) -> int:
        return self._height

    @property
    def value(self) -> float or list:
        return self._value
    
    @value.setter
    def value(self, value: float or list) -> None:
        self._delta = self._value
        if value != self._value:
            if isinstance(value, list):
                self._value = []
                for i, val in enumerate(value):
                    self._value[i] = round(min(1.0, max(0.0, val)), 6)
            else:
                self._value = round(min(1.0, max(0.0, value)), 6)
        if self._value != self._delta:
            self._callback(self.name, 'changed', self._value)
    
    @property
    def delta(self) -> float or list:
        if isinstance(self._value, list):
            deltas = [0.0] * len(self._value)
            for i in range(len(self._value)):
                deltas[i] = self._value[i] - self._delta[i]
            return deltas
        return self._value - self._delta

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
        self._callback(self.name, 'pressed', True)
    
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
        self._callback(self.name, 'released', True)
    
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
        self._callback(self.name, 'held', True)
    
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
        return []