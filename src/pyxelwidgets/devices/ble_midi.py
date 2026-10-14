"""
Bluetooth LE MIDI as a peripheral, on Linux (BlueZ), e.g. a Raspberry Pi:
this computer advertises itself as a Bluetooth MIDI device, another computer
connects to it, and the widgets' messages go there; what it sends back comes
in as MessageReceived::

    bluetooth = BleMidi()
    bluetooth.connect()                    # advertised under the Bluetooth name
    surface.map(kick, bluetooth, NoteOn(36), on = Pressed)

The other side:

- macOS: Audio MIDI Setup > Window > Show MIDI Studio > the Bluetooth
  button: the device shows in the list; press Connect.
- Windows: DAWs that support Bluetooth MIDI (e.g. through MIDIberry or
  Windows MIDI Services) pair with it in Settings > Bluetooth first.
- iOS: in the app's Bluetooth MIDI page (GarageBand, AUM).

Needs dbus-fast (``pip install "pyxelwidgets[bluetooth]"``) and bluetoothd.
The user running it needs the system bus's permission for BlueZ (on
Raspberry Pi OS and Debian: the ``bluetooth`` group,
``sudo usermod -aG bluetooth $USER``, then log in again).

bluetoothd's own MIDI plugin (built into Raspberry Pi OS's) drops a Mac or an
iPad 30 s after it connects; start bluetoothd without it (``-P midi``)::

    sudo systemctl edit bluetooth    # [Service] ExecStart= then ExecStart=/usr/libexec/bluetooth/bluetoothd -P midi
    sudo systemctl restart bluetooth

``warning`` says so while the plugin runs.
"""

import asyncio
import collections
import errno
import platform
import threading
import time
import types

import pyxelwidgets.devices
import pyxelwidgets.events
import pyxelwidgets.message

__all__ = ['BleMidi']

#: The BLE MIDI service and its one characteristic (MIDI I/O)
SERVICE = '03b80e5a-ede8-4b33-a751-6ce34ec4c700'
CHARACTERISTIC = '7772e5db-3868-4112-a1a9-f2669d106bf3'

