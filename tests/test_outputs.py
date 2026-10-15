import socket
import time

import pytest

from pyxelwidgets import MessageReceived
from pyxelwidgets.devices.mackie import HUI, MackieControl
from pyxelwidgets.devices.midi_port import MidiPort
from pyxelwidgets.message import Command, ControlChange, NoteOn, OscMessage


class Port:
    def __init__(self):
        self.sent = []

    def send_message(self, message):
        self.sent.append(list(message))


def wired(cls, **options):
    device = cls(**options)
    device._midi_output = Port()
    received = []
    device.on(MessageReceived, lambda e: received.append(e.message))
    return device, device._midi_output.sent, received


def test_midi_port():
    port, sent, received = wired(MidiPort)
    port.send(NoteOn(60, 100, 2))
    port.decode([0xB0, 7, 127])
    port.decode([0xF8])
    assert sent == [[0x91, 60, 100]] and received == [ControlChange(7, 127, 1)]


def test_mackie_sends_buttons_faders_and_vpots():
    mackie, sent, _ = wired(MackieControl)
    mackie.send(Command('Play', 1.0))
    mackie.send(Command('Play', 0.0))
    mackie.send(Command('Mute 3', 1.0))
    mackie.send(Command('Fader 2', 1.0))
    mackie.send(Command('Master Fader', 0.0))
    mackie.send(Command('V-Pot 1', 3))
    mackie.send(Command('Jog', -2))
    mackie.send(Command('V-Pot 1', 0))
    mackie.send(Command('Unknown', 1.0))
    assert sent == [[0x90, 0x5E, 0x7F], [0x90, 0x5E, 0x00], [0x90, 0x12, 0x7F], [0xE1, 0x7F, 0x7F], [0xE8, 0, 0],
                    [0xB0, 0x10, 3], [0xB0, 0x3C, 0x42]]


def test_mackie_feedback():
    mackie, _, received = wired(MackieControl)
    mackie.decode([0x90, 0x5E, 0x7F])
    mackie.decode([0x90, 0x5F, 0x01])
    mackie.decode([0xE0, 0x00, 0x40])
    mackie.decode([0xB0, 0x30, 0x46])
    mackie.decode([0xD0, 0x2C])
    assert received == [Command('Play', 1.0), Command('Record', 1.0, True), Command('Fader 1', 8192 / 16383),
                        Command('V-Pot 1', 0.5), Command('Meter 3', 1.0)]


def test_mackie_displays():
    mackie, _, received = wired(MackieControl)
    for i, code in enumerate([0x33, 0x32, 0x31]):
        # "  123" right to left from the last digit; 0x40 adds a dot
        mackie.decode([0xB0, 0x40 + i, code | (0x40 if i == 2 else 0)])
    assert received[-1] == Command('Timecode', '1.23')
    received.clear()
    mackie.decode([0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00] + [ord(c) for c in 'Drums  Bass'] + [0xF7])
    names = {m.name: m.value for m in received}
    assert names['Name 1'] == 'Drums' and names['Name 2'] == 'Bass' and names['Value 1'] == ''
    assert names['Display'].startswith('Drums  Bass')


def test_logic_control_handshake():
    mackie, sent, _ = wired(MackieControl, mode = MackieControl.Mode.LogicControl)
    mackie.decode([0xF0, 0x00, 0x00, 0x66, 0x10, 0x00, 0xF7])
    mackie.decode([0xF0, 0x00, 0x00, 0x66, 0x14, 0x00, 0xF7])   # another model's query
    assert len(sent) == 1 and sent[0][:6] == [0xF0, 0x00, 0x00, 0x66, 0x10, 0x01]


def test_hui():
    hui, sent, received = wired(HUI)
    hui.send(Command('Play', 1.0))
    hui.send(Command('Mute 2', 0.0))
    hui.send(Command('Fader 1', 1.0))
    hui.send(Command('V-Pot 2', -1))
    hui.decode([0x90, 0x00, 0x00])
    assert sent == [[0xB0, 0x0F, 0x0E], [0xB0, 0x2F, 0x44], [0xB0, 0x0F, 0x01], [0xB0, 0x2F, 0x02],
                    [0xB0, 0x0F, 0x00], [0xB0, 0x2F, 0x40], [0xB0, 0x00, 0x7F], [0xB0, 0x20, 0x7F],
                    [0xB0, 0x41, 0x01], [0x90, 0x00, 0x7F]]
    hui.decode([0xB0, 0x0C, 0x0E])
    hui.decode([0xB0, 0x2C, 0x45])
    hui.decode([0xB0, 0x02, 0x40])
    hui.decode([0xB0, 0x22, 0x00])
    hui.decode([0xF0, 0x00, 0x00, 0x66, 0x05, 0x00, 0x10, 0x00] + [ord(c) for c in 'Kick'] + [0xF7])
    assert received == [Command('Record', 1.0), Command('Fader 3', 8192 / 16383), Command('Name 1', 'Kick')]
    received.clear()
    hui.decode([0xB0, 0x18, 0x25])
    hui.decode([0xB0, 0x5A, 0x05])
    assert received == [Command('Param 1', 0.4), ControlChange(0x5A, 0x05, 1)]


def test_hui_touches_faders_while_they_move(monkeypatch):
    monkeypatch.setattr(HUI, 'touch_hold', 0.3)
    hui, sent, _ = wired(HUI)
    touch = lambda strip, on: [[0xB0, 0x0F, strip], [0xB0, 0x2F, (0x40 if on else 0) | 0]]
    for value in (0.25, 0.5, 0.75):
        hui.send(Command('Fader 2', value))
        time.sleep(0.02)
    assert sent[:2] == touch(1, True) and len(sent) == 2 + 3 * 2
    deadline = time.monotonic() + 2.0
    while sent[-2:] != touch(1, False) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert sent[-2:] == touch(1, False)
    # A touch sent as a command stays until a command lets go
    sent.clear()
    hui.send(Command('Fader Touch 3', 1.0))
    hui.send(Command('Fader 3', 0.5))
    time.sleep(0.1)
    assert sent == touch(2, True) + [[0xB0, 0x02, 0x40], [0xB0, 0x22, 0x00]]
    hui.send(Command('Fader Touch 3', 0.0))
    hui.send(Command('Fader 4', 0.0))
    hui.on_disconnect()
    assert sent[-2:] == touch(3, False) and not hui._touched


def test_describe_lists_commands():
    commands = {c['name']: c['kind'] for c in MackieControl.describe()['commands']}
    assert commands['Play'] == 'button' and commands['Fader 8'] == 'fader' and commands['Jog'] == 'relative'
    assert commands['Timecode'] == 'display'
    assert {c['name'] for c in HUI.describe()['commands']} >= {'Play', 'Mute 8', 'V-Pot 1'}


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def test_osc_round_trip():
    pytest.importorskip('pythonosc')
    from pyxelwidgets.devices.osc import OSC, REAPER
    a_port, b_port = free_port(), free_port()
    a = OSC(send_port = b_port, receive_port = a_port)
    b = OSC(send_port = a_port, receive_port = b_port)
    received = []
    b.on(MessageReceived, lambda e: received.append(e.message))
    a.connect()
    b.connect()
    try:
        a.send(OscMessage('/track/1/volume', 0.5))
        deadline = time.monotonic() + 2
        while not received and time.monotonic() < deadline:
            time.sleep(0.01)
        assert received == [OscMessage('/track/1/volume', 0.5)]
    finally:
        a.close()
        b.close()
    assert '/track/{x+1}/volume' in REAPER.describe()['addresses']
