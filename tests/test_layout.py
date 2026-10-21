import json
import sys
import types

import pytest

from pyxelwidgets import Changed, Colors, ControlReleased, Fader, Group, Pressed, Sequencer
from pyxelwidgets.devices import Device
from pyxelwidgets.events import Emitter
from pyxelwidgets import parser
from pyxelwidgets.parser import FORMAT, VERSION, LayoutError, Parser, load, schema, text_to_color, color_to_text


def layout(**extra):
    base = {
        'format': FORMAT, 'version': VERSION,
        'surface': {'width': 9, 'height': 9},
        'widgets': [
            {'type': 'Fader', 'name': 'volume', 'x': 8, 'y': 0, 'width': 1, 'height': 8,
             'options': {'active_color': '#00ffff', 'mode': 'Magnitude'}},
            {'type': 'Group', 'name': 'page', 'x': 0, 'y': 0, 'width': 8, 'height': 8, 'options': {'visible': False},
             'widgets': [{'type': 'Sequencer', 'name': 'drums', 'x': 0, 'y': 4, 'width': 8, 'height': 4,
                          'options': {'steps': 32, 'current_color': '#ff000080'}}]},
        ],
    }
    base.update(extra)
    return base


def test_builds_widget_tree():
    ui = load(layout())
    volume, page, drums = ui['volume'], ui['page'], ui['drums']
    assert isinstance(volume, Fader) and volume.mode == Fader.Mode.Magnitude and volume.active_color == Colors.Cyan
    assert isinstance(page, Group) and not page.visible and page['drums'] is drums
    assert isinstance(drums, Sequencer) and drums.steps == 32 and drums.current_color.a == pytest.approx(128 / 255)
    assert ui.surface.root.children == (volume, page)
    seen = []
    volume.on(Changed, seen.append)
    volume.tap(0, 7)
    assert seen[-1].value == 1.0


def test_loads_from_file_and_text(tmp_path):
    path = tmp_path / 'layout.json'
    path.write_text(json.dumps(layout()))
    assert load(str(path))['volume'].height == 8
    assert load(json.dumps(layout()))['drums'].steps == 32


@pytest.mark.parametrize('change, message', [
    (lambda l: l.update(version = 99), 'version 99 was made by a newer PyxelWidgets'),
    (lambda l: l.update(version = 0), 'unsupported pyxelwidgets.layout version 0'),
    (lambda l: l['widgets'][0].update(type = 'Slider'), 'widgets[0].type: unknown widget'),
    (lambda l: l['widgets'][0]['options'].update(mode = 'Turbo'), "widgets[0].options.mode: unknown value 'Turbo'"),
    (lambda l: l['widgets'][0]['options'].update(colour = '#fff'), "widgets[0].options: Fader has no option 'colour'"),
    (lambda l: l['widgets'][0]['options'].update(active_color = 'red'), 'widgets[0].options.active_color: expected'),
    (lambda l: l['widgets'][1]['widgets'][0].update(name = 'volume'), 'widgets[1].widgets[0].name: widget names must be given and unique'),
    (lambda l: l['widgets'][0].update(widgets = [{'type': 'Button', 'name': 'b'}]), 'widgets[0].widgets: only a Group'),
    (lambda l: l['widgets'][0].update(width = 0), 'widgets[0]: width and height must be at least 1'),
])
def test_errors_name_the_problem(change, message):
    data = layout()
    change(data)
    with pytest.raises(LayoutError, match = message.replace('[', r'\[').replace(']', r'\]').replace('(', r'\(')):
        load(data)


class LayoutDevice(Device):
    grid = (9, 9)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ports = None

    def connect(self, *ports):
        super().connect()
        self.ports = ports

    def send_pixel(self, x, y, value):
        pass


def test_devices_created_and_connected(monkeypatch):
    module = types.ModuleType('pyxelwidgets.devices.layouttest')
    module.LayoutDevice = LayoutDevice
    monkeypatch.setitem(sys.modules, module.__name__, module)
    data = layout(devices = [{'type': 'layouttest.LayoutDevice', 'x': 0, 'y': 0, 'input': 'in', 'output': 'out'},
                             {'type': 'layouttest.LayoutDevice', 'options': {'held_time': 0.5}}])
    ui = load(data)
    assert [d.ports for d in ui.devices] == [('in', 'out'), ()]
    assert ui.devices[1].pads.held_time == 0.5
    assert len(ui.surface.devices) == 2
    assert load(data, devices = False).devices == []
    data['devices'][0]['type'] = 'layouttest.Missing'
    with pytest.raises(LayoutError, match = r'devices\[0\]\.type'):
        load(data)


def test_app_drives_sequencers_from_transport():
    data = layout(transport = {'bpm': 90, 'signature': [3, 4]})
    data['widgets'][1]['widgets'][0]['options']['rate'] = '1/8'
    ui = load(data)
    app = ui.app()
    assert app.transport.bpm == 90 and app.transport.signature == (3, 4)
    [subscription] = app.transport.subscriptions
    assert subscription.rate == '1/8' and subscription.callback == ui['drums'].tick
    app.close()


def test_attach_subscribes_sequencers_and_trackers():
    from pyxelwidgets import Transport, Tracker
    data = layout()
    data['widgets'].append({'type': 'Tracker', 'name': 'song', 'x': 0, 'y': 0, 'width': 4, 'height': 4, 'options': {'rate': '1/4'}})
    ui = load(data)
    transport = Transport(sync = True)
    subscriptions = ui.attach(transport)
    assert [s.callback.__self__ for s in subscriptions] == [ui['drums'], ui['song']]
    transport.play()
    for _ in range(24):
        transport.pulse()
    assert ui['drums'].step == 3 and ui['song'].current_bar == 0
    transport.pulse()
    assert ui['song'].current_bar == 1


