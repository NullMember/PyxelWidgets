import numpy

class Pixel():
    def __init__(self, r: int = 0, g: int = 0, b: int = 0, a: float = 1.0) -> None:
        self.alpha = 0.0 if a < 0.0 else (1.0 if a > 1.0 else a)
        
        self.color = [0 if r < 0 else (255 if r > 255 else int(r)),
                     0 if g < 0 else (255 if g > 255 else int(g)),
                     0 if b < 0 else (255 if b > 255 else int(b))]

        self.acolor = [int(self.color[0] * self.alpha),
                       int(self.color[1] * self.alpha),
                       int(self.color[2] * self.alpha)]

        self.gammaCoefficient = ((1.0 / 255.0) ** 2.2) * 255
        self.gcolor = [int((self.acolor[0] ** 2.2) * self.gammaCoefficient),
                       int((self.acolor[1] ** 2.2) * self.gammaCoefficient),
                       int((self.acolor[2] ** 2.2) * self.gammaCoefficient)]
        
        self._value = (int(self.alpha * 255) << 24) | (self.color[0] << 16) | (self.color[1] << 8) | self.color[2]

    @property
    def a(self) -> int:
        return self.alpha

    @a.setter
    def a(self, value: float) -> None:
        self.alpha = 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)

        self.acolor = [int(self.color[0] * self.alpha),
                       int(self.color[1] * self.alpha),
                       int(self.color[2] * self.alpha)]

        self.gammaCoefficient = ((1.0 / 256.0) ** 2.2) * 256.0
        self.gcolor = [int((self.acolor[0] ** 2.2) * self.gammaCoefficient),
                       int((self.acolor[1] ** 2.2) * self.gammaCoefficient),
                       int((self.acolor[2] ** 2.2) * self.gammaCoefficient)]
        
        self._value &= 0x00FFFFFF
        self._value |= (int(self.alpha * 255) << 24)

    @property
    def rgb(self):
        """ Raw (red, green, blue) tuple """
        return self.color[0], self.color[1], self.color[2]

    @property
    def frgb(self):
        """ Raw float (red, green, blue) tuple """
        return self.color[0] / 256.0, self.color[1] / 256.0, self.color[2] / 256.0

    @property
    def argb(self):
        """ Alpha blended (red, green, blue) tuple """
        return self.acolor[0], self.acolor[1], self.acolor[2]
    
    @property
    def fargb(self):
        """ Alpha blended float (red, green, blue) tuple """
        return self.acolor[0] / 256.0, self.acolor[1] / 256.0, self.acolor[2] / 256.0

    @property
    def grgb(self):
        """ Alpha blended and gamma corrected (red, green, blue) tuple """
        return self.gcolor[0], self.gcolor[1], self.gcolor[2]
    
    @property
    def fgrgb(self):
        """ Alpha blended and gamma corrected float (red, green, blue) tuple """
        return self.gcolor[0] / 256.0, self.gcolor[1] / 256.0, self.gcolor[2] / 256.0

    @property
    def r(self) -> int:
        """ Raw red color """
        return self.color[0]
    
    @r.setter
    def r(self, value: int) -> None:
        value = int(value)
        self.color[0] = 0 if value < 0 else (255 if value > 255 else value)
        self.acolor[0] = int(self.color[0] * self.alpha)
        self.gcolor[0] = int((self.acolor[0] ** 2.2) * self.gammaCoefficient)
        self._value &= 0xFF00FFFF
        self._value |= self.color[0] << 16

    @property
    def g(self) -> int:
        """ Raw green color """
        return self.color[1]
    
    @g.setter
    def g(self, value: int) -> None:
        value = int(value)
        self.color[1] = 0 if value < 0 else (255 if value > 255 else value)
        self.acolor[1] = int(self.color[1] * self.alpha)
        self.gcolor[1] = int((self.acolor[1] ** 2.2) * self.gammaCoefficient)
        self._value &= 0xFFFF00FF
        self._value |= self.color[1] << 8

    @property
    def b(self) -> int:
        """ Raw blue color """
        return self.color[2]
    
    @b.setter
    def b(self, value: int) -> None:
        value = int(value)
        self.color[2] = 0 if value < 0 else (255 if value > 255 else value)
        self.acolor[2] = int(self.color[2] * self.alpha)
        self.gcolor[2] = int((self.acolor[2] ** 2.2) * self.gammaCoefficient)
        self._value &= 0xFFFFFF00
        self._value |= self.color[0]

    @property
    def h(self) -> int:
        """ Hue value calculated from alpha blended rgb """
        h = 0.0
        rgb = self.fargb
        minV = min(rgb)
        maxV = max(rgb)
        if maxV == rgb[0]:
            h = (rgb[1] - rgb[2]) / (maxV - minV)
        elif maxV == rgb[1]:
            h = 2.0 + ((rgb[2] - rgb[0]) / (maxV - minV))
        elif maxV == rgb[2]:
            h = 4.0 + ((rgb[0] - rgb[1]) / (maxV - minV))
        return int(h * 60 if h >= 0 else (h * 60) + 360)

    @property
    def s(self) -> float:
        """ Saturation value calculated from alpha blended rgb """
        rgb = self.fargb
        minV = min(rgb)
        maxV = max(rgb)
        if self.l <= 0.5:
            return (maxV - minV) / (maxV + minV)
        return (maxV - minV) / (2.0 - maxV - minV)

    @property
    def l(self) -> float:
        """ Luminance value calculated from alpha blended rgb """
        rgb = self.fargb
        minV = min(rgb)
        maxV = max(rgb)
        return (maxV + minV) / 2.0
    
    @property
    def mono(self) -> int:
        """ Linear monophonic color calculated from alpha blended rgb """
        return int((self.acolor[0] * 0.2126) + (self.acolor[1] * 0.7152) + (self.acolor[2] * 0.0722))
    
    @property
    def gmono(self) -> int:
        """ Linear monophonic color calculated from alpha blended rgb then applied gamma correction """
        return int((((self.acolor[0] * 0.2126) ** 2.2) * self.gammaCoefficient) + 
                   (((self.acolor[1] * 0.7152) ** 2.2) * self.gammaCoefficient) + 
                   (((self.acolor[2] * 0.0722) ** 2.2) * self.gammaCoefficient))

    @property
    def value(self) -> int:
        """ Raw 32-bit rgba value """
        return self._value
    
    @value.setter
    def value(self, value: int) -> None:
        self._value = value & 0xFFFFFFFF
        self.alpha = ((self._value >> 24) & 0xFF) / 255.0

        self.color[0] = (self._value >> 16) & 0xFF
        self.color[1] = (self._value >> 8) & 0xFF
        self.color[2] = self._value & 0xFF
        
        self.acolor = [int(self.color[0] * self.alpha),
                       int(self.color[1] * self.alpha),
                       int(self.color[2] * self.alpha)]
        
        self.gcolor = [int((self.acolor[0] ** 2.2) * self.gammaCoefficient),
                       int((self.acolor[1] ** 2.2) * self.gammaCoefficient),
                       int((self.acolor[2] ** 2.2) * self.gammaCoefficient)]
    
    def findInPalette(self, palette):
        """ Find in palette using alpha blended rgb value """
        palette = numpy.asarray(palette)
        deltas = palette - self.argb
        dist_2 = numpy.einsum('ij,ij->i', deltas, deltas)
        return numpy.argmin(dist_2)

    def __eq__(self, other) -> bool:
        return self._value == other._value
    
    def __ne__(self, other) -> bool:
        return self._value != other._value
    
    def __lt__(self, other) -> bool:
        return self.l < other.l
    
    def __gt__(self, other) -> bool:
        return self.l > other.l
    
    def __le__(self, other) -> bool:
        result = [min(s, o) for s, o in zip(self.color, other.color)] + [min(self.alpha, other.alpha)]
        return Pixel(result[0], result[1], result[2], result[3])

    def __ge__(self, other) -> bool:
        result = [max(s, o) for s, o in zip(self.color, other.color)] + [max(self.alpha, other.alpha)]
        return Pixel(result[0], result[1], result[2], result[3])

    def __add__(self, other: int):
        result = [s + o for s, o in zip(self.color, other.color)] + [self.alpha + other.alpha]
        return Pixel(result[0], result[1], result[2], result[3])
    
    def __sub__(self, other: int):
        result = [s - o for s, o in zip(self.color, other.color)] + [self.alpha - other.alpha]
        return Pixel(result[0], result[1], result[2], result[3])
    
    def __mul__(self, other: float):
        result = [s * other for s in self.color] + [self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])
    
    def __truediv__(self, other: float):
        result = [s / other for s in self.color] + [self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])
    
    def __floordiv__(self, other: float):
        result = [s // other for s in self.color] + [self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])

    def __mod__(self, other: int):
        result = [s % other for s in self.color] + [self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])

    def __lshift__(self, other):
        invalpha = 1.0 - self.alpha
        alpha = self.alpha + (other.alpha * invalpha)
        result = [int((s + (o * invalpha))) for s, o in zip(self.color, other.color)] + [alpha]
        return Pixel(result[0], result[1], result[2], result[3])
    
    def __rshift__(self, other):
        invalpha = 1.0 - other.alpha
        alpha = other.alpha + (self.alpha * invalpha)
        result = [int((o + (s * invalpha))) for s, o in zip(self.color, other.color)] + [alpha]
        return Pixel(result[0], result[1], result[2], result[3])

    def __and__(self, other: int):
        result = [s & other for s in self.color] + [self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])

    def __or__(self, other: int):
        result = [s | other for s in self.color] + [self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])
    
    def __xor__(self, other):
        result = [s ^ other for s in self.color] + [self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])

    def __bool__(self):
        return bool(self.alpha)

    def __invert__(self):
        result = [255 - s for s in self.color] + [1.0 - self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])

    def __neg__(self):
        result = [255 - s for s in self.color] + [1.0 - self.alpha]
        return Pixel(result[0], result[1], result[2], result[3])
    
    def __index__(self):
        return self._value

    def __repr__(self) -> str:
        return f'({self.color.__repr__()}, {self.alpha.__repr__()})'

