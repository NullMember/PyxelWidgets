import asyncio
import os
import platform
import shutil
import socket
import struct
import subprocess
import threading
import time

import pytest

from pyxelwidgets import MessageReceived
from pyxelwidgets.devices import ble_midi, rtp_midi
from pyxelwidgets.devices.ble_midi import BleMidi
from pyxelwidgets.devices.rtp_midi import RtpMidi
from pyxelwidgets.message import ControlChange, NoteOff, NoteOn


def free_port() -> int:
    """An even port whose next one is free too."""
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1] & ~1
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as a, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as b:
                a.bind(('0.0.0.0', port))
                b.bind(('0.0.0.0', port + 1))
            return port
        except OSError:
            continue
    raise RuntimeError('no free ports')


def wait_for(condition, seconds = 3.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


# RTP-MIDI

def test_rtp_packets_round_trip():
    packet = rtp_midi.rtp_packet([[0x90, 60, 100], [0xB0, 7, 99]], 5, 1234, 42)
    assert packet[:2] == bytes([0x80, 0x61]) and struct.unpack_from('>HII', packet, 2) == (5, 1234, 42)
    assert packet[12:] == bytes([7, 0x90, 60, 100, 0x00, 0xB0, 7, 99])
    assert rtp_midi.midi_commands(packet[12:]) == [[0x90, 60, 100], [0xB0, 7, 99]]
    # Apple's packets: delta times between commands, running status, a journal after the list (ignored)
    payload = bytes([0x0B, 0x90, 60, 100, 0x00, 61, 101, 0x81, 0x00, 0xC0, 5, 0xF8]) + b'journal'
    assert rtp_midi.midi_commands(payload) == [[0x90, 60, 100], [0x90, 61, 101], [0xC0, 5]]
    # Z flag: the first command has a delta time too; a whole system exclusive, a clock
    payload = bytes([0x2B, 0x00, 0xF0, 1, 2, 0xF7, 0x00, 0xE0, 0, 64, 0x00, 0xF8])
    assert rtp_midi.midi_commands(payload) == [[0xF0, 1, 2, 0xF7], [0xE0, 0, 64], [0xF8]]
    # Over 15 bytes: a 12-bit length
    long = rtp_midi.rtp_packet([[0x90, 1, 2]] * 6, 0, 0, 0)
    assert long[12] == 0x80 and long[13] == 23 and rtp_midi.midi_commands(long[12:]) == [[0x90, 1, 2]] * 6


def test_rtp_system_exclusive_segments_and_real_time():
    sysex = []
    # RFC 6295 segments: F0 ... F0, F7 ... F0, F7 ... F7 (a clock between them)
    assert rtp_midi.midi_commands(bytes([0x07, 0xF0, 1, 2, 0xF0, 0x00, 0xFA]), sysex) == [[0xFA]]
    assert rtp_midi.midi_commands(bytes([0x04, 0xF7, 3, 4, 0xF0]), sysex) == []
    assert rtp_midi.midi_commands(bytes([0x07, 0xF7, 5, 0xF7, 0x00, 0xFC, 0x00, 0xF8]), sysex) == [[0xF0, 1, 2, 3, 4, 5, 0xF7], [0xFC], [0xF8]]
    assert sysex == []
    # Cancelled (F4): nothing comes out; without a state a segment is skipped
    rtp_midi.midi_commands(bytes([0x04, 0xF0, 1, 2, 0xF0]), sysex)
    assert rtp_midi.midi_commands(bytes([0x03, 0xF7, 3, 0xF4]), sysex) == [] and sysex == []
    assert rtp_midi.midi_commands(bytes([0x04, 0xF0, 1, 2, 0xF0])) == []


def test_rtp_clock_reaches_raw_listeners():
    port = free_port()
    receiver, sender = RtpMidi(name = 'receiver', session = 'Receiver', port = port, announce = False), None
    try:
        receiver.connect()
        sender = RtpMidi(name = 'sender', session = 'Sender', port = free_port(), connect = f'127.0.0.1:{port}', announce = False)
        sender.connect()
        assert wait_for(lambda: receiver.peers and sender.peers)
        heard, messages = [], []
        receiver.raw_listeners.append(heard.append)
        receiver.on(MessageReceived, lambda event: messages.append(event.message))
        for midi in ([0xFA], [0xF8], [0xF0, 0x7E, 1, 0xF7], [0x90, 60, 100]):
            sender.send_midi(midi)
        assert wait_for(lambda: len(heard) == 4)
        assert heard == [[0xFA], [0xF8], [0xF0, 0x7E, 1, 0xF7], [0x90, 60, 100]] and messages == [NoteOn(60, 100)]
    finally:
        receiver.disconnect()
        if sender is not None:
            sender.disconnect()


def test_rtp_sessions_invite_send_and_leave():
    a_port, b_port = free_port(), None
    a = RtpMidi(session = 'A', port = a_port, announce = False)
    a.connect()
    b_port = free_port()
    b = RtpMidi(session = 'B', port = b_port, connect = f'127.0.0.1:{a_port}', announce = False)
    received = {'a': [], 'b': []}
    a.on(MessageReceived, lambda e: received['a'].append(e.message))
    b.on(MessageReceived, lambda e: received['b'].append(e.message))
    b.connect()
    try:
        assert wait_for(lambda: 'B' in a.status_text and 'A' in b.status_text)
        b.send(NoteOn(60, 100, 2))
        a.send(ControlChange(7, 99))
        assert wait_for(lambda: received['a'] and received['b'])
        assert received == {'a': [NoteOn(60, 100, 2)], 'b': [ControlChange(7, 99)]}
        # The inviting side keeps the clocks in sync
        assert wait_for(lambda: any(peer.latency is not None for peer in b.peers.values()))
        # Leaving says goodbye; the session waits again
        b.disconnect()
        assert wait_for(lambda: 'waiting' in a.status_text)
        # Coming back invites again
        b.connect()
        assert wait_for(lambda: 'B' in a.status_text)
    finally:
        b.disconnect()
        a.disconnect()


def test_rtp_invites_again_when_the_other_side_returns():
    a_port, b_port = free_port(), free_port()
    b = RtpMidi(session = 'B', port = b_port, connect = f'127.0.0.1:{a_port}', announce = False)
    b.retry = 0.1
    b.connect()
    a = RtpMidi(session = 'A', port = a_port, announce = False)
    try:
        time.sleep(0.3)
        assert 'waiting' in b.status_text
        a.connect()
        assert wait_for(lambda: 'A' in b.status_text)
        a.disconnect()
        assert wait_for(lambda: 'waiting' in b.status_text)
        a.connect()
        assert wait_for(lambda: 'A' in b.status_text)
    finally:
        a.disconnect()
        b.disconnect()


def test_rtp_taken_port():
    a = RtpMidi(port = free_port(), announce = False)
    a.connect()
    try:
        with pytest.raises(OSError, match = 'another port'):
            RtpMidi(port = a.port, announce = False).connect()
    finally:
        a.disconnect()


# Bluetooth LE MIDI

def test_ble_packets():
    packets = ble_midi.ble_packets([[0x90, 60, 100], [0x80, 60, 0], [0xB0, 1, 2], [0xB0, 1, 3], [0xB0, 1, 4]], 12345)
    # 12345 ms: 13 bits 0x1039 → header 0x80 | 0x20, timestamps 0x80 | 0x39
    assert packets == [bytes([0xA0, 0xB9, 0x90, 60, 100, 0xB9, 0x80, 60, 0, 0xB9, 0xB0, 1, 2, 0xB9, 0xB0, 1, 3]),
                       bytes([0xA0, 0xB9, 0xB0, 1, 4])]
    assert all(len(packet) <= 20 for packet in packets)
    assert len(ble_midi.ble_packets([[0x90, 1, 2]] * 10, 0, 100)) == 1


def test_ble_received_messages():
    state = ble_midi._ParseState()
    # Running status with and without a timestamp, then a system exclusive left open
    first = bytes([0x80, 0x81, 0x90, 60, 100, 61, 101, 0x82, 62, 102, 0x83, 0xF0, 1, 2])
    assert ble_midi.ble_midi_messages(first, state) == [[0x90, 60, 100], [0x90, 61, 101], [0x90, 62, 102]]
    assert state.sysex == [0xF0, 1, 2]
    # It goes on in the next packet (a clock inside it comes out first), ends with a timestamp before F7
    second = bytes([0x80, 3, 0x84, 0xF8, 4, 0x84, 0xF7, 0x85, 0xF8, 0x85, 0xC0, 5])
    assert ble_midi.ble_midi_messages(second, state) == [[0xF8], [0xF0, 1, 2, 3, 4, 0xF7], [0xF8], [0xC0, 5]]
    assert state.sysex is None
    assert ble_midi.ble_midi_messages(b'\x00\x90') == []
    # A real-time message between a message's data bytes, start/stop, song position
    third = bytes([0x80, 0x81, 0x90, 60, 0x81, 0xF8, 100, 0x82, 0xFA, 0x82, 0xF2, 0x10, 0x00, 0x83, 0xFC])
    assert ble_midi.ble_midi_messages(third) == [[0xF8], [0x90, 60, 100], [0xFA], [0xF2, 0x10, 0], [0xFC]]
    # A timestamp of 0xF7 isn't the end of a system exclusive
    state = ble_midi._ParseState()
    assert ble_midi.ble_midi_messages(bytes([0x80, 0xF7, 0xF0, 1, 0xF7, 0xF7]), state) == [[0xF0, 1, 0xF7]]


def test_ble_packets_split_long_system_exclusive():
    sysex = [0xF0, *range(50), 0xF7]
    messages = [[0xF8], sysex, [0x90, 60, 100]]
    packets = ble_midi.ble_packets(messages, 300, 20)
    assert all(len(packet) <= 20 for packet in packets) and len(packets) > 2
    # Continuation packets carry data only (after their header)
    assert packets[1][1] < 0x80
    state = ble_midi._ParseState()
    assert [midi for packet in packets for midi in ble_midi.ble_midi_messages(packet, state)] == messages
    # One that fits shares the packet
    assert len(ble_midi.ble_packets([[0xF0, 1, 2, 0xF7], [0xF8]], 0, 20)) == 1


def test_ble_only_on_linux(monkeypatch):
    monkeypatch.setattr(ble_midi.platform, 'system', lambda: 'Darwin')
    with pytest.raises(OSError, match = 'Linux'):
        BleMidi().connect()


BUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=/tmp</listen>
  <policy context="default"><allow send_destination="*"/><allow eavesdrop="true"/><allow own="*"/></policy>
</busconfig>
"""


@pytest.fixture
def bus(tmp_path):
    """A private D-Bus with a fake BlueZ on it."""
    pytest.importorskip('dbus_fast')
    daemon = shutil.which('dbus-daemon')
    if daemon is None:
        pytest.skip('needs dbus-daemon')
    config = tmp_path / 'bus.conf'
    config.write_text(BUS_CONFIG)
    process = subprocess.Popen([daemon, f'--config-file={config}', '--nofork', '--print-address'], stdout = subprocess.PIPE, text = True)
    address = process.stdout.readline().strip()
    if not address:
        process.wait()
        pytest.skip('dbus-daemon did not start')
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target = loop.run_forever, daemon = True)
    thread.start()
    bluez = asyncio.run_coroutine_threadsafe(_fake_bluez(address), loop).result(5)
    bluez.loop = loop
    yield address, bluez
    loop.call_soon_threadsafe(loop.stop)
    thread.join(2)
    process.terminate()
    process.wait()


async def _fake_bluez(address):
    from dbus_fast import Variant
    from dbus_fast.aio import MessageBus
    from dbus_fast.service import PropertyAccess, ServiceInterface, dbus_property, method

    calls = []

    class Adapter(ServiceInterface):
        def __init__(self):
            super().__init__('org.bluez.Adapter1')
            self.powered = False

        @dbus_property()
        def Powered(self) -> 'b':
            return self.powered

        @Powered.setter
        def Powered(self, value: 'b'):
            self.powered = value
            calls.append(('Powered', value))

    def recorder(interface, members):
        class Recorder(ServiceInterface):
            def __init__(self):
                super().__init__(interface)
        for member, signature in members.items():
            def handler(self, *args, member = member):
                calls.append((member, *args))
            handler.__name__ = member
            parameters = [f'a{index}' for index in range(len(signature))]
            handler.__annotations__ = dict(zip(parameters, signature))
            handler.__signature__ = __import__('inspect').Signature(
                [__import__('inspect').Parameter('self', __import__('inspect').Parameter.POSITIONAL_ONLY)]
                + [__import__('inspect').Parameter(name, __import__('inspect').Parameter.POSITIONAL_OR_KEYWORD, annotation = kind)
                   for name, kind in zip(parameters, signature)])
            setattr(Recorder, member, method()(handler))
        return Recorder()

    bus = await MessageBus(bus_address = address).connect()
    await bus.request_name('org.bluez')
    adapter = Adapter()
    bus.export('/org/bluez/hci0', adapter)
    bus.export('/org/bluez/hci0', recorder('org.bluez.GattManager1', {'RegisterApplication': ['o', 'a{sv}'], 'UnregisterApplication': ['o']}))
    bus.export('/org/bluez/hci0', recorder('org.bluez.LEAdvertisingManager1', {'RegisterAdvertisement': ['o', 'a{sv}'], 'UnregisterAdvertisement': ['o']}))
    bus.export('/org/bluez', recorder('org.bluez.AgentManager1', {'RegisterAgent': ['o', 's'], 'RequestDefaultAgent': ['o'], 'UnregisterAgent': ['o']}))

    class Fake:
        pass

    fake = Fake()
    fake.bus, fake.calls, fake.adapter, fake.Variant = bus, calls, adapter, Variant
    return fake


def _run(bluez, coroutine):
    return asyncio.run_coroutine_threadsafe(coroutine, bluez.loop).result(5)


async def _call(bluez, destination, path, interface, member, signature = '', body = None):
    from dbus_fast import Message, MessageType
    reply = await bluez.bus.call(Message(destination = destination, path = path, interface = interface, member = member,
                                         signature = signature, body = body or []))
    assert reply.message_type != MessageType.ERROR, reply.body
    return reply.body


def test_ble_registers_with_bluez_and_carries_midi(bus):
    address, bluez = bus
    device = BleMidi(name = 'pi grid', bluetooth_name = 'PiGrid')
    device.bus_address = address
    received = []
    device.on(MessageReceived, lambda e: received.append(e.message))
    device.connect()
    try:
        owner = device._bus.unique_name
        app, advert = '/org/pyxelwidgets/pi_grid', '/org/pyxelwidgets/pi_grid_advert'
        assert ('Powered', True) in bluez.calls
        assert [call[:2] for call in bluez.calls if call[0].startswith('Register')] == [('RegisterApplication', app), ('RegisterAdvertisement', advert)]
        # What BlueZ reads from the application and the advertisement
        objects = _run(bluez, _call(bluez, owner, app, 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects'))[0]
        service = objects[f'{app}/service0']['org.bluez.GattService1']
        characteristic = objects[f'{app}/service0/char0']['org.bluez.GattCharacteristic1']
        assert service['UUID'].value == ble_midi.SERVICE and service['Primary'].value
        assert characteristic['UUID'].value == ble_midi.CHARACTERISTIC
        assert characteristic['Flags'].value == ['read', 'write-without-response', 'notify']
        assert characteristic['Service'].value == f'{app}/service0'
        properties = _run(bluez, _call(bluez, owner, advert, 'org.freedesktop.DBus.Properties', 'GetAll', 's', ['org.bluez.LEAdvertisement1']))[0]
        assert {key: value.value for key, value in properties.items()} == {
            'Type': 'peripheral', 'ServiceUUIDs': [ble_midi.SERVICE], 'LocalName': 'PiGrid'}

        # Nothing goes out before a computer subscribes
        assert 'advertising' in device.status_text
        device.send(NoteOn(60, 100))
        char = f'{app}/service0/char0'
        notified = []

        def signal(message):
            if message.member == 'PropertiesChanged' and message.path == char:
                notified.append(bytes(message.body[1]['Value'].value))

        bluez.bus.add_message_handler(signal)
        _run(bluez, bluez.bus.call(__import__('dbus_fast').Message(
            interface = 'org.freedesktop.DBus', path = '/org/freedesktop/DBus', destination = 'org.freedesktop.DBus',
            member = 'AddMatch', signature = 's', body = [f"type='signal',sender='{owner}'"])))
        assert _run(bluez, _call(bluez, owner, char, 'org.bluez.GattCharacteristic1', 'ReadValue', 'a{sv}',
                                 [{'mtu': bluez.Variant('q', 23)}])) == [b'']
        _run(bluez, _call(bluez, owner, char, 'org.bluez.GattCharacteristic1', 'StartNotify'))
        assert device.listening and 'connected' in device.status_text
        device.send(NoteOn(60, 100))
        device.send(NoteOff(60))
        # Sent together they usually share a packet; either way both arrive
        state = ble_midi._ParseState()
        assert wait_for(lambda: sum(len(ble_midi.ble_midi_messages(packet, ble_midi._ParseState())) for packet in notified) == 2)
        assert [midi for packet in notified for midi in ble_midi.ble_midi_messages(packet, state)] == [[0x90, 60, 100], [0x80, 60, 0]]

        # The computer writes MIDI
        _run(bluez, _call(bluez, owner, char, 'org.bluez.GattCharacteristic1', 'WriteValue', 'aya{sv}',
                          [bytes([0x80, 0x80, 0xB0, 7, 99, 0x80, 8, 1]), {'mtu': bluez.Variant('q', 185)}]))
        assert received == [ControlChange(7, 99), ControlChange(8, 1)]
        assert device._payload == 182
        _run(bluez, _call(bluez, owner, char, 'org.bluez.GattCharacteristic1', 'StopNotify'))
        assert not device.listening
    finally:
        device.disconnect()
    assert [call[:2] for call in bluez.calls if call[0].startswith('Unregister')] == [
        ('UnregisterAdvertisement', '/org/pyxelwidgets/pi_grid_advert'), ('UnregisterApplication', '/org/pyxelwidgets/pi_grid')]


def test_ble_passes_midi_through_acquired_sockets(bus):
    """BlueZ acquires the characteristic: MIDI goes through sockets, no D-Bus call per packet."""
    import socket
    from dbus_fast import Message, MessageType
    from dbus_fast.aio import MessageBus
    address, bluez = bus
    device = BleMidi(name = 'pi grid', bluetooth_name = 'PiGrid')
    device.bus_address = address
    received = []
    device.on(MessageReceived, lambda e: received.append(e.message))
    device.connect()
    try:
        owner = device._bus.unique_name
        char = '/org/pyxelwidgets/pi_grid/service0/char0'
        objects = _run(bluez, _call(bluez, owner, '/org/pyxelwidgets/pi_grid', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects'))[0]
        properties = objects[char]['org.bluez.GattCharacteristic1']
        # Present: BlueZ may acquire
        assert properties['WriteAcquired'].value is False and properties['NotifyAcquired'].value is False

        async def acquire(member):
            # Like bluetoothd: a connection passing unix fds
            fds = await MessageBus(bus_address = address, negotiate_unix_fd = True).connect()
            reply = await fds.call(Message(destination = owner, path = char, interface = 'org.bluez.GattCharacteristic1',
                                           member = member, signature = 'a{sv}', body = [{'mtu': bluez.Variant('q', 185)}]))
            assert reply.message_type != MessageType.ERROR, reply.body
            fd, mtu = reply.unix_fds[reply.body[0]], reply.body[1]
            fds.disconnect()
            return socket.socket(fileno = fd), mtu

        written, mtu = _run(bluez, acquire('AcquireWrite'))
        assert mtu == 185 and device._payload == 182
        written.send(bytes([0x80, 0x80, 0xB0, 7, 99, 0x80, 8, 1]))
        assert wait_for(lambda: received == [ControlChange(7, 99), ControlChange(8, 1)])

        notified, mtu = _run(bluez, acquire('AcquireNotify'))
        assert device.listening and 'connected' in device.status_text
        device.send(NoteOn(60, 100))
        device.send(NoteOff(60))
        notified.settimeout(3)
        # Sent together they usually share a packet; either way both arrive
        state, messages = ble_midi._ParseState(), []
        while len(messages) < 2:
            messages += ble_midi.ble_midi_messages(notified.recv(512), state)
        assert messages == [[0x90, 60, 100], [0x80, 60, 0]]

        # BlueZ closes its end when notifications stop or the computer leaves (seen
        # through epoll on Linux; macOS's kqueue doesn't report it for the stand-in datagram sockets)
        if platform.system() != 'Linux':
            return
        notified.close()
        assert wait_for(lambda: not device.listening and device._notify_socket is None)
        written.close()
        assert wait_for(lambda: device._write_socket is None)
    finally:
        device.disconnect()


def test_ble_keeps_notifications_while_bluez_is_behind(bus):
    """A socket holds a few packets: the rest wait until BlueZ reads, none are lost (a lost NoteOff hangs a note)."""
    import socket
    from dbus_fast import Message
    from dbus_fast.aio import MessageBus
    address, bluez = bus
    device = BleMidi(name = 'pi grid', bluetooth_name = 'PiGrid')
    device.bus_address = address
    device.connect()
    try:
        owner = device._bus.unique_name

        async def acquire():
            fds = await MessageBus(bus_address = address, negotiate_unix_fd = True).connect()
            reply = await fds.call(Message(destination = owner, path = '/org/pyxelwidgets/pi_grid/service0/char0',
                                           interface = 'org.bluez.GattCharacteristic1', member = 'AcquireNotify',
                                           signature = 'a{sv}', body = [{'mtu': bluez.Variant('q', 23)}]))
            fds.disconnect()
            return socket.socket(fileno = reply.unix_fds[reply.body[0]])

        notified = _run(bluez, acquire())
        # One packet each, while nothing reads them
        for note in range(60):
            device.send(NoteOn(note, 100))
            time.sleep(0.005)
        assert wait_for(lambda: not device._pending)
        notified.settimeout(3)
        state, notes = ble_midi._ParseState(), []
        while len(notes) < 60:
            notes += [midi[1] for midi in ble_midi.ble_midi_messages(notified.recv(512), state)]
        assert notes == list(range(60)) and device.dropped == 0
        notified.close()
    finally:
        device.disconnect()


def test_ble_secure_pairs_without_a_code_and_uses_the_adapter_name(bus):
    address, bluez = bus
    device = BleMidi(name = 'secure', secure = True)
    device.bus_address = address
    device.connect()
    try:
        owner = device._bus.unique_name
        assert [call[:3] for call in bluez.calls if 'Agent' in call[0]] == [
            ('RegisterAgent', '/org/pyxelwidgets/secure_agent', 'NoInputNoOutput'), ('RequestDefaultAgent', '/org/pyxelwidgets/secure_agent')]
        objects = _run(bluez, _call(bluez, owner, '/org/pyxelwidgets/secure', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects'))[0]
        flags = objects['/org/pyxelwidgets/secure/service0/char0']['org.bluez.GattCharacteristic1']['Flags'].value
        assert 'encrypt-write' in flags and 'encrypt-notify' in flags
        properties = _run(bluez, _call(bluez, owner, '/org/pyxelwidgets/secure_advert', 'org.freedesktop.DBus.Properties', 'GetAll', 's',
                                       ['org.bluez.LEAdvertisement1']))[0]
        assert 'LocalName' not in properties and properties['Includes'].value == ['local-name']
    finally:
        device.disconnect()


def test_ble_without_an_adapter(bus):
    address, bluez = bus
    device = BleMidi(adapter = 'hci7')
    device.bus_address = address
    with pytest.raises(OSError, match = 'no Bluetooth adapter hci7'):
        device.connect()
    assert device._loop is None and not device.connected


# In layouts and the designer

def test_designer_lists_network_and_bluetooth_outputs():
    from pyxelwidgets.designer import catalog
    outputs = {output['type']: output for output in catalog()['outputs']}
    network, bluetooth = outputs['rtp_midi.RtpMidi'], outputs['ble_midi.BleMidi']
    assert [option['name'] for option in network['options']][:4] == ['session', 'port', 'connect', 'announce']
    assert [option['name'] for option in bluetooth['options']][:3] == ['bluetooth_name', 'adapter', 'secure']
    assert 'NoteOn' in network['messages'] and not network['midi'] and not bluetooth['midi']


def test_a_layout_sends_to_the_network_and_the_designer_shows_who_is_connected():
    from pyxelwidgets import codegen, parser
    from pyxelwidgets.designer import Preview
    port = free_port()
    layout = {
        'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 2, 'height': 1},
        'widgets': [{'type': 'Button', 'name': 'kick', 'x': 0, 'y': 0, 'width': 1, 'height': 1, 'options': {}}],
        'outputs': [{'name': 'network', 'type': 'rtp_midi.RtpMidi', 'options': {'session': 'Grid', 'port': port, 'announce': False}}],
        'mappings': [{'widget': 'kick', 'on': 'Pressed', 'output': 'network',
                      'message': {'type': 'NoteOn', 'note': 36, 'velocity': 100, 'channel': 10}}],
    }
    assert f"RtpMidi(name = 'network', session = 'Grid', port = {port}, announce = False)" in codegen.standalone(layout)
    preview = Preview(layout, connect = True)
    computer = RtpMidi(session = 'Computer', port = free_port(), connect = f'127.0.0.1:{port}', announce = False)
    received = []
    computer.on(MessageReceived, lambda e: received.append(e.message))
    computer.connect()
    try:
        assert wait_for(lambda: preview.hardware_status()['outputs'][0].get('text') == 'Grid: Computer')
        preview.input(0, 0, 1.0)
        assert wait_for(lambda: received)
        assert received == [NoteOn(36, 100, 10)]
    finally:
        computer.disconnect()
        preview.close()
    ui = parser.Parser(layout, devices = False)
    assert ui.output_settings()[0]['type'] == 'rtp_midi.RtpMidi'