@pytest.mark.parametrize('transport, message', [
    ({'bpm': 0}, r'transport\.bpm'),
    ({'bpm': 'fast'}, r'transport\.bpm'),
    ({'signature': [4]}, r'transport\.signature'),
    ({'signature': [0, 4]}, r'transport\.signature'),
])
def test_invalid_transport(transport, message):
    with pytest.raises(LayoutError, match = message):
        load(layout(transport = transport))


def test_invalid_rate():
    data = layout()
    data['widgets'][1]['widgets'][0]['options']['rate'] = '1/0'
    with pytest.raises(LayoutError, match = r'widgets\[1\]\.widgets\[0\]\.options\.rate'):
        load(data)


def test_upgrades_step_by_step(monkeypatch):
    from pyxelwidgets import parser
    from pyxelwidgets.parser import upgrade
    # A future format change: version 2 renames the surface's "width"
    def to_2(layout):
        layout['surface']['columns'] = layout['surface'].pop('width')
    monkeypatch.setattr(parser, 'VERSION', 2)
    monkeypatch.setattr(parser, 'UPGRADES', {1: to_2})
    old = {'format': FORMAT, 'version': 1, 'surface': {'width': 8, 'height': 8}}
    new = upgrade(old)
    assert new == {'format': FORMAT, 'version': 2, 'surface': {'columns': 8, 'height': 8}}
    assert old['version'] == 1 and old['surface']['width'] == 8
    assert upgrade(new) is new


def test_current_version_is_3():
    from pyxelwidgets.parser import UPGRADES, VERSION, upgrade
    assert VERSION == 3 and list(UPGRADES) == [1, 2]
    # 2 added links and mappings from device controls, 3 device lights and screens as link targets: nothing else changes
    old = {'format': FORMAT, 'version': 1, 'surface': {'width': 8, 'height': 8}, 'links': [{'widget': 'a'}]}
    assert upgrade(old) == {**old, 'version': 3}
    assert upgrade({**old, 'version': 2}) == {**old, 'version': 3}


@pytest.mark.parametrize('data, message', [
    ({'format': 'other', 'version': 2}, 'not a pyxelwidgets.layout'),
    ({'format': FORMAT, 'version': 99}, 'newer'),
    ({'version': 2}, 'not a pyxelwidgets.layout'),
])
def test_rejects_unknown_formats(data, message):
    with pytest.raises(LayoutError, match = message):
        load(data)


def test_schema_lists_options():
    widgets = schema()['widgets']
    fader = {option['name']: option for option in widgets['Fader']['options']}
    assert fader['mode'] == {'name': 'mode', 'kind': 'enum', 'default': 'Multi', 'choices': ['Simple', 'Multi', 'Magnitude', 'Sensitive', 'Relative'],
                             'doc': 'What a press sets.'}
    assert fader['active_color']['default'] == '#ffffff'
    assert widgets['Group']['container'] and not widgets['Fader']['container']
    assert 'inactive_color' not in {o['name'] for o in widgets['Group']['options']}
    # Every widget is buildable from its schema defaults
    for name, info in widgets.items():
        options = {o['name']: o['default'] for o in info['options'] if 'default' in o and o['default'] is not None}
        Parser({'format': FORMAT, 'version': VERSION, 'surface': {'width': 8, 'height': 8},
                'widgets': [{'type': name, 'name': 'w', 'width': 4, 'height': 4, 'options': options}]})


def test_color_text_round_trip():
    for text in ('#000000', '#ff8000', '#12345678'):
        assert color_to_text(text_to_color(text)) == text


@pytest.fixture
def layout_devices(monkeypatch):
    module = types.ModuleType('pyxelwidgets.devices.layouttest')
    module.LayoutDevice = LayoutDevice
    monkeypatch.setitem(sys.modules, module.__name__, module)


def with_bindings(*bindings, devices = 1):
    return layout(devices = [{'type': 'layouttest.LayoutDevice'}] * devices, bindings = list(bindings))


def test_bindings_to_widgets_and_actions(layout_devices):
    from pyxelwidgets import ControlChanged, ControlPressed, Takeover
    ui = load(with_bindings({'device': 0, 'control': 'Knob1', 'widget': 'volume', 'options': {'takeover': 'Jump'}},
                            {'device': 0, 'control': 'Play', 'action': 'transport.toggle'}))
    [binding] = ui.bindings
    assert binding.takeover is Takeover.Jump and binding.target is ui['volume']
    device = ui.devices[0]
    device.emit(ControlChanged(device, 'Knob1', 0.25))
    assert ui['volume'].value == 0.25
    app = ui.app()
    assert len(ui.bindings) == 2
    device.emit(ControlPressed(device, 'Play', 1.0))
    assert app.transport.playing
    app.close()


def test_bindings_need_devices_to_be_created(layout_devices):
    data = with_bindings({'device': 0, 'control': 'Knob1', 'widget': 'volume'})
    assert load(data, devices = False).bindings == []


@pytest.mark.parametrize('binding, message', [
    ({'device': 1, 'control': 'Knob1', 'widget': 'volume'}, r'bindings\[0\]\.device'),
    ({'device': True, 'control': 'Knob1', 'widget': 'volume'}, r'bindings\[0\]\.device'),
    ({'device': 0, 'control': '', 'widget': 'volume'}, r'bindings\[0\]\.control'),
    ({'device': 0, 'control': 'Knob1'}, r'needs either'),
    ({'device': 0, 'control': 'Knob1', 'widget': 'volume', 'action': 'transport.play'}, r'needs either'),
    ({'device': 0, 'control': 'Knob1', 'widget': 'missing'}, r'bindings\[0\]\.widget'),
    ({'device': 0, 'control': 'Knob1', 'action': 'launch'}, r'bindings\[0\]\.action'),
    ({'device': 0, 'control': 'Knob1', 'widget': 'volume', 'options': {'takeover': 'Slow'}}, r'bindings\[0\]\.options\.takeover'),
    ({'device': 0, 'control': 'Knob1', 'widget': 'volume', 'options': {'control': 'x'}}, r'has no option'),
])
def test_invalid_bindings(layout_devices, binding, message):
    with pytest.raises(LayoutError, match = message):
        load(with_bindings(binding))


