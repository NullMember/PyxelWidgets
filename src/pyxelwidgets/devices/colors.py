"""
Color models: how a device turns RGBA frame buffer cells into the values its
LEDs understand. Each model converts many cells at once and gives the same
result as the matching per-color conversion on ``Color``.
"""

import numpy

import pyxelwidgets.color

# Same expression as Color.grgb / Color.gmono, so results match exactly
_GAMMA = numpy.array([int((c ** 2.2) * pyxelwidgets.color.Color.gamma_coefficient) for c in range(256)])

def blend(rgba: numpy.ndarray) -> numpy.ndarray:
    """Alpha blended (r, g, b) ints for ``(n, 4)`` cells, like ``Color.argb``."""
    alpha = rgba[:, 3:4] / 255.0
    return (rgba[:, :3] * alpha).astype(int)

class ColorModel:
    """Base class: ``convert`` maps ``(n, 4)`` uint8 RGBA cells to ``n`` device values."""

    def convert(self, rgba: numpy.ndarray) -> list:
        raise NotImplementedError

    def describe(self) -> dict:
        return {'model': type(self).__name__}

class PassThrough(ColorModel):
    """Values are ``Color`` objects, for devices that do their own conversion (e.g. on screen)."""

    def convert(self, rgba: numpy.ndarray) -> list:
        return [pyxelwidgets.color.Color.from_array(cell) for cell in rgba]

class RGB(ColorModel):
    """Alpha blended, optionally gamma corrected (r, g, b) tuples with ``bits`` per channel."""

    def __init__(self, bits: int = 8, gamma: bool = True):
        self.bits = bits
        self.gamma = gamma

    def convert(self, rgba: numpy.ndarray) -> list:
        rgb = blend(rgba)
        if self.gamma:
            rgb = _GAMMA[rgb]
        rgb = rgb >> (8 - self.bits)
        return list(map(tuple, rgb.tolist()))

    def describe(self) -> dict:
        return {'model': 'RGB', 'bits': self.bits, 'gamma': self.gamma}

class Palette(ColorModel):
    """Index of the nearest ``table`` entry to the alpha blended color, like ``Color.find_in_palette``."""

    def __init__(self, table):
        self.table = numpy.asarray(table, dtype = int)

    def convert(self, rgba: numpy.ndarray) -> list:
        deltas = self.table[None, :, :] - blend(rgba)[:, None, :]
        distances = numpy.einsum('nkc,nkc->nk', deltas, deltas)
        return [int(i) for i in numpy.argmin(distances, axis = 1)]

    def describe(self) -> dict:
        return {'model': 'Palette', 'size': len(self.table)}

class Levels(ColorModel):
    """
    Brightness mapped onto ``values`` (darkest first): the luminance range is
    split into ``len(values)`` equal steps. ``gamma`` uses ``Color.gmono``
    instead of ``Color.mono``.
    """

    def __init__(self, values, gamma: bool = True):
        self.values = list(values)
        self.gamma = gamma

    def convert(self, rgba: numpy.ndarray) -> list:
        rgb = blend(rgba)
        mono = ((rgb[:, 0] * 0.2126) + (rgb[:, 1] * 0.7152) + (rgb[:, 2] * 0.0722)).astype(int)
        if self.gamma:
            mono = _GAMMA[mono]
        step = 256 // len(self.values)
        return [self.values[i] for i in mono // step]

    def describe(self) -> dict:
        return {'model': 'Levels', 'levels': len(self.values), 'gamma': self.gamma}

class Brightness(ColorModel):
    """
    One color (or white) LEDs: the brightest channel of the alpha blended
    color, split into ``len(values)`` equal steps, picks one of ``values``
    (darkest first). Unlike ``Levels`` a pure red is as bright as white.
    """

    def __init__(self, values):
        self.values = list(values)

    def convert(self, rgba: numpy.ndarray) -> list:
        brightest = blend(rgba).max(axis = 1)
        step = 256 // len(self.values)
        return [self.values[min(i, len(self.values) - 1)] for i in (brightest // step).tolist()]

    def describe(self) -> dict:
        return {'model': 'Brightness', 'levels': len(self.values)}
