import PyxelWidgets.Controllers.MIDI
import PyxelWidgets.Helpers
import enum

class Mini(PyxelWidgets.Controllers.MIDI.MIDI):
    """
    Akai APC Mini Controller class
    ------------------------------

    Thanks to TomasHubelbauer for his amazing documentation:
        https://github.com/TomasHubelbauer/akai-apc-mini
        
    """
    class Colors(enum.Enum):
        Off = 0x00
        Green = 0x01
        GreenBlink = 0x02
        Red = 0x03
        RedBlink = 0x04
        Yellow = 0x05
        YellowBlink = 0x06
    
    class Notes(enum.Enum):
        Button_1 = 64
        Button_2 = 65
        Button_3 = 66
        Button_4 = 67
        Button_5 = 68
        Button_6 = 69
        Button_7 = 70
        Button_8 = 71
        Button_9 = 98
        Button_10 = 89
        Button_11 = 88
        Button_12 = 87
        Button_13 = 86
        Button_14 = 85
        Button_15 = 84
        Button_16 = 83
        Button_17 = 82
    
    class Controls(enum.Enum):
        Fader_1 = 48
        Fader_2 = 49
        Fader_3 = 50
        Fader_4 = 51
        Fader_5 = 52
        Fader_6 = 53
        Fader_7 = 54
        Fader_8 = 55
        Fader_9 = 56

    def __init__(self, **kwargs):
        kwargs['width'] = kwargs.get('width', 8)
        kwargs['height'] = kwargs.get('height', 8)
        super().__init__(**kwargs)
        self.colorList = [Mini.Colors.Off, Mini.Colors.Red, Mini.Colors.Yellow, Mini.Colors.Green]
    
    def sendColor(self, x: int, y: int, color):
        index = (x + (y * 8)) & 0x7F
        self.sendNoteOn(index, color.value)

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Helpers.Pixel):
        colorIndex = pixel.gmono // 64
        index = (x + (y * 8)) & 0x7F
        self.sendNoteOn(index, self.colorList[colorIndex])
    
    def processMIDI(self, message, _):
        midi, delta = message
        cmd = midi[0] & 0xF0
        chn = midi[0] & 0x0F
        if cmd == 0x80:
            if midi[1] < 64:
                x = midi[1] % 8
                y = midi[1] // 8
                self.setButton(x, y, 0.0)
            else:
                self.setCustom('released', Mini.Notes(midi[1]).name, 0.0)
        elif cmd == 0x90:
            if midi[1] < 64:
                x = midi[1] % 8
                y = midi[1] // 8
                self.setButton(x, y, 1.0)
            else:
                self.setCustom('pressed', Mini.Notes(midi[1]).name, 1.0)
        elif cmd == 0xB0:
            self.setCustom('changed', Mini.Controls(midi[1]).name, midi[2] / 127.0)