def test_schema_describes_bindings():
    binding = schema()['binding']
    assert [o['name'] for o in binding['options']] == ['takeover', 'glide_time', 'step', 'axis']
    assert 'transport.toggle' in binding['actions']


def test_schema_marks_bindable_widgets():
    widgets = schema()['widgets']
    assert widgets['Fader']['bindable'] and widgets['XY']['bindable']
    assert not widgets['Group']['bindable'] and not widgets['Sequencer']['bindable']
    assert widgets['Pages']['container']


def test_pages_in_layouts():
    from pyxelwidgets import Pages
    ui = load({'format': FORMAT, 'version': VERSION, 'surface': {'width': 4, 'height': 4}, 'widgets': [
        {'type': 'Pages', 'name': 'pages', 'width': 4, 'height': 4, 'options': {'page': 1, 'selector': 'Left'}, 'widgets': [
            {'type': 'Group', 'name': 'one', 'x': 1, 'width': 3, 'height': 4},
            {'type': 'Group', 'name': 'two', 'x': 1, 'width': 3, 'height': 4}]}]})
    pages = ui['pages']
    assert isinstance(pages, Pages) and pages.selector is Pages.Selector.Left
    assert pages.current is ui['two'] and not ui['one'].visible


def sprite_layout(**sprite):
    entry = {'type': 'Sprite', 'name': 'logo', 'x': 0, 'y': 0, 'width': 2, 'height': 2, 'options': {}}
    entry.update(sprite)
    return layout(widgets = [entry])


def test_widget_animation():
    from pyxelwidgets import Blink, Fade
    ui = load(layout(widgets = [{'type': 'Button', 'name': 'clip', 'animation': {'type': 'Blink', 'options': {'rate': '1/8', 'off_color': '#ff0000'}}},
                                {'type': 'Button', 'name': 'intro', 'animation': {'type': 'Fade', 'options': {'duration': 2, 'out': True}}}]))
    clip, intro = ui['clip'].animation, ui['intro'].animation
    assert isinstance(clip, Blink) and clip.rate == '1/8' and clip.off_color == Colors.Red
    assert isinstance(intro, Fade) and intro.rate == 2 and intro.out


