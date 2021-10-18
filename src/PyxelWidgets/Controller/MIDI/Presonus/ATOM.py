import PyxelWidgets.Controller.MIDI
import PyxelWidgets.Helpers
import enum

class ATOM(PyxelWidgets.Controller.MIDI.MIDI):

    class nativeControl(enum.Enum):
        Enable = 127
        Disable = 0

    def __init__(self, inPort: str, outPort: str, **kwargs):
        kwargs['width'] = kwargs.get('width', 4)
        kwargs['height'] = kwargs.get('height', 4)
        super().__init__(inPort, outPort, **kwargs)

    def setNativeControl(self, state):
        self.sendNoteOff(0, state.value, 15)

    def connect(self):
        super().connect()
        self.setNativeControl(ATOM.nativeControl.Enable)
        for i in range(36, 52):
            self.sendNoteOn(i, 127)
    
    def disconnect(self):
        for i in range(36, 52):
            self.sendNoteOn(i, 0)
        self.setNativeControl(ATOM.nativeControl.Disable)
        super().disconnect()
    
    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        index = 36 + x + (y * 4)
        pixel = pixel * 0.5
        self.sendNoteOn(index, pixel.r, 1)
        self.sendNoteOn(index, pixel.g, 2)
        self.sendNoteOn(index, pixel.b, 3)
    
    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x90:
            if midi[1] >= 36 and midi[1] < 52:
                x = (midi[1] - 36) % 4
                y = (midi[1] - 36) // 4
                self.setButton(x, y, midi[2] / 127.0)