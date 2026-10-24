import pytest

from pyxelwidgets import (Button, ButtonGroup, Changed, Color, Colors, Fader, Keyboard, Link, Pages, Pressed, Source,
                          Surface, Text, Toggled, XY)
from pyxelwidgets.group import Group
from pyxelwidgets.widgets import Sprite


def test_switch_shows_a_group():
    switch, panel = Button(0, 0, 1, 1, mode = Button.Mode.Switch), Group(0, 0, 4, 4, visible = False)
    Link(switch, panel, 'visible', Source('value'), on = Changed)
    switch.tap(0, 0)
    assert panel.visible
    switch.tap(0, 0)
    assert not panel.visible


def test_add_within_limits():
    up, down, keys = Button(0, 0, 1, 1), Button(1, 0, 1, 1), Keyboard(0, 1, 8, 2)
    Link(up, keys, 'octave', 1, on = Pressed, change = Link.Change.Add, maximum = 2)
    Link(down, keys, 'octave', -1, on = Pressed, change = Link.Change.Add, minimum = -1)
    for _ in range(5):
        up.tap(0, 0)
    assert keys.octave == 2
    for _ in range(5):
        down.tap(0, 0)
    assert keys.octave == -1 and keys.configured == {'octave': -1}


def test_toggle_flips_and_cycles():
    button, fader = Button(0, 0, 1, 1), Fader(1, 0, 1, 8)
    Link(button, fader, 'interactive', on = Pressed, change = Link.Change.Toggle)
    Link(button, fader, 'mode', on = Pressed, change = Link.Change.Toggle)
    button.tap(0, 0)
    assert fader.interactive is False and fader.mode == Fader.Mode.Magnitude
    for _ in range(4):
        button.tap(0, 0)
    assert fader.mode == Fader.Mode.Multi


def test_cell_picks_a_page():
    tabs = ButtonGroup(0, 0, 3, 1)
    pages = Pages(0, 1, 4, 4)
    for name in 'abc':
        pages.add(Group(0, 0, 4, 3, name = name))
    Link(tabs, pages, 'page', Source('cell'), on = Toggled)
    tabs.tap(2, 0)
    assert pages.page == 2 and pages.current.name == 'c'


def test_unit_values_cover_a_range():
    fader = Fader(0, 0, 1, 8, mode = Fader.Mode.Magnitude)
    pad, label, keys = Button(1, 0, 1, 1, active_color = Colors.Red), Text(2, 0, 6, 5), Keyboard(0, 0, 4, 4)
    Link(fader, pad, 'active_color', Source('value'), on = Changed)
    Link(fader, label, 'text', Source('value'), on = Changed, minimum = 0, maximum = 100)
    Link(fader, keys, 'scale', Source('value'), on = Changed, minimum = Keyboard.Scale.Major, maximum = Keyboard.Scale.Minor)
    Link(fader, fader, 'inactive_color', Source('value'), on = Changed, minimum = Colors.Blue, maximum = Colors.White)
    fader.set_value(0.5)
    assert pad.active_color == Color(127, 0, 0) and label.text == '50'
    assert keys.scale == list(Keyboard.Scale)[round((list(Keyboard.Scale).index(Keyboard.Scale.Minor)) * 0.5)]
    assert fader.inactive_color == Color(127, 127, 255)
    fader.set_value(1.0)
    assert pad.active_color == Colors.Red and label.text == '100'


def test_whole_numbers_get_an_offset():
    pads = ButtonGroup(0, 0, 4, 2, mode = ButtonGroup.Mode.Button)
    sequencer = Sprite(0, 2, 2, 2)
    Link(pads, sequencer, 'x', Source('x', offset = 2), on = Pressed)
    pads.press(1, 0)
    assert sequencer.x == 3 and sequencer.updated


def test_configure_redraws_and_reshapes():
    fader = Fader(0, 0, 2, 4, value = 1.0)
    fader.render()
    fader.configure(active_color = Colors.Red, direction = Fader.Direction.Horizontal)
    assert fader.updated and fader.configured == {'active_color': Colors.Red, 'direction': Fader.Direction.Horizontal}
    fader.render()
    assert tuple(fader.buffer[1, 0]) == (255, 0, 0, 255)
    with pytest.raises(AttributeError, match = 'no option'):
        fader.configure(colour = Colors.Red)
    group = Group(0, 0, 2, 2)
    group.configure(background = Colors.Blue, x = 3)
    assert group.inactive_color == Colors.Blue and group.rect.x == 3


def test_button_value_sets_switch():
    source, switch = Button(0, 0, 1, 1), Button(1, 0, 1, 1, mode = Button.Mode.Switch)
    Link(source, switch, 'value', 1.0, on = Pressed)
    source.tap(0, 0)
    assert switch.value == 1.0 and switch.state
    switch.tap(0, 0)
    assert switch.value == 0.0


