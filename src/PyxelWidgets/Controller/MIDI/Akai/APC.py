import PyxelWidgets.Controller.MIDI
import PyxelWidgets.Helpers
import enum

class Mini(PyxelWidgets.Controller.MIDI.MIDI):

    class Colors(enum.Enum):
        Off = 0x00
        Green = 0x01
        GreenBlink = 0x02
        Red = 0x03
        RedBlink = 0x04
        Yellow = 0x05
        YellowBlink = 0x06

    def __init__(self, inPort: str, outPort: str, **kwargs):
        kwargs['width'] = kwargs.get('width', 8)
        kwargs['height'] = kwargs.get('height', 8)
        super().__init__(inPort, outPort, **kwargs)
        self.colorList = [Mini.Colors.Off, Mini.Colors.Red, Mini.Colors.Yellow, Mini.Colors.Green]
    
    def sendColor(self, x: int, y: int, color):
        index = (x + (y * 8)) & 0x7F
        self.sendNoteOn(index, color.value)

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        colorIndex = pixel.mono // 64
        index = (x + (y * 8)) & 0x7F
        self.sendNoteOn(index, self.colorList[colorIndex])
    
    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80:
            if midi[1] < 64:
                x = midi[1] % 8
                y = midi[1] // 6
                self.setButton(x, y, 0.0)
            elif midi[1] < 72:
                self.setCustom('released', 'button', midi[1] - 62, 0, 0.0)
            elif midi[1] < 90:
                self.setCustom('released', 'button', 0, 8 - (midi[1] - 82), 0.0)
        elif cmd == 0x90:
            if midi[1] < 64:
                x = midi[1] % 8
                y = midi[1] // 8
                self.setButton(x, y, 1.0)
            elif midi[1] < 72:
                self.setCustom('pressed', 'button', midi[1] - 62, 0, 1.0)
            elif midi[1] < 90:
                self.setCustom('pressed', 'button', 0, 8 - (midi[1] - 82), 1.0)
        elif cmd == 0xB0:
            self.setCustom('changed', 'slider', midi[1] - 48, 0, midi[2] / 127.0)