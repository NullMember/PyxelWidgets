__all__ = ['Gaussian', 'Pulse', 'Sine', 'Triangle']

from enum import Enum, auto

class EffectDirection(Enum):
    Up      = auto()
    Down    = auto()
    Cycle   = auto()

class Effect():

    _count = 0

    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get('name', f'Effect_{Effect._count}')
        self.length = kwargs.get('length', 30)
        self.direction = kwargs.get('direction', EffectDirection.Cycle)
        self.value = 0
        self._directionCurrent = 0
        self._cycleCurrent = 0
        self.reset()

    def reset(self):
        if self.direction == EffectDirection.Up or EffectDirection.Cycle:
            self._directionCurrent = 0
            self._cycleCurrent = 0
        elif self.direction == EffectDirection.Down:
            self._directionCurrent = 1
            self._cycleCurrent = self.length - 1

    def step(self):
        if self.direction == EffectDirection.Up:
            self._cycleCurrent = (self._cycleCurrent + 1) % self.length
        elif self.direction == EffectDirection.Down:
            self._cycleCurrent = (self._cycleCurrent - 1) % self.length
        elif self.direction == EffectDirection.Cycle:
            if self._directionCurrent == 0:
                self._cycleCurrent += 1
                if self._cycleCurrent == self.length:
                    self._directionCurrent = 1
            elif self._directionCurrent == 1:
                self._cycleCurrent -= 1
                if self._cycleCurrent == 0:
                    self._directionCurrent = 0