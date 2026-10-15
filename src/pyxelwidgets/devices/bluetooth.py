"""
Connecting to Bluetooth MIDI devices: BLE MIDI controllers and keyboards, or a
computer advertising MIDI (a Mac's Audio MIDI Setup, a Pi running ``BleMidi``).

``Bluetooth`` scans for devices advertising the BLE MIDI service, connects and
disconnects them, and remembers connected devices so they connect again when the
program starts and when they come back in range (``keep_connected``). Once
connected, a device's MIDI ports are listed like any other (``MIDI.available_ports``),
so devices and outputs use them by name.

Backends (``central()``): on Android, Android's MIDI service through the app's
``BluetoothBridge`` (it lists connected devices' ports itself); elsewhere
``BleakCentral`` (macOS, Windows, Linux; extra ``bluetooth``), which talks BLE
MIDI itself and adds connected devices to ``MIDI``'s port lists (``ports()``).
Received BLE MIDI keeps real-time (clock, start, stop) and system exclusive
messages (``ble_midi.ble_midi_messages``), so a Bluetooth port can drive the
transport (the layout's ``transport.sync``).
"""

import asyncio
import json
import pathlib
import threading
import time

__all__ = ['Bluetooth', 'Unavailable', 'central', 'manager', 'REMEMBERED']

#: The devices to connect again (address and name), kept between runs
REMEMBERED = pathlib.Path.home() / '.pyxelwidgets' / 'bluetooth.json'

class Unavailable(OSError):
    """No Bluetooth MIDI here (no backend, Bluetooth off, permission refused...)."""

class AndroidCentral:
    """Android's MIDI service, which also opens Bluetooth MIDI devices (through BluetoothBridge)."""

    def __init__(self):
        from java import jclass
        self._bridge = jclass('io.github.nullmember.pyxelwidgets.BluetoothBridge')

    def _call(self, method, *args):
        """The bridge's ``method``; its Java errors become OSError with Android's message."""
        try:
            return getattr(self._bridge, method)(*args)
        except Exception as error:
            if type(error).__module__.startswith('java'):
                message = str(error)
                raise OSError(message.split(': ', 1)[1] if message.startswith('java.') and ': ' in message else message) from None
            raise

    def problem(self, ask: bool = False) -> str | None:
        problem = self._call('problem', ask)
        return None if problem is None else str(problem)

    def scan(self, seconds: float) -> list[dict]:
        found = []
        for entry in self._call('scan', int(seconds * 1000)):
            address, name, rssi = str(entry).split('\t')
            found.append({'address': address, 'name': name, 'rssi': int(rssi)})
        return found

    def connect(self, address: str) -> str:
        return str(self._call('connect', address))

    def disconnect(self, address: str) -> None:
        self._call('disconnect', address)

    def connected(self) -> list[dict]:
        devices = []
        for entry in self._call('connected'):
            address, name = str(entry).split('\t')
            devices.append({'address': address, 'name': name})
        return devices

class _Connection:
    """A connected device (BleakCentral): what it sends goes to each listener as MIDI messages."""

    def __init__(self, central, address: str, name: str, client):
        from pyxelwidgets.devices.ble_midi import _ParseState
        self.central = central
        self.address = address
        self.name = name
        self.client = client
        self.listeners = []
        self.state = _ParseState()
        # The longest packet the link takes (its MTU less the ATT header)
        self.payload = max(20, min(getattr(client, 'mtu_size', 23) - 3, 512))
        self.start = time.monotonic()

    def received(self, sender, data) -> None:
        from pyxelwidgets.devices.ble_midi import ble_midi_messages
        for message in ble_midi_messages(bytes(data), self.state):
            for listener in list(self.listeners):
                listener(message)

    def send(self, message) -> None:
        from pyxelwidgets.devices.ble_midi import CHARACTERISTIC, ble_packets
        milliseconds = int((time.monotonic() - self.start) * 1000)
        for packet in ble_packets([list(message)], milliseconds, self.payload):
            self.central._later(self.client.write_gatt_char(CHARACTERISTIC, packet, response = False))

class _Port:
    """One of a connected device's ports for ``MIDI`` (like rtmidi's MidiIn/MidiOut)."""

    def __init__(self, connection: _Connection):
        self._connection = connection
        self._listener = None

    def set_callback(self, callback) -> None:
        self.close_port()
        self._listener = lambda message: callback((message, 0.0), None)
        self._connection.listeners.append(self._listener)

    def ignore_types(self, **types) -> None:
        pass

    def send_message(self, message) -> None:
        self._connection.send(message)

    def close_port(self) -> None:
        if self._listener is not None and self._listener in self._connection.listeners:
            self._connection.listeners.remove(self._listener)
        self._listener = None