def control_rules(links = (), mappings = ()):
    data = with_bindings()
    data['widgets'].append({'type': 'Button', 'name': 'show', 'options': {'mode': 'Switch'}})
    return {**data, 'links': list(links), 'mappings': list(mappings),
            'outputs': [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets Test'}]}


class Output(Emitter):
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


def test_links_and_mappings_from_device_controls(layout_devices):
    from pyxelwidgets import ControlChanged, ControlPressed, ControlTurned
    from pyxelwidgets.message import ControlChange, NoteOn
    data = control_rules(links = [
        {'device': 0, 'control': 'Knob1', 'on': 'ControlChanged', 'target': 'volume', 'option': 'active_color', 'value': {'source': 'value'}},
        {'device': 0, 'control': 'Encoder1', 'on': 'ControlTurned', 'target': 'drums', 'option': 'step', 'change': 'Add', 'value': {'source': 'delta'}},
        {'device': 0, 'control': 'Shift', 'on': 'ControlPressed', 'target': 'show', 'option': 'visible', 'change': 'Toggle'},
        {'device': 0, 'control': 'Shift', 'on': 'ControlReleased', 'action': 'debug', 'value': 'up {velocity}'},
    ], mappings = [
        {'device': 0, 'control': 'Knob1', 'on': 'ControlChanged', 'output': 'synth',
         'message': {'type': 'ControlChange', 'control': 74, 'value': {'source': 'value'}}},
        {'device': 0, 'control': 'Shift', 'on': 'ControlPressed', 'output': 'synth', 'message': {'type': 'NoteOn', 'note': 60}},
    ])
    ui = load(data)
    printed = []
    ui.debug = lambda name, text: printed.append((name, text))
    synth = Output()
    ui.map({'synth': synth})
    device = ui.devices[0]
    device.emit(ControlChanged(device, 'Knob1', 0.5))
    # Another control, or the same name on another device, does nothing
    device.emit(ControlChanged(device, 'Knob2', 1.0))
    other = LayoutDevice()
    ui.surface.add_device(other)
    other.emit(ControlChanged(other, 'Knob1', 1.0))
    assert ui['volume'].active_color.g in (127, 128) and ui['volume'].active_color.r == 0
    assert synth.sent == [ControlChange(74, 64)]
    device.emit(ControlTurned(device, 'Encoder1', 3))
    assert ui['drums'].step == 3
    device.emit(ControlPressed(device, 'Shift', 1.0))
    assert not ui['show'].visible and synth.sent[-1] == NoteOn(60, 127)
    device.emit(ControlReleased(device, 'Shift', 0.0))
    assert printed == [('Shift', 'up 0.0')]


def test_device_controls_follow_the_devices_given_later(layout_devices):
    from pyxelwidgets import ControlChanged
    data = control_rules(links = [
        {'device': 0, 'control': 'Knob1', 'on': 'ControlChanged', 'target': 'volume', 'option': 'active_color', 'value': {'source': 'value'}}])
    ui = load(data, devices = False)
    device = LayoutDevice()
    device.connect()
    ui.surface.add_device(device)
    device.emit(ControlChanged(device, 'Knob1', 0.5))
    assert ui['volume'].active_color == Colors.Cyan
    ui.place_controls([device])
    device.emit(ControlChanged(device, 'Knob1', 0.5))
    assert ui['volume'].active_color.g in (127, 128)
    ui.place_controls([None])
    device.emit(ControlChanged(device, 'Knob1', 1.0))
    assert ui['volume'].active_color.g in (127, 128)


@pytest.mark.parametrize('rule, message', [
    ({'device': 1, 'control': 'Knob1', 'on': 'ControlChanged'}, r'links\[0\]\.device: must be the index of one of the 1 devices'),
    ({'device': 0, 'control': '', 'on': 'ControlChanged'}, r'links\[0\]\.control'),
    ({'device': 0, 'control': 'Knob1', 'widget': 'volume', 'on': 'ControlChanged'}, r'not both'),
    ({'device': 0, 'control': 'Knob1', 'on': 'Changed'}, r"links\[0\]\.on: Knob1 \(control of devices\[0\]\) has no event 'Changed'"),
    ({'device': 0, 'control': 'Knob1', 'on': 'ControlTurned', 'value': {'source': 'value'}}, r"ControlTurned has no 'value'"),
])
def test_invalid_control_links(layout_devices, rule, message):
    link = {'target': 'volume', 'option': 'active_color', 'value': {'source': 'delta'}, **rule}
    with pytest.raises(LayoutError, match = message):
        load(control_rules(links = [link]), devices = False)


@pytest.mark.parametrize('rule, message', [
    ({'on': 'ControlChanged', 'feedback': True}, r'mappings\[0\]\.feedback: a device\'s control only sends'),
    ({}, r'needs "on"'),
    ({'on': 'ControlPressed', 'message': {'type': 'ControlChange', 'value': {'source': 'value'}}}, r"ControlPressed has no 'value'"),
])
def test_invalid_control_mappings(layout_devices, rule, message):
    mapping = {'device': 0, 'control': 'Knob1', 'output': 'synth', 'message': {'type': 'ControlChange', 'value': {'source': 'value'}}, **rule}
    with pytest.raises(LayoutError, match = message):
        load(control_rules(mappings = [mapping]), devices = False)


def test_schema_describes_control_events():
    described = schema()
    assert described['controls']['relative'] == ['ControlTurned']
    assert described['events']['ControlTurned']['sources'] == ['delta']
    assert described['events']['ControlChanged']['sources'][:2] == ['value', 'delta']


@pytest.mark.parametrize('animation, message', [
    ({'type': 'Wobble'}, r'widgets\[0\]\.animation\.type: unknown animation'),
    ('Blink', r'widgets\[0\]\.animation\.type'),
    ({'type': 'Blink', 'options': {'rate': '1/0'}}, r'widgets\[0\]\.animation\.options\.rate'),
    ({'type': 'Pulse', 'options': {'rate': -1}}, r'widgets\[0\]\.animation\.options\.rate'),
    ({'type': 'Pulse', 'options': {'speed': 1}}, r'has no option'),
])
def test_invalid_animations(animation, message):
    with pytest.raises(LayoutError, match = message):
        load(layout(widgets = [{'type': 'Button', 'name': 'clip', 'animation': animation}]))


def test_sprite_frames_from_the_top():
    from pyxelwidgets.parser import frames_to_json
    frames = [[['#ff0000', None], [None, '#00ff0080']], [['#0000ff', '#0000ff'], ['#0000ff', '#0000ff']]]
    ui = load(sprite_layout(options = {'frames': frames, 'rate': 0.25}))
    logo = ui['logo']
    assert logo.rate == 0.25 and len(logo.frames) == 2
    # The first row is the top one
    assert tuple(logo.frames[0][0, 1]) == (255, 0, 0, 255) and tuple(logo.frames[0][1, 0]) == (0, 255, 0, 128)
    assert logo.frames[0][1, 1, 3] == 0
    assert frames_to_json(logo.frames) == frames


@pytest.mark.parametrize('frames, message', [
    ([], 'expected a list of frames'),
    ([['#ff0000']], 'frame 0 must be a list of rows'),
    ([[['red']]], 'frame 0 row 0'),
])
def test_invalid_sprite_frames(frames, message):
    with pytest.raises(LayoutError, match = r'widgets\[0\]\.options\.frames: ' + message):
        load(sprite_layout(options = {'frames': frames}))


def test_invalid_sprite_rate():
    with pytest.raises(LayoutError, match = r'widgets\[0\]\.options\.rate'):
        load(sprite_layout(options = {'rate': 'fast'}))


def test_schema_describes_animations_and_frames():
    described = schema()
    assert list(described['animations']) == ['Blink', 'Pulse', 'Fade']
    rate = described['animations']['Blink']['options'][0]
    assert rate['kind'] == 'rate' and rate['seconds'] and rate['default'] == '1/4'
    sprite = {o['name']: o for o in described['widgets']['Sprite']['options']}
    assert sprite['frames']['kind'] == 'frames' and sprite['rate']['default'] is None and 'active_color' not in sprite
    sequencer = {o['name']: o for o in described['widgets']['Sequencer']['options']}
    assert 'seconds' not in sequencer['rate']


def output_layout(*mappings, outputs = None):
    return layout(widgets = [{'type': 'Button', 'name': 'kick'}, {'type': 'Fader', 'name': 'volume', 'height': 8},
                             {'type': 'Text', 'name': 'clock', 'width': 8, 'height': 5}],
                  outputs = outputs if outputs is not None else [
                      {'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets Test'},
                      {'name': 'daw', 'type': 'mackie.MackieControl', 'options': {'mode': 'LogicControl'}},
                      {'name': 'osc', 'type': 'osc.REAPER', 'options': {'send_port': 8001}}],
                  mappings = list(mappings))


def test_mappings_are_checked_without_devices():
    from pyxelwidgets.message import Command, NoteOn, Source
    ui = load(output_layout(
        {'widget': 'kick', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'NoteOn', 'note': 36, 'channel': 10}},
        {'widget': 'volume', 'on': 'Changed', 'output': 'daw', 'feedback': True,
         'message': {'type': 'Command', 'name': 'Fader 1', 'value': {'source': 'value'}}},
        {'widget': 'clock', 'output': 'daw', 'feedback': True, 'message': {'type': 'Command', 'name': 'Timecode', 'value': {'source': 'text'}}},
        {'widget': 'volume', 'on': 'Changed', 'output': 'osc', 'message': {'type': 'OscMessage', 'address': '/track/1/volume', 'args': [{'source': 'value'}]}},
    ), devices = False)
    settings = ui.mapping_settings()
    assert settings[0] == ('kick', Pressed, 'synth', NoteOn(36, Source('velocity'), 10), False)
    assert settings[1][3] == Command('Fader 1', Source('value')) and settings[2][1] is None
    assert ui.outputs == {} and ui.mappings == []


@pytest.mark.parametrize('mapping, message', [
    ({'widget': 'nope', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'NoteOn'}}, r'mappings\[0\]\.widget'),
    ({'widget': 'kick', 'on': 'Pressed', 'output': 'nope', 'message': {'type': 'NoteOn'}}, r'mappings\[0\]\.output'),
    ({'widget': 'kick', 'on': 'Toggled', 'output': 'synth', 'message': {'type': 'NoteOn'}}, r'mappings\[0\]\.on: kick \(Button\) has no event'),
    ({'widget': 'kick', 'output': 'synth', 'message': {'type': 'NoteOn'}}, r'needs "on", "feedback"'),
    ({'widget': 'kick', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'Sysex'}}, r'mappings\[0\]\.message\.type: unknown message'),
    ({'widget': 'kick', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'NoteOn', 'note': 200}}, r'message\.note: must be a whole number from 0 to 127'),
    ({'widget': 'kick', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'NoteOn', 'pitch': 1}}, r'NoteOn has no field'),
    ({'widget': 'kick', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'Command'}}, r'MIDI Port takes'),
    ({'widget': 'kick', 'on': 'Pressed', 'output': 'daw', 'message': {'type': 'Command', 'name': 'Launch'}}, r'has no command'),
    ({'widget': 'kick', 'on': 'Pressed', 'output': 'osc', 'message': {'type': 'OscMessage', 'address': 'play'}}, r'address: must start'),
    ({'widget': 'volume', 'on': 'Changed', 'output': 'synth', 'message': {'type': 'NoteOn'}}, r"Changed has no 'velocity'"),
    ({'widget': 'kick', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'NoteOn', 'velocity': {'source': 'velocity', 'gain': 2}}}, r'a source is'),
])
def test_invalid_mappings(mapping, message):
    with pytest.raises(LayoutError, match = message):
        load(output_layout(mapping), devices = False)