def test_links_dont_loop():
    a, b = Pages(0, 0, 2, 2), Pages(0, 0, 2, 2)
    for pages in (a, b):
        for name in 'xyz':
            pages.add(Group(0, 0, 2, 1, name = name))
    from pyxelwidgets import PageChanged
    Link(a, b, 'page', 1, on = PageChanged, change = Link.Change.Add)
    Link(b, a, 'page', 1, on = PageChanged, change = Link.Change.Add)
    a.page = 1
    # a → b → a again, where the first link is still running and stops
    assert (a.page, b.page) == (2, 1)


@pytest.mark.parametrize('kwargs, message', [
    ({'option': 'nope', 'value': 1}, 'no option'),
    ({'option': 'octave', 'change': Link.Change.Toggle}, 'only on/off'),
    ({'option': 'visible', 'value': 1, 'change': Link.Change.Add}, 'only numbers'),
    ({'option': 'octave'}, 'a value is needed'),
    ({'option': 'octave', 'value': Source('state')}, "Pressed has no 'state'"),
    ({'option': 'root_color', 'value': Source('x')}, 'not a value from the event'),
])
def test_invalid_links(kwargs, message):
    with pytest.raises(ValueError, match = message):
        Link(Button(0, 0, 1, 1), Keyboard(0, 0, 4, 4), on = Pressed, **kwargs)


def test_surface_links():
    surface = Surface(4, 4)
    button, panel = surface.add(Button(0, 0, 1, 1)), surface.add(Group(1, 0, 3, 3))
    link = surface.link(button, panel, 'visible', on = Pressed, change = Link.Change.Toggle)
    button.tap(0, 0)
    assert not panel.visible and surface.links == [link]
    surface.unlink(link)
    button.tap(0, 0)
    assert not panel.visible and surface.links == []


def test_reversed_range():
    switch, keys = Button(0, 0, 1, 1, mode = Button.Mode.Switch), Keyboard(0, 0, 8, 8)
    Link(switch, keys, 'height', Source('value'), on = Changed, minimum = 8, maximum = 7)
    switch.tap(0, 0)
    assert keys.height == 7
    switch.tap(0, 0)
    assert keys.height == 8


def test_actions():
    from pyxelwidgets import Sequencer, StepPlayed, Transport
    from pyxelwidgets.widgets import Clock
    transport = Transport()
    play, step, pads = Button(0, 0, 1, 1), Button(1, 0, 1, 1), ButtonGroup(0, 1, 4, 1, mode = ButtonGroup.Mode.Button)
    sequencer = Sequencer(0, 2, 4, 1, clock = Clock.Off)
    played = []
    sequencer.on(StepPlayed, lambda e: played.append(e.step))
    Link(play, transport.toggle, on = Pressed)
    Link(step, sequencer.advance, on = Pressed)
    Link(pads, sequencer.play, value = Source('cell'), on = Pressed)
    play.tap(0, 0)
    assert transport.playing
    play.tap(0, 0)
    assert not transport.playing
    step.tap(0, 0)
    step.tap(0, 0)
    pads.tap(3, 0)
    assert played == [1, 2, 3]
    transport.close()


def test_action_values_cover_a_range():
    fader, pages = Fader(0, 0, 1, 8, mode = Fader.Mode.Magnitude), Pages(1, 0, 4, 4)
    for name in 'abcd':
        pages.add(Group(0, 0, 4, 3, name = name))
    chosen = []
    Link(fader, chosen.append, value = Source('value'), on = Changed, minimum = 0, maximum = 3)
    fader.set_value(1.0)
    fader.set_value(0.5)
    assert chosen == [3, 2]
    with pytest.raises(ValueError, match = 'must be an action'):
        Link(fader, pages, on = Changed)
    with pytest.raises(ValueError, match = 'called, not changed'):
        Link(fader, pages.next, on = Changed, change = Link.Change.Toggle)


def test_text_values_and_debug_writing():
    from pyxelwidgets.link import fill_text
    assert fill_text('pad {x},{y+1} {velocity} {missing}', {'x': 1, 'y': 0, 'velocity': 0.123456}) == 'pad 1,1 0.123 {missing}'
    assert fill_text('{all}', {'x': 1, 'value': 0.5}) == 'x=1 value=0.5'
    written = []
    button = Button(0, 0, 1, 1)
    Link(button, written.append, value = 'pressed at {velocity}', on = Pressed)
    button.press(0, 0, 0.5)
    assert written == ['pressed at 0.5']


