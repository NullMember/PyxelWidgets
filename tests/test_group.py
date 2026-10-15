import pytest

from pyxelwidgets.color import Color, Colors
from pyxelwidgets.events import PadPressed
from pyxelwidgets.events import Pressed
from pyxelwidgets.group import Group
from pyxelwidgets.widgets import Button, Knob, Propagation, Sprite


def color_at(widget, x, y):
    return Color.from_array(widget.buffer[x, y])


def presses(widget):
    log = []
    widget.on(Pressed, lambda e: log.append((e.x, e.y)))
    return log


def test_standalone_group_renders_children_in_order():
    group = Group(0, 0, 4, 4)
    lower = group.add(Button(0, 0, 2, 2, inactive_color = Colors.Red))
    group.add(Button(1, 1, 1, 1, inactive_color = Colors.Lime))
    assert group.render()
    assert color_at(group, 0, 0) == Colors.Red
    assert color_at(group, 1, 1) == Colors.Lime
    assert color_at(group, 3, 3) == Colors.Invisible
    assert not group.render()
    lower.value = 1.0
    assert group.render()
    assert color_at(group, 1, 1) == Colors.Lime


def test_transparent_child_shows_child_below():
    group = Group(0, 0, 3, 3)
    group.add(Button(1, 1, 1, 1, inactive_color = Colors.Lime))
    group.add(Knob(0, 0, 3, 3))
    group.render()
    assert color_at(group, 1, 1) == Colors.Lime


def test_nested_groups_use_relative_coordinates():
    outer = Group(0, 0, 8, 8)
    inner = outer.add(Group(4, 2, 4, 4))
    button = inner.add(Button(1, 1, 1, 1, inactive_color = Colors.Blue))
    log = presses(button)
    outer.render()
    assert color_at(outer, 5, 3) == Colors.Blue
    outer.input(PadPressed(None, 5, 3, 1.0))
    assert log == [(0, 0)]


def test_input_stops_at_topmost_widget():
    group = Group(0, 0, 2, 2)
    lower, upper = group.add(Button(0, 0, 2, 2)), group.add(Button(0, 0, 1, 1))
    lower_log, upper_log = presses(lower), presses(upper)
    assert group.input(PadPressed(None, 0, 0, 1.0))
    assert upper_log == [(0, 0)] and lower_log == []
    group.input(PadPressed(None, 1, 1, 1.0))
    assert lower_log == [(1, 1)]


def test_pass_lets_input_continue_underneath():
    group = Group(0, 0, 2, 2)
    lower = group.add(Button(0, 0, 2, 2))
    overlay = group.add(Sprite(0, 0, 2, 2))
    upper = group.add(Button(0, 0, 2, 2, propagation = Propagation.Pass))
    logs = presses(lower), presses(overlay), presses(upper)
    group.input(PadPressed(None, 1, 0, 1.0))
    assert all(log == [(1, 0)] for log in logs)


def test_group_empty_area_passes_unless_stop():
    outer = Group(0, 0, 4, 4)
    below = outer.add(Button(0, 0, 4, 4))
    log = presses(below)
    panel = outer.add(Group(0, 0, 4, 4))
    panel.add(Button(0, 0, 1, 1))
    outer.input(PadPressed(None, 3, 3, 1.0))
    assert log == [(3, 3)]
    panel.propagation = Propagation.Stop
    outer.input(PadPressed(None, 2, 2, 1.0))
    assert log == [(3, 3)]


def test_hidden_children_are_not_drawn_and_get_no_input():
    group = Group(0, 0, 1, 1)
    below = group.add(Button(0, 0, 1, 1, inactive_color = Colors.Red))
    cover = group.add(Button(0, 0, 1, 1, inactive_color = Colors.Blue))
    group.render()
    assert color_at(group, 0, 0) == Colors.Blue
    cover.visible = False
    assert group.render()
    assert color_at(group, 0, 0) == Colors.Red
    log = presses(below)
    group.input(PadPressed(None, 0, 0, 1.0))
    assert log == [(0, 0)]


def test_names_find_remove():
    group = Group(0, 0, 4, 4)
    group.add(Button(0, 0, 1, 1, name = 'play'))
    with pytest.raises(ValueError):
        group.add(Button(1, 0, 1, 1, name = 'play'))
    assert group['play'].name == 'play' and 'play' in group and len(group) == 1
    group.remove('play')
    assert group.find('play') is None and len(group) == 0
    with pytest.raises(KeyError):
        group['play']
