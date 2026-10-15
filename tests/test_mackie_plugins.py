"""
Plug-in parameters through Mackie Control's plug-in mode, against a simulated
DAW: it banks tracks, shows the selected track's plug-ins on the strips after
Plug-in, opens one's parameters on a V-Pot press, pages them with the Bank
buttons, and answers V-Pot turns with the LED ring (like Ableton Live's,
Cubase's or REAPER's CSI/Klinke Mackie support; not REAPER's own).
"""

import threading
import time

import pytest

from pyxelwidgets import Changed, Knob, MessageReceived, Surface
from pyxelwidgets.devices.mackie import _MCU_BUTTONS, _MCU_NOTES, MackieControl
from pyxelwidgets.message import PluginParameter, Source, TrackParameter
from pyxelwidgets import parser

TRACKS = [
    ('Kick', [('ReaEQ', ['Freq', 'Gain', 'Q'])]),
    ('Snare', []),
    ('Bass', [('ReaEQ', ['Freq', 'Gain']), ('ReaComp', [f'P{n}' for n in range(1, 11)])]),
    *[(f'Pad {n}', []) for n in range(1, 8)],
    ('Bass', [('ReaXcomp', ['Thresh'])]),
]


class Daw:
    """The DAW side of the MIDI ports: answers Mackie Control button presses on the display."""

    def __init__(self, tracks, *, plugin_mode = True):
        self.tracks = tracks
        self.plugin_mode = plugin_mode
        self.bank = 0
        self.selected = 0
        self.view = 'channels'
        self.plugin = None
        self.page = 0
        self.values = {}
        self.volumes, self.pans, self.mutes = {}, {}, set()
        self.presses = []
        self.mackie = None

    def connect(self, mackie):
        self.mackie = mackie
        mackie._midi_output = self
        mackie._midi_input = self
        self.show()

    # Closed with the surface's ports
    def close_port(self):
        pass

    def cancel_callback(self):
        pass

    # Received from the surface

    def send_message(self, message):
        status = message[0] & 0xF0
        if status == 0x90 and message[2]:
            self.press(_MCU_NOTES[message[1]])
        elif status == 0xB0 and 0x10 <= message[1] < 0x18:
            steps = message[2] & 0x3F
            strip, steps = message[1] - 0x10, -steps if message[2] & 0x40 else steps
            if self.view == 'channels':
                # Pan
                track = self.bank_start() + strip
                self.pans[track] = min(1.0, max(0.0, self.pans.get(track, 0.5) + steps / 100))
            else:
                self.turn(strip, steps)
        elif status == 0xE0 and (message[0] & 0x0F) < 8:
            # A fader: the track's volume, sent back as the fader's position
            strip = message[0] & 0x0F
            self.volumes[self.bank_start() + strip] = (message[1] | message[2] << 7) / 16383
            self.mackie.decode(list(message))

    def bank_start(self):
        return self.bank

    def press(self, name):
        self.presses.append(name)
        if name.startswith('Mute '):
            track = self.bank_start() + int(name[5:]) - 1
            self.mutes ^= {track}
            self.mackie.decode([0x90, _MCU_BUTTONS[name], 0x7F if track in self.mutes else 0])
        if name in ('Bank Right', 'Bank Left'):
            sign = 1 if name == 'Bank Right' else -1
            if self.view == 'parameters':
                self.page = max(0, min(self.page + sign, (len(self.parameters()) - 1) // 8))
            else:
                self.bank = max(0, min(self.bank + 8 * sign, (len(self.tracks) - 1) // 8 * 8))
                # The bank's faders
                for strip in range(8):
                    if self.bank + strip in self.volumes:
                        position = round(self.volumes[self.bank + strip] * 16383)
                        self.mackie.decode([0xE0 | strip, position & 0x7F, position >> 7])
        elif name.startswith('Select ') and self.view == 'channels':
            self.selected = self.bank + int(name[7:]) - 1
        elif name == 'Plug-in' and self.plugin_mode:
            self.view = 'plugins'
        elif name == 'Pan':
            self.view = 'channels'
        elif name.startswith('V-Select ') and self.view == 'plugins':
            slot = int(name[9:]) - 1
            if slot < len(self.tracks[self.selected][1]):
                self.view, self.plugin, self.page = 'parameters', slot, 0
        self.show()

    def parameters(self):
        return self.tracks[self.selected][1][self.plugin][1]

    def turn(self, strip, steps):
        if self.view != 'parameters':
            return
        index = self.page * 8 + strip
        key = (self.selected, self.plugin, index)
        self.values[key] = min(1.0, max(0.0, self.values.get(key, 0.0) + steps / 100))
        # The LED ring: 1-11
        self.mackie.decode([0xB0, 0x30 + strip, 1 + round(self.values[key] * 10)])

    # Sent to the surface

    def show(self):
        if self.view == 'channels':
            top = [name[:6] for name, _ in self.tracks[self.bank:self.bank + 8]]
            bottom = []
        elif self.view == 'plugins':
            top = [name for name, _ in self.tracks[self.selected][1]]
            bottom = []
        else:
            names = self.parameters()[self.page * 8:self.page * 8 + 8]
            top = names
            bottom = [f'{self.values.get((self.selected, self.plugin, self.page * 8 + i), 0.0):.2f}' for i in range(len(names))]
        text = ''.join(name.ljust(7)[:7] for name in (top + [''] * 8)[:8]) + ''.join(value.ljust(7) for value in (bottom + [''] * 8)[:8])
        self.mackie.decode([0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00, *[ord(c) for c in text], 0xF7])


@pytest.fixture
def mackie(monkeypatch):
    monkeypatch.setattr(MackieControl, 'settle', 0.005)
    monkeypatch.setattr(MackieControl, 'timeout', 0.03)
    device = MackieControl()
    daw = Daw(TRACKS)
    daw.connect(device)
    yield device, daw
    device.close()


def test_scan_tracks(mackie):
    device, daw = mackie
    daw.bank = 8
    tracks = device.scan_tracks()
    # 6 characters as the DAW shows them, repeated names made unique
    assert tracks == ['Kick', 'Snare', 'Bass', *[f'Pad {n}' for n in range(1, 8)], 'Bass (2)']
    assert device.tracks == tracks


def test_scan_plugins_and_parameters(mackie):
    device, daw = mackie
    device.scan_tracks()
    assert device.scan_plugins('Bass') == ['ReaEQ', 'ReaComp']
    assert daw.selected == 2 and daw.view == 'plugins'
    # Names are cut to the display's 7 characters
    assert device.scan_plugins('Bass (2)') == ['ReaXcom']
    assert daw.selected == 10
    # Two pages of parameters; it goes back to the first
    assert device.scan_parameters('Bass', 'ReaComp') == [f'P{n}' for n in range(1, 11)]
    assert (daw.selected, daw.view, daw.plugin, daw.page) == (2, 'parameters', 1, 0)
    assert device.scanned() == {
        'tracks': device.tracks,
        'plugins': {'Bass': ['ReaEQ', 'ReaComp'], 'Bass (2)': ['ReaXcom']},
        'parameters': {'Bass/ReaComp': [f'P{n}' for n in range(1, 11)]},
    }


def test_scans_what_it_needs(mackie):
    device, daw = mackie
    # Without scanning tracks or plug-ins first
    assert device.scan_parameters('Kick', 'ReaEQ') == ['Freq', 'Gain', 'Q']
    with pytest.raises(LookupError, match = 'no track'):
        device.scan_plugins('Vocals')
    with pytest.raises(LookupError, match = 'no plug-in'):
        device.scan_parameters('Snare', 'ReaEQ')


def wait_for(condition, seconds = 3.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_widget_turns_a_parameter_with_feedback(mackie):
    device, daw = mackie
    surface = Surface(8, 8)
    knob = surface.add(Knob(0, 0, 2, 2))
    surface.map(knob, device, PluginParameter('Bass', 'ReaComp', 'P10', Source('delta')), on = Changed, feedback = True)
    knob.set_value(0.5)
    # It goes to the track, the plug-in and the page, then turns the V-Pot (64 steps of 1/127)
    assert wait_for(lambda: (2, 1, 9) in daw.values)
    assert (daw.selected, daw.view, daw.plugin, daw.page) == (2, 'parameters', 1, 1)
    assert daw.values[(2, 1, 9)] == pytest.approx(0.64)
    # The ring came back: the knob shows the DAW's position (11 steps)
    assert knob.value == pytest.approx(0.6)
    # The next turn needs no navigation
    presses = len(daw.presses)
    knob.set_value(0.4)
    assert wait_for(lambda: daw.values[(2, 1, 9)] < 0.6)
    assert len(daw.presses) == presses and device.warning is None


def test_turns_on_another_page_and_plugin(mackie):
    device, daw = mackie
    received = []
    device.on(MessageReceived, lambda e: isinstance(e.message, PluginParameter) and received.append(e.message))
    device.send(PluginParameter('Kick', 'ReaEQ', 'Gain', 10))
    assert wait_for(lambda: (0, 0, 1) in daw.values)
    device.send(PluginParameter('Bass', 'ReaComp', 'P2', -3))
    device.send(PluginParameter('Bass', 'ReaComp', 'P2', 10))
    assert wait_for(lambda: (2, 1, 1) in daw.values)
    assert received[0] == PluginParameter('Kick', 'ReaEQ', 'Gain', 0.1)


def test_moved_plugins_are_found_by_name(mackie):
    device, daw = mackie
    daw.tracks = list(TRACKS)
    device.send(PluginParameter('Bass', 'ReaComp', 'P2', 5))
    assert wait_for(lambda: (2, 1, 1) in daw.values)
    # Another view, then a plug-in goes before ReaComp in the DAW
    device.scan_plugins('Kick')
    name, plugins = daw.tracks[2]
    daw.tracks[2] = (name, [('Gate', ['Thresh']), *plugins])
    device.send(PluginParameter('Bass', 'ReaComp', 'P2', 5))
    assert wait_for(lambda: (2, 2, 1) in daw.values)
    assert (2, 1, 1) not in daw.values or daw.values[(2, 1, 1)] == 0.05
    assert device.scanned()['plugins']['Bass'] == ['Gate', 'ReaEQ', 'ReaComp'] and device.warning is None
    # Removed: it says so
    daw.tracks[2] = (name, [('Gate', ['Thresh'])])
    device.scan_plugins('Kick')
    device.send(PluginParameter('Bass', 'ReaComp', 'P2', 5))
    assert wait_for(lambda: device.warning is not None)
    assert "no plug-in 'ReaComp'" in device.warning


def test_track_parameters(mackie):
    device, daw = mackie
    received = []
    device.on(MessageReceived, lambda e: isinstance(e.message, TrackParameter) and received.append(e.message))
    # Pad 7 is on the second bank: shown there, its strip's fader moves
    device.send(TrackParameter('Pad 7', 'Volume', 0.25))
    assert wait_for(lambda: 9 in daw.volumes)
    assert daw.volumes[9] == pytest.approx(0.25, abs = 1e-3) and daw.bank == 8
    assert TrackParameter('Pad 7', 'Volume', pytest.approx(0.25, abs = 1e-3)) in received
    # Mute switches: pressed only when the LED says otherwise
    device.send(TrackParameter('Kick', 'Mute', 1.0))
    assert wait_for(lambda: 0 in daw.mutes)
    device.send(TrackParameter('Kick', 'Mute', 1.0))
    time.sleep(0.1)
    assert daw.presses.count('Mute 1') == 1 and TrackParameter('Kick', 'Mute', 1.0) in received
    device.send(TrackParameter('Kick', 'Mute', 0.0))
    assert wait_for(lambda: 0 not in daw.mutes)
    # Pan: V-Pot steps in the Pan view
    device.send(TrackParameter('Bass (2)', 'Pan', 10))
    assert wait_for(lambda: 10 in daw.pans)
    assert daw.pans[10] == pytest.approx(0.6) and device.warning is None
    # The faders the DAW sends when a bank shows are its tracks' volumes
    daw.volumes[10] = 0.75
    device.send(TrackParameter('Kick', 'Volume', 0.5))
    assert wait_for(lambda: 0 in daw.volumes)
    received.clear()
    device.send(TrackParameter('Pad 7', 'Mute', 1.0))
    assert wait_for(lambda: TrackParameter('Bass (2)', 'Volume', pytest.approx(0.75, abs = 1e-3)) in received)
    # Plug-ins and tracks take turns
    device.send(PluginParameter('Bass', 'ReaComp', 'P2', 5))
    assert wait_for(lambda: (2, 1, 1) in daw.values)
    device.send(TrackParameter('Snare', 'Volume', 0.5))
    assert wait_for(lambda: 1 in daw.volumes)
    with pytest.raises(ValueError, match = 'parameter must be one of'):
        TrackParameter('Kick', 'Width')


def test_tracks_moved_before_a_turn(mackie):
    device, daw = mackie
    daw.tracks = list(TRACKS)
    device.send(PluginParameter('Bass', 'ReaComp', 'P2', 5))
    assert wait_for(lambda: (2, 1, 1) in daw.values)
    device.scan_plugins('Kick')
    # A track goes before Bass: the tracks are scanned again on the way, the plug-in scans stay
    daw.tracks.insert(0, ('Vocals', []))
    device.send(PluginParameter('Bass', 'ReaComp', 'P2', 5))
    assert wait_for(lambda: (3, 1, 1) in daw.values), device.warning
    assert device.warning is None and device.tracks[0] == 'Vocals'


def test_unknown_parameter_is_a_warning(mackie):
    device, daw = mackie
    device.send(PluginParameter('Kick', 'ReaEQ', 'Drive', 1))
    assert wait_for(lambda: device.warning is not None)
    assert 'Drive' in device.warning and 'Freq' in device.warning


def test_daw_without_plugin_mode(monkeypatch):
    # REAPER's own Mackie Control support ignores Plug-in
    monkeypatch.setattr(MackieControl, 'settle', 0.005)
    monkeypatch.setattr(MackieControl, 'timeout', 0.03)
    device = MackieControl()
    Daw(TRACKS, plugin_mode = False).connect(device)
    assert device.scan_tracks()[:2] == ['Kick', 'Snare']
    with pytest.raises(LookupError, match = 'no plug-in mode'):
        device.scan_plugins('Kick')


def test_needs_a_connection():
    with pytest.raises(ConnectionError):
        MackieControl().scan_tracks()


def test_options():
    with pytest.raises(ValueError, match = 'not a Mackie Control button'):
        MackieControl(plugin_button = 'Plugin')
    device = MackieControl(next_page = 'Channel Right')
    assert device.next_page == 'Channel Right'


def test_layouts():
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 8, 'height': 8},
              'outputs': [{'name': 'daw', 'type': 'mackie.MackieControl', 'virtual': 'MCU'}],
              'widgets': [{'type': 'Knob', 'name': 'ratio', 'x': 0, 'y': 0, 'width': 2, 'height': 2}],
              'mappings': [{'widget': 'ratio', 'on': 'Changed', 'output': 'daw', 'feedback': True,
                            'message': {'type': 'PluginParameter', 'track': 'Bass', 'plugin': 'ReaComp', 'parameter': 'Ratio',
                                        'value': {'source': 'delta'}}}]}
    ui = parser.load(layout, devices = False)
    [(_, _, _, message, _)] = ui.mapping_settings()
    assert message == PluginParameter('Bass', 'ReaComp', 'Ratio')
    assert parser.message_to_json(message)['parameter'] == 'Ratio'
    fields = {field['name']: field for field in parser.message_schema()['PluginParameter']['fields']}
    assert fields['track']['kind'] == 'scan' and fields['value']['default'] == {'source': 'delta'}
    # A plain MIDI port has no plug-in mode
    layout['outputs'][0]['type'] = 'midi_port.MidiPort'
    with pytest.raises(parser.LayoutError, match = 'PluginParameter'):
        parser.load(layout, devices = False)


def test_python_code():
    from pyxelwidgets import codegen
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 8, 'height': 8},
              'outputs': [{'name': 'daw', 'type': 'mackie.MackieControl', 'virtual': 'MCU'}],
              'widgets': [{'type': 'Knob', 'name': 'ratio', 'x': 0, 'y': 0, 'width': 2, 'height': 2}],
              'mappings': [{'widget': 'ratio', 'on': 'Changed', 'output': 'daw',
                            'message': {'type': 'PluginParameter', 'track': 'Bass', 'plugin': 'ReaComp', 'parameter': 'Ratio'}}]}
    code = codegen.standalone(layout)
    assert "ratio, daw, PluginParameter(track = 'Bass', plugin = 'ReaComp', parameter = 'Ratio')," in code
    assert 'from pyxelwidgets.message import PluginParameter' in code


class Logic(Daw):
    """
    Logic Pro's Mackie Control, as tried on Logic Pro (2026-10): assignment
    buttons switch between the tracks view and a one-track view (a dot on the
    assignment display); Plug-in first shows one insert slot of every track, again
    the selected track's plug-ins (names on the bottom line); the cursor buttons
    page parameters, the last page ending at the last parameter; passing messages
    ("Page 2/12") cover the right of the top line for a while.
    """

    message_time = 0.05

    def __init__(self, tracks):
        super().__init__(tracks)
        self.one_track = False
        self.message = None
        self.timer = None
        self.pages = {}

    def press(self, name):
        self.presses.append(name)
        message = None
        if name == 'Pan':
            self.one_track = not self.one_track if self.view == 'channels' else False
            self.view = 'channels'
            message = 'Pan/Surround parameter: Pan'
        elif name.startswith('Select ') and self.view == 'channels' and not self.one_track:
            self.selected = self.bank + int(name[7:]) - 1
        elif name == 'Plug-in':
            if self.view == 'mixer':
                self.view, self.one_track = 'plugins', True
            else:
                self.view, self.one_track = 'mixer', False
        elif name.startswith('V-Select ') and self.view == 'plugins':
            slot = int(name[9:]) - 1
            if slot < len(self.tracks[self.selected][1]):
                # It opens on the page shown last
                self.pages[(self.selected, self.plugin)] = self.page
                self.view, self.plugin = 'parameters', slot
                self.page = self.pages.get((self.selected, slot), 0)
        elif name in ('Right', 'Left') and self.view == 'parameters':
            pages = (len(self.parameters()) + 7) // 8
            self.page = max(0, min(self.page + (1 if name == 'Right' else -1), pages - 1))
            message = f'Page {self.page + 1}/{pages}'
        self.show(message)

    def lines(self):
        if self.view == 'channels' and self.one_track:
            return ['Pan'] + ['-'] * 7, ['0']
        if self.view == 'channels':
            return [name[:6] for name, _ in self.tracks[self.bank:self.bank + 8]], []
        if self.view == 'mixer':
            return [name[:6] for name, _ in self.tracks[self.bank:self.bank + 8]], [
                (plugins[0][0][:6] if plugins else '--') for _, plugins in self.tracks[self.bank:self.bank + 8]]
        if self.view == 'plugins':
            plugins = self.tracks[self.selected][1]
            return [f'Ins{n}Pl' for n in range(1, 9)], [(plugins[n][0][:6] if n < len(plugins) else '--') for n in range(8)]
        names = self.parameters()
        start = min(self.page * 8, max(0, len(names) - 8))
        return names[start:start + 8], [f'{self.values.get((self.selected, self.plugin, start + i), 0.0):.2f}' for i in range(len(names[start:start + 8]))]

    def text(self, message = None):
        top, bottom = self.lines()
        text = ''.join(name.ljust(7)[:7] for name in (top + [''] * 8)[:8])
        if message:
            text = text[:56 - len(message) - 1] + message + ' '
        return text + ''.join(value.ljust(7)[:7] for value in (bottom + [''] * 8)[:8])

    def show(self, message = None):
        if self.mackie is None:
            return
        letters = {'channels': 'PN', 'mixer': 'P1', 'plugins': 'PL', 'parameters': f'P{(self.plugin or 0) + 1}'}[self.view]
        dot = 0x40 if self.one_track or self.view == 'parameters' else 0
        self.mackie.decode([0xB0, 0x4B, ord(letters[0]) - 0x40])
        self.mackie.decode([0xB0, 0x4A, (ord(letters[1]) if letters[1].isdigit() else ord(letters[1]) - 0x40) | dot])
        if message and self.message:
            # A message still showing: one write with the new one in it
            self.write(self.text(message))
        elif message:
            self.write(self.text())
            self.write(self.text(message))
        else:
            self.write(self.text())
        if message:
            self.message = message
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.message_time, self.clear)
            self.timer.start()

    def clear(self):
        self.message = None
        self.write(self.text())

    def turn(self, strip, steps):
        if self.view != 'parameters':
            return
        # The last page ends at the last parameter
        index = min(self.page * 8, max(0, len(self.parameters()) - 8)) + strip
        key = (self.selected, self.plugin, index)
        self.values[key] = min(1.0, max(0.0, self.values.get(key, 0.0) + steps / 100))
        self.mackie.decode([0xB0, 0x30 + strip, 1 + round(self.values[key] * 10)])

    def write(self, text):
        self.mackie.decode([0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, 0x00, *[ord(c) for c in text], 0xF7])