class BleMidi(pyxelwidgets.devices.Device):
    """
    A Bluetooth LE MIDI device other computers connect to (Linux with BlueZ,
    e.g. a Raspberry Pi). Sends MIDI channel messages to the computer that
    connected; what it sends comes in as MessageReceived.
    """

    model = 'Bluetooth MIDI (BLE)'
    messages: tuple = ('NoteOn', 'NoteOff', 'ControlChange', 'ProgramChange', 'PitchBend', 'PolyPressure', 'ChannelPressure')

    #: Seconds to wait for BlueZ when connecting
    timeout = 10.0
    #: The D-Bus to find BlueZ on (None: the system bus); tests pass their own
    bus_address = None
    #: Notification packets kept while BlueZ is behind
    queue_limit = 1000

    def __init__(self, *, bluetooth_name: str = '', adapter: str = '', secure: bool = False, **kwargs):
        """
        bluetooth_name: str, optional
            The name other computers see while it advertises (default: this computer's Bluetooth name). About 8 characters fit beside the MIDI service; longer names are cut.
        adapter: str, optional
            The Bluetooth adapter (e.g. hci1; default: the first that can advertise).
        secure: bool = False
            Ask for pairing (encrypted connection) before MIDI goes through; it accepts any pairing without a code.
        """
        super().__init__(**kwargs)
        self.bluetooth_name = bluetooth_name
        self.adapter = adapter
        self.secure = secure
        #: Why it may not work as expected, or None
        self.warning = None
        #: Whether a computer listens to it (it subscribed to the MIDI characteristic)
        self.listening = False
        self._loop = None
        self._thread = None
        self._bus = None
        self._adapter_path = None
        self._characteristic = None
        self._registered = []
        # MIDI sent from other threads until the loop flushes it
        self._pending = []
        self._pending_lock = threading.Lock()
        # Notification packets BlueZ hasn't taken yet
        self._outgoing = collections.deque()
        #: Notifications given up because BlueZ stopped taking them (more than ``queue_limit`` waiting)
        self.dropped = 0
        # Sockets BlueZ passes MIDI through when it acquires the characteristic (no D-Bus call per packet)
        self._write_socket = None
        self._notify_socket = None
        # Notification payloads: MTU minus 3 (BlueZ tells the MTU with reads and writes)
        self._payload = 20
        self._received_state = _ParseState()
        self._path = f'/org/pyxelwidgets/{_dbus_name(self.name)}'

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['messages'] = list(cls.messages)
        return info

    @property
    def status_text(self) -> str:
        """Whether a computer is connected, for people (the designer shows it)."""
        if self.listening:
            return 'a computer is connected'
        return 'advertising: connect from the other computer (macOS: Audio MIDI Setup > MIDI Studio > Bluetooth)'

    # Lifecycle

    def connect(self) -> None:
        if self.connected:
            self.disconnect()
        if platform.system() != 'Linux' and self.bus_address is None:
            raise OSError('Bluetooth MIDI devices can only be made on Linux (BlueZ), e.g. on a Raspberry Pi')
        try:
            import dbus_fast  # noqa: F401
        except ImportError:
            raise ImportError('Bluetooth MIDI needs dbus-fast: pip install "pyxelwidgets[bluetooth]"') from None
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target = loop.run_forever, name = f'{self.name}_ble', daemon = True)
        thread.start()
        self._loop, self._thread = loop, thread
        try:
            asyncio.run_coroutine_threadsafe(self._start(), loop).result(self.timeout)
        except BaseException as error:
            self._close_loop()
            if isinstance(error, TimeoutError):
                raise TimeoutError('BlueZ didn\'t answer: is bluetoothd running?') from None
            raise
        super().connect()

    def disconnect(self) -> None:
        if self._loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._stop(), self._loop).result(5.0)
            except Exception:
                pass
            self._close_loop()
        self.listening = False
        super().disconnect()

    def _close_loop(self) -> None:
        loop, thread = self._loop, self._thread
        self._loop = self._thread = None
        if loop is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        if thread is not threading.current_thread():
            thread.join(timeout = 2.0)
        loop.close()

    # Sending

    def send(self, message: pyxelwidgets.message.MidiMessage) -> None:
        self.send_midi(message.to_midi())

    def send_midi(self, midi: list) -> None:
        """Send one raw MIDI message (a list of bytes, no system exclusive); messages sent together share a packet."""
        loop = self._loop
        if loop is None or not self.listening:
            return
        with self._pending_lock:
            first = not self._pending
            self._pending.append(list(midi))
        if first:
            # The loop is woken once for everything sent until it flushes (one packet when it fits)
            try:
                loop.call_soon_threadsafe(self._flush)
            except RuntimeError:
                pass

    def _flush(self) -> None:
        with self._pending_lock:
            pending, self._pending = self._pending, []
        if self._characteristic is None or not self.listening:
            return
        packets = ble_packets(pending, int(time.monotonic() * 1000), self._payload)
        if self._notify_socket is None:
            for packet in packets:
                self._characteristic.notify(packet)
            return
        waiting = not self._outgoing
        self._outgoing.extend(packets)
        if len(self._outgoing) > self.queue_limit:
            # BlueZ stopped taking them: the oldest go
            for _ in range(len(self._outgoing) - self.queue_limit):
                self._outgoing.popleft()
                self.dropped += 1
        if waiting:
            self._drain()

    def _drain(self) -> None:
        """Send queued notifications while BlueZ takes them; the rest when its socket has room again."""
        sock = self._notify_socket
        while self._outgoing and sock is not None:
            try:
                sock.send(self._outgoing[0])
            except BlockingIOError:
                # bluetoothd is behind (a socket holds a few packets): never lose a NoteOff
                self._loop.add_writer(sock, self._drain)
                return
            except OSError as error:
                if error.errno == errno.ENOBUFS:
                    # Full the macOS way (the tests' datagram sockets): no writable signal, try again soon
                    self._loop.call_later(0.005, self._drain)
                    return
                self._released('notify')
                return
            self._outgoing.popleft()
        if sock is not None:
            self._loop.remove_writer(sock)

    # BlueZ

    async def _start(self) -> None:
        from dbus_fast import BusType, Variant
        from dbus_fast.aio import MessageBus
        interfaces = _interfaces()
        # Unix fds: BlueZ takes sockets for MIDI (AcquireWrite, AcquireNotify)
        if self.bus_address is not None:
            bus = await MessageBus(bus_address = self.bus_address, negotiate_unix_fd = True).connect()
        else:
            bus = await MessageBus(bus_type = BusType.SYSTEM, negotiate_unix_fd = True).connect()
        self._bus = bus
        objects = (await _call(bus, '/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects'))[0]
        adapters = sorted(path for path, found in objects.items()
                          if 'org.bluez.GattManager1' in found and 'org.bluez.LEAdvertisingManager1' in found
                          and (not self.adapter or path.rsplit('/', 1)[-1] == self.adapter))
        if not adapters:
            raise OSError(f'no Bluetooth adapter {self.adapter + " " if self.adapter else ""}that can advertise (is Bluetooth on? bluetoothctl show)')
        adapter = self._adapter_path = adapters[0]
        if not objects[adapter].get('org.bluez.Adapter1', {}).get('Powered', Variant('b', True)).value:
            try:
                await _call(bus, adapter, 'org.freedesktop.DBus.Properties', 'Set', 'ssv', ['org.bluez.Adapter1', 'Powered', Variant('b', True)])
            except OSError as error:
                raise OSError(f'couldn\'t turn Bluetooth on: {_blocked() or error}') from None

        flags = ['read', 'write-without-response', 'notify']
        if self.secure:
            flags += ['encrypt-read', 'encrypt-write', 'encrypt-notify']
        service_path = f'{self._path}/service0'
        self._characteristic = interfaces.Characteristic(self, f'{service_path}/char0', service_path, flags)
        bus.export(service_path, interfaces.Service())
        bus.export(f'{service_path}/char0', self._characteristic)
        advert_path = f'{self._path}_advert'
        bus.export(advert_path, interfaces.Advertisement(self.bluetooth_name))
        if self.secure:
            agent_path = f'{self._path}_agent'
            bus.export(agent_path, interfaces.Agent())
            await _call(bus, '/org/bluez', 'org.bluez.AgentManager1', 'RegisterAgent', 'os', [agent_path, 'NoInputNoOutput'])
            self._registered.append(('/org/bluez', 'org.bluez.AgentManager1', 'UnregisterAgent', agent_path))
            try:
                await _call(bus, '/org/bluez', 'org.bluez.AgentManager1', 'RequestDefaultAgent', 'o', [agent_path])
            except OSError as error:
                self.warning = f'pairing may ask for confirmation on this computer ({error})'
        if self.bus_address is None and _midi_plugin():
            self.warning = ('bluetoothd\'s own MIDI plugin drops Macs and iPads after 30 s: start it with -P midi '
                            '(sudo systemctl edit bluetooth: [Service] ExecStart= then ExecStart=/usr/libexec/bluetooth/bluetoothd -P midi)')
        await _call(bus, adapter, 'org.bluez.GattManager1', 'RegisterApplication', 'oa{sv}', [self._path, {}])
        self._registered.append((adapter, 'org.bluez.GattManager1', 'UnregisterApplication', self._path))
        await _call(bus, adapter, 'org.bluez.LEAdvertisingManager1', 'RegisterAdvertisement', 'oa{sv}', [advert_path, {}])
        self._registered.append((adapter, 'org.bluez.LEAdvertisingManager1', 'UnregisterAdvertisement', advert_path))

    async def _stop(self) -> None:
        bus, self._bus = self._bus, None
        if bus is None:
            return
        for path, interface, member, argument in reversed(self._registered):
            try:
                await _call(bus, path, interface, member, 'o', [argument])
            except OSError:
                pass
        self._registered = []
        self._released('write')
        self._released('notify')
        self._characteristic = None
        bus.disconnect()

    # Called by the characteristic (on the loop's thread)

    def _options(self, options: dict) -> None:
        mtu = options.get('mtu')
        if mtu is not None and mtu.value > 3:
            self._payload = min(mtu.value - 3, 512)

    def _written(self, value: bytes) -> None:
        for midi in ble_midi_messages(value, self._received_state):
            message = pyxelwidgets.message.MidiMessage.from_midi(midi)
            if message is not None:
                self.emit(pyxelwidgets.events.MessageReceived(self, message))

    def _notifying(self, on: bool) -> None:
        self.listening = on
        if not on:
            with self._pending_lock:
                self._pending = []

    def _acquire(self, kind: str, options: dict) -> tuple:
        """
        A socket pair for BlueZ (AcquireWrite, AcquireNotify): it passes what
        is written to the characteristic through one ('write'), and notifies
        what we send through the other ('notify'). Returns BlueZ's end's fd
        and the MTU.
        """
        import socket
        self._options(options)
        self._released(kind)
        try:
            ours, theirs = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        except OSError:
            # Packets kept apart too (macOS has no SEQPACKET pairs: the tests' fake BlueZ)
            ours, theirs = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
        ours.setblocking(False)
        setattr(self, f'_{kind}_socket', ours)
        # Read: written packets, or BlueZ closing its end (disconnected, notifications off)
        self._loop.add_reader(ours, self._readable, kind, ours)
        # Closed once dbus-fast has sent the fd with the reply (BlueZ has its own copy then);
        # until then BlueZ closing its end isn't noticed, right after it is
        self._loop.call_later(1.0, theirs.close)
        if kind == 'notify':
            self._notifying(True)
        mtu = options.get('mtu')
        return theirs.fileno(), mtu.value if mtu is not None else self._payload + 3

    def _readable(self, kind: str, ours) -> None:
        try:
            packet = ours.recv(1024)
        except BlockingIOError:
            return
        except OSError:
            packet = b''
        if not packet:
            if getattr(self, f'_{kind}_socket') is ours:
                self._released(kind)
            return
        if kind == 'write':
            self._written(packet)

    def _released(self, kind: str) -> None:
        ours = getattr(self, f'_{kind}_socket')
        if ours is None:
            return
        setattr(self, f'_{kind}_socket', None)
        if self._loop is not None:
            self._loop.remove_reader(ours)
            self._loop.remove_writer(ours)
        ours.close()
        if kind == 'notify':
            self._outgoing.clear()
            self._notifying(False)

