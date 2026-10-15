"""
Network MIDI (RTP-MIDI, Apple's network MIDI): other computers on the network
connect to a session and get the widgets' messages, and what they send back
comes in as MessageReceived::

    network = RtpMidi(session = 'Pi grid')
    network.connect()                      # announced on the network as "Pi grid"
    surface.map(kick, network, NoteOn(36), on = Pressed)

The other side:

- macOS: Audio MIDI Setup > Window > Show MIDI Studio > Network: the session
  shows under Directory; select it and press Connect. The Mac's own session
  (My Sessions) must be enabled; it is the port DAWs see.
- Windows: rtpMIDI (Tobias Erichsen), the same way.
- Linux: rtpmidid.

With ``connect = 'macbook.local'`` this side invites that computer instead,
again whenever it comes back (its session must accept: on macOS "Who may
connect to me: Anyone").

Announcing the session uses the ``zeroconf`` package when installed (``pip
install "pyxelwidgets[network]"``), else the system's ``dns-sd`` (macOS,
Windows with Bonjour) or ``avahi-publish-service`` (Linux, avahi-utils); in
the Android app, Android's own (NsdManager).
Messages go without a recovery journal: fine on a local network.
"""

import random
import select
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time

import pyxelwidgets.devices
import pyxelwidgets.events
import pyxelwidgets.message

__all__ = ['RtpMidi']

_SIGNATURE = b'\xff\xff'
_INVITE, _ACCEPT, _REJECT, _END, _SYNC, _FEEDBACK = b'IN', b'OK', b'NO', b'BY', b'CK', b'RS'
_VERSION = 2
# RTP: version 2, payload type 0x61 (what Apple sends)
_RTP = (0x80, 0x61)
_SERVICE = '_apple-midi._udp'

class _Peer:
    """A computer in the session: its control and data addresses, and who started it."""

    def __init__(self, name: str, ssrc: int, control: tuple, token: int, invited: bool) -> None:
        self.name = name
        self.ssrc = ssrc
        self.control = control
        self.data = None
        self.token = token
        #: Whether this side invited it (then this side keeps the clocks in sync)
        self.invited = invited
        self.heard = time.monotonic()
        self.synced = 0
        self.next_sync = 0.0
        self.unanswered = 0
        #: Round trip in seconds, from the last clock sync
        self.latency = None
        # A system exclusive it is sending in segments
        self.sysex = []

