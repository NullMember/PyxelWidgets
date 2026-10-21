import json
import pathlib

import numpy
import pytest

import pyxelwidgets.devices
import pyxelwidgets.devices.desktop
import pyxelwidgets.devices.midi
import pyxelwidgets.devices.osc
import pyxelwidgets.devices.web
from pyxelwidgets import codegen, parser
from pyxelwidgets.events import PadPressed, PadReleased

ROOT = pathlib.Path(__file__).parent.parent
LAYOUTS = sorted([*ROOT.glob('examples/*/layout.json'), *ROOT.glob('src/pyxelwidgets/designer/templates/*.json')])

# Every kind of value the code writes: frames, pages, animations, conditions, debug and transport links
EVERYTHING = {
    'format': 'pyxelwidgets.layout', 'version': 1,
    'surface': {'width': 8, 'height': 8},
    'transport': {'bpm': 90, 'signature': [3, 4]},
    'widgets': [
        {'type': 'ButtonGroup', 'name': 'tabs', 'x': 0, 'y': 6, 'width': 2, 'height': 2, 'options': {'mode': 'Switch'}},
        {'type': 'Pages', 'name': 'book', 'x': 2, 'y': 0, 'width': 6, 'height': 8, 'options': {'selector': 'Left'}, 'widgets': [
            {'type': 'Sprite', 'name': 'logo', 'x': 0, 'y': 0, 'width': 3, 'height': 3, 'options': {
                'frames': [[['#ff0000', None, '#00ff00'], [None, '#ff000080'], ['#0000ff', '#0000ff', '#0000ff']],
                           [['#ffffff']]], 'rate': '1/4'}},
            {'type': 'Group', 'name': 'page 2', 'x': 0, 'y': 0, 'width': 5, 'height': 8, 'options': {'background': '#102030'}, 'widgets': [
                {'type': 'Fader', 'name': 'class', 'x': 0, 'y': 0, 'width': 1, 'height': 8, 'options': {'mode': 'Magnitude'},
                 'animation': {'type': 'Pulse', 'options': {'rate': '1/2'}}},
            ]},
        ]},
        {'type': 'Sequencer', 'name': 'seq', 'x': 0, 'y': 0, 'width': 2, 'height': 2, 'options': {'clock': 'Off'}},
        {'type': 'Button', 'name': 'go', 'x': 0, 'y': 5, 'width': 1, 'height': 1},
        {'type': 'Button', 'name': 'faster', 'x': 1, 'y': 5, 'width': 1, 'height': 1},
        {'type': 'Text', 'name': 'label', 'x': 0, 'y': 2, 'width': 2, 'height': 3, 'options': {'text': 'hi'}},
    ],
    'links': [
        {'widget': 'tabs', 'on': 'Toggled', 'target': 'book', 'option': 'page', 'value': {'source': 'cell'}},
        {'widget': 'tabs', 'on': 'Toggled', 'target': 'label', 'option': 'visible', 'value': {'if': {'source': 'cell'}, 'op': '!=', 'to': 3}},
        {'widget': 'tabs', 'on': 'Toggled', 'target': 'class', 'option': 'active_color',
         'value': {'if': 'cell', 'op': '>=', 'to': 2, 'then': '#ff0000', 'else': '#00ff00'}},
        {'widget': 'go', 'on': 'Pressed', 'target': 'seq', 'action': 'advance'},
        {'widget': 'go', 'on': 'Pressed', 'action': 'transport.toggle'},
        {'widget': 'faster', 'on': 'Pressed', 'action': 'transport.tempo_add', 'value': 5},
        {'widget': 'faster', 'on': 'Pressed', 'action': 'debug', 'value': 'faster {all}'},
    ],
}