# Packets

def ble_packets(messages: list, milliseconds: int, payload: int = 20) -> list:
    """BLE MIDI packets (bytes, at most ``payload`` long) carrying ``messages`` (lists of MIDI bytes), timestamped ``milliseconds``."""
    stamp = milliseconds & 0x1FFF
    header = 0x80 | (stamp >> 7)
    low = 0x80 | (stamp & 0x7F)
    packets = []
    packet = bytearray([header])
    for midi in messages:
        if len(packet) + 1 + len(midi) > payload and len(packet) > 1:
            packets.append(bytes(packet))
            packet = bytearray([header])
        packet.append(low)
        packet.extend(midi)
    if len(packet) > 1:
        packets.append(bytes(packet))
    return packets

class _ParseState:
    """What carries over between received packets: running status and an unfinished system exclusive."""

    def __init__(self) -> None:
        self.running = None
        self.sysex = False

def _message_length(status: int) -> int:
    if status < 0xF0:
        return 1 if status & 0xF0 in (0xC0, 0xD0) else 2
    return {0xF1: 1, 0xF2: 2, 0xF3: 1}.get(status, 0)

def ble_midi_messages(packet: bytes, state: _ParseState | None = None) -> list:
    """The MIDI messages (lists of bytes) in a received BLE MIDI packet; system exclusive and real-time messages are skipped."""
    state = state or _ParseState()
    found = []
    if len(packet) < 2 or not packet[0] & 0x80:
        return found
    position, end = 1, len(packet)
    while position < end:
        byte = packet[position]
        if state.sysex:
            if byte < 0x80:
                position += 1
                continue
            # A timestamp before the end (F7) or a real-time message inside it
            following = packet[position + 1] if position + 1 < end else None
            if byte == 0xF7 or following == 0xF7:
                state.sysex = False
                position += 1 if byte == 0xF7 else 2
                continue
            if following is not None and following >= 0xF8:
                position += 2
                continue
            state.sysex = False
        if byte & 0x80:
            # A timestamp, then a status byte or running status data
            position += 1
            if position >= end:
                break
            byte = packet[position]
        if byte == 0xF0:
            state.sysex = True
            position += 1
            continue
        if byte >= 0xF8:
            position += 1
            continue
        if byte & 0x80:
            status = byte
            position += 1
            state.running = status if status < 0xF0 else None
        elif state.running is None:
            position += 1
            continue
        else:
            status = state.running
        count = _message_length(status)
        data = packet[position:position + count]
        if len(data) < count or any(value & 0x80 for value in data):
            break
        position += count
        found.append([status, *data])
    return found