class _Target:
    """A computer to invite (``connect``): where it is, and how the invitation goes."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.address = None
        self.token = None
        self.stage = None          # None, 'control' (invited), 'data' (control accepted)
        self.next_try = 0.0
        self.refused = None
        self.peer = None

    def __str__(self) -> str:
        return f'{self.host}:{self.port}'

class RtpMidi(pyxelwidgets.devices.Device):
    """
    Network MIDI (RTP-MIDI): a session other computers connect to (macOS
    Audio MIDI Setup > Network, rtpMIDI on Windows, rtpmidid on Linux), or
    that invites them. Sends MIDI channel messages to every computer in the
    session; what they send comes in as MessageReceived (and every MIDI
    message, clock included, goes to ``raw_listeners``).
    """

    model = 'Network MIDI (RTP-MIDI)'
    messages: tuple = ('NoteOn', 'NoteOff', 'ControlChange', 'ProgramChange', 'PitchBend', 'PolyPressure', 'ChannelPressure')

    #: A DAW's MIDI clock sent to it can drive the transport (``raw_listeners``; a layout's ``transport.sync.output``)
    receives_clock = True
    #: Seconds between invitations to a computer that hasn't answered
    retry = 2.0
    #: Seconds between clock syncs once the first ones are done (computers this side invited)
    sync_interval = 10.0
    #: Clock syncs without an answer after which an invited computer is gone (and invited again)
    sync_misses = 3
    #: Seconds of silence after which a computer that joined is forgotten (they sync every few seconds)
    timeout = 120.0

    def __init__(self, *, session: str | None = None, port: int = 5004, connect: str = '', announce: bool = True, **kwargs):
        """
        session: str, optional
            The name other computers see (default: PyxelWidgets and this computer's name).
        port: int = 5004
            The session's UDP port; the next one carries the MIDI.
        connect: str, optional
            Computers to invite, as host or host:port, separated by commas (e.g. macbook.local). Invited again when they come back.
        announce: bool = True
            Announce the session on the network (Bonjour), so it shows in the other side's list.
        """
        super().__init__(**kwargs)
        self.session = session or f'PyxelWidgets ({_computer_name()})'
        self.port = port
        self.connect_to = connect
        self.announce = announce
        #: Why it may not work as expected (an invitation refused, not announced), or None
        self.warning = None
        self.ssrc = random.getrandbits(32)
        self.peers = {}
        #: Called with each received MIDI message (a list of bytes), real-time and system exclusive included
        self.raw_listeners = []
        self._targets = []
        self._sockets = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._sequence = random.getrandbits(16)
        self._start = time.monotonic()
        self._advert = None

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['messages'] = list(cls.messages)
        return info

    @property
    def status_text(self) -> str:
        """Who is in the session, for people (the designer shows it)."""
        with self._lock:
            names = [peer.name or peer.control[0] for peer in self.peers.values() if peer.data is not None]
        if names:
            return f'{self.session}: {", ".join(names)}'
        return f'{self.session}: waiting for a computer to join (port {self.port})'

    # Lifecycle

    def connect(self) -> None:
        if self.connected:
            self.disconnect()
        control = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            control.bind(('0.0.0.0', self.port))
            data.bind(('0.0.0.0', self.port + 1))
        except OSError as error:
            control.close()
            data.close()
            raise OSError(f'ports {self.port} and {self.port + 1} are taken ({error.strerror}): give the session another port') from None
        super().connect()
        self._sockets = (control, data)
        self._targets = [_target(text) for text in self.connect_to.split(',') if text.strip()]
        self.warning = None
        if self.announce:
            self._advert, self.warning = _announce(self.session, self.port)
        self._running = True
        self._thread = threading.Thread(target = self._run, name = f'{self.name}_rtp', daemon = True)
        self._thread.start()

    def disconnect(self) -> None:
        self._running = False
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout = 2.0)
        self._thread = None
        if self._sockets is not None:
            with self._lock:
                peers, self.peers = list(self.peers.values()), {}
            for peer in peers:
                self._send_command(0, _END, peer.control, peer.token)
            for sock in self._sockets:
                sock.close()
            self._sockets = None
        if self._advert is not None:
            self._advert.close()
            self._advert = None
        super().disconnect()

    # Sending

    def send(self, message: pyxelwidgets.message.MidiMessage) -> None:
        self.send_midi(message.to_midi())

    def send_midi(self, *messages: list) -> None:
        """Send raw MIDI messages (lists of bytes, no system exclusive) to everyone in the session, in one packet."""
        if self._sockets is None:
            return
        with self._lock:
            addresses = [peer.data for peer in self.peers.values() if peer.data is not None]
            if not addresses:
                return
            self._sequence = (self._sequence + 1) & 0xFFFF
            sequence = self._sequence
        packet = rtp_packet(messages, sequence, self._clock() & 0xFFFFFFFF, self.ssrc)
        for address in addresses:
            try:
                self._sockets[1].sendto(packet, address)
            except OSError:
                pass

    # The session

    def _clock(self) -> int:
        """Time in RTP-MIDI's units (1/10000 s)."""
        return int((time.monotonic() - self._start) * 10000)

    def _run(self) -> None:
        sockets = self._sockets
        while self._running:
            try:
                ready, _, _ = select.select(sockets, [], [], 0.2)
            except (OSError, ValueError):
                return
            for which, sock in enumerate(sockets):
                if sock in ready:
                    try:
                        packet, address = sock.recvfrom(65536)
                    except OSError:
                        continue
                    try:
                        self._received(which, packet, address)
                    except (struct.error, IndexError):
                        pass
            self._tick()

    def _received(self, which: int, packet: bytes, address: tuple) -> None:
        if packet[:2] == _SIGNATURE:
            self._command(which, packet[2:4], packet, address)
        elif which == 1 and len(packet) > 12 and packet[0] & 0xC0 == 0x80:
            ssrc = struct.unpack_from('>I', packet, 8)[0]
            with self._lock:
                peer = self.peers.get(ssrc)
                if peer is not None:
                    peer.heard = time.monotonic()
            for midi in midi_commands(packet[12:], None if peer is None else peer.sysex):
                for listener in self.raw_listeners:
                    listener(midi)
                message = pyxelwidgets.message.MidiMessage.from_midi(midi)
                if message is not None:
                    self.emit(pyxelwidgets.events.MessageReceived(self, message))

    def _command(self, which: int, command: bytes, packet: bytes, address: tuple) -> None:
        now = time.monotonic()
        if command in (_INVITE, _ACCEPT, _REJECT, _END):
            _, token, ssrc = struct.unpack_from('>III', packet, 4)
            name = packet[16:].split(b'\0')[0].decode('utf-8', 'replace')
            if command == _INVITE:
                self._send_command(which, _ACCEPT, address, token)
                with self._lock:
                    if which == 0:
                        # A computer coming back replaces what it left
                        for old in [key for key, peer in self.peers.items() if peer.control == address and key != ssrc]:
                            del self.peers[old]
                        self.peers[ssrc] = _Peer(name, ssrc, address, token, False)
                    elif ssrc in self.peers:
                        self.peers[ssrc].data = address
                        self.peers[ssrc].heard = now
                    else:
                        # Data invitation without the control one: the control port is the one before
                        peer = self.peers[ssrc] = _Peer(name, ssrc, (address[0], address[1] - 1), token, False)
                        peer.data = address
            elif command == _ACCEPT:
                self._accepted(which, token, ssrc, name, address)
            elif command == _REJECT:
                for target in self._targets:
                    if target.token == token:
                        target.stage, target.refused = None, name or str(target)
                        target.next_try = now + self.retry * 5
                        self.warning = f'{target} refused the invitation (on macOS: Network, "Who may connect to me: Anyone")'
            else:
                with self._lock:
                    self.peers.pop(ssrc, None)
                for target in self._targets:
                    if target.peer == ssrc:
                        target.peer, target.stage, target.next_try = None, None, now + self.retry
        elif command == _SYNC and which == 1:
            ssrc, count = struct.unpack_from('>IB', packet, 4)
            stamps = list(struct.unpack_from('>QQQ', packet, 12))
            with self._lock:
                peer = self.peers.get(ssrc)
                if peer is not None:
                    peer.heard = now
            if count == 0:
                stamps[1] = self._clock()
                self._send_sync(1, stamps, address)
            elif count == 1:
                stamps[2] = self._clock()
                self._send_sync(2, stamps, address)
                if peer is not None:
                    peer.unanswered = 0
                    peer.latency = (stamps[2] - stamps[0]) / 10000
        elif command == _FEEDBACK:
            ssrc = struct.unpack_from('>I', packet, 4)[0]
            with self._lock:
                if ssrc in self.peers:
                    self.peers[ssrc].heard = now

    def _accepted(self, which: int, token: int, ssrc: int, name: str, address: tuple) -> None:
        """A computer this side invited accepted on the control (``which`` 0) or data port."""
        for target in self._targets:
            if target.token != token:
                continue
            if which == 0 and target.stage == 'control':
                target.stage = 'data'
                target.address = address
                with self._lock:
                    self.peers[ssrc] = _Peer(name, ssrc, address, token, True)
                self._send_command(1, _INVITE, (address[0], address[1] + 1), token)
            elif which == 1 and target.stage == 'data':
                target.stage, target.peer, target.refused = 'ready', ssrc, None
                with self._lock:
                    peer = self.peers.get(ssrc)
                    if peer is not None:
                        peer.data = address
                if self.warning and str(target) in self.warning:
                    self.warning = None

    def _tick(self) -> None:
        now = time.monotonic()
        for target in self._targets:
            if target.stage in (None, 'control', 'data') and now >= target.next_try:
                target.next_try = now + self.retry
                address = _resolve(target.host, target.port)
                if address is None:
                    continue
                target.token = random.getrandbits(32)
                target.stage = 'control'
                self._send_command(0, _INVITE, address, target.token)
        with self._lock:
            peers = list(self.peers.values())
        for peer in peers:
            if peer.invited and peer.data is not None and now >= peer.next_sync:
                if peer.unanswered >= self.sync_misses:
                    self._lost(peer)
                    continue
                # A few quick syncs first, then every sync_interval
                peer.next_sync = now + (1.5 if peer.synced < 6 else self.sync_interval)
                peer.synced += 1
                peer.unanswered += 1
                self._send_sync(0, [self._clock(), 0, 0], peer.data)
            elif not peer.invited and now - peer.heard > self.timeout:
                self._lost(peer)

    def _lost(self, peer: _Peer) -> None:
        with self._lock:
            self.peers.pop(peer.ssrc, None)
        for target in self._targets:
            if target.peer == peer.ssrc:
                target.peer, target.stage, target.next_try = None, None, 0.0

    def _send_command(self, which: int, command: bytes, address: tuple, token: int) -> None:
        packet = _SIGNATURE + command + struct.pack('>III', _VERSION, token, self.ssrc)
        if command != _END:
            packet += self.session.encode('utf-8') + b'\0'
        try:
            self._sockets[which].sendto(packet, address)
        except (OSError, TypeError):
            pass

    def _send_sync(self, count: int, stamps: list, address: tuple) -> None:
        packet = _SIGNATURE + _SYNC + struct.pack('>IB3xQQQ', self.ssrc, count, *(stamp & 0xFFFFFFFFFFFFFFFF for stamp in stamps))
        try:
            self._sockets[1].sendto(packet, address)
        except OSError:
            pass

# Packets

def rtp_packet(messages: list, sequence: int, timestamp: int, ssrc: int) -> bytes:
    """An RTP-MIDI packet carrying ``messages`` (lists of MIDI bytes, all at once; no journal)."""
    # A delta time (0) before every message but the first
    commands = b'\0'.join(bytes(midi) for midi in messages)
    if len(commands) < 16:
        header = bytes([len(commands)])
    else:
        header = bytes([0x80 | (len(commands) >> 8), len(commands) & 0xFF])
    return bytes(_RTP) + struct.pack('>HII', sequence, timestamp, ssrc) + header + commands

def _message_length(status: int) -> int:
    """Data bytes after a status byte (sysex: 0, handled apart)."""
    if status < 0xF0:
        return 1 if status & 0xF0 in (0xC0, 0xD0) else 2
    return {0xF1: 1, 0xF2: 2, 0xF3: 1}.get(status, 0)

def midi_commands(payload: bytes, sysex: list | None = None) -> list:
    """
    The MIDI messages (lists of bytes) in an RTP-MIDI payload (after the RTP
    header), in order, real-time messages and system exclusives included. A
    system exclusive split over packets (RFC 6295 segments) is gathered in
    ``sysex`` (a list kept between calls, one per sender); without it, only
    whole ones in a packet come out.
    """
    flags = payload[0]
    if flags & 0x80:
        length, start = ((flags & 0x0F) << 8) | payload[1], 2
    else:
        length, start = flags & 0x0F, 1
    data = payload[start:start + length]
    delta = bool(flags & 0x20)
    found = []
    running = None
    position = 0
    while position < len(data):
        if delta:
            # Delta time: up to 4 bytes, the last without the top bit
            while position < len(data) and data[position] & 0x80:
                position += 1
            position += 1
        delta = True
        if position >= len(data):
            break
        byte = data[position]
        if byte in (0xF0, 0xF7):
            # A system exclusive part: up to its end (F7), a continuation (F0) or a cancel (F4)
            end = position + 1
            while end < len(data) and data[end] not in (0xF7, 0xF0, 0xF4):
                end += 1
            closing = data[end] if end < len(data) else None
            part = list(data[position + 1:end])
            if byte == 0xF0 and closing == 0xF7:
                found.append([0xF0, *part, 0xF7])
            elif sysex is not None:
                if byte == 0xF0:
                    sysex[:] = [0xF0]
                if sysex:
                    sysex.extend(part)
                    if closing == 0xF7:
                        found.append(sysex + [0xF7])
                    if closing != 0xF0 or len(sysex) > 65536:
                        sysex.clear()
            running = None
            position = end + 1
            continue
        if byte >= 0xF8:
            found.append([byte])
            position += 1
            continue
        if byte & 0x80:
            status = byte
            position += 1
            running = status if status < 0xF0 else None
        elif running is None:
            break
        else:
            status = running
        count = _message_length(status)
        message = [status] + list(data[position:position + count])
        position += count
        if len(message) == count + 1:
            found.append(message)
    return found

# Finding computers

def _target(text: str) -> _Target:
    host, _, port = text.strip().rpartition(':')
    if not host or not port.isdigit():
        return _Target(text.strip(), 5004)
    return _Target(host, int(port))

def _resolve(host: str, port: int) -> tuple | None:
    try:
        return (socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_DGRAM)[0][4][0], port)
    except (OSError, IndexError):
        return None

