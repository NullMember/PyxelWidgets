__all__ = ['Akai', 'Novation', 'Presonus']

import PyxelWidgets.Controller
import rtmidi.midiutil

class InvalidMIDIPortException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__("MIDI Port Invalid", *args)

class MIDI(PyxelWidgets.Controller.Controller):
    def __init__(self, inPort: str, outPort: str, **kwargs):
        super().__init__(**kwargs)
        try:
            self._midiInput, self._midiInputName = rtmidi.midiutil.open_midiinput(inPort, interactive = False)
            self._midiOutput, self._midiOutputName = rtmidi.midiutil.open_midioutput(outPort, interactive = False)
            self._midiInput.ignore_types(sysex = False)
        except:
            raise InvalidMIDIPortException()
    
    def __del__(self):
        self.disconnect()
        self._midiInput.close_port()
        self._midiOutput.close_port()

    @staticmethod
    def listInputDevices():
        rtmidi.midiutil.list_input_ports()
    
    @staticmethod
    def listOutputDevices():
        rtmidi.midiutil.list_output_ports()
    
    @staticmethod
    def listIODevices():
        MIDI.listInputDevices()
        MIDI.listOutputDevices()

    def connect(self):
        if not self.connected:
            super().connect()
        self._midiInput.set_callback(self.processMIDI)
    
    def disconnect(self):
        self._midiInput.set_callback(lambda *_, **__: None)
        if self.connected:
            super().disconnect()
    
    def processMIDI(self, message, _):
        raise NotImplementedError("processMIDI must be implemented")

    def sendSysex(self, message):
        self._midiOutput.send_message([240] + message + [247])
    
    def sendNoteOff(self, note, velocity = 0, channel = 0):
        self._midiOutput.send_message([0x80 | channel, note, velocity])

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