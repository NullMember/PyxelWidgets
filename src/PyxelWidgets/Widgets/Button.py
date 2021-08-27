from .Widget import Widget
from enum import Enum

class ButtonMode(Enum):
    Button = 0
    Switch = 1
    Mixed = 2

class Button(Widget):
    def __init__(self, name: str, width: int, height: int, **kwargs):
        super().__init__(name, width, height, **kwargs)
        self._mode = kwargs.get('mode', ButtonMode.Button)
        self._held = False
        self._state = False

    def pressed(self, x: int, y: int, value: float):
        if self._mode == ButtonMode.Button:
            self.value = value
        elif self._mode == ButtonMode.Switch:
            if self._state:
                self.value = 0.0
                self._state = False
            else:
                self.value = value
                self._state = True
        elif self._mode == ButtonMode.Mixed:
            if self._held:
                return
            else:
                self.value = value
        super().pressed(x, y, self.value)
    
    def released(self, x: int, y: int, value: float):
        if self._mode == ButtonMode.Button:
            self.value = 0.0
        elif self._mode == ButtonMode.Switch:
            pass
        elif self._mode == ButtonMode.Mixed:
            if self._held:
                return
            else:
                self.value = 0.0
        super().released(x, y, self.value)
    
    def held(self, x: int, y: int, value: float):
        if self._mode == ButtonMode.Mixed:
            self._held = not self._held
        super().held(x, y, self.value)

    def update(self):
        if self._updated:
            self._updated = False
            for x in range(self.width):
                for y in range(self.height):
                    if self.value:
                        self._pixels[x][y] = [int(self._activeColor[0] * self.value), int(self._activeColor[1] * self.value), int(self._activeColor[2] * self.value)]
                    else:
                        self._pixels[x][y] = self._deactiveColor
            return self._pixels
        return []