@pytest.mark.parametrize('outputs, message', [
    ([{'type': 'midi_port.MidiPort'}], r'outputs\[0\]\.name'),
    ([{'name': 'a', 'type': 'midi_port.MidiPort'}, {'name': 'a', 'type': 'midi_port.MidiPort'}], r'outputs\[1\]\.name'),
    ([{'name': 'a', 'type': 'novation.LaunchpadX'}], r'outputs\[0\]\.type: novation.LaunchpadX is not an output'),
    ([{'name': 'a', 'type': 'osc.OSC', 'options': {'port': 1}}], r'outputs\[0\]\.options'),
])
def test_invalid_outputs(outputs, message):
    with pytest.raises(LayoutError, match = message):
        load(output_layout(outputs = outputs), devices = False)


def test_message_json_round_trip():
    from pyxelwidgets.parser import message_from_json, message_to_json
    for data in ({'type': 'NoteOn', 'note': {'source': 'cell', 'offset': 36}, 'velocity': {'source': 'velocity', 'min': 64}, 'channel': 1},
                 {'type': 'OscMessage', 'address': '/track/{x+1}/mute', 'args': [{'source': 'state'}, 'on']},
                 {'type': 'Command', 'name': 'Play', 'value': 1.0}):
        assert message_to_json(message_from_json(data)) == data


def test_schema_describes_events_and_messages():
    described = schema()
    assert described['widgets']['Button']['events'][:2] == ['Pressed', 'Released'] and 'Changed' in described['widgets']['Button']['events']
    assert 'cell' in described['events']['Pressed']['sources']
    note_on = {f['name']: f for f in described['messages']['NoteOn']['fields']}
    assert note_on['note']['range'] == [0, 127] and note_on['velocity']['default'] == {'source': 'velocity'}
    assert [f['name'] for f in described['messages']['OscMessage']['fields']] == ['address', 'args']


