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
        self._length = kwargs.get('length', 30)
        self.value = 0
        self.values = [0] * self._length
        self.length = self._length
        self.direction = kwargs.get('direction', Effect.Direction.Cycle)
        self._directionCurrent = 0
        self._cycleCurrent = 0
        self.reset()
    
    @property
    def length(self) -> int:
        return self._length

    @length.setter
    def length(self, length: int) -> None:
        self._length = length
        self.calcValues()

    def calcValues(self):
        raise Exception("calcValues should be implemented")

    def reset(self) -> None:
        if self.direction == Effect.Direction.Up or Effect.Direction.Cycle:
            self._directionCurrent = 0
            self._cycleCurrent = 0
        elif self.direction == Effect.Direction.Down:
            self._directionCurrent = 1
            self._cycleCurrent = self.length - 1

    def step(self) -> int:
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
        return self._cycleCurrent
    
    def apply(self, buffer: numpy.ndarray) -> numpy.ndarray:
        return buffer * self.values[self.step()]

class Gaussian(Effect):
    def __init__(self, gauss = 0.25, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Gaussian_{Gaussian._count}')
        super().__init__(**kwargs)
        self._gauss = gauss
        Gaussian._count += 1

    def calcValues(self):
        self.reset()
        self.values = [0] * self._length
        for i in range(self._length):
            self.values[i] = math.exp(-(pow(self.step() / self.length, 2) / (2 * math.pow(self._gauss, 2))))

class Pulse(Effect):
    def __init__(self, width = 0.5, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Pulse_{Pulse._count}')
        super().__init__(**kwargs)
        self.width = width
        Pulse._count += 1
    
    def calcValues(self):
        self.reset()
        self.values = [0] * self._length
        for i in range(self._length):
            if self.step() < int(self.length * self.width):
                self.values[i] = 1.0
            else:
                self.values[i] = 0.0

class Sine(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Sine_{Sine._count}')
        kwargs['direction'] = kwargs.get('direction', Sine.Direction.Up)
        super().__init__(**kwargs)
        Sine._count += 1
    
    def calcValues(self):
        self.reset()
        self.values = [0] * self._length
        for i in range(self._length):
            self.values[i] = (math.sin((self.step() / self.length) * 2 * math.pi) + 1) / 2

class Triangle(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Triangle_{Triangle._count}')
        super().__init__(**kwargs)
        Triangle._count += 1
    
    def calcValues(self):
        self.reset()
        self.values = [0] * self._length
        for i in range(self._length):
            self.values[i] = self.step() / self.length