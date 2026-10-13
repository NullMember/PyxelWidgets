"""
OSC over UDP (needs the ``osc`` extra: ``pip install "pyxelwidgets[osc]"``)::

    reaper = REAPER()                 # REAPER's defaults: sends to port 8000, listens on 9000
    reaper.connect()
    surface.map(play, reaper, OscMessage('/play', 1.0), on = Pressed, feedback = True)
    surface.map(volume, reaper, OscMessage('/track/{x+1}/volume', Source('value')), on = Changed, feedback = True)

Received messages are emitted as MessageReceived with an OscMessage.

REAPER also reaches plug-in parameters by name: ``scan_tracks()``,
``scan_plugins(track)`` and ``scan_parameters(track, plugin)`` ask REAPER
for its names, and ``PluginParameter`` messages set a parameter (0.0-1.0)::

    reaper.scan_tracks()                       # ['Drums', 'Bass', ..., 'MASTER']
    reaper.scan_plugins('Bass')                # ['3-Band EQ', 'Volume/Pan Smoother']
    reaper.scan_parameters('Bass', '3-Band EQ')  # ['Low (dB)', 'Frequency (Hz)', 'Mid (dB)', ...]
    surface.map(knob, reaper, PluginParameter('Bass', '3-Band EQ', 'Mid (dB)', Source('value')),
                on = Changed, feedback = True)
"""

import math
import re
import threading
import time

import pyxelwidgets.devices
import pyxelwidgets.devices.plugins
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
            # One thread, so messages are handled in the order they came
            self.server = pythonosc.osc_server.BlockingOSCUDPServer(('0.0.0.0', self.receive_port), dispatcher)
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

# REAPER's feedback for a plug-in parameter of the selected track, or of a track in the bank
_SELECTED_VALUE = re.compile(r'/fx/(\d+)/fxparam/(\d+)/value')
_TRACK_VALUE = re.compile(r'/track/(\d+)/fx/(\d+)/fxparam/(\d+)/value')
# What scans read: names, numbers and the device's selections
_SCAN_ADDRESS = re.compile(r'/(name|str)$|^/device/')