def test_logic(monkeypatch):
    monkeypatch.setattr(MackieControl, 'settle', 0.005)
    monkeypatch.setattr(MackieControl, 'timeout', 0.03)
    monkeypatch.setattr(MackieControl, 'message_time', 0.3)
    tracks = [('Audio1', []), ('asd', [('Channel EQ', [f'EQ{n}' for n in range(1, 12)]), ('Pro-Q4', ['Gain']),
                                       ('Pro-C3', [f'C{n}' for n in range(1, 21)])])]
    device = MackieControl()
    daw = Logic(tracks)
    daw.one_track = True        # left in a one-track view
    daw.pages[(1, 2)] = 2       # and Pro-C3 on its last page
    daw.connect(device)
    assert device.scan_tracks() == ['Audio1', 'asd']
    assert device.scan_plugins('asd') == ['Channe', 'Pro-Q4', 'Pro-C3']
    # 20 parameters: pages 1-8, 9-16 and 13-20 (the last ends at the last one); every name once
    assert device.scan_parameters('asd', 'Pro-C3') == [f'C{n}' for n in range(1, 21)]
    assert 'Right' in daw.presses and daw.page == 0
    device.send(PluginParameter('asd', 'Pro-C3', 'C20', 10))
    assert wait_for(lambda: (1, 2, 19) in daw.values)
    assert daw.values[(1, 2, 19)] == pytest.approx(0.1) and device.warning is None
    # Audio1 clicked in Logic: its Select lights (asd's goes out), Logic shows its plug-ins, the rings go to 0
    received = []
    device.on(MessageReceived, lambda e: isinstance(e.message, PluginParameter) and received.append(e.message))
    daw.selected, daw.view = 0, 'plugins'
    device.decode([0x90, _MCU_BUTTONS['Select 1'], 0x7F])
    device.decode([0x90, _MCU_BUTTONS['Select 2'], 0x00])
    for strip in range(8):
        device.decode([0xB0, 0x30 + strip, 0])
    assert received == []
    # The next turn goes back to asd's Pro-C3
    device.send(PluginParameter('asd', 'Pro-C3', 'C20', 10))
    assert wait_for(lambda: daw.values[(1, 2, 19)] == pytest.approx(0.2))
    assert daw.selected == 1 and device.warning is None
    device.close()


