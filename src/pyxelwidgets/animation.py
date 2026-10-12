"""
Animations change how a widget (or one of its cells) looks over time without
the widget redrawing::

    clip.animation = Blink('1/8')                 # the whole widget
    launcher.animate_cell(2, 3, Pulse('1/2'))     # one cell
    page.animation = Fade(0.3)                    # fades in once, then is removed

Rates and durations are note values (``'1/8'``, ``'bar'``), which follow a
transport's position while it plays and its tempo while it doesn't, or seconds
(a number). A Surface supplies the time (``surface.transport``); without one,
note values run at 120 bpm.
"""

import dataclasses
import math
import time as _time

import numpy

import pyxelwidgets.color
import pyxelwidgets.rate
from pyxelwidgets.rate import Rate

__all__ = ['Time', 'Animation', 'Blink', 'Pulse', 'Fade', 'now']

@dataclasses.dataclass(frozen = True)
class Time:
    """When a frame is drawn: wall clock ``seconds`` and musical ``beats`` (quarter notes)."""
    seconds: float
    beats: float
    signature: tuple = (4, 4)

def now(transport = None) -> Time:
    """The current Time: from ``transport`` (anything with bpm, beats, playing, signature) if given."""
    seconds = _time.monotonic()
    if transport is None:
        return Time(seconds, seconds * 2.0)
    beats = transport.beats if transport.playing else seconds * transport.bpm / 60.0
    return Time(seconds, beats, transport.signature)

class Animation:
    """
    Base class: ``apply(cells, time)`` returns the animated copy of RGBA
    ``cells``. ``finished(time)`` ends one-shot animations.
    """

    def __init__(self, rate: Rate | float = '1/4'):
        if isinstance(rate, str):
            pyxelwidgets.rate.parse_rate(rate)
        elif not rate > 0:
            raise ValueError(f'rate must be a note value or positive seconds, got {rate!r}')
        self.rate = rate
        self.start = None

    def _position(self, time: Time) -> tuple:
        """(position, length of a period) in beats for note values, else in seconds."""
        if isinstance(self.rate, str):
            return time.beats, pyxelwidgets.rate.quarter_notes(self.rate, time.signature)
        return time.seconds, self.rate

    def phase(self, time: Time) -> float:
        """Position within the current period, 0.0 to 1.0; aligned to the beat for note values."""
        position, length = self._position(time)
        return (position / length) % 1.0

    def elapsed(self, time: Time) -> float:
        """Periods since the animation was first applied."""
        position, length = self._position(time)
        if self.start is None:
            self.start = position
        return (position - self.start) / length

    def apply(self, cells: numpy.ndarray, time: Time) -> numpy.ndarray:
        return cells

    def finished(self, time: Time) -> bool:
        return False

def _scaled(cells: numpy.ndarray, amount: float, alpha: bool = False) -> numpy.ndarray:
    out = cells.copy()
    channels = slice(3, 4) if alpha else slice(0, 3)
    out[..., channels] = (cells[..., channels] * amount).round().astype(numpy.uint8)
    return out

class Blink(Animation):
    """On for ``duty`` of each period, off (transparent, or ``off_color``) for the rest."""

    def __init__(self, rate: Rate | float = '1/4', *, duty: float = 0.5, off_color: pyxelwidgets.color.Color | None = None):
        super().__init__(rate)
        self.duty = duty
        self.off_color = off_color

    def apply(self, cells, time):
        if self.phase(time) < self.duty:
            return cells
        out = numpy.empty_like(cells)
        out[...] = numpy.asarray(self.off_color) if self.off_color is not None else 0
        return out

class Pulse(Animation):
    """Brightness breathes between ``minimum`` and full once per period."""

    def __init__(self, rate: Rate | float = '1/2', *, minimum: float = 0.2):
        super().__init__(rate)
        self.minimum = minimum

    def apply(self, cells, time):
        wave = 0.5 + 0.5 * math.cos(2 * math.pi * self.phase(time))
        return _scaled(cells, self.minimum + (1.0 - self.minimum) * wave)

class Fade(Animation):
    """
    Fades in (or out with ``out = True``) once over ``duration``. A widget
    drops a finished fade; after fading out it is hidden.
    """

    def __init__(self, duration: Rate | float = 0.3, *, out: bool = False):
        super().__init__(duration)
        self.out = out

    def amount(self, time: Time) -> float:
        progress = min(1.0, max(0.0, self.elapsed(time)))
        return 1.0 - progress if self.out else progress

    def apply(self, cells, time):
        # Fading transparency lets what's underneath show through, like on a device
        return _scaled(cells, self.amount(time), alpha = True)

    def finished(self, time):
        return self.elapsed(time) >= 1.0
