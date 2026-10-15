import itertools
import random

import numpy
import pytest

from pyxelwidgets.color import Color
from pyxelwidgets.devices.colors import RGB, Levels, Palette, PassThrough

rng = random.Random(7)
COLORS = [Color(r, g, b) for r, g, b in itertools.product((0, 1, 63, 128, 200, 255), repeat = 3)] \
       + [Color(rng.randrange(256), rng.randrange(256), rng.randrange(256), rng.randrange(256) / 255) for _ in range(3000)]
CELLS = numpy.array([color.rgba for color in COLORS], dtype = numpy.uint8)
PALETTE = [(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255), (127, 127, 127), (255, 255, 0), (40, 0, 90)]


def test_rgb_matches_color_grgb():
    for bits in (6, 7, 8):
        assert RGB(bits).convert(CELLS) == [tuple(c >> (8 - bits) for c in color.grgb) for color in COLORS]
    assert RGB(8, gamma = False).convert(CELLS) == [color.argb for color in COLORS]


def test_palette_matches_find_in_palette():
    assert Palette(PALETTE).convert(CELLS) == [color.find_in_palette(PALETTE) for color in COLORS]


@pytest.mark.parametrize('levels, gamma', [(8, True), (4, True), (16, False)])
def test_levels_match_mono(levels, gamma):
    values = list(range(100, 100 + levels))
    expected = [values[(color.gmono if gamma else color.mono) // (256 // levels)] for color in COLORS]
    assert Levels(values, gamma = gamma).convert(CELLS) == expected


def test_pass_through_round_trips():
    assert PassThrough().convert(CELLS[:50]) == COLORS[:50]
