"""
The rewritten devices must behave like the old MIDI drivers recorded in
tests/golden/devices.json (see tests/golden/record.py), except for the
deliberate fixes listed per device below.
"""

import importlib
import json
import pathlib
import sys

import pytest
import rtmidi.midiutil

from pyxelwidgets import buffer
from pyxelwidgets.events import (ControlChanged, ControlPressed, ControlReleased, ControlTurned,
                                 Event, PadPressed, PadReleased)

sys.path.insert(0, str(pathlib.Path(__file__).parent / 'golden'))
from frames import frames  # noqa: E402

GOLDEN = json.loads((pathlib.Path(__file__).parent / 'golden' / 'devices.json').read_text())


def spec(module, cls, old_grid, shift = (0, 0), **extra):
    return dict(module = module, cls = cls, old_grid = old_grid, shift = shift, **extra)


def control(event):
    """Old (name, action, value) control callback -> new event description."""
    name, action, value = event
    if action == 'Touched':
        action = 'Pressed'
    if action in ('Increased', 'Decreased'):
        return (name, 'Turned', int(value))
    return (name, action, round(value, 6))


def release_if_zero_velocity(message, event):
    if message[0] & 0xF0 == 0x90 and message[2] == 0:
        if event[0] == 'Pressed':
            return ('Released', event[1], event[2], 0.0)
        if event[1] == 'Pressed':
            return (event[0], 'Released', 0.0)
    return event


def apc40_control(event):
    name, action, value = event
    if action == 'Pressed' and value == 0.0:
        return (name, 'Released', 0.0)
    if action == 'Decreased':
        return (name, 'Turned', -int(value))
    return control(event)


