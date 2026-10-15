import json
import sys
import types

import pytest

from pyxelwidgets.devices import Device
from pyxelwidgets.rectangle import Rectangle2D
from pyxelwidgets.widgets import Fader, Sequencer
from pyxelwidgets.surface import Surface


def test_rectangle_area_follows_size():
    rect = Rectangle2D(0, 0, 2, 3)
    rect.set(1, 1, 4, 5)
    assert rect.area == 20
    rect.w = 2
    assert rect.area == 10


def test_widget_resize_updates_area():
    fader = Fader(0, 0, 2, 2, grid = Fader.Grid.Matrix)
    fader.width = 4
    assert fader.rect.area == 8








def test_sequencer_current():
    sequencer = Sequencer(0, 0, 4, 4)
    assert sequencer.current is False
    sequencer.current = True
    assert sequencer.current is True


def test_surface_default_name_uses_own_counter():
    first, second = Surface(1, 1), Surface(1, 1)
    assert first.name.startswith('Surface_')
    assert first.name != second.name




def test_group_and_surface_reject_unknown_arguments():
    from pyxelwidgets.group import Group
    with pytest.raises(TypeError):
        Group(0, 0, 4, 4, nmae = 'typo')
    with pytest.raises(TypeError):
        Surface(4, 4, callbak = print)
    assert Group(0, 0, 4, 4, name = 'main').name == 'main'
