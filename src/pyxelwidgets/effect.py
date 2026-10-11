import enum
import numpy
import math

class Engine():
    _count = 0

    def __init__(self, *, name: str | None = None, length: int = 30) -> None:
        self.name = name if name is not None else f'Engine_{Engine._count}'
        self._length = length
        self.counter = Counter(length = self._length)
        self.effects = {}
        Engine._count += 1
    
    @property
    def length(self) -> int:
        return self._length

    @length.setter
    def length(self, value: int) -> None:
        self._length = value
        for effect in self.effects.values():
            effect.length = self.length
        self.counter.length = self.length
    
    def add_effect(self, effect) -> None:
        effect.length = self.length
        self.effects[effect.name] = effect
    
    def remove_effect(self, name: str) -> None:
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
        return self.effects[name].apply(self.counter._step, buffer)

class Counter():

    _count = 0

    class Direction(enum.Enum):
        Up      = enum.auto()
        Down    = enum.auto()
        Cycle   = enum.auto()

    def __init__(self, *, name: str | None = None, direction: Direction = Direction.Up, length: int = 30) -> None:
        self.name = name if name is not None else f'Counter_{Counter._count}'
        self.direction = direction
        self._length = length
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
        if self.direction in (Counter.Direction.Up, Counter.Direction.Cycle):
            self._direction = 0
            self._step = 0
        elif self.direction == Counter.Direction.Down:
            self._direction = 1
            self._step = self._length - 1

class Effect():

    # Per class counters for default names (Sine_0, Pulse_0, ...)
    _counts = {}

    def __init__(self, *, name: str | None = None, length: int = 30) -> None:
        if name is None:
            cls = type(self).__name__
            count = Effect._counts.get(cls, 0)
            Effect._counts[cls] = count + 1
            name = f'{cls}_{count}'
        self.name = name
        self.length = length
        self.values = []
        self.calc_values()
    
    @property
    def length(self) -> int:
        return self._length

    @length.setter
    def length(self, length: int) -> None:
        self._length = length
        self.calc_values()

    def calc_values(self):
        raise Exception("calcValues should be implemented")
    
    def value(self, step: int) -> float:
        return self.values[step]

    def apply(self, step: int, buffer: numpy.ndarray) -> numpy.ndarray:
        """Return a copy of an RGBA buffer with its color (not alpha) scaled by this step's value."""
        result = buffer.copy()
        result[..., :3] = numpy.clip(numpy.rint(buffer[..., :3] * self.values[step]), 0, 255)
        return result

class Gaussian(Effect):
    def __init__(self, gauss: float = 0.25, **kwargs) -> None:
        self._gauss = gauss
        super().__init__(**kwargs)

    @property
    def gauss(self) -> float:
        return self._gauss
    
    @gauss.setter
    def gauss(self, value: float) -> None:
        self._gauss = value
        self.calc_values()

    def calc_values(self):
        self.values = [0] * self._length
        halflen = int(self._length // 2)
        for i in range(self._length):
            self.values[i] = math.exp(-(math.pow((i - halflen) / halflen, 2) / (2 * math.pow(self._gauss, 2))))

class Pulse(Effect):
    def __init__(self, width: float = 0.5, **kwargs) -> None:
        self._width = width
        super().__init__(**kwargs)
    
    @property
    def width(self) -> float:
        return self._width
    
    @width.setter
    def width(self, value: float) -> None:
        self._width = value
        self.calc_values()

    def calc_values(self):
        self.values = [0] * self._length
        for i in range(self._length):
            if i <= int(self._length * self.width):
                self.values[i] = 1.0
            else:
                self.values[i] = 0.0

class Sine(Effect):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
    
    def calc_values(self):
        self.values = [0] * self._length
        for i in range(self._length):
            self.values[i] = (math.sin((i / self._length) * 2 * math.pi) + 1) / 2

class Saw(Effect):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
    
    def calc_values(self):
        self.values = [0] * self._length
        for i in range(self._length):
            self.values[i] = i / self._length

class Triangle(Effect):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
    
    def calc_values(self):
        self.values = [0] * self._length
        halflength = self._length // 2
        for i in range(self._length):
            if i < halflength:
                self.values[i] = i / halflength
            else:
                self.values[i] = (self.length - i) / halflength

class Custom(Effect):
    def __init__(self, waveform: list | None = None, **kwargs) -> None:
        self._waveform = waveform if waveform is not None else [0.0, 1.0]
        super().__init__(**kwargs)
    
    @property
    def waveform(self) -> list:
        return self._waveform
    
    @waveform.setter
    def waveform(self, waveform: list) -> None:
        self._waveform = waveform
        self.calc_values()

    def calc_values(self):
        self.values = [0] * self._length
        ratio = (len(self._waveform) - 1) / self._length
        for i in range(self._length):
            coeff = (i * ratio) % 1.0
            input_index = int(i * ratio)
            self.values[i] = (self._waveform[input_index] * (1.0 - coeff)) + (self._waveform[input_index + 1] * coeff)