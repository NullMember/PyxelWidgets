from .ButtonGroup import ButtonGroup
from enum import Enum

class KeyboardMode(Enum):
    Keyboard = 0
    ChromaticVertical = 1
    ChromaticHorizontal = 2
    Diatonic = 3
    DiatonicVertical = 4
    DiatonicHorizontal = 5

class KeyboardScale(Enum):
    Major = 0
    Minor = 1
    Dorian = 2
    Mixolydian = 3
    Lydian = 4
    Phrygian = 5
    Locrian = 6
    Diminished = 7
    WholeHalf = 8
    WholeTone = 9
    MinorBlues = 10
    MinorPentatonic = 11
    MajorPentatonic = 12
    MinorHarmonic = 13
    MinorMelodic = 14

class KeyboardTone(Enum):
    C = 0
    CS = 1
    D = 2
    DS = 3
    E = 4
    F = 5
    FS = 6
    G = 7
    GS = 8
    A = 9
    AS = 10
    B = 11

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
    def __init__(self, name: str, width: int, height: int, **kwargs) -> None:
        self._buttons = ButtonGroup(name, width, height)
        self._notes = [[-1 for y in range(height)] for x in range(width)]
        self._width = width
        self._height = height
        self._mode = kwargs.get('mode', KeyboardMode.Diatonic)
        self._scale = kwargs.get('scale', KeyboardScale.Major)
        self._tone = kwargs.get('tone', KeyboardTone.C)
        self._octave = kwargs.get('octave', 0)
        self._fold = kwargs.get('fold', 4)
        self._toneColor = kwargs.get('toneColor', [255, 0, 255])
        self._keyboardColor = kwargs.get('keyboardColor', [0, 255, 255])
        self._nonScaleColor = kwargs.get('nonScaleColor', [255, 255, 0])
        self._calcNotes()
        self._callback = kwargs.get('callback', lambda *_, **__: None)
        self._buttons.setCallback(self.process)

    @property
    def mode(self):
        return self._mode
    
    @mode.setter
    def mode(self, mode: KeyboardMode):
        self._mode = mode
        self._calcNotes()
        for widget in self.widgets:
            widget.forceUpdate()
    
    @property
    def scale(self):
        return self._scale
    
    @scale.setter
    def scale(self, scale: KeyboardScale):
        self._scale = scale
        self._calcNotes()
        for widget in self.widgets:
            widget.forceUpdate()
    
    @property
    def tone(self):
        return self._tone
    
    @tone.setter
    def tone(self, tone: KeyboardTone):
        self._tone = tone
        self._calcNotes()
        for widget in self.widgets:
            widget.forceUpdate()
    
    @property
    def fold(self):
        return self._fold
    
    @fold.setter
    def fold(self, fold: int):
        self._fold = fold
        self._calcNotes()
        for widget in self.widgets:
            widget.forceUpdate()
    
    @property
    def octave(self):
        return self._octave
    
    @octave.setter
    def octave(self, octave: int):
        self._octave = octave
        self._calcNotes()
        for widget in self.widgets:
            widget.forceUpdate()
    
    @property
    def buttons(self):
        return self._buttons.buttons
    
    @property
    def widgets(self):
        return self._buttons.widgets

    @property
    def width(self):
        return self._width
    
    @property
    def height(self):
        return self._height

    def setCallback(self, callback):
        self._callback = callback
    
    def process(self, name: str, event, value):
        n, x, y = name.split(',')
        x = int(x)
        y = int(y)
        if self._notes[x][y] != -1:
            self._callback(self._buttons.name, event, (self._notes[x][y], self.buttons[x][y].value))
    
    def _calcNotes(self):
        base = self._tone.value + (self._octave * 12)
        scale = KeyboardScales[self._scale.name]
        precalc = []
        #precalculate scale values
        for i in range(self.height * self.width):
            precalc.append(scale[i % len(scale)] + base + ((i // len(scale)) * 12))
        for x in range(self.width):
            for y in range(self.height):
                #calculate notes
                if self._mode == KeyboardMode.Keyboard:
                    base = KeyboardTone.C.value + (self._octave * 12)
                    length = 7 if 7 < self.width else self.width
                    if y % 2 == 0:
                        scale = KeyboardScales['Keyboard']
                    else:
                        scale = KeyboardScales['KeyboardUpper']
                    if scale[x % length] == -1:
                        self._notes[x][y] = -1
                    else:
                        self._notes[x][y] = scale[x % length] + base + ((y // 2) * 12) + ((x // length) * 12)
                elif self._mode == KeyboardMode.ChromaticVertical:
                    # index = x + (y * self.width)
                    # index = x + (y * 5)
                    index = x + (y * (self._fold - 1))
                    self._notes[x][y] = index + base
                elif self._mode == KeyboardMode.ChromaticHorizontal:
                    index = y + (x * (self._fold - 1))
                    self._notes[x][y] = index + base
                elif self._mode == KeyboardMode.Diatonic:
                    self._notes[x][y] = precalc[x + (y * len(scale))]
                    # self._notes[x][y] = scale[x % len(scale)] + base + (y * 12) + ((x // len(scale)) * 12)
                elif self._mode == KeyboardMode.DiatonicVertical:
                    # self._notes[x][y] = precalc[x + (y * (self.width - 1)) - (y * 4)]
                    self._notes[x][y] = precalc[x + (y * len(scale)) - (y * (len(scale) - self._fold + 1))]
                elif self._mode == KeyboardMode.DiatonicHorizontal:
                    # self._notes[x][y] = precalc[y + (x * (self.width - 1)) - (x * 5)]
                    self._notes[x][y] = precalc[y + (x * len(scale)) - (x * (len(scale) - self._fold + 1))]
                #change colors
                if self._notes[x][y] == -1:
                    self.buttons[x][y].deactiveColor = [0, 0, 0]
                else:
                    if (self._notes[x][y] - self._tone.value) % 12 == 0:
                        self.buttons[x][y].deactiveColor = self._toneColor
                    elif (self._notes[x][y] - self._tone.value) % 12 in KeyboardScales[self._scale.name]:
                        self.buttons[x][y].deactiveColor = self._keyboardColor
                    else:
                        self.buttons[x][y].deactiveColor = self._nonScaleColor