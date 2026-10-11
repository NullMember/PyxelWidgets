__all__ = ['InvalidMIDIPortException', 'MIDI']

import pyxelwidgets.controllers
import pyxelwidgets.controllers.midi.te_virtual_midi
import platform
import rtmidi
import rtmidi.midiutil

class InvalidMIDIPortException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__("MIDI Port Invalid", *args)

class MIDI(pyxelwidgets.controllers.Controller):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._midi_input = None
        self._midi_output = None
        self.virtual = False

    @staticmethod
    def list_input_devices():
        rtmidi.midiutil.list_input_ports()
    
    @staticmethod
    def list_output_devices():
        rtmidi.midiutil.list_output_ports()
    
    @staticmethod
    def list_io_devices():
        MIDI.list_input_devices()
        MIDI.list_output_devices()

    def connect(self, in_port: str = None, out_port: str = None):
        super().connect()
        if in_port is not None:
            self._midi_input, self._midi_input_name = rtmidi.midiutil.open_midiinput(in_port, interactive = False)
            self._midi_input.ignore_types(sysex = False, timing = False)
            self._midi_input.set_callback(self.process_midi)
        if out_port is not None:
            self._midi_output, self._midi_output_name = rtmidi.midiutil.open_midioutput(out_port, interactive = False)
        if self._midi_input == None and self._midi_output == None:
            self.connected = False
    
    def connect_virtual(self, port: str):
        super().connect()
        if platform.system() == 'Windows':
            self._virtual_port = pyxelwidgets.controllers.midi.te_virtual_midi.TeVirtualMIDI()
            if self._virtual_port.open_port(port):
                self._virtual_port.set_callback(self.process_midi)
                self._midi_input, self._midi_input_name = (self._virtual_port, port)
                self._midi_output, self._midi_output_name = (self._virtual_port, port)
                self.virtual = True
            else:
                self.connected = False
        else:
            self._midi_input, self._midi_input_name = (rtmidi.MidiIn(), port)
            self._midi_input.open_virtual_port(port)
            self._midi_input.ignore_types(sysex = False, timing = False)
            self._midi_input.set_callback(self.process_midi)
            self._midi_output, self._midi_output_name = (rtmidi.MidiOut(), port)
            self._midi_output.open_virtual_port(port)
            self.virtual = True

    def disconnect(self):
        super().disconnect()
        if self._midi_input is not None:
            self._midi_input.close_port()
            self._midi_input = None
        if self._midi_output is not None:
            self._midi_output.close_port()
            self._midi_output = None
    
    def process_midi(self, message, _):
        pass

    def send_sysex(self, message):
        self._midi_output.send_message([240] + message + [247])
    
    def send_note_off(self, note, velocity = 0, channel = 0):
        self._midi_output.send_message([0x80 | channel, note & 0x7F, velocity & 0x7F])

    def send_note_on(self, note, velocity, channel = 0):
        self._midi_output.send_message([0x90 | channel, note & 0x7F, velocity & 0x7F])

    def send_aftertouch(self, note, velocity, channel = 0):
        self._midi_output.send_message([0xA0 | channel, note & 0x7F, velocity & 0x7F])
    
    def send_control_change(self, control, value, channel = 0):
        self._midi_output.send_message([0xB0 | channel, control & 0x7F, value & 0x7F])
    
    def send_program_change(self, program, channel = 0):
        self._midi_output.send_message([0xC0 | channel, program & 0x7F])
    
    def send_channel_aftertouch(self, velocity, channel = 0):
        self._midi_output.send_message([0xD0 | channel, velocity & 0x7F])
    
    def send_pitch_bend(self, bend, channel = 0):
        self._midi_output.send_message([0xE0 | channel, bend & 0x7F, (bend >> 7) & 0x7F])
    
    def send_message(self, message: list):
        self._midi_output.send_message(message)