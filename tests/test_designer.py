import json
import threading
import time
import urllib.error
import urllib.request

import pytest

import pathlib

import pyxelwidgets.color
import pyxelwidgets.designer
from pyxelwidgets import parser
from pyxelwidgets.designer import Preview, catalog, new_layout, serve


@pytest.fixture
def designer(tmp_path):
    server = serve(str(tmp_path / 'layout.json'), port = 0, connect = False, snippets = str(tmp_path / 'snippets'), dialogs = False)
    thread = threading.Thread(target = server.serve_forever, daemon = True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_address[1]}'

    def call(method, path, body = None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(base + path, data = data, method = method, headers = {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def api(method, path, body = None):
        status, raw = call(method, path, body)
        return status, json.loads(raw)

    yield api, call, tmp_path / 'layout.json'
    server.RequestHandlerClass.designer.close()
    server.shutdown()
    server.server_close()


def layout_with(*widgets):
    layout = new_layout(4, 2)
    layout['widgets'] = list(widgets)
    return layout


BUTTON = {'type': 'Button', 'name': 'rec', 'x': 1, 'y': 0, 'width': 1, 'height': 1,
          'options': {'active_color': '#00ff00', 'inactive_color': '#ff0000'}}


def test_catalog(designer):
    api, _, _ = designer
    status, catalog = api('GET', '/api/catalog')
    assert status == 200
    assert 'Fader' in catalog['widgets'] and catalog['colors']['Red'] == '#ff0000'
    devices = {device['type']: device for device in catalog['devices']}
    assert devices['novation.LaunchpadMiniMK3']['grid'] == {'width': 9, 'height': 9}
    assert 'virtual.Virtual' in devices


def test_layout_frame_and_input(designer):
    api, _, _ = designer
    assert api('GET', '/api/layout')[1]['layout']['surface'] == {'width': 9, 'height': 9}
    assert api('PUT', '/api/layout', layout_with(BUTTON)) == (200, {'ok': True, 'layout': layout_with(BUTTON), 'revision': 2})
    frame = api('GET', '/api/frame')[1]
    assert (frame['width'], frame['height']) == (4, 2)
    # Rows from the top: y = 0 is the last row
    assert frame['pixels'][1][1] == '#ff0000' and frame['pixels'][1][0] == '#000000'
    api('POST', '/api/input', {'x': 1, 'y': 0, 'velocity': 1.0})
    frame = api('GET', '/api/frame')[1]
    assert frame['pixels'][1][1] == '#00ff00'
    kinds = [(e['widget'], e['event']) for e in frame['events']]
    assert kinds == [('rec', 'Pressed'), ('rec', 'Changed')]
    assert frame['events'][1]['value'] == 1.0
    since = frame['events'][-1]['id']
    api('POST', '/api/input', {'x': 1, 'y': 0, 'velocity': 0.0})
    assert [e['event'] for e in api('GET', f'/api/frame?since={since}')[1]['events']] == ['Released', 'Changed']



def test_frame_without_pixels(designer):
    """Perform mode asks for frames without pixels; widgets keep updating on the render thread."""
    api, _, _ = designer
    api('PUT', '/api/layout', layout_with(BUTTON))
    api('POST', '/api/input', {'x': 1, 'y': 0, 'velocity': 1.0})
    frame = api('GET', '/api/frame?pixels=0')[1]
    assert frame['pixels'] is None and (frame['width'], frame['height']) == (4, 2)
    assert [e['event'] for e in frame['events']] == ['Pressed', 'Changed']
    assert api('GET', '/api/frame')[1]['pixels'][1][1] == '#00ff00'

def test_invalid_layout_is_rejected_and_previous_kept(designer):
    api, _, _ = designer
    api('PUT', '/api/layout', layout_with(BUTTON))
    status, reply = api('PUT', '/api/layout', layout_with(dict(BUTTON, type = 'Slider')))
    assert status == 400 and 'unknown widget' in reply['error']
    assert api('GET', '/api/layout')[1]['layout']['widgets'][0]['type'] == 'Button'


def test_play_runs_sequencers(designer):
    api, _, _ = designer
    layout = layout_with({'type': 'Sequencer', 'name': 'drums', 'x': 0, 'y': 0, 'width': 4, 'height': 2})
    layout['transport'] = {'bpm': 600, 'signature': [4, 4]}
    api('PUT', '/api/layout', layout)
    api('POST', '/api/play', {'playing': True})
    time.sleep(0.3)
    frame = api('GET', '/api/frame')[1]
    api('POST', '/api/play', {'playing': False})
    assert frame['playing'] and any(e['event'] == 'StepPlayed' for e in frame['events'])
    assert frame['position'].startswith(('1.', '2.'))
    stopped = api('GET', '/api/frame')[1]
    assert not stopped['playing'] and stopped['position'] is None


def test_older_layouts_come_back_upgraded(designer, monkeypatch):
    api, _, _ = designer
    # A future version 2 renaming a widget type: the page gets the upgraded layout
    def to_2(layout):
        for widget in layout['widgets']:
            widget['type'] = 'Button' if widget['type'] == 'OldButton' else widget['type']
    monkeypatch.setattr(parser, 'VERSION', 2)
    monkeypatch.setattr(parser, 'UPGRADES', {1: to_2})
    old = dict(layout_with(dict(BUTTON, type = 'OldButton')), version = 1)
    status, reply = api('PUT', '/api/layout', old)
    assert status == 200 and reply['layout']['version'] == 2 and reply['layout']['widgets'][0]['type'] == 'Button'
    assert api('GET', '/api/layout')[1]['layout'] == reply['layout']


def test_save_writes_file(designer):
    api, _, path = designer
    status, reply = api('POST', '/api/save', layout_with(BUTTON))
    assert status == 200 and reply['ok'] and reply['file'] == str(path.resolve())
    assert json.loads(path.read_text())['widgets'][0]['name'] == 'rec'
    status, reply = api('POST', '/api/save', layout_with(dict(BUTTON, width = 0)))
    assert status == 400 and json.loads(path.read_text())['widgets'][0]['width'] == 1


def test_static_files(designer):
    _, call, _ = designer
    status, body = call('GET', '/')
    assert status == 200 and b'<title>' in body
    assert call('GET', '/app.js')[0] == 200
    assert call('GET', '/../pyproject.toml')[0] == 404


# Hardware mirroring, with fake hardware

import sys
import types

from pyxelwidgets.designer import Preview
from pyxelwidgets.devices import Device


class Hardware(Device):
    grid = (4, 2)
    opened = []

    def connect(self, *ports):
        super().connect()
        self.sent = []
        self.closed = False
        Hardware.opened.append(self)

    def disconnect(self):
        super().disconnect()
        self.closed = True

    def send_pixel(self, x, y, color):
        self.sent.append((x, y, color))


class Missing(Device):
    ports = ('Nowhere',)

    def connect(self, *ports):
        pass

    def send_pixel(self, x, y, color):
        pass


@pytest.fixture
def hardware(monkeypatch):
    module = types.ModuleType('pyxelwidgets.devices.designertest')
    module.Hardware, module.Missing = Hardware, Missing
    monkeypatch.setitem(sys.modules, module.__name__, module)
    Hardware.opened = []
    return Hardware.opened


def with_devices(*devices):
    layout = layout_with(BUTTON)
    layout['devices'] = list(devices)
    return layout


def wait_for(condition, timeout = 1.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_hardware_mirrors_preview_and_works_widgets(hardware):
    preview = Preview(with_devices({'type': 'designertest.Hardware'}))
    assert preview.set_hardware(True)['devices'] == [{'connected': True, 'error': None}]
    [device] = hardware
    # The render thread sends frames without the browser asking
    assert wait_for(lambda: (1, 0, pyxelwidgets.color.Colors.Red) in [(x, y, c) for x, y, c in device.sent])
    device.set_button(1, 0, 1.0)
    assert [e['event'] for _, e in preview.events][:2] == ['Pressed', 'Changed']
    assert preview.frame()['hardware'] == {'devices': [{'connected': True, 'error': None}], 'outputs': []}
    preview.set_hardware(False)
    assert device.closed and preview.frame()['hardware'] == {'devices': [{'connected': False, 'error': None}], 'outputs': []}


def test_hardware_survives_edits(hardware):
    preview = Preview(with_devices({'type': 'designertest.Hardware'}))
    preview.fps = 0.2  # keep the render thread out of the way
    preview.set_hardware(True)
    [device] = hardware
    layout = with_devices({'type': 'designertest.Hardware', 'x': 1})
    layout['widgets'][0]['x'] = 2
    preview.load(layout)
    # Same connection, moved: reused, redrawn in full on the new surface
    assert hardware == [device] and not device.closed
    assert list(preview.ui.surface.devices.values())[-1]['rect'].x == 1
    device.sent.clear()
    preview.frame()
    # Three columns of the surface reach the device; the button is at surface x 2
    assert len(device.sent) == 6 and (1, 0, pyxelwidgets.color.Colors.Red) in device.sent
    # Changed options: a new connection
    preview.load(with_devices({'type': 'designertest.Hardware', 'options': {'held_time': 0.5}}))
    assert device.closed and len(hardware) == 2 and hardware[1].pads.held_time == 0.5
    preview.close()
    assert hardware[1].closed


def test_hardware_reports_devices_it_cannot_connect(hardware):
    preview = Preview(with_devices({'type': 'designertest.Missing'}, {'type': 'virtual.Virtual'}, {'type': 'designertest.Hardware'}))
    missing, virtual, connected = preview.set_hardware(True)['devices']
    assert not missing['connected'] and 'Nowhere' in missing['error']
    assert not virtual['connected'] and 'browser' in virtual['error']
    assert connected == {'connected': True, 'error': None}
    preview.close()


def test_hardware_api(designer, hardware):
    api, _, _ = designer
    api('PUT', '/api/layout', with_devices({'type': 'designertest.Hardware'}))
    assert api('POST', '/api/connect', {'kind': 'devices', 'index': 0, 'connected': True}) == (200, {'ok': True, 'devices': [{'connected': True, 'error': None}], 'outputs': []})
    assert api('GET', '/api/frame')[1]['hardware']['devices'][0]['connected']
    assert api('POST', '/api/connect', {'kind': 'devices', 'index': 0, 'connected': False})[1]['devices'] == [{'connected': False, 'error': None}]
    assert api('POST', '/api/connect', {'kind': 'outputs', 'index': 0, 'connected': True})[0] == 400
    assert hardware[0].closed


def test_hardware_bindings_work_in_preview(hardware):
    from pyxelwidgets.events import ControlChanged, ControlPressed
    layout = with_devices({'type': 'designertest.Hardware'})
    layout['widgets'].append({'type': 'Fader', 'name': 'level', 'x': 0, 'y': 0, 'width': 1, 'height': 2})
    layout['bindings'] = [{'device': 0, 'control': 'Knob1', 'widget': 'level', 'options': {'takeover': 'Jump'}},
                          {'device': 0, 'control': 'Play', 'action': 'transport.toggle'}]
    preview = Preview(layout)
    preview.set_hardware(True)
    device = hardware[0]
    device.emit(ControlChanged(device, 'Knob1', 0.5))
    assert preview.ui['level'].value == 0.5
    device.emit(ControlPressed(device, 'Play', 1.0))
    assert wait_for(lambda: preview.transport is not None)
    # Survives an edit: bound again on the rebuilt surface
    preview.load(layout)
    device.emit(ControlChanged(device, 'Knob1', 1.0))
    assert preview.ui['level'].value == 1.0 and len(preview.ui.surface.bindings) == 2
    preview.close()


def test_preview_logs_messages_and_forwards_feedback(monkeypatch):
    from pyxelwidgets.devices.midi_port import MidiPort
    from pyxelwidgets.message import ControlChange
    layout = new_layout()
    layout['outputs'] = [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets Test'}]
    layout['widgets'] = [{'type': 'Fader', 'name': 'level', 'x': 0, 'y': 0, 'width': 1, 'height': 8}]
    layout['mappings'] = [{'widget': 'level', 'on': 'Changed', 'output': 'synth', 'feedback': True,
                           'message': {'type': 'ControlChange', 'control': 7, 'value': {'source': 'value'}}}]
    preview = Preview(layout)
    # Without hardware: logged only
    preview.input(0, 7, 1.0)
    sent = [e for _, e in preview.events if e['event'] == '→ ControlChange']
    value = round(preview.ui['level'].value * 127)
    assert value > 0 and sent == [{'event': '→ ControlChange', 'widget': 'synth', 'control': 7, 'value': value, 'channel': 1}]
    # With hardware: the real output gets it, and its feedback moves the fader
    connected = []
    def connect_virtual(self, name):
        connected.append(self)
        self.connected = True
    monkeypatch.setattr(MidiPort, 'connect_virtual', connect_virtual)
    monkeypatch.setattr(MidiPort, 'send', lambda self, message: self.sent.append(message) if hasattr(self, 'sent') else setattr(self, 'sent', [message]))
    assert preview.set_hardware(True)['outputs'] == [{'connected': True, 'error': None}]
    [port] = connected
    preview.input(0, 0, 1.0)
    assert port.sent[-1] == ControlChange(7, 0, 1)
    port.decode([0xB0, 7, 127])
    assert preview.ui['level'].value == 1.0
    assert any(e['event'] == '← ControlChange' for _, e in preview.events)
    # Edits keep the connection
    preview.load(layout)
    port.decode([0xB0, 7, 0])
    assert preview.ui['level'].value == 0.0 and connected == [port]
    preview.close()
    assert port.terminated


def test_catalog_lists_outputs_and_messages():
    from pyxelwidgets.designer import catalog
    described = catalog()
    outputs = {output['type']: output for output in described['outputs']}
    assert {'midi_port.MidiPort', 'mackie.MackieControl', 'mackie.HUI', 'osc.OSC', 'osc.REAPER'} <= set(outputs)
    assert outputs['midi_port.MidiPort']['midi'] and not outputs['osc.REAPER']['midi']
    assert 'Play' in [c['name'] for c in outputs['mackie.MackieControl']['commands']]
    assert 'midi_port.MidiPort' not in {device['type'] for device in described['devices']}
    assert 'NoteOn' in described['messages'] and 'velocity' in described['events']['Pressed']['sources']


def test_connect_one_by_one_and_remember_it(hardware):
    preview = Preview(with_devices({'type': 'designertest.Hardware'}, {'type': 'designertest.Hardware', 'x': 3}), connect = True)
    assert [d['connected'] for d in preview.hardware_status()['devices']] == [True, True]
    first, second = hardware
    # Both entries are the same connection: switching one switches both
    preview.set_connected('devices', 0, False)
    assert first.closed and second.closed
    layout = with_devices({'type': 'designertest.Hardware'}, {'type': 'designertest.Hardware', 'x': 3})
    layout['widgets'][0]['x'] = 1
    preview.load(layout)
    # Disconnected by hand: stays so across edits; added devices of another kind connect
    assert [d['connected'] for d in preview.hardware_status()['devices']] == [False, False] and len(hardware) == 2
    preview.set_connected('devices', 1, True)
    assert [d['connected'] for d in preview.hardware_status()['devices']] == [True, True]
    preview.close()
    assert all(device.closed for device in hardware)


def test_widget_state_survives_edits():
    layout = new_layout()
    layout['widgets'] = [{'type': 'Fader', 'name': 'level', 'x': 0, 'y': 0, 'width': 1, 'height': 8},
                         {'type': 'ButtonGroup', 'name': 'mutes', 'x': 1, 'y': 0, 'width': 4, 'height': 1, 'options': {'mode': 'Multi'}},
                         {'type': 'Sequencer', 'name': 'drums', 'x': 0, 'y': 4, 'width': 8, 'height': 2}]
    preview = Preview(layout)
    preview.input(0, 7, 1.0)
    preview.input(0, 7, 0.0)
    preview.input(2, 0, 1.0)
    preview.input(3, 5, 1.0)
    level = preview.ui['level'].value
    assert level > 0
    # Moved, and another widget added: everything keeps its state
    layout['widgets'][0]['x'] = 6
    layout['widgets'].append({'type': 'Button', 'name': 'extra', 'x': 7, 'y': 0, 'width': 1, 'height': 1})
    preview.load(layout)
    assert preview.ui['level'].value == level and preview.ui['mutes'].state[1, 0] and preview.ui['drums'].state[3, 1]
    # Setting the value option in the designer wins
    layout['widgets'][0]['options'] = {'value': 0.25}
    preview.load(layout)
    assert preview.ui['level'].value == 0.25
    # Another type under the same name starts fresh
    layout['widgets'][1]['type'] = 'Fader'
    layout['widgets'][1]['options'] = {}
    preview.load(layout)
    assert preview.ui['mutes'].value == 0.0
    preview.close()


def test_linked_options_survive_edits():
    layout = new_layout()
    layout['widgets'] = [{'type': 'Button', 'name': 'show', 'x': 0, 'y': 8, 'width': 1, 'height': 1, 'options': {'mode': 'Switch'}},
                         {'type': 'Group', 'name': 'panel', 'x': 0, 'y': 0, 'width': 8, 'height': 8, 'options': {'visible': False}},
                         {'type': 'Button', 'name': 'up', 'x': 1, 'y': 8, 'width': 1, 'height': 1},
                         {'type': 'Keyboard', 'name': 'keys', 'x': 0, 'y': 0, 'width': 8, 'height': 4}]
    layout['links'] = [{'widget': 'show', 'on': 'Changed', 'target': 'panel', 'option': 'visible', 'value': {'source': 'value'}},
                       {'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'change': 'Add', 'value': 1}]
    preview = Preview(layout)
    assert 'link' in catalog() and catalog()['widgets']['Group']['linkable'][4]['name'] == 'background'
    preview.input(0, 8, 1.0)
    preview.input(1, 8, 1.0)
    assert preview.ui['panel'].visible and preview.ui['keys'].octave == 1
    # Another widget added: the linked options stay
    layout['widgets'].append({'type': 'Button', 'name': 'extra', 'x': 8, 'y': 0, 'width': 1, 'height': 1})
    preview.load(layout)
    assert preview.ui['panel'].visible and preview.ui['keys'].octave == 1
    # The layout changing the option wins; so does removing the link
    layout['widgets'][3]['options'] = {'octave': 2}
    layout['links'] = layout['links'][1:]
    preview.load(layout)
    assert not preview.ui['panel'].visible and preview.ui['keys'].octave == 2
    preview.close()


def test_preview_runs_own_clocks_and_link_tempo():
    layout = new_layout()
    layout['widgets'] = [{'type': 'Sequencer', 'name': 'own', 'x': 0, 'y': 0, 'width': 8, 'height': 1,
                          'options': {'clock': 'Own', 'bpm': 6000}},
                         {'type': 'Fader', 'name': 'tempo', 'x': 8, 'y': 0, 'width': 1, 'height': 8, 'options': {'mode': 'Magnitude'}}]
    layout['links'] = [{'widget': 'tempo', 'on': 'Changed', 'action': 'transport.tempo', 'value': {'source': 'value'}, 'min': 60, 'max': 180}]
    preview = Preview(layout)
    clock = preview.ui.clocks[0]
    time.sleep(0.2)
    # Its own clock ticks while the transport is stopped (the step itself wraps around)
    assert clock.tick > 0 and clock.playing and preview.transport is None
    old = preview.ui
    preview.load(layout)
    assert old.clocks == [] and len(preview.ui.clocks) == 1
    preview.input(8, 7, 1.0)
    assert preview.bpm == 180 and preview.ui.surface.transport.bpm == 180
    preview.play()
    assert preview.transport.bpm == 180
    # Changing the layout's tempo drops the linked one
    layout['transport'] = {'bpm': 100, 'signature': [4, 4]}
    preview.load(layout)
    assert preview.transport.bpm == 100
    preview.close()
    assert preview.ui.clocks == []


class Pluggable(Device):
    """Hardware that can be unplugged: ``check()`` follows ``Pluggable.present``."""
    ports = ('Pluggable',)
    present = False

    def connect(self, *ports):
        super().connect()
        if not Pluggable.present:
            self.connected, self.lost = False, True

    def check(self, ports = None):
        if self.connected and not Pluggable.present:
            self.connected, self.lost = False, True
            return True
        if self.lost and Pluggable.present:
            self.connected, self.lost = True, False
            return True
        return False

    def send_pixel(self, x, y, color):
        pass


def test_hardware_waits_to_be_plugged_in(hardware, monkeypatch):
    sys.modules['pyxelwidgets.devices.designertest'].Pluggable = Pluggable
    monkeypatch.setattr(Preview, 'check_interval', 0.02)
    Pluggable.present = False
    preview = Preview(with_devices({'type': 'designertest.Pluggable'}), connect = True)
    [status] = preview.hardware_status()['devices']
    assert not status['connected'] and status['error'].startswith('not plugged in')
    Pluggable.present = True
    assert wait_for(lambda: preview.hardware_status()['devices'][0]['connected'])
    Pluggable.present = False
    assert wait_for(lambda: not preview.hardware_status()['devices'][0]['connected'])
    assert wait_for(lambda: any(entry['event'] == 'device unplugged' for _, entry in preview.events))
    preview.close()


def test_web_grid_in_the_designer():
    layout = with_devices({'type': 'web.WebGrid', 'options': {'port': 0, 'host': '127.0.0.1', 'columns': 9, 'rows': 9}})
    assert any(device['type'] == 'web.WebGrid' for device in catalog()['devices'])
    preview = Preview(layout, connect = True)
    [status] = preview.hardware_status()['devices']
    assert status['connected'] and status['url'].startswith('http://127.0.0.1:')
    page = urllib.request.urlopen(status['url']).read()
    assert b'WebSocket' in page
    # Kept across edits: same address
    preview.load(layout)
    assert preview.hardware_status()['devices'][0]['url'] == status['url']
    preview.close()



def test_file_dialogs(tmp_path):
    server = serve(None, port = 0, connect = False, snippets = str(tmp_path / 'snippets'))
    threading.Thread(target = server.serve_forever, daemon = True).start()
    designer = server.RequestHandlerClass.designer
    url = f'http://127.0.0.1:{server.server_address[1]}/api/pick'

    def pick(body):
        request = urllib.request.Request(url, data = json.dumps(body).encode(), method = 'POST', headers = {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())

    try:
        assert designer.pick is pyxelwidgets.designer.dialogs.pick_file
        designer.pick = lambda mode, path: f'{mode}:{path}'
        assert pick({'mode': 'save', 'path': '/a/b.json'}) == {'ok': True, 'path': 'save:/a/b.json'}
        designer.pick = lambda mode, path: None
        assert pick({'mode': 'open'}) == {'ok': True, 'path': None}

        def unavailable(mode, path):
            raise pyxelwidgets.designer.dialogs.Unavailable('No display')
        designer.pick = unavailable
        assert pick({'mode': 'open'}) == {'ok': False, 'unavailable': True, 'error': 'No display'}
        designer.pick = None
        assert pick({'mode': 'open'}) == {'ok': False, 'unavailable': True}
    finally:
        designer.close()
        server.shutdown()
        server.server_close()


def test_open_save_as_and_new(designer, tmp_path):
    api, _, path = designer
    other = tmp_path / 'sets' / 'other'
    status, reply = api('POST', '/api/save', {'layout': layout_with(BUTTON), 'path': str(other)})
    assert status == 200 and reply['file'] == str(other.with_suffix('.json').resolve())
    assert json.loads(other.with_suffix('.json').read_text())['widgets'][0]['name'] == 'rec'
    status, reply = api('POST', '/api/new', {'template': 'drums'})
    assert status == 200 and reply['file'] is None and reply['layout']['widgets'][0]['name'] == 'pads'
    status, reply = api('POST', '/api/open', {'path': str(other.with_suffix('.json'))})
    assert status == 200 and reply['layout']['widgets'][0]['name'] == 'rec'
    status, reply = api('POST', '/api/open', {'path': str(tmp_path / 'missing.json')})
    assert status == 400 and 'No file' in reply['error']
    assert [template['name'] for template in api('GET', '/api/templates')[1]['templates']] == ['drums', 'keyboard', 'mixer', 'performance', 'macros']
    for name in ('drums', 'keyboard', 'mixer', 'performance', 'macros'):
        parser.load(json.loads((pathlib.Path(pyxelwidgets.designer.__file__).parent / 'templates' / f'{name}.json').read_text()), devices = False)


def test_keyboard_and_mouse_wait_for_connect(monkeypatch):
    import pyxelwidgets.devices.desktop

    class Recorder:
        def __getattr__(self, name):
            return lambda *args: None
    monkeypatch.setattr(pyxelwidgets.devices.desktop, '_Pynput', Recorder)
    layout = layout_with(BUTTON)
    layout['outputs'] = [{'name': 'desktop', 'type': 'desktop.Desktop', 'options': {}}]
    preview = Preview(layout, connect = True)
    # Trying pads in the designer would press keys in the browser: only on request
    assert preview.hardware_status()['outputs'] == [{'connected': False, 'error': None}]
    assert preview.set_connected('outputs', 0, True)['outputs'][0]['connected']
    preview.close()


def test_debug_links_write_to_the_event_log():
    layout = layout_with(BUTTON)
    layout['links'] = [{'widget': 'rec', 'on': 'Pressed', 'action': 'debug', 'value': 'rec at {velocity}'}]
    preview = Preview(layout)
    preview.input(1, 0, 0.5)
    entries = [entry for _, entry in preview.events if entry['event'] == 'Debug']
    assert entries == [{'event': 'Debug', 'widget': 'rec', 'text': 'rec at 0.5'}]
    preview.close()


def test_preview_follows_a_daws_clock(monkeypatch):
    from pyxelwidgets.devices.midi_clock import MidiClockInput
    opened = []
    def connect_virtual(self, name):
        opened.append((self, name))
        self.connected = True
    monkeypatch.setattr(MidiClockInput, 'connect_virtual', connect_virtual)
    layout = new_layout()
    layout['transport']['sync'] = {'virtual': 'PyxelWidgets Clock'}
    layout['widgets'] = [{'type': 'Sequencer', 'name': 'beat', 'x': 0, 'y': 0, 'width': 8, 'height': 1, 'options': {'swing': 75.0}}]
    preview = Preview(layout, connect = True)
    [(clock, name)] = opened
    assert name == 'PyxelWidgets Clock' and preview.synced and not preview.playing
    assert preview.hardware_status()['sync'] == {'connected': True, 'error': None}
    # The DAW plays it, not the Play button
    preview.play()
    assert not preview.playing
    clock.decode([0xFA])
    for _ in range(12):
        clock.decode([0xF8])
    assert preview.playing and preview.frame()['playing'] and preview.frame()['synced']
    steps = [e['step'] for _, e in preview.events if e['event'] == 'StepPlayed']
    # Half a beat: steps 0 and 1 (swung, 3/4 of the way through the pair)
    assert steps == [0, 1]
    # An edit keeps the port and where the DAW is
    preview.load(layout)
    assert len(opened) == 1 and preview.playing and clock.transport is preview.transport
    for _ in range(6):
        clock.decode([0xF8])
    steps = [e['step'] for _, e in preview.events if e['event'] == 'StepPlayed']
    assert steps == [0, 1, 2]
    clock.decode([0xFC])
    assert not preview.playing
    # Without sync the port closes and Play works again
    del layout['transport']['sync']
    preview.load(layout)
    assert not preview.synced and 'sync' not in preview.hardware_status() and clock.terminated
    preview.play()
    assert preview.playing
    preview.close()


def test_preview_follows_the_clock_an_output_receives():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1] & ~1
    layout = new_layout()
    layout['outputs'] = [{'name': 'net', 'type': 'rtp_midi.RtpMidi', 'options': {'port': port, 'announce': False}}]
    layout['transport']['sync'] = {'output': 'net'}
    preview = Preview(layout, connect = True)
    try:
        output = preview.outputs[0]['device']
        assert output is not None and preview.synced
        assert preview.hardware_status()['sync'] == {'connected': True, 'error': None}
        for listener in list(output.raw_listeners):
            listener([0xFA])
        assert preview.playing
        # Disconnected: it waits; connected again, it follows the new connection
        preview.set_connected('outputs', 0, False)
        assert preview.hardware_status()['sync']['error'] == "waiting for the output 'net' to connect"
        preview.set_connected('outputs', 0, True)
        output = preview.outputs[0]['device']
        assert preview.sync['input'].source is output and preview.hardware_status()['sync']['connected']
        for listener in list(output.raw_listeners):
            listener([0xFC])
        assert not preview.playing
    finally:
        preview.close()


def test_preview_sync_offline():
    layout = new_layout()
    layout['transport']['sync'] = {'input': 'Nowhere'}
    preview = Preview(layout)
    assert not preview.synced and 'offline' in preview.hardware_status()['sync']['error']
    preview.play()
    assert preview.playing
    preview.close()


# Snippets

def test_built_in_snippets_load_and_cover_the_common_sizes(tmp_path):
    import pyxelwidgets.codegen
    from pyxelwidgets.designer import check_snippet, snippet_layout, snippets
    found = snippets(tmp_path)
    assert len(found) >= 25 and all(entry['builtin'] for entry in found)
    sizes = {tuple(entry['size']) for entry in found}
    assert {(8, 8), (8, 2), (8, 5), (2, 8), (4, 4), (9, 9), (8, 1), (1, 8)} <= sizes
    for entry in found:
        snippet = check_snippet(entry['snippet'])
        assert entry['preview'] is not None and len(entry['preview']) == snippet['size'][1], entry['id']
        assert entry['title'] and entry['doc'] and entry['category']
        # Messages only go to outputs it brings along
        outputs = {output['name'] for output in snippet.get('outputs', [])}
        assert {mapping['output'] for mapping in snippet.get('mappings', [])} <= outputs, entry['id']
        pyxelwidgets.codegen.standalone(snippet_layout(snippet), run = False)


def test_snippets_of_your_own(tmp_path):
    from pyxelwidgets.designer import delete_snippet, save_snippet, snippets
    snippet = {'format': 'pyxelwidgets.snippet', 'title': 'My Pads!', 'size': [2, 2],
               'widgets': [{'type': 'DrumPads', 'name': 'pads', 'x': 0, 'y': 0, 'width': 2, 'height': 2}]}
    assert save_snippet(snippet, tmp_path) == 'user/my-pads'
    own = [entry for entry in snippets(tmp_path) if not entry['builtin']]
    assert [(entry['id'], entry['category'], entry['size']) for entry in own] == [('user/my-pads', 'My snippets', [2, 2])]
    for broken in ({**snippet, 'size': [1, 1]}, {**snippet, 'title': ''}, {**snippet, 'widgets': []},
                   {**snippet, 'widgets': [{'type': 'Nope', 'name': 'x', 'x': 0, 'y': 0, 'width': 1, 'height': 1}]}):
        with pytest.raises(ValueError):
            save_snippet(broken, tmp_path)
    with pytest.raises(ValueError):
        delete_snippet('drum-pads-4x4', tmp_path)
    delete_snippet('user/my-pads', tmp_path)
    assert all(entry['builtin'] for entry in snippets(tmp_path))


def test_snippets_api(designer):
    api, _, path = designer
    status, reply = api('GET', '/api/snippets')
    assert status == 200 and any(entry['id'] == 'mixer-8x8' for entry in reply['snippets'])
    snippet = {'format': 'pyxelwidgets.snippet', 'title': 'Fader', 'size': [1, 8],
               'widgets': [{'type': 'Fader', 'name': 'f', 'x': 0, 'y': 0, 'width': 1, 'height': 8}]}
    status, reply = api('POST', '/api/snippets', {'snippet': snippet})
    assert status == 200 and reply['id'] == 'user/fader'
    assert (path.parent / 'snippets' / 'fader.json').is_file()
    status, reply = api('POST', '/api/snippets', {'snippet': {**snippet, 'size': [1, 2]}})
    assert status == 400 and 'outside' in reply['error']
    status, reply = api('POST', '/api/snippets', {'delete': 'user/fader'})
    assert status == 200 and not any(entry['id'] == 'user/fader' for entry in reply['snippets'])
