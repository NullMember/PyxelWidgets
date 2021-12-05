from . import Effect, EffectDirection
from math import exp, pow

class Gaussian(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Gaussian_{Gaussian._count}')
        super().__init__(**kwargs)
        self._gauss = kwargs.get('gauss', 0.25)
        Gaussian._count += 1
    
    def step(self):
        super().step()
        self.value = exp(-(pow(self._cycleCurrent / self.length, 2) / (2 * pow(self._gauss, 2))))
        return self.value