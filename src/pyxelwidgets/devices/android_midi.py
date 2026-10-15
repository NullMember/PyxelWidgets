"""
The MIDI backend on Android (``midi.backend`` there): Android's MIDI service
(USB MIDI devices, paired Bluetooth MIDI devices, other apps' virtual ports)
through the app's Java ``MidiBridge`` (android/ in the repository), called with
Chaquopy. Ports look like rtmidi's, so ``MIDI`` devices work unchanged.

``MidiFramer`` (no Android needed) splits the byte runs Android delivers into
whole messages, as rtmidi does.
"""

__all__ = ['AndroidMidi', 'MidiFramer']

BRIDGE = 'io.github.nullmember.pyxelwidgets.MidiBridge'

def _length(status: int) -> int:
    """Data bytes after a status byte (sysex excluded)."""
    if status < 0xF0:
        return 1 if status & 0xF0 in (0xC0, 0xD0) else 2
    return {0xF1: 1, 0xF2: 2, 0xF3: 1}.get(status, 0)

class MidiFramer:
    """
    Turns a MIDI byte stream into messages: running status, system real-time
    bytes in the middle of other messages, and sysex spread over several runs.
    """

    def __init__(self):
        self._status = None
        self._data = []
        self._sysex = None

    def feed(self, data) -> list[list[int]]:
        messages = []
        for byte in data:
            if byte >= 0xF8:
                # Real-time: on its own, wherever it comes
                messages.append([byte])
            elif byte == 0xF0:
                self._sysex = [byte]
                self._status = None
            elif byte == 0xF7:
                if self._sysex is not None:
                    messages.append(self._sysex + [byte])
                    self._sysex = None
            elif byte & 0x80:
                self._sysex = None
                self._data = []
                if _length(byte) == 0:
                    messages.append([byte])
                    self._status = None
                else:
                    self._status = byte
            elif self._sysex is not None:
                self._sysex.append(byte)
            elif self._status is not None:
                self._data.append(byte)
                if len(self._data) == _length(self._status):
                    messages.append([self._status] + self._data)
                    self._data = []
                    # Running status lasts for channel messages only
                    if self._status >= 0xF0:
                        self._status = None
        return messages

class _Port:
    """An open port, looking like rtmidi's MidiIn/MidiOut."""

    def __init__(self, port, framer = None):
        self._port = port
        self._framer = framer
        self._callback = None

    def set_callback(self, callback) -> None:
        self._callback = callback

    def ignore_types(self, **types) -> None:
        """Sysex and timing always come through (as with ``ignore_types(sysex = False, timing = False)``)."""

    def receive(self, data) -> None:
        callback = self._callback
        for message in self._framer.feed(bytes(data)):
            if callback is not None:
                callback((message, 0.0), None)

    def send_message(self, message) -> None:
        self._port.send(bytes(message))

    def close_port(self) -> None:
        if self._port is not None:
            self._port.close()
            self._port = None

class AndroidMidi:
    """Lists and opens ports through ``MidiBridge`` (``midi.backend``)."""

    def __init__(self):
        from java import dynamic_proxy, jclass
        self._bridge = jclass(BRIDGE)
        listener = jclass(BRIDGE + '$Listener')

        class Listener(dynamic_proxy(listener)):
            def __init__(self, port):
                super().__init__()
                self.port = port

            def onMidi(self, data):
                self.port.receive(data)

        self._listener = Listener

    def list_ports(self) -> tuple:
        return list(self._bridge.inputs()), list(self._bridge.outputs())

    @staticmethod
    def _name(port, names) -> str:
        if isinstance(port, int):
            if not 0 <= port < len(names):
                raise ValueError(f'No MIDI port {port}')
            return names[port]
        return port

    def open_input(self, port) -> tuple:
        name = self._name(port, list(self._bridge.inputs()))
        opened = _Port(None, MidiFramer())
        opened._port = self._bridge.openInput(name, self._listener(opened))
        return opened, name

    def open_output(self, port) -> tuple:
        name = self._name(port, list(self._bridge.outputs()))
        return _Port(self._bridge.openOutput(name)), name

    def open_virtual(self, port: str) -> tuple:
        """The app's own MIDI device (named PyxelWidgets; Android's ports are declared up front, so ``port`` isn't used)."""
        receiving = _Port(None, MidiFramer())
        ports = self._bridge.openVirtual(self._listener(receiving))
        receiving._port = ports[0]
        return receiving, _Port(ports[1])
