from ..Button import Button

class ButtonGroup():
    def __init__(self, name: str, width: int, height: int, **kwargs):
        self.width = width
        self.height = height
        self.name = name
        self._buttons = [[Button(name + ',' + str(_x) + ',' + str(_y), \
                                1, \
                                1, \
                                **kwargs) \
                                for _y in range(height)] \
                                for _x in range(width)] 
        self._hold = kwargs.get('hold', True)
        self._deactiveColor = self._buttons[0][0].deactiveColor
        self._activeColor = self._buttons[0][0].activeColor
        self._lastButton = [-1, -1]
    
    @property
    def buttons(self):
        return self._buttons
    
    @property
    def widgets(self):
        return [y for x in self.buttons for y in x]
    
    @property
    def width(self):
        return self._width
    
    @width.setter
    def width(self, width: int):
        self._width = width
    
    @property
    def height(self):
        return self._height
    
    @height.setter
    def height(self, height: int):
        self._height = height
    
    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, name: str):
        self._name = name
    
    def setCallback(self, callback):
        for widget in self.widgets:
            widget.setCallback(callback)