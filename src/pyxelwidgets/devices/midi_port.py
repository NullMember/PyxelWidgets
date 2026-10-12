"""
A plain MIDI port pair to send widget messages to other software (a DAW, a
synth) and receive what it sends back::

    port = MidiPort()
    port.connect_virtual('PyxelWidgets')          # a port the DAW can pick
    port.connect(out_port = 'IAC Driver Bus 1')    # or an existing port

    surface.map(kick, port, NoteOn(36), on = Pressed)

See ``pyxelwidgets.mapping`` and ``pyxelwidgets.message``.
"""

import pyxelwidgets.devices.midi
import pyxelwidgets.events
import pyxelwidgets.message

__all__ = ['MidiPort']

class MidiPort(pyxelwidgets.devices.midi.MIDI):
    """Sends MidiMessages with ``send``; received channel messages are emitted as MessageReceived."""

    model = 'MIDI Port'
    #: Message classes ``send`` takes (by name, from pyxelwidgets.message)
    messages: tuple = ('NoteOn', 'NoteOff', 'ControlChange', 'ProgramChange', 'PitchBend', 'PolyPressure', 'ChannelPressure')

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['messages'] = list(cls.messages)
        return info

    def send(self, message: pyxelwidgets.message.MidiMessage) -> None:
        if self._midi_output is not None:
            self._midi_output.send_message(message.to_midi())

    def decode(self, midi: list) -> None:
        message = pyxelwidgets.message.MidiMessage.from_midi(midi)
        if message is not None:
            self.emit(pyxelwidgets.events.MessageReceived(self, message))
