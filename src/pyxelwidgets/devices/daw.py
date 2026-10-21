"""
The PyxelWidgets DAW protocol: one set of commands for every DAW, spoken by a
small script installed in the DAW (``pyxelwidgets daw install live``, see
``pyxelwidgets.daws``), the way controller makers ship theirs::

    daw = DAW()
    daw.connect_virtual('PyxelWidgets DAW')     # the script talks to this port
    surface.map(play, daw, Command('Play'), on = Pressed, feedback = True)
    surface.map(volume, daw, Command('Volume 1', Source('value')), on = Changed, feedback = True)
    surface.map(name, daw, Command('Track Name 1', Source('text')), feedback = True)

The commands (``COMMANDS``, the same in every DAW):

- buttons (pressed while the value is above 0; the DAW sends back their
  light, 1.0 or 0.0): transport (``Play``, ``Stop``, ``Record``, ``Loop``,
  ``Metronome``, ``Rewind``, ``Forward``, ``Undo``, ``Redo``, ``Tap Tempo``,
  ``Automation``, ``Capture``), navigation (``Track Left``/``Right`` move the
  selection, ``Bank Left``/``Right`` move the 8 strips by 8,
  ``Device Left``/``Right``, ``Macro Page Left``/``Right``, ``Scene Up``/``Down``),
  ``Scene Launch``, ``Stop All Clips``, ``Device On``, the selected track's
  ``Selected Mute``/``Solo``/``Arm``, and for strips 1-8 of the bank
  ``Select n``, ``Mute n``, ``Solo n``, ``Arm n``, ``Launch n`` (its clip in
  the selected scene) and ``Stop n``;
- faders (0.0-1.0 both ways): ``Volume n``, ``Pan n``, ``Send A n``,
  ``Send B n``, the selected device's ``Macro n`` (its first 8 parameters,
  or the DAW's quick/remote controls), ``Selected Volume``/``Pan``/``Send A``/
  ``Send B`` and ``Master Volume``;
- displays (received text): ``Track Name n``, ``Selected Name``,
  ``Device Name``, ``Macro Name n``, ``Macro Value n`` and ``DAW`` (which DAW
  the script runs in; also ``status_text``).

What a DAW can't do is ignored by its script (clips outside Ableton Live and
Bitwig, for example). On the wire: MIDI channel 16, buttons are notes
(``BUTTONS``), faders control changes (``FADERS``), texts SysEx
``F0 7D 50 57 field index text F7`` (``TEXTS``); ``F0 7D 50 57 7F F7`` asks the
script to send everything again, which ``DAW`` does when it connects.
"""

import pyxelwidgets.devices.midi_port
import pyxelwidgets.events
import pyxelwidgets.message

__all__ = ['DAW', 'COMMANDS', 'protocol']

#: The protocol's version, sent nowhere yet: bump it with changes scripts need to know about
VERSION = 1
CHANNEL = 15
#: SysEx after F0: the non-commercial manufacturer id, then "PW"
SYSEX = [0x7D, 0x50, 0x57]
REFRESH = 0x7F

def _strips(names: list, first: int) -> dict:
    return {f'{name} {strip + 1}': first + index * 8 + strip for index, name in enumerate(names) for strip in range(8)}

#: Button name → note number
BUTTONS = {
    'Play': 0, 'Stop': 1, 'Record': 2, 'Loop': 3, 'Metronome': 4, 'Rewind': 5, 'Forward': 6, 'Undo': 7, 'Redo': 8,
    'Tap Tempo': 9, 'Automation': 10, 'Capture': 11,
    'Track Left': 16, 'Track Right': 17, 'Bank Left': 18, 'Bank Right': 19, 'Device Left': 20, 'Device Right': 21,
    'Macro Page Left': 22, 'Macro Page Right': 23, 'Scene Up': 24, 'Scene Down': 25, 'Scene Launch': 26,
    'Stop All Clips': 27, 'Device On': 28, 'Selected Mute': 29, 'Selected Solo': 30, 'Selected Arm': 31,
    **_strips(['Select', 'Mute', 'Solo', 'Arm', 'Launch', 'Stop'], 32),
}
#: Fader name → control change number
FADERS = {
    **_strips(['Volume', 'Pan', 'Send A', 'Send B', 'Macro'], 16),
    'Selected Volume': 56, 'Selected Pan': 57, 'Selected Send A': 58, 'Selected Send B': 59, 'Master Volume': 60,
}
#: Text name → (field, index) in the SysEx
TEXTS = {
    **{f'Track Name {strip + 1}': (1, strip) for strip in range(8)},
    'Selected Name': (2, 0), 'Device Name': (3, 0),
    **{f'Macro Name {strip + 1}': (4, strip) for strip in range(8)},
    **{f'Macro Value {strip + 1}': (5, strip) for strip in range(8)},
    'DAW': (16, 0),
}
COMMANDS = {**{name: 'button' for name in BUTTONS}, **{name: 'fader' for name in FADERS}, **{name: 'display' for name in TEXTS}}