class Cubase(Daw):
    """
    Cubase's Mackie Control, as tried on Cubase 15 (2026-10): the channels view
    has a header on top and track names on the bottom line, its last bank ends
    at the last track; Plug-in shows the selected track's insert slots one at a
    time (V-Pot 1 picks the slot, " IFX 2    On         Pro-C 3"), Channel
    Left/Right page from the slot's page to its parameters (names cut to the 7
    characters of a strip, often the same); a page counter on the bottom line;
    V-Pot rings sent when a page is shown, not when turned; it draws only what
    changed.
    """

    def __init__(self, tracks):
        super().__init__(tracks)
        self.slot = 0
        self.lcd = ' ' * 112

    def bank_start(self):
        return max(0, min(self.bank, len(self.tracks) - 8))

    def press(self, name):
        self.presses.append(name)
        if name in ('Pan', 'Send'):
            self.view = 'channels' if name == 'Pan' else 'sends'
        elif name in ('Bank Right', 'Bank Left') and self.view in ('channels', 'sends'):
            sign = 1 if name == 'Bank Right' else -1
            self.bank = max(0, min(self.bank_start() + 8 * sign, len(self.tracks) - 8))
            for strip in range(8):
                if self.bank_start() + strip in self.volumes:
                    position = round(self.volumes[self.bank_start() + strip] * 16383)
                    self.mackie.decode([0xE0 | strip, position & 0x7F, position >> 7])
        elif name.startswith('Select ') and self.view in ('channels', 'sends'):
            self.selected = self.bank_start() + int(name[7:]) - 1
        elif name.startswith('Fader Touch '):
            # Touching a fader selects its track: the plug-in view shows that track's (rings first)
            self.selected = self.bank_start() + int(name[12:]) - 1
            if self.view == 'parameters':
                if self.plugin_at() is None:
                    self.view, self.page = 'plugins', 0
                else:
                    self.rings()
        elif name == 'Plug-in':
            self.view = 'parameters' if self.view == 'parameters' else 'plugins'
        elif name in ('Channel Right', 'Channel Left') and self.view in ('plugins', 'parameters'):
            page = (self.page + 1 if self.view == 'parameters' else 0) + (1 if name == 'Channel Right' else -1)
            plugin = self.plugin_at()
            pages = (len(plugin[1]) + 7) // 8 if plugin else 0
            page = max(0, min(page, pages))
            self.view, self.page = ('plugins', 0) if page == 0 else ('parameters', page - 1)
            self.plugin = self.slot
            if self.view == 'parameters':
                self.rings()
        self.show()

    def rings(self):
        for strip in range(8):
            key = (self.selected, self.plugin, self.page * 8 + strip)
            self.mackie.decode([0xB0, 0x30 + strip, 0x20 | (1 + round(self.values.get(key, 0.0) * 10))])

    def plugin_at(self):
        plugins = self.tracks[self.selected][1]
        return plugins[self.slot] if self.slot < len(plugins) else None

    def turn(self, strip, steps):
        if self.view == 'plugins' and strip == 0:
            # 16 slots, then the user page
            self.slot = max(0, min(self.slot + steps, 16))
            return self.show()
        if self.view != 'parameters':
            return
        key = (self.selected, self.plugin, self.page * 8 + strip)
        self.values[key] = min(1.0, max(0.0, self.values.get(key, 0.0) + steps / 100))

    def show(self):
        if self.mackie is None:
            return
        name = self.tracks[self.selected][0]
        if self.view in ('channels', 'sends'):
            top = 'Pan             Left-Right                   Page:01/02' if self.view == 'channels' else ' Level' * 8
            bottom = ''.join(name[:6].ljust(7) for name, _ in self.tracks[self.bank_start():self.bank_start() + 8])
        elif self.view == 'plugins':
            plugin = self.plugin_at()
            pages = (len(plugin[1]) + 7) // 8 + 1 if plugin else 1
            top = '  User' if self.slot == 16 else f' IFX {self.slot + 1}    On         {plugin[0]}' if plugin \
                else f' IFX {self.slot + 1}              No Effect'
            bottom = f'Inserts         {name.ljust(29)}Page:01/{pages:02}'
        else:
            plugin = self.plugin_at()
            names = plugin[1][self.page * 8:self.page * 8 + 8]
            top = ''.join(name.ljust(7)[:7] for name in names)
            bottom = f'{plugin[0][:16].ljust(16)}{name.ljust(29)}Page:{self.page + 2:02}/{(len(plugin[1]) + 7) // 8 + 1:02}'
        text = top.ljust(56)[:56] + bottom.ljust(56)[:56]
        # Only the characters that changed, from the first one
        changed = [i for i in range(112) if text[i] != self.lcd[i]]
        if changed:
            start, end = changed[0], changed[-1] + 1
            self.mackie.decode([0xF0, 0x00, 0x00, 0x66, 0x14, 0x12, start, *[ord(c) for c in text[start:end]], 0xF7])
        self.lcd = text


