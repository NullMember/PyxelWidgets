import numpy

class Point2D():
    def __init__(self, x: int = 0, y: int = 0) -> None:
        self._x = x
        self._y = y
    
    @property
    def x(self) -> int:
        return self._x
    
    @x.setter
    def x(self, value: int) -> None:
        self._x = max(0, int(value))
    
    @property
    def y(self) -> int:
        return self._y
    
    @y.setter
    def y(self, value: int) -> None:
        self._y = max(0, int(value))
    
    def set(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
    
    def get(self) -> tuple:
        return self.x, self.y
    
    def __repr__(self) -> str:
        return f'x: {self._x}, y: {self._y}'

class Dimension2D():
    def __init__(self, width: int = 1, height: int = 1) -> None:
        self._width = width
        self._height = height
    
    @property
    def width(self) -> int:
        return self._width
    
    @width.setter
    def width(self, value: int) -> None:
        self._width = max(1, int(value))
    
    @property
    def w(self) -> int:
        return self.width
    
    @w.setter
    def w(self, value: int) -> None:
        self.width = value
    
    @property
    def height(self) -> int:
        return self._height
    
    @height.setter
    def height(self, value: int) -> None:
        self._height = max(1, int(value))
    
    @property
    def h(self) -> int:
        return self.height
    
    @h.setter
    def h(self, value: int) -> None:
        self.height = value
    
    def set(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
    
    def get(self) -> tuple:
        return self.width, self.height

    def __repr__(self) -> str:
        return f'width: {self._width}, height: {self._height}'

class Rectangle(Point2D, Dimension2D):
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        Point2D.__init__(self, x, y)
        Dimension2D.__init__(self, width, height)

    @property
    def left(self) -> int:
        return self.x
    
    @property
    def right(self) -> int:
        return self.x + self.width
    
    @property
    def bottom(self) -> int:
        return self.y
    
    @property
    def top(self) -> int:
        return self.y + self.h
    
    @property
    def l(self) -> int:
        return self.left
    
    @property
    def r(self) -> int:
        return self.right
    
    @property
    def b(self) -> int:
        return self.bottom
    
    @property
    def t(self) -> int:
        return self.top
    
    def set(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def get(self) -> tuple:
        return self.x, self.y, self.width, self.height

    def intersect(self, rect):
        if self.collide(rect):
            x = max(self.x, rect.x)
            y = max(self.y, rect.y)
            width = min(self.r, rect.r) - max(self.l, rect.l)
            height = min(self.t, rect.t) - max(self.b, rect.b)
            return Rectangle(x, y, width, height)
        return None

    def collide(self, rect):
        return (self.x < rect.x + rect.w and 
                rect.x < self.x + self.w and
                self.y < rect.y + rect.h and 
                rect.y < self.y + self.h)
    
    def __repr__(self) -> str:
        return f'x: {self.x}, y: {self.y}, width: {self.width}, height: {self.height}'

class Pixel():
    def __init__(self, r: int = 0, g: int = 0, b: int = 0, a: float = 1.0) -> None:
        self._rgb = numpy.array([r, g, b], numpy.uint8)
        self._alpha = numpy.clip(a, 0.0, 1.0).astype(numpy.single)
        self._color = (self._rgb * self._alpha).astype(numpy.uint8)

    def lighter(self, other):
        if max(self.l, other.l) == self.l:
            return self
        return other

    def darker(self, other):
        if min(self.l, other.l) == self.l:
            return self
        return other
    
    @property
    def color(self) -> numpy.ndarray:
        return self._color

    @property
    def a(self) -> int:
        return self._alpha

    @a.setter
    def a(self, value: float) -> None:
        self._alpha = numpy.clip(value, 0.0, 1.0).astype(numpy.single)
        self._color = (self._rgb * self._alpha).astype(numpy.uint8)

    @property
    def r(self) -> int:
        return self._color[0]
    
    @r.setter
    def r(self, value: int) -> None:
        self._rgb[0] = value
        self._color[0] = (value * self._alpha).astype(numpy.uint8)

    @property
    def g(self) -> int:
        return self._color[1]
    
    @g.setter
    def g(self, value: int) -> None:
        self._rgb[1] = value
        self._color[1] = (value * self._alpha).astype(numpy.uint8)

    @property
    def b(self) -> int:
        return self._color[2]
    
    @b.setter
    def b(self, value: int) -> None:
        self._rgb[2] = value
        self._color[2] = (value * self._alpha).astype(numpy.uint8)

    @property
    def h(self) -> int:
        h = 0.0
        rgb = self._color / 255.0
        minV = rgb.min()
        maxV = rgb.max()
        if maxV == rgb[0]:
            h = (rgb[1] - rgb[2]) / (maxV - minV)
        elif maxV == rgb[1]:
            h = 2.0 + ((rgb[2] - rgb[0]) / (maxV - minV))
        elif maxV == rgb[2]:
            h = 4.0 + ((rgb[0] - rgb[1]) / (maxV - minV))
        return int(h * 60 if h >= 0 else (h * 60) + 360)

    @property
    def s(self) -> float:
        rgb = self._color / 255.0
        minV = rgb.min()
        maxV = rgb.max()
        if self.l <= 0.5:
            return (maxV - minV) / (maxV + minV)
        return (maxV - minV) / (2.0 - maxV - minV)

    @property
    def l(self) -> float:
        rgb = self._color / 255.0
        minV = rgb.min()
        maxV = rgb.max()
        return (maxV + minV) / 2.0

    @property
    def rgb(self) -> int:
        return (self.r << 16) | (self.g << 8) | self.b
    
    @rgb.setter
    def rgb(self, value: int) -> None:
        self.r = (value >> 16) & 0xFF
        self.g = (value >> 8) & 0xFF
        self.b = value & 0xFF
    
    @property
    def rgba(self) -> int:
        return (int(self.a * 255.0) << 24) | (self.r << 16) | (self.g << 8) | self.b
    
    @rgba.setter
    def rgba(self, value: int) -> None:
        self.a = ((value >> 24) & 0xFF) / 255.0
        self.r = (value >> 16) & 0xFF
        self.g = (value >> 8) & 0xFF
        self.b = value & 0xFF
    
    def __add__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r + other.r, self.g + other.g, self.b + other.b, self.a + other.a)
        elif isinstance(other, int):
            return Pixel(self.r + other, self.g + other, self.b + other)
        else:
            raise TypeError
    
    def __sub__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r - other.r, self.g - other.g, self.b - other.b, self.a - other.a)
        elif isinstance(other, int):
            return Pixel(self.r - other, self.g - other, self.b - other)
        else:
            raise TypeError
    
    def __mul__(self, other):
        if isinstance(other, Pixel):
            mulalpha = other.fa * (1.0 - self.fa)
            alphablend = self.fa + mulalpha
            return Pixel(int((self.r + (other.r * mulalpha)) / alphablend), int((self.g + (other.g * mulalpha)) / alphablend), int((self.b + (other.b * mulalpha)) / alphablend), alphablend)
        elif isinstance(other, float):
            return Pixel(int(self.r * other), int(self.g * other), int(self.b * other))
        else:
            raise TypeError
    
    def __truediv__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r / other.r, self.g / other.g, self.b / other.b)
        elif isinstance(other, int):
            return Pixel(self.r / other, self.g / other, self.b / other)
        elif isinstance(other, float):
            return Pixel(self.r / other, self.g / other, self.b / other)
        else:
            raise TypeError
    
    def __floordiv__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r // other.r, self.g // other.g, self.b // other.b)
        elif isinstance(other, int):
            return Pixel(self.r // other, self.g // other, self.b // other)
        elif isinstance(other, float):
            return Pixel(self.r // other, self.g // other, self.b // other)
        else:
            raise TypeError
    
    def __mod__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r % other.r, self.g % other.g, self.b % other.b)
        elif isinstance(other, int):
            return Pixel(self.r % other, self.g % other, self.b % other)
        elif isinstance(other, float):
            return Pixel(self.r % other, self.g % other, self.b % other)
        else:
            raise TypeError
    
    def __divmod__(self, other):
        return (self // other, self % other)
    
    def __pow__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r ** other.r, self.g ** other.g, self.b ** other.b)
        elif isinstance(other, int):
            return Pixel(self.r ** other, self.g ** other, self.b ** other)
        elif isinstance(other, float):
            return Pixel(self.r ** other, self.g ** other, self.b ** other)
        else:
            raise TypeError
    
    def __lshift__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r << other.r, self.g << other.g, self.b << other.b)
        elif isinstance(other, int):
            return Pixel(self.r << other, self.g << other, self.b << other)
        else:
            raise TypeError
    
    def __rshift__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r >> other.r, self.g >> other.g, self.b >> other.b)
        elif isinstance(other, int):
            return Pixel(self.r >> other, self.g >> other, self.b >> other)
        else:
            raise TypeError
    
    def __and__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r & other.r, self.g & other.g, self.b & other.b)
        elif isinstance(other, int):
            return Pixel(self.r & other, self.g & other, self.b & other)
        else:
            raise TypeError
    
    def __xor__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r ^ other.r, self.g ^ other.g, self.b ^ other.b)
        elif isinstance(other, int):
            return Pixel(self.r ^ other, self.g ^ other, self.b ^ other)
        else:
            raise TypeError
    
    def __or__(self, other):
        if isinstance(other, Pixel):
            return Pixel(self.r | other.r, self.g | other.g, self.b | other.b)
        elif isinstance(other, int):
            return Pixel(self.r | other, self.g | other, self.b | other)
        else:
            raise TypeError
    
    def __index__(self):
        return self.rgb

    def __repr__(self) -> str:
        return f'r: {self.r}, g: {self.g}, b: {self.b}, a: {self.a}'

