import platform

import rtmidi
import rtmidi.midiutil

import pyxelwidgets.devices
import pyxelwidgets.devices.te_virtual_midi
import pyxelwidgets.events

class InvalidMIDIPortException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__("MIDI Port Invalid", *args)

class MIDI(pyxelwidgets.devices.Device):
    """
    A device talking MIDI through rtmidi (or teVirtualMIDI for virtual ports on
    Windows). Subclasses implement ``decode`` for input, ``send_pixel(s)`` for
    output, and ``on_connect`` / ``on_disconnect`` for mode switching messages.

    Without a grid (the default 1x1 with no output) it's a plain MIDI port pair:
    use ``send_*`` and override ``process_midi`` or ``decode``.

    ``check()`` notices the device being unplugged and plugged back in.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._midi_input = None
        self._midi_output = None
        self.virtual = False
        # The ports connect() was asked for, to reopen them after an unplug
        self._wanted = None
        #: True while unplugged: ``check()`` reconnects when the ports are back
        self.lost = False

    @staticmethod
    def available_ports() -> tuple:
        """Names of the (input, output) MIDI ports."""
        # A port still appearing can have no name yet
        return ([name for name in rtmidi.MidiIn().get_ports() if name is not None],
                [name for name in rtmidi.MidiOut().get_ports() if name is not None])

    @classmethod
    def find_ports(cls) -> tuple:
        """The first (input, output) port names containing one of ``cls.ports``, in pattern order."""
        inputs, outputs = cls.available_ports()
        return cls._first(inputs), cls._first(outputs)

    @classmethod
    def find(cls, **kwargs) -> 'MIDI':
        """Create the device and connect it to the ports matching ``cls.ports``."""
        in_port, out_port = cls.find_ports()
        if in_port is None and out_port is None:
            raise LookupError(f'No MIDI port found for {cls.__name__} (looked for {", ".join(cls.ports) or "nothing"})')
        device = cls(**kwargs)
        device.connect(in_port, out_port)
        return device

    def connect(self, in_port: str | None = None, out_port: str | None = None) -> None:
        """Open the given ports (names or indexes); with neither, find them from ``ports``."""
        self._wanted = (in_port, out_port)
        self.lost = False
        if in_port is None and out_port is None and self.ports:
            in_port, out_port = self.find_ports()
        super().connect()
        if in_port is not None:
            self._midi_input, self._midi_input_name = rtmidi.midiutil.open_midiinput(in_port, interactive = False)
            self._midi_input.ignore_types(sysex = False, timing = False)
            self._midi_input.set_callback(self.process_midi)
        if out_port is not None:
            self._midi_output, self._midi_output_name = rtmidi.midiutil.open_midioutput(out_port, interactive = False)
        if self._midi_input is None and self._midi_output is None:
            self.connected = False
            # Not plugged in: check() connects it when it is
            self.lost = bool(self.ports) or in_port is not None or out_port is not None
            return
        if self._midi_output is not None:
            self.on_connect()

    def connect_virtual(self, port: str) -> None:
        """Create virtual input and output ports named ``port`` for other software to connect to."""
        super().connect()
        if platform.system() == 'Windows':
            self._virtual_port = pyxelwidgets.devices.te_virtual_midi.TeVirtualMIDI()
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

    def check(self, ports: tuple | None = None) -> bool:
        """
        Notice the device being unplugged or plugged back in; call it now and
        then (App and the designer do, about once a second). A device whose
        port is gone closes its ports, sets ``lost`` and emits DeviceDisconnected;
        once its ports are back it reconnects, emits DeviceReconnected and
        resends everything it shows. Returns True if the connection changed.
        ``ports`` are ``available_ports()`` if known. Virtual ports are left alone.
        """
        if self.virtual or self._wanted is None or (not self.connected and not self.lost):
            return False
        inputs, outputs = ports if ports is not None else self.available_ports()
        if self.connected:
            gone = ((self._midi_input is not None and self._midi_input_name not in inputs)
                    or (self._midi_output is not None and self._midi_output_name not in outputs))
            if gone:
                self._unplugged()
            return gone
        in_port, out_port = self._wanted
        if in_port is None and out_port is None:
            in_port, out_port = self._first(inputs), self._first(outputs)
            if in_port is None and out_port is None:
                return False
        def present(port, names):
            return port is None or (port in names if isinstance(port, str) else 0 <= port < len(names))
        if not (present(in_port, inputs) and present(out_port, outputs)):
            return False
        wanted = self._wanted
        try:
            self.connect(in_port, out_port)
        except Exception:
            # Not ready yet (still appearing): next time
            self._close_ports()
            self.connected, self.lost = False, True
            return False
        finally:
            self._wanted = wanted
        if not self.connected:
            self.lost = True
            return False
        self.invalidate()
        self.emit(pyxelwidgets.events.DeviceReconnected(self))
        return True

    @classmethod
    def _first(cls, names) -> str | None:
        for pattern in cls.ports:
            for name in names:
                if pattern in name:
                    return name
        return None

    def _unplugged(self) -> None:
        # The ports are gone: close them without the goodbye messages
        self._close_ports()
        pyxelwidgets.devices.Device.disconnect(self)
        self.lost = True
        self.emit(pyxelwidgets.events.DeviceDisconnected(self))

    def _close_ports(self) -> None:
        for port in (self._midi_input, self._midi_output):
            if port is not None:
                try:
                    port.close_port()
                except Exception:
                    pass
        self._midi_input = self._midi_output = None

    def disconnect(self) -> None:
        self.lost = False
        if self.connected and self._midi_output is not None:
            self.on_disconnect()
        super().disconnect()
        if self._midi_input is not None:
            self._midi_input.close_port()
            self._midi_input = None
        if self._midi_output is not None:
            self._midi_output.close_port()
            self._midi_output = None

    def on_connect(self) -> None:
        """Override to put the device in the mode the driver expects."""

    def on_disconnect(self) -> None:
        """Override to return the device to its standalone mode."""

    def process_midi(self, message, _) -> None:
        """rtmidi callback: ``message`` is ``(bytes, delta_time)``."""
        self.decode(list(message[0]))

    def decode(self, midi: list) -> None:
        """Override to turn an incoming message into ``set_button`` calls and control events."""

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
