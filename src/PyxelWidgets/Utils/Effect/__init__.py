import enum
import numpy
import math

class Engine():
    _count = 0

    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get('name', f'Engine_{Engine._count}')
        self.length = kwargs.get('length', 30)
        self.counter = Counter(length = self.length)
        self.effects = {}
    
    @property
    def length(self) -> int:
        return self._length

    @length.setter
    def length(self, value: int) -> None:
        self.length = value
        for effect in self.effects.values():
            effect.length = self.length
        self.counter.length = self.length
    
    def addEffect(self, effect) -> None:
        effect.length = self.length
        self.effects[effect.name] = effect
    
    def removeEffect(self, name: str) -> None:
        if name in self.effects:
            self.effects.pop(name)

    def reset(self) -> None:
        self.counter.reset()

    def step(self) -> int:
        return self.counter.step
    
    def value(self, name: str) -> float:
        if name in self.effects:
            return self.effects[name].value(self.counter._step)
    
    def apply(self, name: str, buffer: numpy.ndarray) -> numpy.ndarray:
        return buffer * self.effects[name].value(self.counter._step)

class Counter():

    _count = 0

    class Direction(enum.Enum):
        Up      = enum.auto()
        Down    = enum.auto()
        Cycle   = enum.auto()

    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get('name', f'Counter_{Counter._count}')
        self.direction = kwargs.get('direction', Counter.Direction.Up)
        self._length = kwargs.get('length', 30)
        self._step = 0
        self._direction = 0
        self.reset()
        Counter._count += 1
    
    @property
    def length(self) -> int:
        return self._length

    @length.setter
    def length(self, length: int) -> None:
        self._length = length
        self.step = self._step

    @property
    def current(self) -> int:
        return self._step

    @property
    def step(self) -> int:
        if self.direction == Counter.Direction.Up:
            self._step = (self._step + 1) % self._length
        elif self.direction == Counter.Direction.Down:
            self._step = (self._step - 1) % self._length
        elif self.direction == Counter.Direction.Cycle:
            if self._direction == 0:
                self._step += 1
                if self._step == self._length - 1:
                    self._direction = 1
            elif self._direction == 1:
                self._step -= 1
                if self._step == 0:
                    self._direction = 0
        return self._step

    @step.setter
    def step(self, value: int) -> None:
        self._step = value % self._length

    def reset(self) -> None:
        if self.direction == Counter.Direction.Up or Counter.Direction.Cycle:
            self._direction = 0
            self._step = 0
        elif self.direction == Counter.Direction.Down:
            self._direction = 1
            self._step = self._length - 1

class Effect():

    _count = 0

    def __init__(self, **kwargs) -> None:
        self.name = kwargs.get('name', f'Effect_{Effect._count}')
        self.length = kwargs.get('length', 30)
        self.values = []
        self.calcValues()
        Effect._count += 1
    
    @property
    def length(self) -> int:
        return self._length

    @length.setter
    def length(self, length: int) -> None:
        self._length = length
        self.calcValues()

    def calcValues(self):
        raise Exception("calcValues should be implemented")
    
    def value(self, step: int) -> float:
        return self.values[step]

    def apply(self, step: int, buffer: numpy.ndarray) -> numpy.ndarray:
        return buffer * self.values[step]

class Gaussian(Effect):
    def __init__(self, gauss = 0.25, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Gaussian_{Gaussian._count}')
        self._gauss = gauss
        super().__init__(**kwargs)
        Gaussian._count += 1

    @property
    def gauss(self) -> float:
        return self._gauss
    
    @gauss.setter
    def gauss(self, value: float) -> None:
        self._gauss = value
        self.calcValues()

    def calcValues(self):
        self.values = [0] * self._length
        halflen = int(self._length // 2)
        for i in range(self._length):
            self.values[i] = math.exp(-(math.pow((i - halflen) / halflen, 2) / (2 * math.pow(self._gauss, 2))))

class Pulse(Effect):
    def __init__(self, width = 0.5, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Pulse_{Pulse._count}')
        self._width = width
        super().__init__(**kwargs)
        Pulse._count += 1
    
    @property
    def width(self) -> float:
        return self._width
    
    @width.setter
    def width(self, value: float) -> None:
        self._width = value
        self.calcValues()

    def calcValues(self):
        self.values = [0] * self._length
        for i in range(self._length):
            if i <= int(self._length * self.width):
                self.values[i] = 1.0
            else:
                self.values[i] = 0.0

class Sine(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Sine_{Sine._count}')
        super().__init__(**kwargs)
        Sine._count += 1
    
    def calcValues(self):
        self.values = [0] * self._length
        for i in range(self._length):
            self.values[i] = (math.sin((i / self._length) * 2 * math.pi) + 1) / 2

class Saw(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Saw_{Saw._count}')
        super().__init__(**kwargs)
        Saw._count += 1
    
    def calcValues(self):
        self.values = [0] * self._length
        for i in range(self._length):
            self.values[i] = i / self._length

class Triangle(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Triangle_{Saw._count}')
        super().__init__(**kwargs)
        Triangle._count += 1
    
    def calcValues(self):
        self.values = [0] * self._length
        halflength = self._length // 2
        for i in range(self._length):
            if i < halflength:
                self.values[i] = i / halflength
            else:
                self.values[i] = (self.length - i) / halflength

class Custom(Effect):
    def __init__(self, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', f'Custom_{Custom._count}')
        self._waveform = kwargs.get('waveform', [0.0, 1.0])
        super().__init__(**kwargs)
        Custom._count += 1
    
    @property
    def waveform(self) -> list:
        return self._waveform
    
    @waveform.setter
    def waveform(self, waveform: list) -> None:
        self._waveform = waveform
        self.calcValues()

    def calcValues(self):
        self.values = [0] * self._length
        ratio = (len(self._waveform) - 1) / self._length
        for i in range(self._length):
            coeff = (i * ratio) % 1.0
            inputIndex = int(i * ratio)
            self.values[i] = (self._waveform[inputIndex] * (1.0 - coeff)) + (self._waveform[inputIndex + 1] * coeff)