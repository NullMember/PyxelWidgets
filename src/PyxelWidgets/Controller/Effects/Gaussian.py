from .Effect import Effect
from math import exp, pow

class Gaussian(Effect):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._gauss = kwargs.get('gauss', 0.25)
    
    def update(self):
        super().update()
        return exp(-(pow(self._cycleCurrent / self._cycleTotal, 2) / (2 * pow(self._gauss, 2))))