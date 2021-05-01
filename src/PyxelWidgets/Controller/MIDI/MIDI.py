from ..Controller import Controller
import rtmidi.midiutil

class MIDI(Controller):
    def __init__(self, inPort: str, outPort: str, **kwargs):
        super().__init__(**kwargs)
        self._midiInput, self._midiInputName = rtmidi.midiutil.open_midiinput(inPort, interactive = False)
        self._midiOutput, self._midiOutputName = rtmidi.midiutil.open_midioutput(outPort, interactive = False)
        self._midiInput.ignore_types(sysex = False)
    
    def __del__(self):
        self._midiInput.close_port()
        self._midiInput.delete()
        self._midiOutput.close_port()
        self._midiOutput.delete()
    
    # def sendInquiry(self):
    #     inPorts = rtmidi.MidiIn().get_ports()
    #     outPorts = rtmidi.MidiOut().get_ports()
    #     ins = [rtmidi.MidiIn()] * len(inPorts)
    #     for i in range(len(inPorts)):
    #         ins.open_port(i)
    #     out = rtmidi.MidiOut()
    #     for i in range(len(outPorts)):

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
        self._midiOutput.send_message([0xD0 | channel, bend & 0x7F, (bend >> 7) & 0x7F])