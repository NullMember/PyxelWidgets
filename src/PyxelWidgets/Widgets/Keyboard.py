import PyxelWidgets.Widgets
import PyxelWidgets.Helpers
import enum
import numpy

class Keyboard(PyxelWidgets.Widgets.Widget):

    _count = 0

    class Mode(enum.Enum):
        Keyboard            = enum.auto()
        ChromaticVertical   = enum.auto()
        ChromaticHorizontal = enum.auto()
        Diatonic            = enum.auto()
        DiatonicVertical    = enum.auto()
        DiatonicHorizontal  = enum.auto()

    class Scale(enum.Enum):
        Major           = enum.auto()
        Minor           = enum.auto()
        Dorian          = enum.auto()
        Mixolydian      = enum.auto()
        Lydian          = enum.auto()
        Phrygian        = enum.auto()
        Locrian         = enum.auto()
        Diminished      = enum.auto()
        WholeHalf       = enum.auto()
        WholeTone       = enum.auto()
        MinorBlues      = enum.auto()
        MinorPentatonic = enum.auto()
        MajorPentatonic = enum.auto()
        MinorHarmonic   = enum.auto()
        MinorMelodic    = enum.auto()

    class Tone(enum.Enum):
        C   = enum.auto()
        CS  = enum.auto()
        D   = enum.auto()
        DS  = enum.auto()
        E   = enum.auto()
        F   = enum.auto()
        FS  = enum.auto()
        G   = enum.auto()
        GS  = enum.auto()
        A   = enum.auto()
        AS  = enum.auto()
        B   = enum.auto()

    Scales = {
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

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, **kwargs):
        kwargs['name'] = kwargs.get('name', f'Keyboard_{Keyboard._count}')
        self._octave = kwargs.get('octave', 0)
        self._fold = kwargs.get('fold', 4)
        self._mode: Keyboard.Mode = kwargs.get('mode', Keyboard.Mode.Diatonic)
        self._scale: Keyboard.Scale = kwargs.get('scale', Keyboard.Scale.Major)
        self._tone: Keyboard.Tone = kwargs.get('tone', Keyboard.Tone.C)
        self._toneColor: PyxelWidgets.Helpers.Pixel = kwargs.get('toneColor', PyxelWidgets.Helpers.Colors.Magenta)
        self._keyboardColor: PyxelWidgets.Helpers.Pixel = kwargs.get('keyboardColor', PyxelWidgets.Helpers.Colors.Cyan)
        self._nonScaleColor: PyxelWidgets.Helpers.Pixel = kwargs.get('nonScaleColor', PyxelWidgets.Helpers.Colors.Yellow)
        kwargs['activeColor'] = kwargs.get('activeColor', PyxelWidgets.Helpers.Colors.Green)
        self.buttons = None
        self.notes = None
        self.colors = None
        self.states = None
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        Keyboard._count += 1

    @property
    def octave(self):
        return self._octave
    
    @octave.setter
    def octave(self, octave: int):
        self._octave = octave
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def fold(self):
        return self._fold
    
    @fold.setter
    def fold(self, fold: int):
        self._fold = fold
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def mode(self):
        return self._mode
    
    @mode.setter
    def mode(self, mode: Mode):
        self._mode = mode
        self._resize(self.width, self.height)
        self.updated = True
    
    @property
    def scale(self):
        return self._scale
    
    @scale.setter
    def scale(self, scale: Scale):
        self._scale = scale
        self._resize(self.width, self.height)
        self.updated = True
    
    @property
    def tone(self):
        return self._tone
    
    @tone.setter
    def tone(self, tone: Tone):
        self._tone = tone
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def toneColor(self):
        return self._toneColor
    
    @toneColor.setter
    def toneColor(self, toneColor: PyxelWidgets.Helpers.Pixel):
        self._toneColor = toneColor
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def keyboardColor(self):
        return self._keyboardColor
    
    @keyboardColor.setter
    def keyboardColor(self, keyboardColor: PyxelWidgets.Helpers.Pixel):
        self._keyboardColor = keyboardColor
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def nonScaleColor(self):
        return self._nonScaleColor
    
    @nonScaleColor.setter
    def nonScaleColor(self, nonScaleColor: PyxelWidgets.Helpers.Pixel):
        self._nonScaleColor = nonScaleColor
        self._resize(self.width, self.height)
        self.updated = True

    def pressed(self, x: int, y: int, value: float):
        super().pressed(x, y, value)
        for button in self.buttons[self.notes[x, y]]:
            self.states[button[0], button[1]] = True
        self._callback(self.name, 'changed', (self.notes[x, y], 1.0))
        self.updated = True
        
    
    def released(self, x: int, y: int, value: float):
        super().released(x, y, value)
        for button in self.buttons[self.notes[x, y]]:
            self.states[button[0], button[1]] = False
        self._callback(self.name, 'changed', (self.notes[x, y], 0.0))
        self.updated = True
    
    def updateArea(self, rect: PyxelWidgets.Helpers.Rectangle2D) -> tuple:
        self.updated = False
        intersect = self.rect.intersect(rect)
        if intersect is not None:
            area = intersect - self.rect
            for x in area.columns:
                for y in area.rows:
                    note = self.notes[x, y]
                    if note >= 0:
                        if self.states[x, y]:
                            self.buffer[x, y] = self.activeColor
                        else:
                            self.buffer[x, y] = self.colors[note]
            return intersect, self.buffer[area.slice]
        return None, None

    def _resize(self, width, height) -> bool:
        self.notes = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.states = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.colors = [PyxelWidgets.Helpers.Colors.Invisible for i in range(128)]
        self.buttons = [[] for i in range(128)]
        self._calcNotes()

    def _calcNotes(self):
        base = self._tone.value + (self._octave * 12)
        scale = Keyboard.Scales[self._scale.name]
        precalc = []
        #precalculate scale values
        for i in range(self.rect.h * self.rect.w):
            precalc.append(scale[i % len(scale)] + base + ((i // len(scale)) * 12))
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                #calculate notes
                if self._mode == Keyboard.Mode.Keyboard:
                    base = Keyboard.Tone.C.value + (self._octave * 12)
                    length = 7 if 7 < self.rect.w else self.rect.w
                    if y % 2 == 0:
                        scale = Keyboard.Scales['Keyboard']
                    else:
                        scale = Keyboard.Scales['KeyboardUpper']
                    if scale[x % length] == -1:
                        self.notes[x, y] = -1
                    else:
                        self.notes[x, y] = scale[x % length] + base + ((y // 2) * 12) + ((x // length) * 12)
                elif self._mode == Keyboard.Mode.ChromaticVertical:
                    index = x + (y * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._mode == Keyboard.Mode.ChromaticHorizontal:
                    index = y + (x * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._mode == Keyboard.Mode.Diatonic:
                    self.notes[x, y] = precalc[x + (y * len(scale))]
                elif self._mode == Keyboard.Mode.DiatonicVertical:
                    self.notes[x, y] = precalc[x + (y * len(scale)) - (y * (len(scale) - self._fold + 1))]
                elif self._mode == Keyboard.Mode.DiatonicHorizontal:
                    self.notes[x, y] = precalc[y + (x * len(scale)) - (x * (len(scale) - self._fold + 1))]
                #clear notes 128 or higher
                if self.notes[x, y] > 127:
                    self.notes[x, y] = -1
                #make array from same buttons
                if self.notes[x, y] != -1:
                    self.buttons[self.notes[x, y]].append([x, y])
                #change colors
                if self.notes[x, y] != -1:
                    if (self.notes[x, y] - self._tone.value) % 12 == 0:
                        self.colors[self.notes[x, y]] = self._toneColor
                    elif (self.notes[x, y] - self._tone.value) % 12 in Keyboard.Scales[self._scale.name]:
                        self.colors[self.notes[x, y]] = self._keyboardColor
                    else:
                        self.colors[self.notes[x, y]] = self._nonScaleColor