class Buffer():
    def __init__(self, width: int, height: int, x: int = 0, y: int = 0) -> None:
        self._rect = Rectangle(x, y, width, height)
        self._buffer = numpy.zeros((width, height, 4), numpy.uint8)
    
    @property
    def buffer(self) -> numpy.ndarray:
        return self._buffer

    @property
    def window(self) -> numpy.ndarray:
        xs = self.x
        ys = self.y
        xe = xs + self.w
        ye = ys + self.h
        return self._buffer[xs:xe, ys:ye]
    
    @window.setter
    def window(self, buffer) -> None:
        xs = self.x
        ys = self.y
        xe = xs + (buffer.shape[0] if buffer.shape[0] < self.w else self.w)
        ye = ys + (buffer.shape[1] if buffer.shape[1] < self.h else self.h)
        self._buffer[xs:xe, ys:ye] = buffer[:self.w, :self.h]

    @property
    def x(self) -> int:
        return self._rect.x
    
    @x.setter
    def x(self, value: int) -> None:
        self._rect.x = value
    
    @property
    def y(self) -> int:
        return self._rect.y
    
    @y.setter
    def y(self, value: int) -> None:
        self._rect.y = value
    
    @property
    def w(self) -> int:
        return self._rect.width

    @w.setter
    def w(self, value: int) -> None:
        self._rect.width = value
    
    @property
    def h(self) -> int:
        return self._rect.height
    
    @h.setter
    def h(self, value: int) -> None:
        self._rect.height = value
    
    @property
    def width(self) -> int:
        return self._buffer.shape[0]
    
    @property
    def height(self) -> int:
        return self._buffer.shape[1]
    
    def set(self, x: int, y: int, width: int, height: int, values) -> None:
        self._buffer[x:x+width, y:y+height] = values
    
    def get(self, x: int, y: int, width: int, height: int) -> None:
        return self._buffer[x:x+width, y:y+height]
    
    def reset(self) -> None:
        self._rect.set(0, 0, self._buffer.shape[0], self._buffer.shape[1])

    def __getitem__(self, indexes):
        if len(indexes) == 1:
            idx = indexes
            xs = idx + self.x
            ys = self.y
            xe = xs + self.w
            ye = ys + self.h
            return self._buffer[xs:xe, ys:ye]
        elif len(indexes) == 2:
            idx, idy = indexes
            xs = idx + self.x
            ys = idy + self.y
            xe = xs + self.w
            ye = ys + self.h
            return self._buffer[xs:xe, ys:ye]
        elif len(indexes) == 3:
            idx, idy, idc = indexes
            xs = idx + self.x
            ys = idy + self.y
            xe = xs + self.w
            ye = ys + self.h
            return self._buffer[xs:xe, ys:ye, idc]
        raise IndexError
    
    def __setitem__(self, indexes, buffer):
        if isinstance(buffer, numpy.ndarray):
            if len(indexes) == 1:
                idx = buffer
                xs = idx + self.x
                ys = self.y
                xe = xs + (buffer.shape[0] if buffer.shape[0] < self.w else self.w)
                ye = ys + (buffer.shape[1] if buffer.shape[1] < self.h else self.h)
                self._buffer[xs:xe, ys:ye] = buffer[:self.w, :self.h]
            elif len(indexes) == 2:
                idx, idy = indexes
                xs = idx + self.x
                ys = idy + self.y
                xe = xs + (buffer.shape[0] if buffer.shape[0] < self.w else self.w)
                ye = ys + (buffer.shape[1] if buffer.shape[1] < self.h else self.h)
                self._buffer[xs:xe, ys:ye] = buffer[:self.w, :self.h]
            elif len(indexes) == 3:
                idx, idy, idc = indexes
                xs = idx + self.x
                ys = idy + self.y
                xe = xs + (buffer.shape[0] if buffer.shape[0] < self.w else self.w)
                ye = ys + (buffer.shape[1] if buffer.shape[1] < self.h else self.h)
                self._buffer[xs:xe, ys:ye, idc] = buffer[:self.w, :self.h, idc]