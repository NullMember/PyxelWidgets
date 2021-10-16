from PyxelWidgets.Controller.MIDI.MIDI import MIDI

class Launchkey(MIDI):
    """
    Base class for Novation's Launchkey series devices
    """
    def __init__(self, inPort: str = None, outPort: str = None, **kwargs):
        super().__init__(inPort, outPort, **kwargs)