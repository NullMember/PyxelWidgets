"""
Connecting to Bluetooth MIDI devices: BLE MIDI controllers and keyboards, or a
computer advertising MIDI (a Mac's Audio MIDI Setup, a Pi running ``BleMidi``).

``Bluetooth`` scans for devices advertising the BLE MIDI service, connects and
disconnects them, and remembers connected devices so they connect again when the
program starts and when they come back in range (``keep_connected``). Once
connected, a device's MIDI ports are listed like any other (``MIDI.available_ports``),
so devices and outputs use them by name.

Backends (``central()``): Android's MIDI service through the app's
``BluetoothBridge``. Elsewhere ``Bluetooth.status()`` says it isn't available yet.
"""

import json
import pathlib
import threading

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

def _android() -> bool:
    import sys
    return hasattr(sys, 'getandroidapilevel')

_central = None

def central():
    """This system's backend, or None where Bluetooth MIDI isn't supported yet."""
    global _central
    if _central is None and _android():
        _central = AndroidCentral()
    return _central

class Bluetooth:
    """Scanning, connecting and remembering Bluetooth MIDI devices (one per program: ``manager()``)."""

    #: Seconds between attempts to connect remembered devices that aren't connected
    retry_interval = 10.0

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
            return 'Bluetooth MIDI devices can be connected from the Android app for now'
        return self.backend.problem(ask)

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
        """Try once to connect remembered devices that aren't connected; returns the names connected."""
        if self.backend is None or self.problem(ask = False) is not None:
            return []
        here = {device['address'] for device in self.backend.connected()}
        done = []
        for entry in self.remembered():
            if entry['address'] in here:
                continue
            try:
                with self._lock:
                    done.append(self.backend.connect(entry['address']))
                self.errors.pop(entry['address'], None)
            except Exception as error:
                self.errors[entry['address']] = str(error)
        return done

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

def manager() -> Bluetooth:
    """The program's ``Bluetooth`` (the designer and the Android app share it)."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = Bluetooth()
        return _manager