class BleakCentral:
    """
    Bluetooth MIDI devices through bleak (macOS, Windows, Linux): this program
    connects and speaks BLE MIDI itself, on an asyncio loop of its own.
    """

    #: Seconds a connection may take
    connect_timeout = 20.0

    def __init__(self):
        self._loop = None
        self._start = threading.Lock()
        self._connections = {}
        # Devices seen by the last scans: connecting to one needs no scan of its own
        self._seen = {}

    def _run(self, coroutine, timeout: float):
        with self._start:
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                threading.Thread(target = self._loop.run_forever, name = 'Bluetooth', daemon = True).start()
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(timeout)

    def _later(self, coroutine) -> None:
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        future.add_done_callback(lambda done: done.exception())

    def problem(self, ask: bool = False) -> str | None:
        try:
            import bleak  # noqa: F401
        except ImportError:
            return 'Bluetooth MIDI needs bleak: pip install "pyxelwidgets[bluetooth]"'
        return None

    @staticmethod
    def _error(error: Exception) -> OSError:
        text = str(error) or type(error).__name__
        if 'turned off' in text.lower() or type(error).__name__ == 'BleakBluetoothNotAvailableError':
            return OSError(f'Bluetooth is off or not available: {text}')
        return OSError(text)

    def scan(self, seconds: float) -> list[dict]:
        import bleak
        from pyxelwidgets.devices.ble_midi import SERVICE

        async def discover():
            return await bleak.BleakScanner.discover(timeout = seconds, service_uuids = [SERVICE], return_adv = True)

        try:
            found = self._run(discover(), seconds + 10)
        except Exception as error:
            raise self._error(error) from None
        self._seen.update({address: device for address, (device, _) in found.items()})
        return [{'address': address, 'name': advertisement.local_name or device.name or address, 'rssi': advertisement.rssi}
                for address, (device, advertisement) in found.items() if address not in self._connections]

    def connect(self, address: str) -> str:
        import bleak
        from pyxelwidgets.devices.ble_midi import CHARACTERISTIC
        if address in self._connections:
            return self._connections[address].name

        async def connect():
            device = self._seen.pop(address, None) or await bleak.BleakScanner.find_device_by_address(address, timeout = self.connect_timeout / 2)
            if device is None:
                raise OSError(f'{address} isn\'t advertising (is it on, in range, and not connected to something else?)')
            client = bleak.BleakClient(device, disconnected_callback = lambda client: self._lost(address))
            await client.connect(timeout = self.connect_timeout / 2)
            connection = _Connection(self, address, device.name or address, client)
            await client.start_notify(CHARACTERISTIC, connection.received)
            return connection

        try:
            connection = self._run(connect(), self.connect_timeout + 5)
        except OSError:
            raise
        except Exception as error:
            raise self._error(error) from None
        self._connections[address] = connection
        return connection.name

    def _lost(self, address: str) -> None:
        self._connections.pop(address, None)

    def disconnect(self, address: str) -> None:
        connection = self._connections.pop(address, None)
        if connection is not None:
            try:
                self._run(connection.client.disconnect(), 10)
            except Exception:
                pass

    def connected(self) -> list[dict]:
        return [{'address': address, 'name': connection.name} for address, connection in list(self._connections.items())]

    def ports(self) -> list[str]:
        """Names of the connected devices, listed as both input and output MIDI ports."""
        return [connection.name for connection in list(self._connections.values())]

    def open(self, name: str) -> _Port:
        for connection in list(self._connections.values()):
            if connection.name == name:
                return _Port(connection)
        raise OSError(f'No Bluetooth MIDI device {name} connected')

def _android() -> bool:
    import sys
    return hasattr(sys, 'getandroidapilevel')

_central = None

def central():
    """This system's backend: Android's MIDI service, or bleak elsewhere."""
    global _central
    if _central is None:
        _central = AndroidCentral() if _android() else BleakCentral()
    return _central

