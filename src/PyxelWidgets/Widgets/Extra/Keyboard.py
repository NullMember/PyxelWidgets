from .ButtonGroup import ButtonGroup
from ...Helpers import *
from enum import Enum, auto
import numpy

class KeyboardMode(Enum):
    Keyboard            = auto()
    ChromaticVertical   = auto()
    ChromaticHorizontal = auto()
    Diatonic            = auto()
    DiatonicVertical    = auto()
    DiatonicHorizontal  = auto()

class KeyboardScale(Enum):
    Major           = auto()
    Minor           = auto()
    Dorian          = auto()
    Mixolydian      = auto()
    Lydian          = auto()
    Phrygian        = auto()
    Locrian         = auto()
    Diminished      = auto()
    WholeHalf       = auto()
    WholeTone       = auto()
    MinorBlues      = auto()
    MinorPentatonic = auto()
    MajorPentatonic = auto()
    MinorHarmonic   = auto()
    MinorMelodic    = auto()

class KeyboardTone(Enum):
    C   = auto()
    CS  = auto()
    D   = auto()
    DS  = auto()
    E   = auto()
    F   = auto()
    FS  = auto()
    G   = auto()
    GS  = auto()
    A   = auto()
    AS  = auto()
    B   = auto()

KeyboardScales = {
    'Major': [0, 2, 4, 5, 7, 9, 11],
    'Minor': [0, 2, 3, 5, 7, 8, 10],
    'Dorian': [0, 2, 3, 5, 7, 9, 10],
    'Mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'Lydian': [0, 2, 4, 6, 7, 9, 11],
    'Phrygian': [0, 1, 3, 5, 7, 8, 10],
    'Locrian': [0, 1, 3, 5, 6, 8, 10],
    'Diminished': [0, 1, 3, 4, 6, 7, 9, 10],
    'WholeHalf': [0, 2, 3, 5, 6, 8, 9, 11],
    'WholeTone': [0, 2, 4, 6, 8, 10],
    'MinorBlues': [0, 3, 5, 6, 7, 10],
    'MinorPentatonic': [0, 3, 5, 7, 10],
    'MajorPentatonic': [0, 2, 4, 7, 9],
    'MinorHarmonic': [0, 2, 3, 5, 7, 8, 11],
    'MinorMelodic': [0, 2, 3, 5, 7, 9, 11],

    'Keyboard': [0, 2, 4, 5, 7, 9, 11],
    'KeyboardUpper': [-1, 1, 3, -1, 6, 8, 10]
}

