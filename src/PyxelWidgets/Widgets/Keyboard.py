import PyxelWidgets.Widgets
import PyxelWidgets.Utils.Enums
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle
import enum
import numpy

class Keyboard(PyxelWidgets.Widgets.Widget):

    _count = 0

    class Type(enum.Enum):
        Keyboard            = 0
        ChromaticVertical   = 1
        ChromaticHorizontal = 2
        Diatonic            = 3
        DiatonicVertical    = 4
        DiatonicHorizontal  = 5

    class Scale(enum.Enum):
        Major           = 0
        Minor           = 1
        Dorian          = 2
        Mixolydian      = 3
        Lydian          = 4
        Phrygian        = 5
        Locrian         = 6
        Diminished      = 7
        WholeHalf       = 8
        WholeTone       = 9
        MinorBlues      = 10
        MinorPentatonic = 11
        MajorPentatonic = 12
        MinorHarmonic   = 13
        MinorMelodic    = 14

    class Root(enum.Enum):
        C   = 0
        CS  = 1
        D   = 2
        DS  = 3
        E   = 4
        F   = 5
        FS  = 6
        G   = 7
        GS  = 8
        A   = 9
        AS  = 10
        B   = 11

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
        self._type: Keyboard.Type = kwargs.get('type', Keyboard.Type.Diatonic)
        self._scale: Keyboard.Scale = kwargs.get('scale', Keyboard.Scale.Major)
        self._root: Keyboard.Root = kwargs.get('root', Keyboard.Root.C)
        self._rootColor: PyxelWidgets.Utils.Pixel.Pixel = kwargs.get('rootColor', PyxelWidgets.Utils.Pixel.Colors.Magenta)
        self._keyboardColor: PyxelWidgets.Utils.Pixel.Pixel = kwargs.get('keyboardColor', PyxelWidgets.Utils.Pixel.Colors.Cyan)
        self._nonScaleColor: PyxelWidgets.Utils.Pixel.Pixel = kwargs.get('nonScaleColor', PyxelWidgets.Utils.Pixel.Colors.Yellow)
        kwargs['activeColor'] = kwargs.get('activeColor', PyxelWidgets.Utils.Pixel.Colors.Green)
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
    def type(self):
        return self._type
    
    @type.setter
    def type(self, mode: Type):
        self._type = mode
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
    def root(self):
        return self._root
    
    @root.setter
    def root(self, root: Root):
        self._root = root
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def rootColor(self):
        return self._rootColor
    
    @rootColor.setter
    def rootColor(self, rootColor: PyxelWidgets.Utils.Pixel.Pixel):
        self._rootColor = rootColor
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def keyboardColor(self):
        return self._keyboardColor
    
    @keyboardColor.setter
    def keyboardColor(self, keyboardColor: PyxelWidgets.Utils.Pixel.Pixel):
        self._keyboardColor = keyboardColor
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def nonScaleColor(self):
        return self._nonScaleColor
    
    @nonScaleColor.setter
    def nonScaleColor(self, nonScaleColor: PyxelWidgets.Utils.Pixel.Pixel):
        self._nonScaleColor = nonScaleColor
        self._resize(self.width, self.height)
        self.updated = True

    def press(self, x: int, y: int, value: float):
        if self.notes[x, y] >= 0:
            for button in self.buttons[self.notes[x, y]]:
                self.states[button[0], button[1]] = True
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Changed, (self.notes[x, y], 1.0))
        self.updated = True
    
    def release(self, x: int, y: int, value: float):
        if self.notes[x, y] >= 0:
            for button in self.buttons[self.notes[x, y]]:
                self.states[button[0], button[1]] = False
        self.callback(self.name, PyxelWidgets.Utils.Enums.Event.Changed, (self.notes[x, y], 0.0))
        self.updated = True
    
    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D) -> tuple:
        intersect = self.rect.intersect(rect)
        if intersect is not None:
            area = intersect - self.rect
            if self.bufferUpdated:
                self.bufferUpdated = False
                for x in area.columns:
                    for y in area.rows:
                        note = self.notes[x, y]
                        if note >= 0:
                            if self.states[x, y]:
                                self.buffer[x, y] = self.activeColor
                            else:
                                self.buffer[x, y] = self.colors[note]
                        else:
                            self.buffer[x, y] = self.deactiveColor
                if self.effect is None:
                    return intersect, self.buffer[area.slice]
            if self.effect is not None:
                return intersect, self.effect.apply(self.buffer[area.slice])
        return None, None

    def _resize(self, width, height) -> bool:
        self.notes = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.states = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.colors = [PyxelWidgets.Utils.Pixel.Colors.Invisible for i in range(128)]
        self.buttons = [[] for i in range(128)]
        self._calcNotes()

    def _calcNotes(self):
        base = self._root.value + (self._octave * 12)
        scale = Keyboard.Scales[self._scale.name]
        precalc = []
        #precalculate scale values
        for i in range(self.rect.area):
            precalc.append(scale[i % len(scale)] + base + ((i // len(scale)) * 12))
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                #calculate notes
                if self._type == Keyboard.Type.Keyboard:
                    base = Keyboard.Root.C.value + (self._octave * 12)
                    length = 7 if 7 < self.rect.w else self.rect.w
                    if y % 2 == 0:
                        scale = Keyboard.Scales['Keyboard']
                    else:
                        scale = Keyboard.Scales['KeyboardUpper']
                    if scale[x % length] == -1:
                        self.notes[x, y] = -1
                    else:
                        self.notes[x, y] = scale[x % length] + base + ((y // 2) * 12) + ((x // length) * 12)
                elif self._type == Keyboard.Type.ChromaticVertical:
                    index = x + (y * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._type == Keyboard.Type.ChromaticHorizontal:
                    index = y + (x * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._type == Keyboard.Type.Diatonic:
                    self.notes[x, y] = precalc[x + (y * len(scale))]
                elif self._type == Keyboard.Type.DiatonicVertical:
                    self.notes[x, y] = precalc[x + (y * len(scale)) - (y * (len(scale) - self._fold + 1))]
                elif self._type == Keyboard.Type.DiatonicHorizontal:
                    self.notes[x, y] = precalc[y + (x * len(scale)) - (x * (len(scale) - self._fold + 1))]
                #clear notes 128 or higher
                if self.notes[x, y] > 127:
                    self.notes[x, y] = -1
                #make array from same buttons
                if self.notes[x, y] != -1:
                    self.buttons[self.notes[x, y]].append([x, y])
                #change colors
                if self.notes[x, y] != -1:
                    if (self.notes[x, y] - self._root.value) % 12 == 0:
                        self.colors[self.notes[x, y]] = self._rootColor
                    elif (self.notes[x, y] - self._root.value) % 12 in Keyboard.Scales[self._scale.name]:
                        self.colors[self.notes[x, y]] = self._keyboardColor
                    else:
                        self.colors[self.notes[x, y]] = self._nonScaleColor