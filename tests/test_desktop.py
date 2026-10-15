"""The keyboard and mouse output, with a recorder instead of the real keyboard and mouse."""

import pytest

from pyxelwidgets import Button, ButtonGroup, Changed, Knob, Pressed, Source, Surface, Toggled, XY
from pyxelwidgets.devices.desktop import Desktop
from pyxelwidgets.message import Hotkey, Key, MouseButton, MouseClick, MouseMove, Scroll, TypeText, parse_keys
from pyxelwidgets.parser import FORMAT, VERSION, LayoutError, load, schema


class Recorder:
    def __init__(self):
        self.done = []

    def __getattr__(self, name):
        return lambda *args: self.done.append((name, *args))

    def screen(self):
        return 1001, 501


@pytest.fixture
def desktop():
    desktop = Desktop(backend = Recorder())
    desktop.connect()
    yield desktop
    desktop.close()


def test_keys(desktop):
    desktop.perform(Hotkey('ctrl+shift+s'))
    desktop.perform(Key('shift', 1.0))
    desktop.perform(Key('shift', 1.0))          # already held
    desktop.perform(Key('shift', 0.0))
    desktop.perform(TypeText('hi'))
    assert desktop.backend.done == [('press', 'ctrl'), ('press', 'shift'), ('press', 's'), ('release', 's'), ('release', 'shift'),
                                    ('release', 'ctrl'), ('press', 'shift'), ('release', 'shift'), ('type', 'hi', 0.0)]


def test_mouse(desktop):
    desktop.perform(MouseMove(0.5, 1.0))          # from the bottom-left
    desktop.perform(MouseMove(10, 5, True))       # positive y is up
    desktop.perform(MouseButton('left', 1.0))
    desktop.perform(MouseButton('left', 0.0))
    desktop.perform(MouseClick('right', 2))
    desktop.perform(Scroll(0, -3))
    assert desktop.backend.done == [('move_to', 500, 0), ('move_by', 10, -5), ('button', 'left', True), ('button', 'left', False),
                                    ('click', 'right', 2), ('scroll', 0, -3)]


def test_held_keys_are_let_go(desktop):
    desktop.send(Key('ctrl+alt', 1.0))
    desktop.send(MouseButton('middle', 1.0))
    desktop.disconnect()
    assert desktop.backend.done[-3:] == [('release', 'alt'), ('release', 'ctrl'), ('button', 'middle', False)]


def test_widgets_drive_it(desktop):
    surface = Surface(8, 8)
    save, keys, pad, knob = (surface.add(Button(0, 0, 1, 1)), surface.add(ButtonGroup(1, 0, 4, 1)),
                             surface.add(XY(0, 1, 4, 4)), surface.add(Knob(4, 1, 3, 3)))
    surface.map(save, desktop, Hotkey('cmd+s'), on = Pressed)
    surface.map(keys, desktop, Hotkey('f{x+1}'), on = Toggled)
    surface.map(pad, desktop, MouseMove(Source('value_x'), Source('value_y')), on = Changed)
    surface.map(knob, desktop, Scroll(0, Source('delta')), on = Changed)
    save.tap(0, 0)
    keys.tap(2, 0)
    pad.press(3, 3)
    desktop.disconnect()
    done = desktop.backend.done
    assert ('press', 'cmd') in done and ('press', 'f3') in done and done[-1][0] == 'move_to'


def test_parse_keys():
    assert parse_keys('Control+Option+Return') == ('ctrl', 'alt', 'enter')
    assert parse_keys('plus') == ('+',) and parse_keys('volume_up') == ('media_volume_up',)
    with pytest.raises(ValueError, match = 'unknown key'):
        parse_keys('ctrl+hyper')
    with pytest.raises(ValueError, match = 'button must be'):
        MouseClick('back')


def test_in_layouts():
    layout = {'format': FORMAT, 'version': VERSION, 'surface': {'width': 4, 'height': 4},
              'widgets': [{'type': 'Button', 'name': 'save'}],
              'outputs': [{'name': 'desktop', 'type': 'desktop.Desktop', 'options': {'type_delay': 0.01}}],
              'mappings': [{'widget': 'save', 'on': 'Pressed', 'output': 'desktop', 'message': {'type': 'Hotkey', 'keys': 'ctrl+s'}},
                           {'widget': 'save', 'on': 'Released', 'output': 'desktop', 'message': {'type': 'TypeText', 'text': 'saved {x}'}}]}
    ui = load(layout, devices = False)
    assert ui.mapping_settings()[0][3] == Hotkey('ctrl+s')
    layout['mappings'][0]['message']['keys'] = 'ctrl+nope'
    with pytest.raises(LayoutError, match = r"mappings\[0\]\.message: unknown key 'nope'"):
        load(layout, devices = False)
    fields = {field['name']: field for field in schema()['messages']['MouseClick']['fields']}
    assert fields['button']['choices'] == ['left', 'right', 'middle'] and fields['count']['range'] == [1, 3]
    assert schema()['messages']['Hotkey']['fields'][0]['kind'] == 'keys'
    assert schema()['messages']['MouseMove']['fields'][2]['kind'] == 'bool'


def test_on_off_fields_in_layouts():
    layout = {'format': FORMAT, 'version': VERSION, 'surface': {'width': 4, 'height': 4},
              'widgets': [{'type': 'XY', 'name': 'pad', 'width': 4, 'height': 4}],
              'outputs': [{'name': 'desktop', 'type': 'desktop.Desktop'}],
              'mappings': [{'widget': 'pad', 'on': 'Changed', 'output': 'desktop',
                            'message': {'type': 'MouseMove', 'x': {'source': 'delta'}, 'y': 0, 'relative': True}}]}
    assert load(layout, devices = False).mapping_settings()[0][3].relative is True
    layout['mappings'][0]['message']['relative'] = 'yes'
    with pytest.raises(LayoutError, match = r'message\.relative: must be true or false'):
        load(layout, devices = False)