def push2_note_off(message):
    if message[0] & 0xF0 != 0x80:
        return []
    from pyxelwidgets.devices.ableton import Push2
    number = message[1]
    if 36 <= number < 100:
        return [('Released', (number - 36) % 8, (number - 36) // 8, 0.0)]
    if number in Push2.Notes._value2member_map_:
        return [(Push2.Notes(number).name, 'Released', 0.0)]
    return []


NOVATION = 'pyxelwidgets.devices.novation'
SPECS = {
    'LaunchpadMK1': spec(NOVATION, 'LaunchpadMK1', (9, 9)),
    # Fixed: 9x9 grid starts at the bottom left pad instead of a missing LED 0
    'LaunchpadMK2': spec(NOVATION, 'LaunchpadMK2', (9, 9), shift = (1, 1)),
    'LaunchpadX': spec(NOVATION, 'LaunchpadX', (10, 10), shift = (1, 1)),
    'LaunchpadMiniMK3': spec(NOVATION, 'LaunchpadMiniMK3', (10, 10), shift = (1, 1)),
    'LaunchpadProMK3': spec(NOVATION, 'LaunchpadProMK3', (10, 10)),
    'LaunchpadPro': spec(NOVATION, 'LaunchpadPro', (10, 10)),
    'LaunchkeyMK1': spec(NOVATION, 'LaunchkeyMK1', (9, 2), fix_control = control),
    'LaunchkeyMK2': spec(NOVATION, 'LaunchkeyMK2', (8, 2)),
    'LaunchkeyMK3': spec(NOVATION, 'LaunchkeyMK3', (8, 2)),
    'LaunchControl': spec(NOVATION, 'LaunchControl', (8, 16)),
    # Input is only decoded in factory template 8; fixed: knobs and faders reach 1.0 (were / 128)
    'LaunchControlXL': spec(NOVATION, 'LaunchControlXL', (8, 5), golden_input = 'input_factory_template',
                            setup = lambda d: setattr(d, 'current_template', d.Templates.Factory_7),
                            fix_control = lambda e: control(e if e[1] != "Changed" else (e[0], e[1], round(e[2] * 128) / 127))),
    # Fixed: note on with velocity 0 releases (pads and buttons); faders reach 1.0 (were / 128)
    'APCMini': spec('pyxelwidgets.devices.akai', 'APCMini', (8, 8),
                    fix_control = lambda e: control(e if e[1] != 'Changed' else (e[0], e[1], round(e[2] * 128) / 127)),
                    adjust = lambda message, expected: [release_if_zero_velocity(message, event) for event in expected]),
    # Fixed: buttons released with note on velocity 0 sent "pressed 0.0"; Cue/Tempo turn by value - 64
    'APC40MK2': spec('pyxelwidgets.devices.akai', 'APC40MK2', (8, 5), fix_control = apc40_control),
    # Added: note off releases pads and touches (the old driver ignored it)
    'Push2': spec('pyxelwidgets.devices.ableton', 'Push2', (8, 8), extra_input = push2_note_off),
    'ATOM': spec('pyxelwidgets.devices.presonus', 'ATOM', (4, 4)),
}


class Port:
    def __init__(self, log):
        self.log = log

    def send_message(self, message):
        self.log.append([int(b) for b in message])

    def ignore_types(self, **_):
        pass

    def set_callback(self, _):
        pass

    def close_port(self):
        pass


def make(name):
    info = SPECS[name]
    return getattr(importlib.import_module(info['module']), info['cls'])(double_press_time = 0.0, held_time = 1e9)


def connected(name, monkeypatch):
    sent = []
    monkeypatch.setattr(rtmidi.midiutil, 'open_midiinput', lambda port, **_: (Port([]), port))
    monkeypatch.setattr(rtmidi.midiutil, 'open_midioutput', lambda port, **_: (Port(sent), port))
    device = make(name)
    device.connect('in', 'out')
    return device, sent


def drop_unmapped_leds(messages, shift):
    """For shifted grids: drop LED specs the old driver sent to cells left of / below the hardware."""
    if shift == (0, 0):
        return messages
    kept = []
    for message in messages:
        assert message[0] == 0xF0 and message[6] == 3, message
        head, specs = message[:7], message[7:-1]
        body = []
        for i in range(0, len(specs), 5):
            led = specs[i + 1]
            if led % 10 >= shift[0] and led // 10 >= shift[1]:
                body += specs[i:i + 5]
        if body:
            kept.append(head + body + [0xF7])
    return kept


@pytest.mark.parametrize('name', sorted(SPECS))
def test_output_matches_golden(name, monkeypatch):
    golden = GOLDEN[name]['output']
    device, sent = connected(name, monkeypatch)
    assert sent == golden['connect']
    sx, sy = SPECS[name]['shift']
    for old_frame, expected in zip(frames(*SPECS[name]['old_grid']), golden['frames']):
        frame = buffer.new(device.width, device.height)
        for x in range(device.width):
            for y in range(device.height):
                if x + sx < old_frame.shape[0] and y + sy < old_frame.shape[1]:
                    frame[x, y] = old_frame[x + sx, y + sy]
        sent.clear()
        device.show(frame)
        assert sent == drop_unmapped_leds(expected, (sx, sy))
    sent.clear()
    device.disconnect()
    assert sent == golden['disconnect']


def expected_events(name, old_events, device):
    sx, sy = SPECS[name]['shift']
    fix = SPECS[name].get('fix_control', control)
    expected = []
    for event in old_events:
        if event[0] == 'pad':
            _, x, y, velocity = event
            x, y = x - sx, y - sy
            if 0 <= x < device.width and 0 <= y < device.height:
                expected.append(('Pressed' if velocity > 0 else 'Released', x, y, velocity))
        elif event[0] == 'control':
            expected.append(fix(tuple(event[1:])))
    return [event for event in expected if event is not None]


def describe(event):
    if isinstance(event, (PadPressed, PadReleased)):
        return ('Pressed' if isinstance(event, PadPressed) else 'Released', event.x, event.y, round(event.velocity, 6))
    if isinstance(event, ControlPressed):
        return (event.control, 'Pressed', round(event.velocity, 6))
    if isinstance(event, ControlReleased):
        return (event.control, 'Released', round(event.velocity, 6))
    if isinstance(event, ControlChanged):
        return (event.control, 'Changed', round(event.value, 6))
    if isinstance(event, ControlTurned):
        return (event.control, 'Turned', event.delta)
    return ('unexpected', type(event).__name__)


def sweep():
    for status in [0x80, 0x90, 0xB0]:
        for channel in range(16):
            for data1 in range(128):
                for data2 in (0, 1, 63, 64, 65, 127):
                    yield [status | channel, data1, data2]


@pytest.mark.parametrize('name', sorted(SPECS))
def test_input_matches_golden(name):
    golden = GOLDEN[name]['input']
    device = make(name)
    setup = SPECS[name].get('setup')
    if setup:
        setup(device)
        golden = GOLDEN[name][SPECS[name]['golden_input']]
    extra = SPECS[name].get('extra_input', lambda message: [])
    seen = []
    device.on(Event, lambda event: seen.append(describe(event)))
    mismatches = []
    for message in sweep():
        key = ' '.join(f'{b:02X}' for b in message)
        expected = expected_events(name, golden.get(key, []), device)
        expected = SPECS[name].get('adjust', lambda message, events: events)(message, expected) + extra(message)
        seen.clear()
        device.decode(list(message))
        if seen != expected:
            mismatches.append((key, golden.get(key), expected, list(seen)))
    assert not mismatches, f'{len(mismatches)} mismatches, first: {mismatches[:5]}'
