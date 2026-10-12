"""
OSC over UDP (needs the ``osc`` extra: ``pip install "pyxelwidgets[osc]"``)::

    reaper = REAPER()                 # REAPER's defaults: sends to port 8000, listens on 9000
    reaper.connect()
    surface.map(play, reaper, OscMessage('/play', 1.0), on = Pressed, feedback = True)
    surface.map(volume, reaper, OscMessage('/track/{x+1}/volume', Source('value')), on = Changed, feedback = True)

Received messages are emitted as MessageReceived with an OscMessage.
"""

import threading

import pyxelwidgets.devices
import pyxelwidgets.events
import pyxelwidgets.message

__all__ = ['OSC', 'REAPER']

class OSC(pyxelwidgets.devices.Device):
    """
    Sends OscMessages to ``host``:``send_port`` with ``send`` and listens on
    ``receive_port`` (None: doesn't listen). ``addresses`` are suggestions for
    editors.
    """

    model = 'OSC'
    messages: tuple = ('OscMessage',)
    addresses: tuple = ()

    def __init__(self, *, host: str = '127.0.0.1', send_port: int = 8000, receive_port: int | None = 9000, **kwargs):
        super().__init__(**kwargs)
        self.host = host
        self.send_port = send_port
        self.receive_port = receive_port
        self.client = None
        self.server = None

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['addresses'] = list(cls.addresses)
        info['messages'] = list(cls.messages)
        return info

    def connect(self) -> None:
        import pythonosc.dispatcher
        import pythonosc.osc_server
        import pythonosc.udp_client
        super().connect()
        self.client = pythonosc.udp_client.SimpleUDPClient(self.host, self.send_port)
        if self.receive_port is not None:
            dispatcher = pythonosc.dispatcher.Dispatcher()
            dispatcher.set_default_handler(self._received)
            self.server = pythonosc.osc_server.ThreadingOSCUDPServer(('0.0.0.0', self.receive_port), dispatcher)
            threading.Thread(target = self.server.serve_forever, name = f'{self.name}_osc', daemon = True).start()

    def disconnect(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.client = None
        super().disconnect()

    def send(self, message: pyxelwidgets.message.OscMessage) -> None:
        if self.client is not None:
            self.client.send_message(message.address, list(message.args))

    def _received(self, address: str, *args) -> None:
        self.emit(pyxelwidgets.events.MessageReceived(self, pyxelwidgets.message.OscMessage(address, *args)))

class REAPER(OSC):
    """REAPER's default OSC pattern (Default.ReaperOSC): tracks are ``{x+1}``-style placeholders for ``@``."""

    model = 'REAPER (OSC)'
    vendor = 'Cockos'
    addresses = (
        '/play', '/stop', '/pause', '/record', '/rewind', '/forward', '/repeat', '/click',
        '/track/{x+1}/volume', '/track/{x+1}/pan', '/track/{x+1}/mute', '/track/{x+1}/solo',
        '/track/{x+1}/recarm', '/track/{x+1}/select', '/track/{x+1}/name', '/track/{x+1}/vu',
        '/master/volume', '/master/pan', '/time/str', '/beat/str', '/tempo/raw', '/action',
    )
