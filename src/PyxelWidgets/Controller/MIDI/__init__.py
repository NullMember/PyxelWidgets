__all__ = ['Akai', 'Novation']

import PyxelWidgets.Controller
import rtmidi.midiutil

class MIDI(PyxelWidgets.Controller.Controller):
    def __init__(self, inPort: str, outPort: str, **kwargs):
        super().__init__(**kwargs)
        self._midiInput, self._midiInputName = rtmidi.midiutil.open_midiinput(inPort, interactive = False)
        self._midiOutput, self._midiOutputName = rtmidi.midiutil.open_midioutput(outPort, interactive = False)
        self._midiInput.ignore_types(sysex = False)
    
    def __del__(self):
        self.disconnect()
        self._midiInput.close_port()
        self._midiOutput.close_port()

    def connect(self):
        super().connect()
        self._midiInput.set_callback(self.processInput)
    
    def disconnect(self):
        self._midiInput.set_callback(lambda *_, **__: None)
        super().disconnect()

    def sendSysex(self, message):
        self._midiOutput.send_message([240] + message + [247])
    
    def sendNoteOff(self, note, channel = 0):
        self._midiOutput.send_message([0x80 | channel, note, 0])

    def sendNoteOn(self, note, velocity, channel = 0):
        self._midiOutput.send_message([0x90 | channel, note, velocity])

    def sendAftertouch(self, note, velocity, channel = 0):
        self._midiOutput.send_message([0xA0 | channel, note, velocity])
    
    def sendControlChange(self, control, value, channel = 0):
        self._midiOutput.send_message([0xB0 | channel, control, value])
    
    def sendProgramChange(self, program, channel = 0):
        self._midiOutput.send_message([0xC0 | channel, program])
    
    def sendChannelAftertouch(self, velocity, channel):
        self._midiOutput.send_message([0xD0 | channel, velocity])
    
    def sendPitchBend(self, bend, channel = 0):
        self._midiOutput.send_message([0xE0 | channel, bend & 0x7F, (bend >> 7) & 0x7F])