class Widget:
    def __init__(self, name: str, x: int = 0, y: int = 0, width: int = 1, height: int = 1, **kwargs):
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
        self._name = name
        self._x = 0 if x < 0 else x
        self._y = 0 if y < 0 else y
        self._width = 1 if width < 1 else width
        self._height = 1 if height < 1 else height
        self._callback = kwargs.get('callback', lambda *_, **__: None)
        self._activeColor = kwargs.get('activeColor', [255, 255, 255])
        self._deactiveColor = kwargs.get('deactiveColor', [0, 0, 0])
        self._value = 0.0
        self._oldValue = -1
        self._pixels = [[[0, 0, 0] for y in range(self.height)] for x in range(self.width)]

    @property
    def name(self) -> str:
        return self._name

    @property
    def x(self) -> int:
        return self._x
    
    @x.setter
    def x(self, x: int) -> None:
        self._x = max(0, x)
    
    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, y: int) -> None:
        self._y = max(0, y)

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
        if isinstance(value, list):
            self._value = []
            for val in value:
                self._value.append(0.0 if val < 0.0 else (1.0 if val > 1.0 else val))
        else:
            self._value = 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)
        self._callback(self.name, value)
    
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
        pass
    
    def released(self, x: int, y: int):
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
        pass
    
    def held(self, x: int, y: int):
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
        pass
    
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
        pass
    
    def forceUpdate(self):
        self._pixels = [[[0, 0, 0] for y in range(self.height)] for x in range(self.width)]
        self._oldValue = -1

    def print(self) -> None:
        for y in reversed(range(self.height)):
            print(end = ">|")
            for x in range(self.width):
                print("0x{:02X},0x{:02X},0x{:02X}".format(self._pixels[x][y][0], self._pixels[x][y][1], self._pixels[x][y][2]), end='|')
            print()
            print()