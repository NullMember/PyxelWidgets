

class Position2D():
    def __init__(self, x: int = 0, y: int = 0) -> None:
        self.x = x
        self.y = y
    
    def set(self, x: int, y: int) -> None:
        self.x = x
        self.y = y
    
    def get(self) -> tuple:
        return self.x, self.y

    def __repr__(self) -> str:
        return f'({self.x}, {self.y})'

class Dimension2D():
    def __init__(self, w: int = 1, h: int = 1) -> None:
        self.w = w
        self.h = h
        self.area = self.w * self.h
    
    def set(self, w: int, h: int) -> None:
        self.w = w
        self.h = h
        self.area = self.w * self.h
    
    def get(self) -> tuple:
        return self.w, self.h

    def __repr__(self) -> str:
        return f'({self.w}, {self.h})'

class Rectangle2D(Position2D, Dimension2D):
    def __init__(self, x: int = 0, y: int = 0, w: int = 1, h: int = 1, position: Position2D = None, dimension: Dimension2D = None) -> None:
        if position == None:
            Position2D.__init__(self, x, y)
        else:
            Position2D.__init__(self, position.x, position.y)
        if dimension == None:
            Dimension2D.__init__(self, w, h)
        else:
            Dimension2D.__init__(self, dimension.w, dimension.h)

    @property
    def l(self) -> int:
        return self.x
    
    @property
    def r(self) -> int:
        return self.x + self.w
    
    @property
    def b(self) -> int:
        return self.y
    
    @property
    def t(self) -> int:
        return self.y + self.h
    
    @property
    def slice(self) -> slice:
        return (slice(self.l, self.r, 1), slice(self.b, self.t, 1))
    
    @property
    def columns(self) -> range:
        return range(self.x, self.x + self.w)
    
    @property
    def rows(self) -> range:
        return range(self.y, self.y + self.h)
    
    @property
    def origin(self):
        return Rectangle2D(0, 0, self.w, self.h)

    def set(self, x: int, y: int, w: int, h: int) -> None:
        self.x = x
        self.y = y
        self.w = w
        self.h = h
    
    def get(self) -> tuple:
        return self.x, self.y, self.w, self.h
    
    def copy(self):
        return Rectangle2D(self.x, self.y, self.w, self.h)

    def intersect(self, rect):
        if self.collide(rect):
            x = max(self.x, rect.x)
            y = max(self.y, rect.y)
            w = min(self.r, rect.r) - max(self.l, rect.l)
            h = min(self.t, rect.t) - max(self.b, rect.b)
            return Rectangle2D(x, y, w, h)
        return None

    def collide(self, rect):
        return (self.x < rect.x + rect.w and 
                rect.x < self.x + self.w and
                self.y < rect.y + rect.h and 
                rect.y < self.y + self.h)

    def __add__(self, other):
        return Rectangle2D(self.x + other.x, self.y + other.y, self.w, self.h)
    
    def __sub__(self, other):
        return Rectangle2D(self.x - other.x, self.y - other.y, self.w, self.h)

    def __repr__(self) -> str:
        return f'({self.x}, {self.y}, {self.w}, {self.h})'