def test_outputs_open_and_map(monkeypatch):
    # Building with devices opens the outputs; the virtual port is faked
    from pyxelwidgets.devices.midi_port import MidiPort
    opened = []
    monkeypatch.setattr(MidiPort, 'connect_virtual', lambda self, name: opened.append(name))
    ui = load(output_layout({'widget': 'kick', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'NoteOn', 'note': 36}},
                            outputs = [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets Test'}]))
    assert opened == ['PyxelWidgets Test'] and isinstance(ui.outputs['synth'], MidiPort)
    sent = []
    ui.outputs['synth'].send = sent.append
    ui['kick'].press(0, 0)
    assert sent[0].to_midi() == [0x90, 36, 127]
    ui.surface.close()
    assert ui.surface.mappings == [] and ui.outputs['synth'].terminated


def link_layout(*links):
    return {'format': FORMAT, 'version': VERSION, 'surface': {'width': 9, 'height': 9}, 'widgets': [
        {'type': 'Button', 'name': 'show', 'x': 0, 'y': 8, 'options': {'mode': 'Switch'}},
        {'type': 'Button', 'name': 'up', 'x': 1, 'y': 8},
        {'type': 'Fader', 'name': 'level', 'x': 8, 'y': 0, 'height': 8, 'options': {'mode': 'Magnitude'}},
        {'type': 'Keyboard', 'name': 'keys', 'x': 0, 'y': 0, 'width': 8, 'height': 4},
        {'type': 'Text', 'name': 'label', 'x': 0, 'y': 4, 'width': 8, 'height': 3},
        {'type': 'Group', 'name': 'panel', 'x': 0, 'y': 7, 'width': 8, 'height': 1, 'options': {'visible': False}},
    ], 'links': list(links)}


def test_links_change_options():
    from pyxelwidgets import Color, Keyboard
    ui = load(link_layout(
        {'widget': 'show', 'on': 'Changed', 'target': 'panel', 'option': 'visible', 'value': {'source': 'value'}},
        {'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'change': 'Add', 'value': 1, 'max': 1},
        {'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'scale', 'change': 'Toggle'},
        {'widget': 'level', 'on': 'Changed', 'target': 'keys', 'option': 'root_color', 'value': {'source': 'value'}, 'min': '#000000', 'max': '#00ff00'},
        {'widget': 'level', 'on': 'Changed', 'target': 'label', 'option': 'text', 'value': {'source': 'value'}, 'min': 0, 'max': 10},
        {'widget': 'up', 'on': 'Pressed', 'target': 'label', 'option': 'y', 'value': 5},
    ), devices = False)
    assert len(ui.links) == 6 and ui.surface.links == ui.links
    ui['show'].tap(0, 0)
    ui['up'].tap(0, 0)
    ui['up'].tap(0, 0)
    ui['level'].set_value(0.5)
    keys = ui['keys']
    assert ui['panel'].visible and keys.octave == 1 and keys.scale == list(Keyboard.Scale)[2]
    assert keys.root_color == Color(0, 127, 0) and ui['label'].text == '5' and ui['label'].rect.y == 5


@pytest.mark.parametrize('link, message', [
    ({'widget': 'nope', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'value': 1}, r'links\[0\]\.widget: no widget'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'nope', 'option': 'octave', 'value': 1}, r'links\[0\]\.target: no widget'),
    ({'widget': 'up', 'on': 'Toggled', 'target': 'keys', 'option': 'octave', 'value': 1}, r'links\[0\]\.on: up \(Button\) has no event'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'pitch', 'value': 1}, r'links\[0\]\.option: keys \(Keyboard\) has no option'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'change': 'Double', 'value': 1}, r'links\[0\]\.change: must be one of'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'change': 'Toggle'}, r'Toggle works on bool and enum'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'scale', 'change': 'Toggle', 'value': 1}, r'Toggle takes no value'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave'}, r'links\[0\]\.value: needed'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'value': 1.5}, r'links\[0\]\.value: must be a whole number'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'scale', 'value': 'Lydian7'}, r'links\[0\]\.value: unknown value'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'root_color', 'value': 'red'}, r'links\[0\]\.value: expected "#rrggbb"'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'value': {'source': 'value'}}, r"Pressed has no 'value'"),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'value': {'source': 'x', 'min': 0}}, r'a source is'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'root_color', 'value': {'source': 'x'}}, r'a color takes a 0\.0-1\.0 value'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'visible', 'value': True, 'min': 0}, r"links\[0\]\.min: 'visible' \(bool\) has no range"),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'value': 1, 'extra': 1}, r'unknown keys extra'),
])
def test_invalid_links(link, message):
    with pytest.raises(LayoutError, match = message):
        load(link_layout(link), devices = False)


def test_schema_describes_links():
    data = schema()
    linkable = {option['name']: option['kind'] for option in data['widgets']['Keyboard']['linkable']}
    assert list(linkable)[:4] == ['x', 'y', 'width', 'height'] and linkable['scale'] == 'enum'
    assert 'frames' not in {option['name'] for option in data['widgets']['Sprite']['linkable']}
    assert data['link']['changes'] == {'Set': None, 'Add': ['enum', 'float', 'int'], 'Toggle': ['bool', 'enum']}


def test_link_actions_and_detached_sequencers():
    from pyxelwidgets import StepPlayed
    layout = link_layout(
        {'widget': 'up', 'on': 'Pressed', 'action': 'transport.toggle'},
        {'widget': 'show', 'on': 'Pressed', 'target': 'free', 'action': 'advance'},
        {'widget': 'level', 'on': 'Changed', 'target': 'free', 'action': 'play', 'value': {'source': 'value'}, 'min': 0, 'max': 7},
    )
    layout['widgets'] += [{'type': 'Sequencer', 'name': 'free', 'x': 0, 'y': 0, 'width': 8, 'height': 1, 'options': {'clock': 'Off'}},
                          {'type': 'Sequencer', 'name': 'clocked', 'x': 0, 'y': 1, 'width': 8, 'height': 1}]
    ui = load(layout, devices = False)
    # Transport actions wait for a transport
    assert len(ui.links) == 2
    played = []
    ui['free'].on(StepPlayed, lambda e: played.append(e.step))
    ui['show'].tap(0, 0)
    ui['level'].set_value(0.5)
    assert played == [1, 4]
    app = ui.app()
    assert len(ui.links) == 3
    ui['up'].tap(0, 0)
    assert app.transport.playing
    # Only the sequencer following the transport is subscribed
    assert [s.callback.__self__.name for s in app.transport.subscriptions] == ['clocked']
    app.transport.close()


