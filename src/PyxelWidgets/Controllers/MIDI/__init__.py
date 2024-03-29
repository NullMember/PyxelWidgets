__all__ = ['Akai', 'Novation', 'Presonus']

import PyxelWidgets.Controllers
import PyxelWidgets.Utils.teVirtualMIDI
import platform
import rtmidi
import rtmidi.midiutil

class InvalidMIDIPortException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__("MIDI Port Invalid", *args)

class MIDI(PyxelWidgets.Controllers.Controller):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._midiInput = None
        self._midiOutput = None
        self.virtual = False

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

    def connect(self, inPort: str = None, outPort: str = None):
        super().connect()
        if inPort is not None:
            self._midiInput, self._midiInputName = rtmidi.midiutil.open_midiinput(inPort, interactive = False)
            self._midiInput.ignore_types(sysex = False, timing = False)
            self._midiInput.set_callback(self.processMIDI)
        if outPort is not None:
            self._midiOutput, self._midiOutputName = rtmidi.midiutil.open_midioutput(outPort, interactive = False)
        if self._midiInput == None and self._midiOutput == None:
            self.connected = False
    
    def connectVirtual(self, port: str):
        super().connect()
        if platform.system() == 'Windows':
            self._virtualPort = PyxelWidgets.Utils.teVirtualMIDI.teVirtualMIDI()
            if self._virtualPort.open_port(port):
                self._virtualPort.set_callback(self.processMIDI)
                self._midiInput, self._midiInputName = (self._virtualPort, port)
                self._midiOutput, self._midiOutputName = (self._virtualPort, port)
                self.virtual = True
            else:
                self.connected = False
        else:
            self._midiInput, self._midiInputName = (rtmidi.MidiIn(), port)
            self._midiInput.open_virtual_port(port)
            self._midiInput.ignore_types(sysex = False, timing = False)
            self._midiInput.set_callback(self.processMIDI)
            self._midiOutput, self._midiOutputName = (rtmidi.MidiOut(), port)
            self._midiOutput.open_virtual_port(port)
            self.virtual = True

    def disconnect(self):
        super().disconnect()
        if self._midiInput is not None:
            self._midiInput.close_port()
            self._midiInput = None
        if self._midiOutput is not None:
            self._midiOutput.close_port()
            self._midiOutput = None
    
    def processMIDI(self, message, _):
        pass

    def sendSysex(self, message):
        self._midiOutput.send_message([240] + message + [247])
    
    def sendNoteOff(self, note, velocity = 0, channel = 0):
        self._midiOutput.send_message([0x80 | channel, note & 0x7F, velocity & 0x7F])

    def sendNoteOn(self, note, velocity, channel = 0):
        self._midiOutput.send_message([0x90 | channel, note & 0x7F, velocity & 0x7F])

    def sendAftertouch(self, note, velocity, channel = 0):
        self._midiOutput.send_message([0xA0 | channel, note & 0x7F, velocity & 0x7F])
    
    def sendControlChange(self, control, value, channel = 0):
        self._midiOutput.send_message([0xB0 | channel, control & 0x7F, value & 0x7F])
    
    def sendProgramChange(self, program, channel = 0):
        self._midiOutput.send_message([0xC0 | channel, program & 0x7F])
    
    def sendChannelAftertouch(self, velocity, channel = 0):
        self._midiOutput.send_message([0xD0 | channel, velocity & 0x7F])
    
    def sendPitchBend(self, bend, channel = 0):
        self._midiOutput.send_message([0xE0 | channel, bend & 0x7F, (bend >> 7) & 0x7F])
    
    def sendMessage(self, message: list):
        self._midiOutput.send_message(message)