# D-Bus

def _dbus_name(name: str) -> str:
    return ''.join(character if character.isalnum() else '_' for character in name) or 'ble_midi'

async def _call(bus, path: str, interface: str, member: str, signature: str = '', body: list | None = None) -> list:
    from dbus_fast import Message, MessageType
    reply = await bus.call(Message(destination = 'org.bluez', path = path, interface = interface, member = member,
                                   signature = signature, body = body or []))
    if reply.message_type == MessageType.ERROR:
        text = reply.body[0] if reply.body else reply.error_name
        if reply.error_name in ('org.freedesktop.DBus.Error.AccessDenied', 'org.bluez.Error.NotPermitted'):
            text += ' (add the user to the bluetooth group: sudo usermod -aG bluetooth $USER, then log in again)'
        elif reply.error_name == 'org.freedesktop.DBus.Error.ServiceUnknown':
            text = 'BlueZ isn\'t running (sudo systemctl start bluetooth)'
        raise OSError(f'{interface.rsplit(".", 1)[-1]}.{member}: {text}')
    return reply.body

def _blocked() -> str | None:
    """Why rfkill keeps Bluetooth off, if it does (BlueZ only answers "Failed" then)."""
    import glob
    for folder in glob.glob('/sys/class/rfkill/rfkill*'):
        try:
            with open(f'{folder}/type') as file:
                if file.read().strip() != 'bluetooth':
                    continue
            with open(f'{folder}/hard') as file:
                if file.read().strip() == '1':
                    return 'Bluetooth is blocked by a hardware switch (rfkill)'
            with open(f'{folder}/soft') as file:
                if file.read().strip() == '1':
                    return 'Bluetooth is blocked by rfkill (sudo rfkill unblock bluetooth)'
        except OSError:
            continue
    return None