@pytest.mark.parametrize('link, message', [
    ({'widget': 'up', 'on': 'Pressed', 'action': 'transport.jump'}, r'links\[0\]\.action: unknown action'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'action': 'transport.play'}, r'transport actions have no target'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'action': 'advance'}, r'keys \(Keyboard\) has no action'),
    ({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'action': 'advance', 'value': 1}, r'either "option" or "action"'),
    ({'widget': 'up', 'on': 'Pressed', 'action': 'transport.play', 'value': 1}, r'takes no value'),
    ({'widget': 'up', 'on': 'Pressed', 'action': 'transport.play', 'change': 'Add'}, r'called, not changed'),
])
def test_invalid_link_actions(link, message):
    with pytest.raises(LayoutError, match = message):
        load(link_layout(link), devices = False)


def test_own_clocks_and_tempo_actions():
    import time
    from pyxelwidgets import Transport
    layout = link_layout(
        {'widget': 'level', 'on': 'Changed', 'action': 'transport.tempo', 'value': {'source': 'value'}, 'min': 60, 'max': 180},
        {'widget': 'up', 'on': 'Pressed', 'action': 'transport.tempo_add', 'value': 2.5},
        {'widget': 'show', 'on': 'Pressed', 'target': 'own', 'action': 'toggle'},
    )
    layout['widgets'] += [{'type': 'Sequencer', 'name': 'own', 'x': 0, 'y': 0, 'width': 8, 'height': 1,
                           'options': {'clock': 'Own', 'bpm': 6000, 'rate': '1/16'}}]
    ui = load(layout, devices = False)
    assert ui.attach(Transport()) == []
    from pyxelwidgets import StepPlayed
    played = []
    ui['own'].on(StepPlayed, played.append)
    clocks = ui.start_clocks()
    try:
        time.sleep(0.2)
        assert played                           # (the step itself wraps around)
        ui['show'].tap(0, 0)                    # paused
        time.sleep(0.05)
        count = len(played)
        time.sleep(0.1)
        assert len(played) == count and len(clocks) == 1
    finally:
        ui.close_clocks()
    transport = Transport()
    ui.links += ui.link(transport, widgets = False)
    ui['level'].set_value(0.5)
    assert transport.bpm == 120
    ui['up'].tap(0, 0)
    assert transport.bpm == 122.5
    with pytest.raises(LayoutError, match = r'links\[0\]\.value: must be a number'):
        load(link_layout({'widget': 'up', 'on': 'Pressed', 'action': 'transport.tempo', 'value': 'fast'}), devices = False)


def test_register_widgets_and_devices_of_your_own(monkeypatch):
    import pyxelwidgets.parser
    from pyxelwidgets.devices import Device
    from pyxelwidgets.widgets import Widget
    from pyxelwidgets.designer import catalog
    monkeypatch.setattr(pyxelwidgets.parser, '_WIDGETS', {})
    monkeypatch.setattr(pyxelwidgets.parser, '_DEVICES', {})

    @pyxelwidgets.parser.register
    class Dice(Widget):
        """Rolls a die."""
        def __init__(self, x = 0, y = 0, width = 3, height = 3, *, sides: int = 6, **kwargs):
            self.sides = sides
            super().__init__(x, y, width, height, **kwargs)

    @pyxelwidgets.parser.register
    class PadBox(Device):
        model = 'PadBox'
        grid = (4, 4)
        def send_pixel(self, x, y, value):
            pass

    kind = pyxelwidgets.parser.device_type(PadBox)
    assert kind == f'{PadBox.__module__}.PadBox'
    ui = load({'format': FORMAT, 'version': VERSION, 'surface': {'width': 4, 'height': 4},
               'devices': [{'type': kind}],
               'widgets': [{'type': 'Dice', 'name': 'die', 'width': 3, 'height': 3, 'options': {'sides': 20}}]})
    assert ui['die'].sides == 20 and type(ui.devices[0]) is PadBox
    info = catalog()
    assert info['widgets']['Dice']['doc'] == 'Rolls a die.' and any(device['type'] == kind for device in info['devices'])
    with pytest.raises(TypeError):
        pyxelwidgets.parser.register(int)


def test_debug_links(capsys):
    ui = load(link_layout(
        {'widget': 'up', 'on': 'Pressed', 'action': 'debug'},
        {'widget': 'level', 'on': 'Changed', 'action': 'debug', 'value': 'level {value}'},
    ), devices = False)
    ui['up'].tap(0, 0)
    ui['level'].set_value(0.25)
    assert capsys.readouterr().out.splitlines() == ['up: Pressed x=0 y=0 velocity=1.0 cell=0', 'level: level 0.25']
    written = []
    ui.debug = lambda widget, text: written.append((widget, text))
    ui['up'].tap(0, 0)
    assert written == [('up', 'Pressed x=0 y=0 velocity=1.0 cell=0')]
    assert schema()['link']['actions']['debug'] == 'text'


@pytest.mark.parametrize('link, message', [
    ({'widget': 'up', 'on': 'Pressed', 'action': 'debug', 'target': 'keys'}, r'debug has no target'),
    ({'widget': 'up', 'on': 'Pressed', 'action': 'debug', 'value': 3}, r'debug takes a text'),
    ({'widget': 'up', 'on': 'Pressed', 'action': 'debug', 'min': 0}, r'debug has no range'),
])
def test_invalid_debug_links(link, message):
    with pytest.raises(LayoutError, match = message):
        load(link_layout(link), devices = False)