def test_cubase(monkeypatch):
    monkeypatch.setattr(MackieControl, 'settle', 0.005)
    monkeypatch.setattr(MackieControl, 'timeout', 0.03)
    names = ['GainScale', 'Output Level', 'Ratio'] + [f'Side Chain {n}' for n in range(1, 15)]
    # As Cubase shortens "Audio 01"
    tracks = [(f'Audi{n:02}', []) for n in range(1, 21)]
    tracks[0] = ('Audi01', [('Pro-Q 4', ['Band 1 Gain']), ('Pro-C 3', names)])
    tracks[11] = ('Audi12', [('Pro-R 2', ['Decay'])])
    tracks[18] = ('Audi19', [('Pro-L 2', ['Gain'])])
    device = MackieControl()
    daw = Cubase(tracks)
    daw.view = 'plugins'
    daw.volumes[12] = 0.25
    daw.connect(device)
    received = []
    device.on(MessageReceived, lambda e: isinstance(e.message, (PluginParameter, TrackParameter)) and received.append(e.message))
    # Names on the bottom line; the last bank (13-20) repeats 13-16 of the one before
    assert device.scan_tracks() == [f'Audi{n:02}' for n in range(1, 21)] and device._cubase
    assert device.scan_plugins('Audi01') == ['Pro-Q 4', 'Pro-C 3']
    assert device.scan_plugins('Audi12') == ['Pro-R 2']
    # In the last bank, which starts at 13: Audi19 is its 7th strip
    assert device.scan_plugins('Audi19') == ['Pro-L 2'] and daw.selected == 18
    received.clear()
    device.send(TrackParameter('Audi19', 'Volume', 0.5))
    assert wait_for(lambda: 18 in daw.volumes)
    # Audi13 shows again on the last bank's first strip: its fader is its volume
    assert TrackParameter('Audi13', 'Volume', pytest.approx(0.25, abs = 1e-3)) in received
    # 3 pages of names filling the strips, the same names on pages 2 and 3
    labels = device.scan_parameters('Audi01', 'Pro-C 3')
    assert labels[:4] == ['GainSca', 'Output', 'Ratio', 'Side Ch'] and labels[-1] == 'Side Ch (14)' and len(labels) == 17
    assert (daw.view, daw.page) == ('parameters', 0)
    # The first page's rings, once its display settled, came back as positions
    assert wait_for(lambda: PluginParameter('Audi01', 'Pro-C 3', 'Ratio', 0.0) in received)
    # A turn on the last page
    device.send(PluginParameter('Audi01', 'Pro-C 3', 'Side Ch (14)', 10))
    assert wait_for(lambda: (0, 1, 16) in daw.values)
    assert daw.values[(0, 1, 16)] == pytest.approx(0.1) and device.warning is None
    # Touching Audi02's fader in Cubase selects it: its Pro-C 3 shows, and its rings aren't Audi01's
    daw.tracks[1] = ('Audi02', [('Pro-Q 4', ['Band 1 Gain']), ('Pro-C 3', names)])
    daw.values[(1, 1, 16)] = 1.0
    received.clear()
    daw.press('Fader Touch 2')
    time.sleep(0.05)
    assert received == []
    device.send(PluginParameter('Audi01', 'Pro-C 3', 'Side Ch (14)', 10))
    assert wait_for(lambda: daw.values[(0, 1, 16)] == pytest.approx(0.2))
    assert daw.values[(1, 1, 16)] == 1.0 and daw.selected == 0
    # Another track's plug-in: back to its slot's page, then the slot
    device.send(PluginParameter('Audi12', 'Pro-R 2', 'Decay', -3))
    device.send(PluginParameter('Audi12', 'Pro-R 2', 'Decay', 5))
    assert wait_for(lambda: (11, 0, 0) in daw.values)
    assert daw.values[(11, 0, 0)] == pytest.approx(0.02)
    # A plug-in added before Pro-C 3: found in its new slot
    daw.tracks[0] = ('Audi01', [('Pro-Q 4', ['Band 1 Gain']), ('Pro-G', ['Thresh']), ('Pro-C 3', names)])
    device.send(PluginParameter('Audi01', 'Pro-C 3', 'Ratio', 4))
    assert wait_for(lambda: (0, 2, 2) in daw.values)
    assert device.scanned()['plugins']['Audi01'] == ['Pro-Q 4', 'Pro-G', 'Pro-C 3']
    device.close()
