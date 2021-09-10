from .Effect import *
from math import pi, sin

class Sine(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['direction'] = kwargs.get('direction', EffectDirection.Up)
        super().__init__(**kwargs)
    
    def step(self):
        super().step()
        return (sin((self._cycleCurrent / self._cycleTotal) * 2 * pi) + 1) / 2