@pytest.fixture(autouse = True)
def offline(monkeypatch):
    # The code connects its devices and outputs: not to real ports here
    for cls in (pyxelwidgets.devices.Device, pyxelwidgets.devices.midi.MIDI, pyxelwidgets.devices.web.WebGrid,
                pyxelwidgets.devices.osc.OSC, pyxelwidgets.devices.desktop.Desktop):
        monkeypatch.setattr(cls, 'connect', lambda self, *args: None)
    monkeypatch.setattr(pyxelwidgets.devices.midi.MIDI, 'connect_virtual', lambda self, port: None)

def run(layout: dict, **kwargs) -> dict:
    namespace = {}
    exec(compile(codegen.standalone(layout, run = False, **kwargs), 'standalone.py', 'exec'), namespace)
    app = namespace['app']
    for clock in [app.transport, *app.clocks]:
        clock.close()
    return namespace

def frames(surface, pads):
    """The surface's frames after pressing and releasing each pad."""
    shown = []
    for x, y in pads:
        for event in (PadPressed, PadReleased):
            surface.root.input(event(None, x, y, 1.0))
            surface.update()
            shown.append(surface.buffer.copy())
    return shown

@pytest.mark.parametrize('path', LAYOUTS, ids = lambda path: f'{path.parent.name}/{path.name}')
def test_standalone_builds_the_layout(path):
    layout = json.loads(path.read_text())
    namespace = run(layout, handlers = True)
    ui = parser.Parser(layout, devices = False)
    surface = namespace['surface']
    assert {name: (type(widget), repr(widget.rect)) for name, widget in ui.widgets.items()} == \
           {widget.name: (type(widget), repr(widget.rect)) for widget in _widgets(surface.root)}
    assert len(surface.links) == len(ui.link_settings())
    assert len(surface.mappings) == len(ui.mapping_settings())
    assert len(surface.bindings) == len(ui.binding_settings())
    assert len(surface.devices) == len(layout.get('devices') or [])

def test_standalone_behaves_like_the_layout():
    namespace = run(EVERYTHING)
    ui = parser.load(EVERYTHING, devices = False)
    app = ui.app()
    app.transport.close()
    pads = [(x, y) for y in range(8) for x in range(8)]
    for shown, expected in zip(frames(namespace['surface'], pads), frames(ui.surface, pads)):
        numpy.testing.assert_array_equal(shown, expected)
    # The transport links act on the code's transport
    assert namespace['app'].transport.bpm == 95 and app.transport.bpm == 95

def test_standalone_code(capsys):
    code = codegen.standalone(EVERYTHING)
    assert "from pyxelwidgets import " in code and 'Surface(8, 8)' in code
    # Names that aren't Python names become ones
    assert "page_2 = book.add(Group(0, 0, 5, 8, name = 'page 2', background = Color(16, 32, 48)))" in code
    assert "class_ = page_2.add(Fader(0, 0, 1, 8, name = 'class', mode = Fader.Mode.Magnitude))" in code
    assert "class_.animation = Pulse(rate = '1/2')" in code
    assert "picture([\n        'r.g',\n" not in code and "def picture(rows, colors):" in code
    assert "Condition(Source('cell'), '!=', 3)" in code
    assert "Condition(Source('cell'), '>=', 2, then = Colors.Red, otherwise = Colors.Lime)" in code
    assert "surface.link(go, app.transport.toggle, on = Pressed)" in code
    assert "surface.link(faster, lambda text: print('faster:', text), value = 'faster {all}', on = Pressed)" in code
    assert "app = App(surface, bpm = 90, signature = (3, 4))" in code
    assert code.rstrip().endswith('app.run()') and 'app.transport.play()' not in code
    # The debug link prints like the layout's
    namespace = run(EVERYTHING)
    namespace['faster'].press(0, 0)
    assert capsys.readouterr().out.startswith('faster: faster ')

