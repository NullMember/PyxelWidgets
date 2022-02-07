import enum
import numpy
import math

class Effect():

    _count = 0

    class Direction(enum.Enum):
        Up      = enum.auto()
        Down    = enum.auto()
        Cycle   = enum.auto()

    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get('name', f'Effect_{Effect._count}')
        self.wait = kwargs.get('wait', 0)
        self.length = kwargs.get('length', 30)
        self.direction = kwargs.get('direction', Effect.Direction.Cycle)
        self.value = 0
        self.tick = 0
        self._directionCurrent = 0
        self._cycleCurrent = 0
        self.reset()

    def reset(self):
        if self.direction == Effect.Direction.Up or Effect.Direction.Cycle:
            self._directionCurrent = 0
            self._cycleCurrent = 0
        elif self.direction == Effect.Direction.Down:
            self._directionCurrent = 1
            self._cycleCurrent = self.length - 1

    def step(self):
        self.tick += 1
        self.tick %= (self.wait + 1)
        if self.tick == 0:
            if self.direction == Effect.Direction.Up:
                self._cycleCurrent = (self._cycleCurrent + 1) % self.length
            elif self.direction == Effect.Direction.Down:
                self._cycleCurrent = (self._cycleCurrent - 1) % self.length
            elif self.direction == Effect.Direction.Cycle:
                if self._directionCurrent == 0:
                    self._cycleCurrent += 1
                    if self._cycleCurrent == self.length:
                        self._directionCurrent = 1
                elif self._directionCurrent == 1:
                    self._cycleCurrent -= 1
                    if self._cycleCurrent == 0:
                        self._directionCurrent = 0
    
    def apply(self, buffer: numpy.ndarray) -> numpy.ndarray:
        self.step()
        return buffer * self.value

class Gaussian(Effect):
    def __init__(self, gauss = 0.25, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Gaussian_{Gaussian._count}')
        super().__init__(**kwargs)
        self._gauss = gauss
        Gaussian._count += 1
    
    def step(self):
        super().step()
        self.value = math.exp(-(pow(self._cycleCurrent / self.length, 2) / (2 * math.pow(self._gauss, 2))))
        return self.value

class Pulse(Effect):
    def __init__(self, width = 0.5, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Pulse_{Pulse._count}')
        super().__init__(**kwargs)
        self.width = width
        Pulse._count += 1
    
    def step(self):
        super().step()
        if self._cycleCurrent < int(self.length * self.width):
            self.value = 1.0
        else:
            self.value = 0.0
        return self.value

class Sine(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Sine_{Sine._count}')
        kwargs['direction'] = kwargs.get('direction', Sine.Direction.Up)
        super().__init__(**kwargs)
        Sine._count += 1
    
    def step(self):
        super().step()
        self.value = (math.sin((self._cycleCurrent / self.length) * 2 * math.pi) + 1) / 2
        return self.value

class Triangle(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Triangle_{Triangle._count}')
        super().__init__(**kwargs)
        Triangle._count += 1
    
    def step(self):
        super().step()
        self.value = self._cycleCurrent / self.length
        return self.value