def _midi_plugin() -> bool:
    """
    Whether bluetoothd runs with its MIDI plugin. The plugin reads the MIDI
    service of every device that connects (a Mac or an iPad has one), gets
    "insufficient authentication", asks for stronger pairing the other side
    never answers, and the link drops when that times out after 30 s.
    """
    import glob
    for path in glob.glob('/proc/[0-9]*/cmdline'):
        try:
            with open(path, 'rb') as file:
                arguments = file.read().decode(errors = 'replace').split('\0')
        except OSError:
            continue
        if not arguments[0].endswith('/bluetoothd'):
            continue
        # -P midi, -Pmidi, --noplugin midi, --noplugin=midi (lists separated by commas)
        off = []
        for index, argument in enumerate(arguments):
            if argument in ('-P', '--noplugin') and index + 1 < len(arguments):
                off += arguments[index + 1].split(',')
            elif argument.startswith('--noplugin='):
                off += argument.split('=', 1)[1].split(',')
            elif argument.startswith('-P'):
                off += argument[2:].split(',')
        if 'midi' in off:
            return False
        try:
            # Built with it: its source path is in the binary's log messages
            with open(arguments[0], 'rb') as file:
                return b'profiles/midi/midi.c' in file.read()
        except OSError:
            return False
    return False

_INTERFACES = None

