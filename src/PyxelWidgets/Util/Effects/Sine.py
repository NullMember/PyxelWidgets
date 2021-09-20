from . import Effect, EffectDirection
from math import pi, sin

class Sine(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Sine_{Sine._count}')
        kwargs['direction'] = kwargs.get('direction', EffectDirection.Up)
        super().__init__(**kwargs)
        Sine._count += 1
    
    def step(self):
        super().step()
        self.value = (sin((self._cycleCurrent / self.length) * 2 * pi) + 1) / 2
        return self.value