class REAPER(pyxelwidgets.devices.plugins.PluginParameters, OSC):
    """
    REAPER's default OSC pattern (Default.ReaperOSC): tracks are ``{x+1}``-style
    placeholders for ``@``. In REAPER: Preferences > Control/OSC/web > Add >
    OSC, mode "Configure device IP+local port", device port 9000 (``receive_port``),
    local listen port 8000 (``send_port``).

    Plug-in parameters by name: REAPER sends a device the names in its banks
    (tracks 8 at a time, a plug-in's parameters 16 at a time) and only what
    changed, so the output keeps all it was sent (``state``, after a refresh
    of the surfaces on the first scan) and goes through the banks. Setting a
    parameter selects its track in the device (``/track/...`` without a
    number then means that track). REAPER sends a parameter's changes back
    only while its track is in the device's bank of tracks (the first 8,
    unless the bank was moved) and the parameter among the 16 shown.
    """

    model = 'REAPER (OSC)'
    vendor = 'Cockos'
    addresses = (
        '/play', '/stop', '/pause', '/record', '/rewind', '/forward', '/repeat', '/click',
        '/track/{x+1}/volume', '/track/{x+1}/pan', '/track/{x+1}/mute', '/track/{x+1}/solo',
        '/track/{x+1}/recarm', '/track/{x+1}/select', '/track/{x+1}/name', '/track/{x+1}/vu',
        '/master/volume', '/master/pan', '/time/str', '/beat/str', '/tempo/raw', '/action',
        '/device/track/bank/+', '/device/track/bank/-', '/fx/1/fxparam/{x+1}/value',
    )
    messages = OSC.messages + ('PluginParameter',)
    #: PluginParameter's value: the parameter's position 0.0-1.0 (a widget's value)
    parameter_value = 'value'

    #: Seconds without new names after which REAPER has answered
    settle = 0.1
    #: Seconds to wait for REAPER to answer at all (it sends nothing when nothing changed)
    timeout = 0.5
    #: Seconds a refresh of everything may take (REAPER spaces its packets)
    refresh_time = 5.0
    #: The most banks of parameters, or plug-ins past the bank, a scan goes through
    most_pages = 64
    #: REAPER's action "Control surface: Refresh all surfaces"
    refresh_action = 41743

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        #: Address → the last value REAPER sent there (it sends changes only)
        self.state = {}
        self._changes = threading.Condition()
        self._change_count = 0
        self._change_time = 0.0
        self._synced = False
        # Where scans found things: track numbers (0 is the master) by label, plug-ins as
        # (label, number) by track, parameters as (label, number) by (track, plugin)
        self._track_numbers = {}
        # (track number, plug-in number, parameter number) → (track, plugin, parameter) labels
        self._found = {}
        self._emitted = {}

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['parameter_value'] = cls.parameter_value
        return info

    def connect(self) -> None:
        self.state = {}
        self._synced = False
        super().connect()

    def send(self, message) -> None:
        if isinstance(message, pyxelwidgets.message.PluginParameter):
            if not isinstance(message.value, str):
                self._turn_later(message, min(1.0, max(0.0, float(message.value))))
            return
        super().send(message)

    def _received(self, address: str, *args) -> None:
        value = args[0] if len(args) == 1 else args
        with self._changes:
            self.state[address] = value
            if _SCAN_ADDRESS.search(address):
                self._change_count += 1
                self._change_time = time.monotonic()
                self._changes.notify_all()
        self._parameter_feedback(address, value)
        super()._received(address, *args)

    def _parameter_feedback(self, address: str, value) -> None:
        """A scanned parameter's value, received as a PluginParameter."""
        if not self._found or isinstance(value, (str, tuple)):
            return
        match = _SELECTED_VALUE.fullmatch(address)
        if match:
            track = self._number(self.state.get('/track/number/str'))
            plugin, slot = int(match[1]), int(match[2])
        else:
            match = _TRACK_VALUE.fullmatch(address)
            if not match:
                return
            track = self._number(self.state.get(f'/track/{match[1]}/number/str'))
            plugin, slot = int(match[2]), int(match[3])
        bank = self._number(self.state.get('/device/fxparam/bank/str')) or 1
        names = self._found.get((track, plugin, (bank - 1) * self._size('fxparam', 16) + slot))
        if names is not None and self._emitted.get(names) != value:
            self._emitted[names] = value
            self.emit(pyxelwidgets.events.MessageReceived(self, pyxelwidgets.message.PluginParameter(*names, float(value))))

    # Plug-in parameters

    def scan_tracks(self) -> list:
        """
        REAPER's track names, then 'MASTER' (repeated names get " (2)"). Blocks
        for a while; don't call it from an OSC or widget event handler.
        """
        with self._navigation:
            self._sync()
            bank = self._bank()
            size = self._size('track', 8)
            # Past the last track selects the last one (the master first, so it changes)
            self._show_bank(1)
            self._ask('/device/track/select', 0)
            self._ask('/device/track/select', 1 << 20)
            count = self._number(self.state.get('/track/number/str')) or 0
            names = []
            for page in range(math.ceil(count / size)):
                self._show_bank(page + 1)
                names += [self.state.get(f'/track/{slot}/name') or f'Track {page * size + slot}'
                          for slot in range(1, size + 1)]
            self._show_bank(bank)
            self.tracks = pyxelwidgets.devices.plugins.labels(names[:count] + ['MASTER'])
            self._track_numbers = {label: number for number, label in enumerate(self.tracks[-1:] + self.tracks[:-1])}
            self._plugins, self._parameters, self._found = {}, {}, {}
            return list(self.tracks)

    def scan_plugins(self, track: str) -> list:
        """The plug-ins on ``track`` (a name from ``scan_tracks``), in their order."""
        with self._navigation:
            self._select_track(self._track_number(track))
            size = self._size('fx', 8)
            names = [self.state.get(f'/fx/{slot}/name') or '' for slot in range(1, size + 1)]
            names = names[:names.index('')] if '' in names else names
            if len(names) == size:
                # Past the bank: select each, until REAPER goes back to the first
                for number in range(size + 1, size + self.most_pages):
                    self._ask('/device/fx/select', number)
                    if self._number(self.state.get('/fx/number/str')) != number:
                        break
                    names.append(self.state.get('/fx/name') or '')
                self._ask('/device/fx/select', 1)
            self._plugins[track] = list(zip(pyxelwidgets.devices.plugins.labels(names), range(1, len(names) + 1)))
            return [label for label, _ in self._plugins[track]]

    def scan_parameters(self, track: str, plugin: str) -> list:
        """The parameters of ``plugin`` on ``track``: goes through its banks of parameters."""
        with self._navigation:
            number, plugin_number = self._track_number(track), self._plugin_number(track, plugin)
            self._select_track(number)
            if self._number(self.state.get('/fx/number/str')) != plugin_number:
                self._ask('/device/fx/select', plugin_number)
            size = self._size('fxparam', 16)
            names = []
            for page in range(self.most_pages):
                if not self._show_parameters(page + 1):
                    break
                shown = [self.state.get(f'/fxparam/{slot}/name') or '' for slot in range(1, size + 1)]
                names += shown[:shown.index('')] if '' in shown else shown
                if '' in shown:
                    break
            self._show_parameters(1)
            labels = pyxelwidgets.devices.plugins.labels(names)
            self._parameters[(track, plugin)] = list(zip(labels, range(1, len(labels) + 1)))
            self._found = {key: names for key, names in self._found.items() if key[:2] != (number, plugin_number)}
            self._found.update({(number, plugin_number, index): (track, plugin, label)
                                for label, index in self._parameters[(track, plugin)]})
            return labels

    def _turn(self, track: str, plugin: str, parameter: str, value: float) -> None:
        with self._navigation:
            if (track, plugin) not in self._parameters:
                self.scan_parameters(track, plugin)
            found = dict(self._parameters[(track, plugin)])
            if parameter not in found:
                raise LookupError(f'no parameter {parameter!r} (parameters: {", ".join(found) or "none found"})')
            self._select_track(self._track_number(track))
            # The parameter's number counts from the device's bank of parameters
            index = found[parameter] - ((self._number(self.state.get('/device/fxparam/bank/str')) or 1) - 1) * self._size('fxparam', 16)
            if index < 1:
                self._show_parameters(1)
                index = found[parameter]
            self.client.send_message(f'/fx/{self._plugin_number(track, plugin)}/fxparam/{index}/value', [float(value)])

    def _track_number(self, track: str) -> int:
        if not self.tracks:
            self.scan_tracks()
        if track not in self._track_numbers:
            raise LookupError(f'no track {track!r} (tracks: {", ".join(self.tracks) or "none found"})')
        return self._track_numbers[track]

    def _plugin_number(self, track: str, plugin: str) -> int:
        if track not in self._plugins:
            self.scan_plugins(track)
        found = dict(self._plugins[track])
        if plugin not in found:
            raise LookupError(f'no plug-in {plugin!r} on {track!r} (plug-ins: {", ".join(found) or "none found"})')
        return found[plugin]

    def _select_track(self, number: int) -> None:
        """Select a track in the device: its number counts from the bank's first track (0 is the one before)."""
        if self._number(self.state.get('/track/number/str')) == number:
            return
        # REAPER falls back to the first plug-in and bank of parameters by itself on a track with
        # fewer, without sending their names: go there first
        self._show_parameters(1)
        if (self._number(self.state.get('/fx/number/str')) or 1) != 1:
            self._ask('/device/fx/select', 1)
        bank = self._bank()
        first = (bank - 1) * self._size('track', 8) + 1
        if number < first - 1 or (number == 0 and first != 1):
            # Before the bank: from the first bank, then back
            self._show_bank(1)
            self._ask('/device/track/select', number)
            self._show_bank(bank)
        else:
            self._ask('/device/track/select', number - first + 1)
        if self._number(self.state.get('/track/number/str')) != number:
            raise LookupError(f'REAPER did not select track {number} (have the tracks changed? scan them again)')

    def _show_bank(self, bank: int) -> None:
        if self._bank() != bank:
            self._ask('/device/track/bank/select', bank)

    def _show_parameters(self, bank: int) -> bool:
        """Show a bank of the selected plug-in's parameters; False when there is no such bank."""
        if (self._number(self.state.get('/device/fxparam/bank/str')) or 1) != bank:
            self._ask('/device/fxparam/bank/select', bank)
        return (self._number(self.state.get('/device/fxparam/bank/str')) or 1) == bank

    def _bank(self) -> int:
        """The device's bank of tracks, from its first track's number."""
        first = self._number(self.state.get('/track/1/number/str')) or 1
        return (first - 1) // self._size('track', 8) + 1

    def _size(self, kind: str, default: int) -> int:
        """How many tracks, plug-ins or parameters a bank has (the pattern's DEVICE_..._COUNT), from what REAPER sent."""
        pattern = re.compile(rf'/{kind}/(\d+)/name')
        sizes = [int(match[1]) for match in map(pattern.fullmatch, list(self.state)) if match]
        return max(sizes, default = default)

    @staticmethod
    def _number(text) -> int | None:
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    def _sync(self) -> None:
        """Have REAPER send everything once, so ``state`` is complete (it sends changes only after)."""
        if self.client is None or self.server is None:
            raise ConnectionError('REAPER is not connected (connect it, with a receive port)')
        if self._synced:
            return
        self._ask('/action', self.refresh_action, wait = self.refresh_time)
        if '/track/number/str' not in self.state:
            raise ConnectionError(f'REAPER does not answer: its OSC control surface (Preferences > Control/OSC/web) '
                                  f'needs local listen port {self.send_port}, device port {self.receive_port} and '
                                  f'device IP 127.0.0.1 (where REAPER sends to: not 0.0.0.0)')
        self._synced = True

    def _ask(self, address: str, *args, wait: float | None = None) -> bool:
        """Send, then wait until REAPER's names stop changing; False when nothing changed."""
        with self._changes:
            before = self._change_count
        self.client.send_message(address, list(args))
        deadline = time.monotonic() + (self.timeout if wait is None else wait)
        with self._changes:
            while self._change_count == before:
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                self._changes.wait(left)
            while (quiet := self._change_time + self.settle - time.monotonic()) > 0:
                self._changes.wait(quiet)
        return True
