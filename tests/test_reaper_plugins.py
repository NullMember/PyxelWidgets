"""
Plug-in parameters through REAPER's OSC (its default pattern), against a
simulated REAPER that behaves like the real one (checked on REAPER 7.79):
banks of 8 tracks and 16 parameters, track selection counting from the
bank's first track, names for empty slots past the last track, only changes
sent, and the plug-in it falls back to without sending its names.
"""

import time

import pytest

from pyxelwidgets import Changed, Knob, MessageReceived, Surface
from pyxelwidgets.devices.osc import REAPER
from pyxelwidgets.message import PluginParameter, Source
from pyxelwidgets import parser

TRACKS = [
    ('Kick', [('ReaEQ', ['Freq', 'Gain', 'Q'])]),
    ('Snare', []),
    ('Bass', [('ReaEQ', ['Freq', 'Gain']), ('ReaComp', [f'P{n}' for n in range(1, 21)])]),
    ('', [('JS: Volume', ['Volume'])]),
    *[(f'Pad {n}', []) for n in range(5, 10)],
    ('Many', [(f'FX {n}', ['Amount']) for n in range(1, 11)]),
    ('Bass', [('ReaXcomp', ['Thresh'])]),
]
MASTER = [('ReaLimit', ['Ceiling', 'Release'])]


class Reaper:
    """REAPER's side of the OSC ports, answering what the device sends."""

    def __init__(self, tracks, master = ()):
        self.tracks = tracks
        self.master = list(master)
        self.first = 1          # the bank's first track
        self.selected = 0       # 0 is the master
        self.fx = 1
        self.parameter_bank = 1
        self.values = {}
        # (track name, 'volume'|'pan'|'mute'|'solo'|'recarm') → value
        self.mixer = {}
        self.sent = {}
        self.device = None

    def connect(self, device):
        self.device = device
        device.client = self
        device.server = self

    # The device's client and server
    def send_message(self, address, args):
        self.handle(address, *args)

    def shutdown(self):
        pass

    def server_close(self):
        pass

    def plugins(self, number):
        return self.master if number == 0 else self.tracks[number - 1][1] if number <= len(self.tracks) else []

    def handle(self, address, value = None):
        count = len(self.tracks)
        if address == '/action' and value == 41743:
            return self.publish(everything = True)
        if address == '/device/track/bank/select':
            if (value - 1) * 8 + 1 <= count:
                self.first = (value - 1) * 8 + 1
        elif address == '/device/track/select':
            if value < 0:
                return
            self.selected = min(count, self.first + value - 1)
            if self.fx > len(self.plugins(self.selected)):
                # It shows the missing plug-in, then goes back to the first without its names
                self.publish()
                self.fx, self.parameter_bank = 1, 1
                return self.publish(skip = '/fxparam/')
        elif address == '/device/fx/select':
            self.fx = value if value <= len(self.plugins(self.selected)) else 1
        elif address == '/device/fxparam/bank/select':
            if (value - 1) * 16 < len(self.parameters(self.fx)):
                self.parameter_bank = value
        elif address.split('/')[-1] in ('volume', 'pan', 'mute', 'solo', 'recarm') and address.count('/') == 2:
            # The selected track's
            self.mixer[(self.track_name(), address.split('/')[-1])] = value
        elif address.startswith('/fx/') and address.endswith('/value'):
            _, _, fx, _, index, _ = address.split('/')
            self.values[(self.track_name(), int(fx), (self.parameter_bank - 1) * 16 + int(index))] = value
        self.publish()

    def track_name(self):
        return 'MASTER' if self.selected == 0 else self.tracks[self.selected - 1][0] or f'Track {self.selected}'

    def parameters(self, fx):
        plugins = self.plugins(self.selected)
        return plugins[fx - 1][1] if fx <= len(plugins) else []

    def view(self) -> dict:
        # Tracks were deleted
        self.selected = min(self.selected, len(self.tracks))
        shown = {'/device/fxparam/bank/str': str(self.parameter_bank)}
        for slot in range(1, 9):
            number = self.first + slot - 1
            exists = number <= len(self.tracks)
            shown[f'/track/{slot}/name'] = (self.tracks[number - 1][0] if exists else '') or f'Track {number}'
            shown[f'/track/{slot}/number/str'] = str(number)
            if exists:
                name = self.tracks[number - 1][0] or f'Track {number}'
                shown[f'/track/{slot}/volume'] = self.mixer.get((name, 'volume'), 0.716)
                shown[f'/track/{slot}/mute'] = self.mixer.get((name, 'mute'), 0)
        plugins = self.plugins(self.selected)
        shown['/track/number/str'] = str(self.selected)
        shown['/track/name'] = self.track_name()
        shown['/track/volume'] = self.mixer.get((self.track_name(), 'volume'), 0.716)
        shown['/master/volume'] = self.mixer.get(('MASTER', 'volume'), 0.716)
        valid = self.fx <= len(plugins)
        shown['/fx/number/str'] = str(self.fx) if valid else ''
        shown['/fx/name'] = plugins[self.fx - 1][0] if valid else ''
        for fx in range(1, 9):
            shown[f'/fx/{fx}/name'] = plugins[fx - 1][0] if fx <= len(plugins) else ''
        first = (self.parameter_bank - 1) * 16
        for slot in range(1, 17):
            names = self.parameters(self.fx)
            shown[f'/fxparam/{slot}/name'] = names[first + slot - 1] if first + slot <= len(names) else ''
            for fx in range(1, len(plugins) + 1):
                if first + slot <= len(self.parameters(fx)):
                    shown[f'/fx/{fx}/fxparam/{slot}/value'] = self.values.get((self.track_name(), fx, first + slot), 0.5)
        return shown

    def publish(self, *, everything = False, skip = None):
        for address, value in self.view().items():
            if (everything or self.sent.get(address) != value) and not (skip and address.startswith(skip)):
                self.sent[address] = value
                self.device._received(address, value)