def test_condition_chooses_between_two_values():
    from pyxelwidgets import Condition, Sequencer
    tabs = ButtonGroup(0, 0, 4, 4)
    sequencers = [Sequencer(0, 0, 8, 4, visible = n == 0) for n in range(16)]
    for n, sequencer in enumerate(sequencers):
        Link(tabs, sequencer, 'visible', Condition(Source('cell'), '==', n), on = Toggled)
    for x, y in ((3, 0), (1, 2), (0, 0), (3, 3)):
        tabs.tap(x, y)
        assert [n for n, sequencer in enumerate(sequencers) if sequencer.visible] == [x + y * 4]
    # Any values, other comparisons
    pad = Button(0, 0, 1, 1)
    Link(tabs, pad, 'active_color', Condition(Source('x'), '<', 2, Colors.Red, Colors.Blue), on = Toggled)
    tabs.tap(1, 0)
    assert pad.active_color == Colors.Red
    tabs.tap(2, 0)
    assert pad.active_color == Colors.Blue
    fader, chosen = Fader(0, 0, 1, 8, mode = Fader.Mode.Magnitude), []
    Link(fader, chosen.append, value = Condition(Source('value'), '>=', 0.5, 10, 20), on = Changed)
    fader.set_value(0.75)
    fader.set_value(0.25)
    assert chosen == [10, 20]
    with pytest.raises(ValueError, match = 'op must be'):
        Condition(Source('x'), '=~', 1)
    with pytest.raises(ValueError, match = "Pressed has no 'value'"):
        Link(pad, fader, 'visible', Condition(Source('value')), on = Pressed)


def test_switch_turns_off_before_on():
    from pyxelwidgets import Toggled
    tabs = ButtonGroup(0, 0, 4, 1)
    tabs.tap(3, 0)
    events = []
    tabs.on(Toggled, events.append)
    tabs.tap(1, 0)                  # (1, 0) comes before (3, 0) on the grid, but turns on
    assert [(e.x, e.state) for e in events] == [(3, False), (1, True)]


def test_emitting_links_let_the_target_s_links_follow():
    from pyxelwidgets import Stepper
    shortcut, selector, pages = Button(0, 0, 1, 1), Stepper(0, 1, 4, 1, maximum = 3, interactive = False), Pages(0, 2, 4, 1)
    for _ in range(4):
        pages.add(Group(0, 0, 4, 1))
    Link(selector, pages, 'page', Source('value'), on = Changed, minimum = 0, maximum = 3)
    quiet = Link(shortcut, selector, 'value', 1.0, on = Pressed)
    shortcut.tap(0, 0)
    assert selector.number == 3 and pages.page == 0          # configure alone: nothing follows
    quiet.close()
    Link(shortcut, selector, 'value', 2 / 3, on = Pressed, emit = True)
    changed = []
    selector.on(Changed, changed.append)
    shortcut.tap(0, 0)
    # Set although it isn't interactive, then Changed with the value it took
    assert selector.number == 2 and pages.page == 2 and [e.value for e in changed] == [pytest.approx(2 / 3, abs = 1e-6)]
    shortcut.tap(0, 0)
    assert len(changed) == 1                                  # unchanged: nothing sent
    with pytest.raises(ValueError, match = "only a link setting a widget's value can emit"):
        Link(shortcut, selector, 'maximum', 4, on = Pressed, emit = True)
    with pytest.raises(ValueError, match = "only a link setting a widget's value can emit"):
        Link(shortcut, pages, 'page', 1, on = Pressed, emit = True)


def test_emitting_links_in_layouts_and_code():
    from pyxelwidgets import codegen, parser
    layout = {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 4, 'height': 3},
              'widgets': [{'type': 'Button', 'name': 'shortcut', 'x': 0, 'y': 0, 'width': 1, 'height': 1},
                          {'type': 'Stepper', 'name': 'selector', 'x': 0, 'y': 1, 'width': 4, 'height': 1, 'options': {'maximum': 3}},
                          {'type': 'Fader', 'name': 'shown', 'x': 0, 'y': 2, 'width': 4, 'height': 1, 'options': {'direction': 'Horizontal'}}],
              'links': [{'widget': 'shortcut', 'on': 'Pressed', 'target': 'selector', 'option': 'value', 'value': 1.0, 'emit': True},
                        {'widget': 'selector', 'on': 'Changed', 'target': 'shown', 'option': 'value', 'value': {'source': 'value'}}]}
    ui = parser.Parser(layout, devices = False)
    ui['shortcut'].tap(0, 0)
    assert ui['shown'].value == 1.0
    code = codegen.standalone(layout, run = False)
    assert "surface.link(shortcut, selector, 'value', 1.0, on = Pressed, emit = True)" in code
    layout['links'].append({'widget': 'shortcut', 'on': 'Pressed', 'target': 'shown', 'option': 'visible', 'value': False})
    for bad, message in ((1, 'must be true or false'), (True, "only a link setting a widget's value")):
        layout['links'][2]['emit'] = bad
        with pytest.raises(parser.LayoutError, match = rf'links\[2\]\.emit: {message}'):
            parser.Parser(layout, devices = False)
