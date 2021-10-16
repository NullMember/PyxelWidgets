from PyxelWidgets.Controller.MIDI.MIDI import MIDI

class Launchpad(MIDI):
    """
    Base class for Novation's Launchpad devices
    """
    def __init__(self, inPort: str = None, outPort: str = None, **kwargs):
        super().__init__(inPort, outPort, **kwargs)