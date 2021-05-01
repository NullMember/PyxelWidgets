from enum import Enum

class EffectDirection(Enum):
    Up = 0
    Down = 1
    Cycle = 2

class Effect():
    def __init__(self, **kwargs) -> None:
        self._cycleTotal = kwargs.get('length', 30)
        self._direction = kwargs.get('direction', EffectDirection.Cycle)
        self._directionCurrent = 0
        self._cycleCurrent = 0
        self.reset()

    def reset(self):
        if self._direction == EffectDirection.Up or EffectDirection.Cycle:
            self._directionCurrent = 0
            self._cycleCurrent = 0
        elif self._direction == EffectDirection.Down:
            self._directionCurrent = 1
            self._cycleCurrent = self._cycleTotal - 1

    def update(self):
        if self._direction == EffectDirection.Up:
            self._cycleCurrent = (self._cycleCurrent + 1) % self._cycleTotal
        elif self._direction == EffectDirection.Down:
            self._cycleCurrent = (self._cycleCurrent - 1) % self._cycleTotal
        elif self._direction == EffectDirection.Cycle:
            if self._directionCurrent == 0:
                self._cycleCurrent += 1
                if self._cycleCurrent == self._cycleTotal:
                    self._directionCurrent = 1
            elif self._directionCurrent == 1:
                self._cycleCurrent -= 1
                if self._cycleCurrent == 0:
                    self._directionCurrent = 0