class Bluetooth:
    """Scanning, connecting and remembering Bluetooth MIDI devices (one per program: ``manager()``)."""

    #: Seconds between attempts to connect remembered devices that aren't connected
    retry_interval = 10.0
    #: Seconds of scanning for a remembered device that may have changed its address
    rename_scan = 3.0

    def __init__(self, backend = None, path: pathlib.Path = REMEMBERED):
        self.backend = backend if backend is not None else central()
        self.path = path
        self._lock = threading.RLock()
        self._keeping = None
        #: The last attempt's error per remembered address, shown next to it
        self.errors = {}

    def remembered(self) -> list[dict]:
        try:
            entries = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return []
        return [entry for entry in entries if isinstance(entry, dict) and 'address' in entry]

    def _remember(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents = True, exist_ok = True)
        self.path.write_text(json.dumps(entries, indent = 2) + '\n')

    def problem(self, ask: bool = False) -> str | None:
        if self.backend is None:
            return 'No Bluetooth MIDI here'
        return self.backend.problem(ask)

    def ports(self) -> list[str]:
        """Connected devices' MIDI port names this program adds to the system's (none where the system lists them)."""
        return self.backend.ports() if hasattr(self.backend, 'ports') else []

    def open(self, name: str):
        return self.backend.open(name)

    def status(self) -> dict:
        problem = self.problem()
        connected = self.backend.connected() if self.backend is not None else []
        here = {device['address'] for device in connected}
        return {'available': self.backend is not None, 'problem': problem, 'connected': connected,
                'remembered': [dict(entry, error = self.errors.get(entry['address'])) for entry in self.remembered()
                               if entry['address'] not in here]}

    def _ready(self, ask: bool = True) -> None:
        problem = self.problem(ask)
        if problem is not None:
            raise Unavailable(problem)

    def scan(self, seconds: float = 4.0) -> list[dict]:
        """Devices advertising MIDI nearby (address, name, rssi), strongest first."""
        self._ready()
        found = self.backend.scan(seconds)
        return sorted(found, key = lambda device: -device['rssi'])

    def connect(self, address: str, *, remember: bool = True) -> str:
        """Connect the device at ``address`` (and connect it again next time); returns its name."""
        self._ready()
        with self._lock:
            name = self.backend.connect(address)
            self.errors.pop(address, None)
            if remember:
                entries = [entry for entry in self.remembered() if entry['address'] != address]
                self._remember(entries + [{'address': address, 'name': name}])
        return name

    def disconnect(self, address: str, *, forget: bool = True) -> None:
        """Disconnect the device at ``address``; with ``forget``, it isn't connected again."""
        with self._lock:
            if forget:
                self._remember([entry for entry in self.remembered() if entry['address'] != address])
                self.errors.pop(address, None)
            if self.backend is not None:
                self.backend.disconnect(address)

    def reconnect(self) -> list[str]:
        """
        Try once to connect remembered devices that aren't connected; returns the names
        connected. Phones (and other devices with private addresses) advertise from a new
        address now and then: one found by its remembered name (and only one) is taken
        for it, and remembered at its new address.
        """
        if self.backend is None or self.problem(ask = False) is not None:
            return []
        here = {device['address'] for device in self.backend.connected()}
        missing = [entry for entry in self.remembered() if entry['address'] not in here]
        done = []
        found = None
        for entry in missing:
            try:
                with self._lock:
                    done.append(self.backend.connect(entry['address']))
                self.errors.pop(entry['address'], None)
                continue
            except Exception as error:
                self.errors[entry['address']] = str(error)
            if found is None:
                try:
                    found = self.backend.scan(self.rename_scan)
                except Exception:
                    found = []
            named = [device for device in found if device['name'] == entry.get('name') and device['address'] not in here]
            if len(named) != 1:
                continue
            address = named[0]['address']
            try:
                with self._lock:
                    name = self.backend.connect(address)
                    entries = [dict(other, address = address) if other['address'] == entry['address'] else other
                               for other in self.remembered()]
                    self._remember(entries)
                self.errors.pop(entry['address'], None)
                done.append(name)
            except Exception as error:
                self.errors[entry['address']] = str(error)
        return done

    def keep_connected_if_remembered(self) -> None:
        """``keep_connected`` when devices are remembered (else bleak isn't even loaded)."""
        if self.remembered():
            self.keep_connected()

    def keep_connected(self) -> None:
        """Connect remembered devices now and whenever they're back (a thread, every ``retry_interval``)."""
        if self._keeping is not None or self.backend is None:
            return
        stop = threading.Event()
        self._keeping = stop

        def run():
            while True:
                for name in self.reconnect():
                    print(f'Bluetooth MIDI: connected {name}', flush = True)
                if stop.wait(self.retry_interval):
                    return

        threading.Thread(target = run, name = 'BluetoothReconnect', daemon = True).start()

    def close(self) -> None:
        if self._keeping is not None:
            self._keeping.set()
            self._keeping = None

_manager = None
_manager_lock = threading.Lock()

def added_ports() -> list[str]:
    """MIDI port names of Bluetooth devices this program connected itself (``MIDI`` lists them; empty until one is)."""
    return _manager.ports() if _manager is not None else []

def open_port(name: str):
    return _manager.open(name)

def manager() -> Bluetooth:
    """The program's ``Bluetooth`` (the designer and the Android app share it)."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = Bluetooth()
        return _manager
