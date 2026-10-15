"""Frames shown to every device by the golden recorder and the golden tests."""

import random

from pyxelwidgets import buffer
from pyxelwidgets.color import Color, Colors


def frames(width, height):
    rng = random.Random(1234)
    plain = [Colors.White, Colors.Red, Colors.Lime, Colors.Blue, Colors.Black, Colors.Gray,
             Color(255, 128, 0), Color(10, 200, 90), Color(255, 255, 255, 0.5), Color(200, 30, 120, 0.25)]
    out = [buffer.new(width, height, color) for color in plain]
    for _ in range(3):
        frame = buffer.new(width, height)
        for x in range(width):
            for y in range(height):
                frame[x, y] = Color(rng.randrange(256), rng.randrange(256), rng.randrange(256), rng.choice([1.0, 1.0, 0.5, 0.0]))
        out.append(frame)
    return out