def test_link_conditions():
    widgets = [{'type': 'ButtonGroup', 'name': 'tabs', 'x': 0, 'y': 4, 'width': 4, 'height': 4}]
    widgets += [{'type': 'Sequencer', 'name': f'seq{n}', 'width': 8, 'height': 4, 'options': {} if n == 0 else {'visible': False}} for n in range(16)]
    links = [{'widget': 'tabs', 'on': 'Toggled', 'target': f'seq{n}', 'option': 'visible',
              'value': {'if': {'source': 'cell'}, 'op': '==', 'to': n}} for n in range(16)]
    links.append({'widget': 'tabs', 'on': 'Toggled', 'target': 'tabs', 'option': 'active_color',
                  'value': {'if': 'x', 'op': '<', 'to': 2, 'then': '#ff0000', 'else': '#0000ff'}})
    ui = load({'format': FORMAT, 'version': VERSION, 'surface': {'width': 8, 'height': 8}, 'widgets': widgets, 'links': links}, devices = False)
    ui['tabs'].tap(2, 1)
    assert [n for n in range(16) if ui[f'seq{n}'].visible] == [6]
    assert color_to_text(ui['tabs'].active_color) == '#0000ff'


@pytest.mark.parametrize('value, message', [
    ({'if': 'value', 'to': 1}, r"Pressed has no 'value'"),
    ({'if': 'x', 'op': '~', 'to': 1}, r'value\.op: must be one of'),
    ({'if': 'x', 'to': [1]}, r'value\.to: must be a number or text'),
    ({'if': 'x', 'to': 1, 'then': 2}, r'value\.else: needed'),
    ({'if': 'x', 'to': 1, 'then': 2.5, 'else': 1}, r'value\.then: must be a whole number'),
    ({'if': 'x', 'to': 1, 'then': 1, 'else': 2, 'maybe': 3}, r'a condition is'),
])
def test_invalid_link_conditions(value, message):
    with pytest.raises(LayoutError, match = message):
        load(link_layout({'widget': 'up', 'on': 'Pressed', 'target': 'keys', 'option': 'octave', 'value': value}), devices = False)


def test_transport_sync(monkeypatch):
    from pyxelwidgets.devices.midi_clock import MidiClockInput
    opened = []
    monkeypatch.setattr(MidiClockInput, 'connect', lambda self, in_port, out_port = None: opened.append((in_port, out_port)))
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 8, 'height': 8},
              'transport': {'bpm': 100, 'sync': {'input': 'IAC Driver Bus 1'}}, 'widgets': []}
    ui = parser.load(layout, devices = False)
    assert ui.sync_settings() == {'input': 'IAC Driver Bus 1'}
    app = ui.app()
    assert app.transport.sync and ui.clock_input in app.clocks and ui.clock_input.transport is app.transport
    assert opened == [('IAC Driver Bus 1', None)]
    app.close()
    assert parser.load({**layout, 'transport': {'bpm': 100}}, devices = False).sync_settings() is None
    for sync, message in ((['x'], 'transport.sync'), ({'input': ''}, 'transport.sync.input'), ({'input': 'a', 'virtual': 'b'}, 'transport.sync'),
                          ({'output': 'a'}, 'transport.sync')):
        with pytest.raises(parser.LayoutError, match = message):
            parser.load({**layout, 'transport': {'sync': sync}}, devices = False)
    with pytest.raises(parser.LayoutError, match = 'unknown keys'):
        parser.load({**layout, 'transport': {'tempo': 100}}, devices = False)


def presets_layout(**options):
    return {'format': FORMAT, 'version': VERSION, 'surface': {'width': 4, 'height': 4},
            'widgets': [{'type': 'Presets', 'name': 'snapshots', 'x': 0, 'y': 0, 'width': 4, 'height': 4, 'options': options,
                         'widgets': [{'type': 'Fader', 'name': 'level', 'x': 0, 'y': 0, 'width': 1, 'height': 3}]}]}


def test_presets_are_saved_to_the_layout_file(tmp_path):
    path = tmp_path / 'layout.json'
    path.write_text(json.dumps(presets_layout()))
    ui = load(path, devices = False)
    ui['level'].value = 0.5
    # Edited meanwhile (e.g. saved by the designer): kept
    edited = presets_layout()
    edited['surface']['width'] = 5
    path.write_text(json.dumps(edited))
    ui['snapshots'].store(1)
    saved = json.loads(path.read_text())
    assert saved['surface']['width'] == 5
    assert saved['widgets'][0]['options']['presets'] == {'1': {'level': {'value': 0.5}}}
    again = load(path, devices = False)
    again['snapshots'].recall(1)
    assert again['level'].value == 0.5
    # Not from a file, or save off: nothing written
    load(presets_layout(), devices = False)['snapshots'].store(0)
    path.write_text(json.dumps(presets_layout(save = False)))
    load(path, devices = False)['snapshots'].store(0)
    assert 'presets' not in json.loads(path.read_text())['widgets'][0]['options']


def test_presets_save_failure_is_printed(tmp_path, capsys):
    path = tmp_path / 'layout.json'
    path.write_text(json.dumps(presets_layout()))
    ui = load(path, devices = False)
    path.write_text(json.dumps({**presets_layout(), 'widgets': []}))
    ui['snapshots'].store(0)
    assert 'presets not saved' in capsys.readouterr().out


def test_option_docs_come_from_docstrings():
    from pyxelwidgets import Binding, Presets
    docs = parser.option_docs(Presets)
    # Shared lines, inherited options, and the class's own text first
    assert docs['current_color'] == docs['empty_color'] == 'The slot brought back last, slots with something stored, empty ones.'
    assert docs['visible'].startswith('Hidden widgets')
    assert 'glide_time' in parser.option_docs(Binding)['takeover']
    # Every widget option a layout has is described in the schema
    for name, info in schema()['widgets'].items():
        for option in info['options']:
            assert option.get('doc'), f'{name}.{option["name"]} has no description'
