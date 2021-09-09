from ..MIDI import MIDI

class Launchpad(MIDI):
    def __init__(self, inPort: str = None, outPort: str = None, **kwargs):
        super().__init__(inPort, outPort, **kwargs)