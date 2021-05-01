from .Effect import Effect
from math import pi, sin

class Sine(Effect):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
    
    def update(self):
        super().update()
        return sin((self._cycleCurrent / self._cycleTotal) * pi)