def _lan_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('10.255.255.255', 1))
            return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'

def _computer_name() -> str:
    if hasattr(sys, 'getandroidapilevel'):
        # Android's host name is "localhost": the phone's own name instead
        try:
            from java import jclass
            return str(jclass('io.github.nullmember.pyxelwidgets.NsdAdvert').deviceName())
        except Exception:
            pass
    return socket.gethostname().split('.')[0]

class _AndroidNsd:
    """The session announced by Android (NsdManager, through the app's NsdAdvert)."""

    #: Milliseconds to wait for Android's answer
    timeout = 3000

    def __init__(self, name: str, port: int) -> None:
        from java import jclass
        self.advert = jclass('io.github.nullmember.pyxelwidgets.NsdAdvert').register(name, _SERVICE, port, self.timeout)
        error = self.advert.error()
        if error is not None:
            self.advert.close()
            raise OSError(str(error))

    def close(self) -> None:
        self.advert.close()

class _Zeroconf:
    def __init__(self, name: str, port: int) -> None:
        import zeroconf
        self.zeroconf = zeroconf.Zeroconf()
        host = socket.gethostname().split('.')[0]
        self.info = zeroconf.ServiceInfo(f'{_SERVICE}.local.', f'{name}.{_SERVICE}.local.', port = port,
                                         addresses = [socket.inet_aton(_lan_address())], server = f'{host}.local.')
        self.zeroconf.register_service(self.info, allow_name_change = True)

    def close(self) -> None:
        self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()

class _Process:
    def __init__(self, command: list) -> None:
        self.process = subprocess.Popen(command, stdin = subprocess.DEVNULL, stdout = subprocess.DEVNULL, stderr = subprocess.DEVNULL)

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout = 2.0)
        except subprocess.TimeoutExpired:
            self.process.kill()

def _announce(name: str, port: int) -> tuple:
    """Announce the session on the network: (something to close, None) or (None, why it isn't)."""
    if hasattr(sys, 'getandroidapilevel'):
        try:
            return _AndroidNsd(name, port), None
        except Exception as error:
            return None, f'not announced on the network ({error}): add {_lan_address()}:{port} by hand on the other side'
    try:
        return _Zeroconf(name, port), None
    except ImportError:
        pass
    except Exception as error:
        return None, f'not announced on the network ({error}): add {_lan_address()}:{port} by hand on the other side'
    if shutil.which('dns-sd'):
        return _Process(['dns-sd', '-R', name, _SERVICE, 'local', str(port)]), None
    if shutil.which('avahi-publish-service'):
        return _Process(['avahi-publish-service', name, _SERVICE, str(port)]), None
    return None, (f'not announced on the network: pip install zeroconf (or avahi-utils), or add {_lan_address()}:{port} '
                  'by hand on the other side')