def test_message_names_clashing_with_events():
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 8, 'height': 8},
              'outputs': [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'Synth'}],
              'widgets': [{'type': 'Keyboard', 'name': 'keys', 'x': 0, 'y': 0, 'width': 8, 'height': 8}],
              'mappings': [{'widget': 'keys', 'on': 'NoteOn', 'output': 'synth', 'message': {'type': 'NoteOn', 'note': {'source': 'note'}}},
                           {'widget': 'keys', 'on': 'NoteOn', 'output': 'synth', 'message': {'type': 'ControlChange', 'value': 1}}]}
    code = codegen.standalone(layout)
    assert "surface.map(keys, synth, message.NoteOn(note = Source('note')), on = NoteOn)" in code
    # Every message through the module then, not only the clashing one
    assert 'message.ControlChange(value = 1)' in code
    assert "synth.connect_virtual('Synth')" in code
    run(layout)

def test_loader():
    code = codegen.loader(EVERYTHING, 'my layout.json', handlers = True)
    assert "ui = parser.load('my layout.json')" in code
    assert "ui['tabs'].on(Toggled, lambda e: print('tabs', e.x, e.y, e.state))" in code
    assert code.rstrip().endswith('ui.app().run()')

def test_invalid_layout():
    with pytest.raises(parser.LayoutError):
        codegen.standalone({**EVERYTHING, 'links': [{'widget': 'nobody', 'on': 'Pressed', 'target': 'seq', 'action': 'advance'}]})

def _widgets(group):
    for child in group._children:
        yield child
        if hasattr(child, '_children'):
            yield from _widgets(child)


def test_sync():
    layout = {**EVERYTHING, 'transport': {'bpm': 90, 'sync': {'virtual': 'PyxelWidgets Clock'}}}
    code = codegen.standalone(layout)
    assert 'app = App(surface, bpm = 90, sync = True)' in code
    assert "daw_clock = MidiClockInput(app.transport)\ndaw_clock.connect_virtual('PyxelWidgets Clock')" in code
    assert 'from pyxelwidgets.devices.midi_clock import MidiClockInput' in code and 'app.transport.play()' not in code
    namespace = run(layout)
    assert namespace['daw_clock'].transport is namespace['app'].transport and namespace['app'].transport.sync
    code = codegen.standalone({**layout, 'transport': {'sync': {'input': 'IAC Driver Bus 1'}}})
    assert "daw_clock.connect('IAC Driver Bus 1', None)" in code
    code = codegen.standalone({**layout, 'outputs': [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'Synth'}],
                               'transport': {'sync': {'output': 'synth'}}})
    assert 'daw_clock = ClockFollower(app.transport, synth)' in code
    assert "DAW's MIDI clock" in codegen.loader(layout)


def test_controls_start_links_and_mappings():
    from pyxelwidgets.events import ControlChanged
    layout = {**EVERYTHING,
              'devices': [{'type': 'akai.APCMini', 'x': 0, 'y': 0}],
              'outputs': [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'Synth'}],
              'links': [{'device': 0, 'control': 'Fader_1', 'on': 'ControlChanged', 'target': 'class', 'option': 'active_color', 'value': {'source': 'value'}},
                        {'device': 0, 'control': 'Button_1', 'on': 'ControlPressed', 'action': 'debug'}],
              'mappings': [{'device': 0, 'control': 'Fader_1', 'on': 'ControlChanged', 'output': 'synth',
                            'message': {'type': 'ControlChange', 'control': 7, 'value': {'source': 'value'}}}]}
    code = codegen.standalone(layout)
    assert "fader_1 = surface.control(apc_mini, 'Fader_1')" in code
    assert "surface.map(fader_1, synth, ControlChange(control = 7), on = ControlChanged)" in code
    assert "surface.link(fader_1, class_, 'active_color', Source('value'), on = ControlChanged)" in code
    assert "    button_1, lambda text: print('Button_1:', text),\n" in code
    namespace = run(layout)
    device = namespace['apc_mini']
    sent = []
    namespace['synth'].send = sent.append
    device.emit(ControlChanged(device, 'Fader_1', 1.0))
    assert namespace['class_'].active_color.r == 255 and sent[0].value == 127