def _interfaces():
    """The D-Bus objects BlueZ talks to, made on first use (dbus-fast is imported only then)."""
    global _INTERFACES
    if _INTERFACES is not None:
        return _INTERFACES
    from dbus_fast.service import PropertyAccess, ServiceInterface, dbus_property, method

    class Service(ServiceInterface):
        def __init__(self) -> None:
            super().__init__('org.bluez.GattService1')

        @dbus_property(access = PropertyAccess.READ)
        def UUID(self) -> 's':
            return SERVICE

        @dbus_property(access = PropertyAccess.READ)
        def Primary(self) -> 'b':
            return True

    class Characteristic(ServiceInterface):
        def __init__(self, owner: BleMidi, path: str, service: str, flags: list) -> None:
            super().__init__('org.bluez.GattCharacteristic1')
            self._owner = owner
            self._path = path
            self._service = service
            self._flags = flags
            self._value = b''

        @dbus_property(access = PropertyAccess.READ)
        def UUID(self) -> 's':
            return CHARACTERISTIC

        @dbus_property(access = PropertyAccess.READ)
        def Service(self) -> 'o':
            return self._service

        @dbus_property(access = PropertyAccess.READ)
        def Flags(self) -> 'as':
            return self._flags

        @dbus_property(access = PropertyAccess.READ)
        def Value(self) -> 'ay':
            return self._value

        @method()
        def ReadValue(self, options: 'a{sv}') -> 'ay':
            # BLE MIDI: reads answer nothing
            self._owner._options(options)
            return b''

        @method()
        def WriteValue(self, value: 'ay', options: 'a{sv}'):
            self._owner._options(options)
            self._owner._written(bytes(value))

        # Their presence tells BlueZ it may pass MIDI through sockets instead of these calls
        @dbus_property(access = PropertyAccess.READ)
        def WriteAcquired(self) -> 'b':
            return self._owner._write_socket is not None

        @dbus_property(access = PropertyAccess.READ)
        def NotifyAcquired(self) -> 'b':
            return self._owner._notify_socket is not None

        @method()
        def AcquireWrite(self, options: 'a{sv}') -> 'hq':
            return list(self._owner._acquire('write', options))

        @method()
        def AcquireNotify(self, options: 'a{sv}') -> 'hq':
            return list(self._owner._acquire('notify', options))

        @method()
        def StartNotify(self):
            self._owner._notifying(True)

        @method()
        def StopNotify(self):
            self._owner._notifying(False)

        def notify(self, value: bytes) -> None:
            self._value = value
            self.emit_properties_changed({'Value': value})

    class Advertisement(ServiceInterface):
        """A connectable advertisement of the MIDI service, named ``name``."""

        def __init__(self, name: str) -> None:
            super().__init__('org.bluez.LEAdvertisement1')
            self._local_name = name

        @dbus_property(access = PropertyAccess.READ)
        def Type(self) -> 's':
            return 'peripheral'

        @dbus_property(access = PropertyAccess.READ)
        def ServiceUUIDs(self) -> 'as':
            return [SERVICE]

        @dbus_property(access = PropertyAccess.READ)
        def LocalName(self) -> 's':
            return self._local_name

        @method()
        def Release(self):
            pass

    class AdapterNamed(Advertisement):
        """The same with the adapter's own name (BlueZ shortens it to fit)."""

        @dbus_property(access = PropertyAccess.READ, disabled = True)
        def LocalName(self) -> 's':
            return ''

        @dbus_property(access = PropertyAccess.READ)
        def Includes(self) -> 'as':
            return ['local-name']

    class Agent(ServiceInterface):
        """Accepts pairing without a code (NoInputNoOutput)."""

        def __init__(self) -> None:
            super().__init__('org.bluez.Agent1')

        @method()
        def Release(self):
            pass

        @method()
        def RequestConfirmation(self, device: 'o', passkey: 'u'):
            pass

        @method()
        def RequestAuthorization(self, device: 'o'):
            pass

        @method()
        def AuthorizeService(self, device: 'o', uuid: 's'):
            pass

        @method()
        def Cancel(self):
            pass

    _INTERFACES = types.SimpleNamespace(Service = Service, Characteristic = Characteristic, Agent = Agent,
                                        Advertisement = lambda name: Advertisement(name) if name else AdapterNamed(name))
    return _INTERFACES