class Colors:
    IndianRed = Pixel(205, 92, 92)
    LightCoral = Pixel(240, 128, 128)
    Salmon = Pixel(250, 128, 114)
    DarkSalmon = Pixel(233, 150, 122)
    LightSalmon = Pixel(255, 160, 122)
    Crimson = Pixel(220, 20, 60)
    Red = Pixel(255, 0, 0)
    FireBrick = Pixel(178, 34, 34)
    DarkRed = Pixel(139, 0, 0)
    Pink = Pixel(255, 192, 203)
    LightPink = Pixel(255, 182, 193)
    HotPink = Pixel(255, 105, 180)
    DeepPink = Pixel(255, 20, 147)
    MediumVioletRed = Pixel(199, 21, 133)
    PaleVioletRed = Pixel(219, 112, 147)
    Coral = Pixel(255, 127, 80)
    Tomato = Pixel(255, 99, 71)
    OrangeRed = Pixel(255, 69, 0)
    DarkOrange = Pixel(255, 140, 0)
    Orange = Pixel(255, 165, 0)
    Gold = Pixel(255, 215, 0)
    Yellow = Pixel(255, 255, 0)
    LightYellow = Pixel(255, 255, 224)
    LemonChiffon = Pixel(255, 250, 205)
    LightGoldenrodYellow = Pixel(250, 250, 210)
    PapayaWhip = Pixel(255, 239, 213)
    Moccasin = Pixel(255, 228, 181)
    PeachPuff = Pixel(255, 218, 185)
    PaleGoldenrod = Pixel(238, 232, 170)
    Khaki = Pixel(240, 230, 140)
    DarkKhaki = Pixel(189, 183, 107)
    Lavender = Pixel(230, 230, 250)
    Thistle = Pixel(216, 191, 216)
    Plum = Pixel(221, 160, 221)
    Violet = Pixel(238, 130, 238)
    Orchid = Pixel(218, 112, 214)
    Fuchsia = Pixel(255, 0, 255)
    Magenta = Pixel(255, 0, 255)
    MediumOrchid = Pixel(186, 85, 211)
    MediumPurple = Pixel(147, 112, 219)
    RebeccaPurple = Pixel(102, 51, 153)
    BlueViolet = Pixel(138, 43, 226)
    DarkViolet = Pixel(148, 0, 211)
    DarkOrchid = Pixel(153, 50, 204)
    DarkMagenta = Pixel(139, 0, 139)
    Purple = Pixel(128, 0, 128)
    Indigo = Pixel(75, 0, 130)
    SlateBlue = Pixel(106, 90, 205)
    DarkSlateBlue = Pixel(72, 61, 139)
    MediumSlateBlue = Pixel(123, 104, 238)
    GreenYellow = Pixel(173, 255, 47)
    Chartreuse = Pixel(127, 255, 0)
    LawnGreen = Pixel(124, 252, 0)
    Lime = Pixel(0, 255, 0)
    LimeGreen = Pixel(50, 205, 50)
    PaleGreen = Pixel(152, 251, 152)
    LightGreen = Pixel(144, 238, 144)
    MediumSpringGreen = Pixel(0, 250, 154)
    SpringGreen = Pixel(0, 255, 127)
    MediumSeaGreen = Pixel(60, 179, 113)
    SeaGreen = Pixel(46, 139, 87)
    ForestGreen = Pixel(34, 139, 34)
    Green = Pixel(0, 128, 0)
    DarkGreen = Pixel(0, 100, 0)
    YellowGreen = Pixel(154, 205, 50)
    OliveDrab = Pixel(107, 142, 35)
    Olive = Pixel(128, 128, 0)
    DarkOliveGreen = Pixel(85, 107, 47)
    MediumAquamarine = Pixel(102, 205, 170)
    DarkSeaGreen = Pixel(143, 188, 139)
    LightSeaGreen = Pixel(32, 178, 170)
    DarkCyan = Pixel(0, 139, 139)
    Teal = Pixel(0, 128, 128)
    Aqua = Pixel(0, 255, 255)
    Cyan = Pixel(0, 255, 255)
    LightCyan = Pixel(224, 255, 255)
    PaleTurquoise = Pixel(175, 238, 238)
    Aquamarine = Pixel(127, 255, 212)
    Turquoise = Pixel(64, 224, 208)
    MediumTurquoise = Pixel(72, 209, 204)
    DarkTurquoise = Pixel(0, 206, 209)
    CadetBlue = Pixel(95, 158, 160)
    SteelBlue = Pixel(70, 130, 180)
    LightSteelBlue = Pixel(176, 196, 222)
    PowderBlue = Pixel(176, 224, 230)
    LightBlue = Pixel(173, 216, 230)
    SkyBlue = Pixel(135, 206, 235)
    LightSkyBlue = Pixel(135, 206, 250)
    DeepSkyBlue = Pixel(0, 191, 255)
    DodgerBlue = Pixel(30, 144, 255)
    CornflowerBlue = Pixel(100, 149, 237)
    RoyalBlue = Pixel(65, 105, 225)
    Blue = Pixel(0, 0, 255)
    MediumBlue = Pixel(0, 0, 205)
    DarkBlue = Pixel(0, 0, 139)
    Navy = Pixel(0, 0, 128)
    MidnightBlue = Pixel(25, 25, 112)
    Cornsilk = Pixel(255, 248, 220)
    BlanchedAlmond = Pixel(255, 235, 205)
    Bisque = Pixel(255, 228, 196)
    NavajoWhite = Pixel(255, 222, 173)
    Wheat = Pixel(245, 222, 179)
    BurlyWood = Pixel(222, 184, 135)
    Tan = Pixel(210, 180, 140)
    RosyBrown = Pixel(188, 143, 143)
    SandyBrown = Pixel(244, 164, 96)
    Goldenrod = Pixel(218, 165, 32)
    DarkGoldenrod = Pixel(184, 134, 11)
    Peru = Pixel(205, 133, 63)
    Chocolate = Pixel(210, 105, 30)
    SaddleBrown = Pixel(139, 69, 19)
    Sienna = Pixel(160, 82, 45)
    Brown = Pixel(165, 42, 42)
    Maroon = Pixel(128, 0, 0)
    White = Pixel(255, 255, 255)
    Snow = Pixel(255, 250, 250)
    HoneyDew = Pixel(240, 255, 240)
    MintCream = Pixel(245, 255, 250)
    Azure = Pixel(240, 255, 255)
    AliceBlue = Pixel(240, 248, 255)
    GhostWhite = Pixel(248, 248, 255)
    WhiteSmoke = Pixel(245, 245, 245)
    SeaShell = Pixel(255, 245, 238)
    Beige = Pixel(245, 245, 220)
    OldLace = Pixel(253, 245, 230)
    FloralWhite = Pixel(255, 250, 240)
    Ivory = Pixel(255, 255, 240)
    AntiqueWhite = Pixel(250, 235, 215)
    Linen = Pixel(250, 240, 230)
    LavenderBlush = Pixel(255, 240, 245)
    MistyRose = Pixel(255, 228, 225)
    Gainsboro = Pixel(220, 220, 220)
    LightGray = Pixel(211, 211, 211)
    Silver = Pixel(192, 192, 192)
    DarkGray = Pixel(169, 169, 169)
    Gray = Pixel(128, 128, 128)
    DimGray = Pixel(105, 105, 105)
    LightSlateGray = Pixel(119, 136, 153)
    SlateGray = Pixel(112, 128, 144)
    DarkSlateGray = Pixel(47, 79, 79)
    Black = Pixel(0, 0, 0)
    Invisible = Pixel(0, 0, 0, 0.0)