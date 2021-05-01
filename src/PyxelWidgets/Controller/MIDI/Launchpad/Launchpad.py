from ..MIDI import MIDI

class Launchpad(MIDI):
    def __init__(self, inPort: str = None, outPort: str = None, **kwargs):
        # if inPort == None and outPort == None:
        #     self._inPort, self._outPort = self._findLaunchpad()
        # else:
        #     self._inPort = inPort
        #     self._outPort = outPort
        super().__init__(inPort, outPort, **kwargs)
    #     self._model, self._version = self._findLaunchpadModel()
    
    # def getLaunchpadInquiry(self):
    #     pass