_NOTES = {note: name for name, note in BUTTONS.items()}
_CONTROLS = {number: name for name, number in FADERS.items()}
_FIELDS = {place: name for name, place in TEXTS.items()}

def protocol() -> dict:
    """The protocol as plain data, for DAW scripts (``pyxelwidgets.daws`` writes it into them)."""
    return {'version': VERSION, 'channel': CHANNEL, 'sysex': SYSEX, 'refresh': REFRESH,
            'buttons': BUTTONS, 'faders': FADERS, 'texts': {name: list(place) for name, place in TEXTS.items()}}

def text_sysex(name: str, text: str) -> list:
    """The SysEx (without F0/F7) a script sends for display ``name``."""
    field, index = TEXTS[name]
    return SYSEX + [field, index] + [ord(c) if 32 <= ord(c) < 127 else ord('?') for c in str(text)[:32]]

class DAW(pyxelwidgets.devices.midi_port.MidiPort):
    """
    Talks the PyxelWidgets DAW protocol (see the module) to the script
    installed in a DAW: send ``Command``s by name, receive the DAW's lights,
    values and names. Plain MIDI messages pass through too.
    """

    model = 'DAW (PyxelWidgets script)'
    #: Command name → kind: button, fader, display
    commands = COMMANDS
    messages = ('Command',) + pyxelwidgets.devices.midi_port.MidiPort.messages

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        #: The DAW the script said it runs in, once it did
        self.daw_name = None

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['commands'] = [{'name': name, 'kind': kind} for name, kind in cls.commands.items()]
        return info

    @property
    def status_text(self) -> str:
        return f'talking to {self.daw_name}' if self.daw_name else 'waiting for the DAW\'s PyxelWidgets script'

    def on_connect(self) -> None:
        # The script sends everything again: lights, values and names
        self.send_sysex(SYSEX + [REFRESH])

    def send(self, message) -> None:
        if not isinstance(message, pyxelwidgets.message.Command):
            return super().send(message)
        if self._midi_output is None:
            return
        name, value = message.name, message.value
        if name in BUTTONS:
            pressed = not isinstance(value, str) and float(value) > 0
            self._midi_output.send_message([0x90 | CHANNEL, BUTTONS[name], 127 if pressed else 0])
        elif name in FADERS and not isinstance(value, str):
            self._midi_output.send_message([0xB0 | CHANNEL, FADERS[name], max(0, min(127, round(float(value) * 127)))])

    def decode(self, midi: list) -> None:
        if midi[:1] == [0xF0]:
            if midi[1:4] == SYSEX and len(midi) >= 7:
                name = _FIELDS.get((midi[4], midi[5]))
                if name is not None:
                    text = bytes(midi[6:-1]).decode('ascii', 'replace')
                    if name == 'DAW':
                        self.daw_name = text
                    self._received(name, text)
            return
        status, channel = midi[0] & 0xF0, midi[0] & 0x0F
        if channel == CHANNEL and len(midi) >= 3:
            if status in (0x80, 0x90) and midi[1] in _NOTES:
                return self._received(_NOTES[midi[1]], 1.0 if status == 0x90 and midi[2] > 0 else 0.0)
            if status == 0xB0 and midi[1] in _CONTROLS:
                return self._received(_CONTROLS[midi[1]], midi[2] / 127)
        super().decode(midi)

    def _received(self, name: str, value) -> None:
        self.emit(pyxelwidgets.events.MessageReceived(self, pyxelwidgets.message.Command(name, value)))