@pytest.fixture
def reaper(monkeypatch):
    monkeypatch.setattr(REAPER, 'settle', 0.001)
    monkeypatch.setattr(REAPER, 'timeout', 0.01)
    device = REAPER()
    daw = Reaper(TRACKS, MASTER)
    daw.connect(device)
    yield device, daw
    device.close()


def test_scan_tracks(reaper):
    device, daw = reaper
    daw.first, daw.selected = 9, 10
    tracks = device.scan_tracks()
    # Unnamed tracks are numbered, repeated names made unique, empty slots past the last track left out
    assert tracks == ['Kick', 'Snare', 'Bass', 'Track 4', *[f'Pad {n}' for n in range(5, 10)], 'Many', 'Bass (2)', 'MASTER']
    # The device's bank is back where it was
    assert daw.first == 9
    # Tracks are found by name when they move
    assert device.warning == 'Name every track, each differently, so tracks are found when they move: Track 4, Bass'
    daw.tracks = [(name or 'Volume', plugins) for name, plugins in TRACKS[:-1]]
    device.scan_tracks()
    assert device.warning is None


def test_scan_plugins_and_parameters(reaper):
    device, daw = reaper
    device.scan_tracks()
    assert device.scan_plugins('Bass') == ['ReaEQ', 'ReaComp']
    # Past the 8 plug-ins REAPER shows
    assert device.scan_plugins('Many') == [f'FX {n}' for n in range(1, 11)]
    assert device.scan_plugins('MASTER') == ['ReaLimit']
    # Two banks of parameters; it goes back to the first
    assert device.scan_parameters('Bass', 'ReaComp') == [f'P{n}' for n in range(1, 21)]
    assert (daw.selected, daw.fx, daw.parameter_bank) == (3, 2, 1)
    assert device.scanned() == {
        'tracks': device.tracks,
        'plugins': {'Bass': ['ReaEQ', 'ReaComp'], 'Many': [f'FX {n}' for n in range(1, 11)], 'MASTER': ['ReaLimit']},
        'parameters': {'Bass/ReaComp': [f'P{n}' for n in range(1, 21)]},
    }


def test_plugin_reaper_falls_back_to(reaper):
    device, daw = reaper
    # The second plug-in is selected; the next track has one: REAPER would go back to it without its names
    assert device.scan_parameters('Bass', 'ReaComp')[:2] == ['P1', 'P2']
    assert device.scan_parameters('Bass (2)', 'ReaXcomp') == ['Thresh']
    assert device.scan_parameters('Kick', 'ReaEQ') == ['Freq', 'Gain', 'Q']


def test_scans_what_it_needs(reaper):
    device, daw = reaper
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


def test_widget_sets_a_parameter_with_feedback(reaper):
    device, daw = reaper
    surface = Surface(8, 8)
    knob = surface.add(Knob(0, 0, 2, 2))
    surface.map(knob, device, PluginParameter('Bass', 'ReaComp', 'P2', Source('value')), on = Changed, feedback = True)
    knob.set_value(0.25)
    assert wait_for(lambda: daw.values.get(('Bass', 2, 2)) == 0.25)
    # Changed in REAPER: the knob follows
    daw.values[('Bass', 2, 2)] = 0.75
    daw.publish()
    assert knob.value == pytest.approx(0.75)


