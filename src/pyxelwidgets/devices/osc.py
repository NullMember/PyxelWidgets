"""OSC devices (needs the ``osc`` extra: ``pip install "pyxelwidgets[osc]"``)."""

__all__ = ['OSC', 'REAPER']

import pythonosc.udp_client
import pythonosc.dispatcher
import pythonosc.osc_server
import threading

import pyxelwidgets.devices
import pyxelwidgets.events

class OSC(pyxelwidgets.devices.Device):
    """
    Talks OSC over UDP. ``messages`` maps control names to OSC addresses:
    incoming messages are emitted as ControlChanged (``value`` is the message's
    first argument) and ``send(name, value)`` sends one.
    """

    model = 'OSC'
    messages: dict = {}

    def __init__(self, ip: str, in_port: int = 8000, out_port: int = 9000, **kwargs):
        super().__init__(**kwargs)
        self.messages = dict(self.messages)
        self.client = pythonosc.udp_client.SimpleUDPClient(ip, out_port)
        self.dispatcher = pythonosc.dispatcher.Dispatcher()
        self.server = pythonosc.osc_server.ThreadingOSCUDPServer(('0.0.0.0', in_port), self.dispatcher)
        self.handlers = {}

    def connect(self) -> None:
        super().connect()
        self.register()
        self._server_thread = threading.Thread(target = self.server.serve_forever, daemon = True)
        self._server_thread.start()
    
    def disconnect(self) -> None:
        self.server.shutdown()
        self.unregister()
        super().disconnect()
    
    def send(self, name: str, value) -> None:
        self.client.send_message(self.messages[name], value)
    
    def register(self) -> None:
        for name, address in self.messages.items():
            self.handlers[name] = self.dispatcher.map(address, self.process, name)
    
    def unregister(self) -> None:
        for name, address in self.messages.items():
            self.dispatcher.unmap(address, self.handlers[name])
    
    def process(self, address: str, args, *values) -> None:
        self.emit(pyxelwidgets.events.ControlChanged(self, args[0], values[0] if values else None))

class REAPER(OSC):
    """REAPER's default OSC pattern (a starting point: only a few addresses so far)."""

    model = 'REAPER'
    messages = {
        "Update" : "/update",
        "Crossfade" : "/crossfade",
        "ProjectName" : "/project/name",
        "ProjectEngine" : "/project/engine",
        "Play" : "/play",
        "Record" : "/record",
        "Repeat" : "/repeat",
        "Click" : "/click",
        "ClickVolume" : "/click/volume"
    }
