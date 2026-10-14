import numpy

class Color():
    """
    Immutable RGBA color. ``r``, ``g`` and ``b`` are 0-255, ``a`` is 0.0-1.0
    (stored in 1/255 steps so a color survives a round trip through a buffer).
    Out-of-range values are clamped. Operations return new colors.
    """

    __slots__ = ('r', 'g', 'b', 'a', '_array')

    gamma_coefficient = ((1.0 / 255.0) ** 2.2) * 255

    def __init__(self, r: int = 0, g: int = 0, b: int = 0, a: float = 1.0) -> None:
        set_ = object.__setattr__
        set_(self, 'r', min(255, max(0, int(r))))
        set_(self, 'g', min(255, max(0, int(g))))
        set_(self, 'b', min(255, max(0, int(b))))
        set_(self, 'a', round(min(1.0, max(0.0, float(a))) * 255) / 255)

    def __setattr__(self, name, value):
        raise AttributeError(f'{type(self).__name__} is immutable, use replace()')

    def __delattr__(self, name):
        raise AttributeError(f'{type(self).__name__} is immutable')

    def replace(self, **channels) -> 'Color':
        """ Copy with some channels changed, e.g. ``Colors.Red.replace(a = 0.5)`` """
        values = {'r': self.r, 'g': self.g, 'b': self.b, 'a': self.a}
        values.update(channels)
        return Color(**values)

    @classmethod
    def from_value(cls, value: int) -> 'Color':
        """ Create a Color from a packed 32-bit 0xAARRGGBB value """
        return cls((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF, ((value >> 24) & 0xFF) / 255.0)

    @classmethod
    def from_array(cls, rgba) -> 'Color':
        """ Create a Color from a frame buffer cell """
        r, g, b, a = (int(v) for v in rgba)
        return cls(r, g, b, a / 255.0)

    @property
    def value(self) -> int:
        """ Packed 32-bit 0xAARRGGBB value """
        return (round(self.a * 255) << 24) | (self.r << 16) | (self.g << 8) | self.b

    @property
    def rgba(self) -> tuple:
        """ Raw (red, green, blue, alpha) tuple, alpha scaled to 0-255 """
        return self.r, self.g, self.b, round(self.a * 255)

    def __array__(self, dtype = None, copy = None):
        """ Lets a Color be assigned to frame buffer cells and slices """
        try:
            array = self._array
        except AttributeError:
            # Made once: colors are assigned to buffers every frame
            array = numpy.array(self.rgba, dtype = numpy.uint8)
            array.flags.writeable = False
            object.__setattr__(self, '_array', array)
        if dtype is not None and dtype != numpy.uint8:
            return array.astype(dtype)
        return array.copy() if copy else array

    @property
    def rgb(self) -> tuple:
        """ Raw (red, green, blue) tuple """
        return self.r, self.g, self.b

    @property
    def frgb(self) -> tuple:
        """ Raw float (red, green, blue) tuple """
        return self.r / 255.0, self.g / 255.0, self.b / 255.0

    @property
    def argb(self) -> tuple:
        """ Alpha blended (red, green, blue) tuple """
        return int(self.r * self.a), int(self.g * self.a), int(self.b * self.a)
    
    @property
    def fargb(self) -> tuple:
        """ Alpha blended float (red, green, blue) tuple """
        return tuple(c / 255.0 for c in self.argb)

    @property
    def grgb(self) -> tuple:
        """ Alpha blended and gamma corrected (red, green, blue) tuple """
        return tuple(int((c ** 2.2) * self.gamma_coefficient) for c in self.argb)
    
    @property
    def fgrgb(self) -> tuple:
        """ Alpha blended and gamma corrected float (red, green, blue) tuple """
        return tuple(c / 255.0 for c in self.grgb)

    @property
    def h(self) -> int:
        """ Hue value calculated from alpha blended rgb """
        h = 0.0
        rgb = self.fargb
        min_v = min(rgb)
        max_v = max(rgb)
        if max_v == min_v:
            # Achromatic (gray, black or white), hue is undefined
            return 0
        if max_v == rgb[0]:
            h = (rgb[1] - rgb[2]) / (max_v - min_v)
        elif max_v == rgb[1]:
            h = 2.0 + ((rgb[2] - rgb[0]) / (max_v - min_v))
        elif max_v == rgb[2]:
            h = 4.0 + ((rgb[0] - rgb[1]) / (max_v - min_v))
        return int(h * 60 if h >= 0 else (h * 60) + 360)

    @property
    def s(self) -> float:
        """ Saturation value calculated from alpha blended rgb """
        rgb = self.fargb
        min_v = min(rgb)
        max_v = max(rgb)
        if max_v == min_v:
            return 0.0
        if self.l <= 0.5:
            return (max_v - min_v) / (max_v + min_v)
        return (max_v - min_v) / (2.0 - max_v - min_v)

    @property
    def l(self) -> float:
        """ Luminance value calculated from alpha blended rgb """
        rgb = self.fargb
        return (max(rgb) + min(rgb)) / 2.0
    
    @property
    def mono(self) -> int:
        """ Linear monophonic color calculated from alpha blended rgb """
        r, g, b = self.argb
        return int((r * 0.2126) + (g * 0.7152) + (b * 0.0722))
    
    @property
    def gmono(self) -> int:
        """ Linear monophonic color calculated from alpha blended rgb then applied gamma correction """
        return int((self.mono ** 2.2) * self.gamma_coefficient)
    
    def find_in_palette(self, palette) -> int:
        """ Find in palette using alpha blended rgb value """
        palette = numpy.asarray(palette)
        deltas = palette - self.argb
        dist_2 = numpy.einsum('ij,ij->i', deltas, deltas)
        return int(numpy.argmin(dist_2))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Color):
            return NotImplemented
        return self.rgba == other.rgba

    def __hash__(self) -> int:
        return hash(self.rgba)
    
    def __lt__(self, other) -> bool:
        return self.l < other.l
    
    def __gt__(self, other) -> bool:
        return self.l > other.l
    
    def __le__(self, other) -> bool:
        return self.l <= other.l

    def __ge__(self, other) -> bool:
        return self.l >= other.l

    def minimum(self, other) -> 'Color':
        """ Channel-wise minimum of two colors (darken blend) """
        return Color(min(self.r, other.r), min(self.g, other.g), min(self.b, other.b), min(self.a, other.a))

    def maximum(self, other) -> 'Color':
        """ Channel-wise maximum of two colors (lighten blend) """
        return Color(max(self.r, other.r), max(self.g, other.g), max(self.b, other.b), max(self.a, other.a))

    def _map(self, function, a = None) -> 'Color':
        return Color(function(self.r), function(self.g), function(self.b), self.a if a is None else a)

    def __add__(self, other) -> 'Color':
        return Color(self.r + other.r, self.g + other.g, self.b + other.b, self.a + other.a)
    
    def __sub__(self, other) -> 'Color':
        return Color(self.r - other.r, self.g - other.g, self.b - other.b, self.a - other.a)
    
    def __mul__(self, other: float) -> 'Color':
        return self._map(lambda c: c * other)
    
    def __truediv__(self, other: float) -> 'Color':
        return self._map(lambda c: c / other)
    
    def __floordiv__(self, other: float) -> 'Color':
        return self._map(lambda c: c // other)

    def __mod__(self, other: int) -> 'Color':
        return self._map(lambda c: c % other)

    def __lshift__(self, other) -> 'Color':
        """ Draw ``other`` behind this color """
        invalpha = 1.0 - self.a
        return Color(*(int(s + (o * invalpha)) for s, o in zip(self.rgb, other.rgb)), self.a + (other.a * invalpha))
    
    def __rshift__(self, other) -> 'Color':
        """ Draw ``other`` in front of this color """
        return other << self

    def __and__(self, other: int) -> 'Color':
        return self._map(lambda c: c & other)

    def __or__(self, other: int) -> 'Color':
        return self._map(lambda c: c | other)
    
    def __xor__(self, other: int) -> 'Color':
        return self._map(lambda c: c ^ other)

    def __bool__(self) -> bool:
        return bool(self.a)

    def __invert__(self) -> 'Color':
        return self._map(lambda c: 255 - c, 1.0 - self.a)

    __neg__ = __invert__

    def __repr__(self) -> str:
        return f'Color({self.r}, {self.g}, {self.b}, {self.a:g})'

class Colors:
    IndianRed = Color(205, 92, 92)
    LightCoral = Color(240, 128, 128)
    Salmon = Color(250, 128, 114)
    DarkSalmon = Color(233, 150, 122)
    LightSalmon = Color(255, 160, 122)
    Crimson = Color(220, 20, 60)
    Red = Color(255, 0, 0)
    FireBrick = Color(178, 34, 34)
    DarkRed = Color(139, 0, 0)
    Pink = Color(255, 192, 203)
    LightPink = Color(255, 182, 193)
    HotPink = Color(255, 105, 180)
    DeepPink = Color(255, 20, 147)
    MediumVioletRed = Color(199, 21, 133)
    PaleVioletRed = Color(219, 112, 147)
    Coral = Color(255, 127, 80)
    Tomato = Color(255, 99, 71)
    OrangeRed = Color(255, 69, 0)
    DarkOrange = Color(255, 140, 0)
    Orange = Color(255, 165, 0)
    Gold = Color(255, 215, 0)
    Yellow = Color(255, 255, 0)
    LightYellow = Color(255, 255, 224)
    LemonChiffon = Color(255, 250, 205)
    LightGoldenrodYellow = Color(250, 250, 210)
    PapayaWhip = Color(255, 239, 213)
    Moccasin = Color(255, 228, 181)
    PeachPuff = Color(255, 218, 185)
    PaleGoldenrod = Color(238, 232, 170)
    Khaki = Color(240, 230, 140)
    DarkKhaki = Color(189, 183, 107)
    Lavender = Color(230, 230, 250)
    Thistle = Color(216, 191, 216)
    Plum = Color(221, 160, 221)
    Violet = Color(238, 130, 238)
    Orchid = Color(218, 112, 214)
    Fuchsia = Color(255, 0, 255)
    Magenta = Color(255, 0, 255)
    MediumOrchid = Color(186, 85, 211)
    MediumPurple = Color(147, 112, 219)
    RebeccaPurple = Color(102, 51, 153)
    BlueViolet = Color(138, 43, 226)
    DarkViolet = Color(148, 0, 211)
    DarkOrchid = Color(153, 50, 204)
    DarkMagenta = Color(139, 0, 139)
    Purple = Color(128, 0, 128)
    Indigo = Color(75, 0, 130)
    SlateBlue = Color(106, 90, 205)
    DarkSlateBlue = Color(72, 61, 139)
    MediumSlateBlue = Color(123, 104, 238)
    GreenYellow = Color(173, 255, 47)
    Chartreuse = Color(127, 255, 0)
    LawnGreen = Color(124, 252, 0)
    Lime = Color(0, 255, 0)
    LimeGreen = Color(50, 205, 50)
    PaleGreen = Color(152, 251, 152)
    LightGreen = Color(144, 238, 144)
    MediumSpringGreen = Color(0, 250, 154)
    SpringGreen = Color(0, 255, 127)
    MediumSeaGreen = Color(60, 179, 113)
    SeaGreen = Color(46, 139, 87)
    ForestGreen = Color(34, 139, 34)
    Green = Color(0, 128, 0)
    DarkGreen = Color(0, 100, 0)
    YellowGreen = Color(154, 205, 50)
    OliveDrab = Color(107, 142, 35)
    Olive = Color(128, 128, 0)
    DarkOliveGreen = Color(85, 107, 47)
    MediumAquamarine = Color(102, 205, 170)
    DarkSeaGreen = Color(143, 188, 139)
    LightSeaGreen = Color(32, 178, 170)
    DarkCyan = Color(0, 139, 139)
    Teal = Color(0, 128, 128)
    Aqua = Color(0, 255, 255)
    Cyan = Color(0, 255, 255)
    LightCyan = Color(224, 255, 255)
    PaleTurquoise = Color(175, 238, 238)
    Aquamarine = Color(127, 255, 212)
    Turquoise = Color(64, 224, 208)
    MediumTurquoise = Color(72, 209, 204)
    DarkTurquoise = Color(0, 206, 209)
    CadetBlue = Color(95, 158, 160)
    SteelBlue = Color(70, 130, 180)
    LightSteelBlue = Color(176, 196, 222)
    PowderBlue = Color(176, 224, 230)
    LightBlue = Color(173, 216, 230)
    SkyBlue = Color(135, 206, 235)
    LightSkyBlue = Color(135, 206, 250)
    DeepSkyBlue = Color(0, 191, 255)
    DodgerBlue = Color(30, 144, 255)
    CornflowerBlue = Color(100, 149, 237)
    RoyalBlue = Color(65, 105, 225)
    Blue = Color(0, 0, 255)
    MediumBlue = Color(0, 0, 205)
    DarkBlue = Color(0, 0, 139)
    Navy = Color(0, 0, 128)
    MidnightBlue = Color(25, 25, 112)
    Cornsilk = Color(255, 248, 220)
    BlanchedAlmond = Color(255, 235, 205)
    Bisque = Color(255, 228, 196)
    NavajoWhite = Color(255, 222, 173)
    Wheat = Color(245, 222, 179)
    BurlyWood = Color(222, 184, 135)
    Tan = Color(210, 180, 140)
    RosyBrown = Color(188, 143, 143)
    SandyBrown = Color(244, 164, 96)
    Goldenrod = Color(218, 165, 32)
    DarkGoldenrod = Color(184, 134, 11)
    Peru = Color(205, 133, 63)
    Chocolate = Color(210, 105, 30)
    SaddleBrown = Color(139, 69, 19)
    Sienna = Color(160, 82, 45)
    Brown = Color(165, 42, 42)
    Maroon = Color(128, 0, 0)
    White = Color(255, 255, 255)
    Snow = Color(255, 250, 250)
    HoneyDew = Color(240, 255, 240)
    MintCream = Color(245, 255, 250)
    Azure = Color(240, 255, 255)
    AliceBlue = Color(240, 248, 255)
    GhostWhite = Color(248, 248, 255)
    WhiteSmoke = Color(245, 245, 245)
    SeaShell = Color(255, 245, 238)
    Beige = Color(245, 245, 220)
    OldLace = Color(253, 245, 230)
    FloralWhite = Color(255, 250, 240)
    Ivory = Color(255, 255, 240)
    AntiqueWhite = Color(250, 235, 215)
    Linen = Color(250, 240, 230)
    LavenderBlush = Color(255, 240, 245)
    MistyRose = Color(255, 228, 225)
    Gainsboro = Color(220, 220, 220)
    LightGray = Color(211, 211, 211)
    Silver = Color(192, 192, 192)
    DarkGray = Color(169, 169, 169)
    Gray = Color(128, 128, 128)
    DimGray = Color(105, 105, 105)
    LightSlateGray = Color(119, 136, 153)
    SlateGray = Color(112, 128, 144)
    DarkSlateGray = Color(47, 79, 79)
    Black = Color(0, 0, 0)
    Invisible = Color(0, 0, 0, 0.0)