class Keyboard():
    def __init__(self, x: int, y: int, width: int, height: int, **kwargs) -> None:
        self.buttons = ButtonGroup(x, y, width, height, callback = self.process)
        self.notes = numpy.array([[-1 for y in range(height)] for x in range(width)])
        self.rect = Rectangle2D(x, y, width, height)
        self._mode = kwargs.get('mode', KeyboardMode.Diatonic)
        self._scale = kwargs.get('scale', KeyboardScale.Major)
        self._tone = kwargs.get('tone', KeyboardTone.C)
        self._octave = kwargs.get('octave', 0)
        self._fold = kwargs.get('fold', 4)
        self._toneColor = kwargs.get('toneColor', Pixel(255, 0, 255, 1.0))
        self._keyboardColor = kwargs.get('keyboardColor', Pixel(0, 255, 255, 1.0))
        self._nonScaleColor = kwargs.get('nonScaleColor', Pixel(255, 255, 0, 1.0))
        self._calcNotes()
        self._callback = kwargs.get('callback', lambda *_, **__: None)

    @property
    def mode(self):
        return self._mode
    
    @mode.setter
    def mode(self, mode: KeyboardMode):
        self._mode = mode
        self._calcNotes()
        for x in self.rect.origin.columns:
            for y in self.rect.origin.rows:
                self.buttons.buttons[x, y].updated = True
    
    @property
    def scale(self):
        return self._scale
    
    @scale.setter
    def scale(self, scale: KeyboardScale):
        self._scale = scale
        self._calcNotes()
        for x in self.rect.origin.columns:
            for y in self.rect.origin.rows:
                self.buttons.buttons[x, y].updated = True
    
    @property
    def tone(self):
        return self._tone
    
    @tone.setter
    def tone(self, tone: KeyboardTone):
        self._tone = tone
        self._calcNotes()
        for x in self.rect.origin.columns:
            for y in self.rect.origin.rows:
                self.buttons.buttons[x, y].updated = True
    
    @property
    def octave(self):
        return self._octave
    
    @octave.setter
    def octave(self, octave: int):
        self._octave = octave
        self._calcNotes()
        for x in self.rect.origin.columns:
            for y in self.rect.origin.rows:
                self.buttons.buttons[x, y].updated = True

    @property
    def fold(self):
        return self._fold
    
    @fold.setter
    def fold(self, fold: int):
        self._fold = fold
        self._calcNotes()
        for x in self.rect.origin.columns:
            for y in self.rect.origin.rows:
                self.buttons.buttons[x, y].updated = True

    @property
    def toneColor(self):
        return self._toneColor
    
    @toneColor.setter
    def toneColor(self, toneColor: Pixel):
        self._toneColor = toneColor
        self._calcNotes()
        for x in self.rect.origin.columns:
            for y in self.rect.origin.rows:
                self.buttons.buttons[x, y].updated = True

    @property
    def keyboardColor(self):
        return self._keyboardColor
    
    @keyboardColor.setter
    def keyboardColor(self, keyboardColor: Pixel):
        self._keyboardColor = keyboardColor
        self._calcNotes()
        for x in self.rect.origin.columns:
            for y in self.rect.origin.rows:
                self.buttons.buttons[x, y].updated = True

    @property
    def nonScaleColor(self):
        return self._nonScaleColor
    
    @nonScaleColor.setter
    def nonScaleColor(self, nonScaleColor: Pixel):
        self._nonScaleColor = nonScaleColor
        self._calcNotes()
        for x in self.rect.origin.columns:
            for y in self.rect.origin.rows:
                self.buttons.buttons[x, y].updated = True

    def setCallback(self, callback):
        self._callback = callback
    
    def process(self, name: str, event, value):
        prefix, n, x, y = name.split('_')
        x = int(x)
        y = int(y)
        if self.notes[x, y] != -1:
            self._callback(self.buttons.buttons[x, y].name, event, (self.notes[x, y], self.buttons.buttons[x, y].value))
    
    def _calcNotes(self):
        base = self._tone.value + (self._octave * 12)
        scale = KeyboardScales[self._scale.name]
        precalc = []
        #precalculate scale values
        for i in range(self.rect.h * self.rect.w):
            precalc.append(scale[i % len(scale)] + base + ((i // len(scale)) * 12))
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                #calculate notes
                if self._mode == KeyboardMode.Keyboard:
                    base = KeyboardTone.C.value + (self._octave * 12)
                    length = 7 if 7 < self.rect.w else self.rect.w
                    if y % 2 == 0:
                        scale = KeyboardScales['Keyboard']
                    else:
                        scale = KeyboardScales['KeyboardUpper']
                    if scale[x % length] == -1:
                        self.notes[x, y] = -1
                    else:
                        self.notes[x, y] = scale[x % length] + base + ((y // 2) * 12) + ((x // length) * 12)
                elif self._mode == KeyboardMode.ChromaticVertical:
                    index = x + (y * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._mode == KeyboardMode.ChromaticHorizontal:
                    index = y + (x * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._mode == KeyboardMode.Diatonic:
                    self.notes[x, y] = precalc[x + (y * len(scale))]
                elif self._mode == KeyboardMode.DiatonicVertical:
                    self.notes[x, y] = precalc[x + (y * len(scale)) - (y * (len(scale) - self._fold + 1))]
                elif self._mode == KeyboardMode.DiatonicHorizontal:
                    self.notes[x, y] = precalc[y + (x * len(scale)) - (x * (len(scale) - self._fold + 1))]
                #change colors
                if self.notes[x, y] == -1:
                    self.buttons.buttons[x, y].deactiveColor = Colors.Black
                else:
                    if (self.notes[x, y] - self._tone.value) % 12 == 0:
                        self.buttons.buttons[x, y].deactiveColor = self._toneColor
                    elif (self.notes[x, y] - self._tone.value) % 12 in KeyboardScales[self._scale.name]:
                        self.buttons.buttons[x, y].deactiveColor = self._keyboardColor
                    else:
                        self.buttons.buttons[x, y].deactiveColor = self._nonScaleColor