def test_parameters_past_the_bank_and_tracks_before_it(reaper):
    device, daw = reaper
    received = []
    device.on(MessageReceived, lambda e: isinstance(e.message, PluginParameter) and received.append(e.message))
    device.scan_tracks()
    daw.first = 9
    daw.publish()
    device.send(PluginParameter('Bass', 'ReaComp', 'P20', 0.9))
    assert wait_for(lambda: ('Bass', 2, 20) in daw.values)
    assert daw.values[('Bass', 2, 20)] == pytest.approx(0.9)
    # Selected from the first bank, then back to the device's
    assert (daw.selected, daw.first) == (3, 9)
    device.send(PluginParameter('MASTER', 'ReaLimit', 'Release', 2.0))
    assert wait_for(lambda: ('MASTER', 1, 2) in daw.values)
    assert daw.values[('MASTER', 1, 2)] == 1.0
    assert PluginParameter('MASTER', 'ReaLimit', 'Release', 1.0) in received


def test_unknown_parameter_is_a_warning(reaper):
    device, daw = reaper
    device.send(PluginParameter('Kick', 'ReaEQ', 'Drive', 1.0))
    # The scan's own warning (unnamed tracks) may show first
    assert wait_for(lambda: 'Drive' in (device.warning or ''))
    assert 'Freq' in device.warning


def test_reaper_not_answering(monkeypatch):
    monkeypatch.setattr(REAPER, 'refresh_time', 0.01)
    device = REAPER()
    Reaper(TRACKS).connect(device)
    device.handle = None
    device.client = type('Nowhere', (), {'send_message': lambda self, address, args: None})()
    with pytest.raises(ConnectionError, match = 'does not answer'):
        device.scan_tracks()
    with pytest.raises(ConnectionError, match = 'not connected'):
        REAPER().scan_tracks()


def test_editors_set_the_value():
    assert REAPER.describe()['parameter_value'] == 'value'
    assert 'PluginParameter' in REAPER.describe()['messages']
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 8, 'height': 8},
              'outputs': [{'name': 'reaper', 'type': 'osc.REAPER'}],
              'widgets': [{'type': 'Knob', 'name': 'ratio', 'x': 0, 'y': 0, 'width': 2, 'height': 2}],
              'mappings': [{'widget': 'ratio', 'on': 'Changed', 'output': 'reaper', 'feedback': True,
                            'message': {'type': 'PluginParameter', 'track': 'Bass', 'plugin': 'ReaComp', 'parameter': 'Ratio',
                                        'value': {'source': 'value'}}}]}
    ui = parser.load(layout, devices = False)
    [(_, _, _, message, _)] = ui.mapping_settings()
    assert message.value == Source('value')


def test_moved_tracks_and_plugins_are_found_by_name(reaper):
    device, daw = reaper
    received = []
    device.on(MessageReceived, lambda e: isinstance(e.message, PluginParameter) and received.append(e.message))
    device.send(PluginParameter('Kick', 'ReaEQ', 'Gain', 0.25))
    assert wait_for(lambda: ('Kick', 1, 2) in daw.values)
    # Kick moves after Snare, and gets another plug-in before ReaEQ
    daw.tracks = [TRACKS[1], ('Kick', [('ReaGate', ['Thresh']), *TRACKS[0][1]]), *TRACKS[2:]]
    daw.publish()
    device.send(PluginParameter('Kick', 'ReaEQ', 'Gain', 0.75))
    assert wait_for(lambda: daw.values.get(('Kick', 2, 2)) == 0.75)
    assert ('Snare', 1, 2) not in daw.values and device.warning.startswith('Name every track')
    # Feedback comes from where it is now
    received.clear()
    daw.values[('Kick', 2, 2)] = 0.5
    daw.publish()
    assert received == [PluginParameter('Kick', 'ReaEQ', 'Gain', 0.5)]
    # Gone: it says so
    daw.tracks = TRACKS[1:]
    daw.publish()
    device.send(PluginParameter('Kick', 'ReaEQ', 'Gain', 0.1))
    assert wait_for(lambda: device.warning.startswith('Kick'))
    assert "no track 'Kick'" in device.warning


def test_track_parameters(reaper):
    from pyxelwidgets.message import TrackParameter
    device, daw = reaper
    received = []
    device.on(MessageReceived, lambda e: isinstance(e.message, TrackParameter) and received.append(e.message))
    device.scan_tracks()
    # Many is past the device's bank of 8: selected, then its volume
    device.send(TrackParameter('Many', 'Volume', 0.25))
    assert wait_for(lambda: daw.mixer.get(('Many', 'volume')) == 0.25)
    assert TrackParameter('Many', 'Volume', 0.25) in received
    device.send(TrackParameter('Kick', 'Mute', 1.0))
    device.send(TrackParameter('Kick', 'Pan', 0.3))
    assert wait_for(lambda: daw.mixer.get(('Kick', 'pan')) == 0.3)
    assert daw.mixer[('Kick', 'mute')] == 1
    # Kick is in the bank: its mute comes back from its slot too
    assert TrackParameter('Kick', 'Mute', 1.0) in received
    device.send(TrackParameter('MASTER', 'Volume', 0.5))
    assert wait_for(lambda: daw.mixer.get(('MASTER', 'volume')) == 0.5)
    assert device.warning.startswith('Name every track')
