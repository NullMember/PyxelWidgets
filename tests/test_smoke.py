import pathlib
import py_compile

import pytest

from pyxelwidgets.devices import Device
from pyxelwidgets.color import Color, Colors
from pyxelwidgets.events import Changed, Event, Pressed, Released
from pyxelwidgets.surface import Surface
from pyxelwidgets.widgets import *

EXAMPLES = sorted(pathlib.Path(__file__).parent.parent.glob('examples/*/*.py'))


class FakeDevice(Device):
    """Records pixels instead of sending them to hardware."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent = {}

    def send_pixel(self, x, y, pixel):
        self.sent[x, y] = pixel


WIDGETS = [
    lambda: Button(0, 0, 1, 1),
    lambda: ButtonGroup(0, 0, 8, 1),
    lambda: Fader(0, 0, 1, 8),
    lambda: Fader(0, 0, 4, 4, grid = Fader.Grid.Matrix, type = Fader.Type.BoostCut),
    lambda: Keyboard(0, 0, 8, 8, type = Keyboard.Type.DiatonicVertical),
    lambda: Knob(0, 0, 3, 3, type = Knob.Type.Spread),
    lambda: Sequencer(0, 0, 8, 4),
    lambda: Sprite(0, 0, 2, 2),
    lambda: Tracker(0, 0, 8, 8),
    lambda: XY(0, 0, 4, 4),
]


@pytest.fixture
def setup():
    controller = FakeDevice(width = 9, height = 9)
    controller.connect()
    surface = Surface(9, 9)
    surface.add_device(controller, 0, 0)
    return controller, surface


@pytest.mark.parametrize('factory', WIDGETS)
def test_widget_renders_through_surface(setup, factory):
    controller, surface = setup
    surface.add(factory())
    surface.update()
    # Every cell of the 9x9 surface is pushed to the controller on first frame
    assert len(controller.sent) == 81
    assert all(isinstance(p, Color) for p in controller.sent.values())


def test_button_press_lights_pad(setup):
    controller, surface = setup
    events = []
    button = surface.add(Button(2, 3, 1, 1, active_color = Colors.Red))
    button.on(Event, events.append)
    surface.update()
    controller.set_button(2, 3, 1.0)
    surface.update()
    assert controller.sent[2, 3] == Colors.Red
    controller.set_button(2, 3, 0.0)
    surface.update()
    assert controller.sent[2, 3] == Colors.Black
    assert [type(e) for e in events] == [Pressed, Changed, Released, Changed]
    assert events[0].widget is button and (events[0].x, events[0].y) == (0, 0)


def test_fader_tap_sets_value():
    fader = Fader(0, 0, 1, 8, mode = Fader.Mode.Magnitude)
    fader.tap(0, 7)
    assert fader.value == 1.0


def test_sequencer_toggles_step():
    sequencer = Sequencer(0, 0, 4, 4)
    sequencer.press(1, 0, 1.0)
    assert sequencer.state[1, 0]
    sequencer.steps = 32
    assert sequencer.pages == 2


def test_pixel_compares_with_non_pixel():
    assert Color(1, 2, 3) == Color(1, 2, 3)
    assert Color(1, 2, 3) != Color(3, 2, 1)
    assert not (Color() == 0)
    assert Color() != None


@pytest.mark.parametrize('path', EXAMPLES, ids = lambda p: p.name)
def test_examples_compile(path):
    py_compile.compile(str(path), doraise = True)


def test_unknown_widget_argument_raises():
    with pytest.raises(TypeError):
        Fader(0, 0, 1, 8, activeColour = Colors.Red)
    with pytest.raises(TypeError):
        Button(0, 0, 1, 1, lock = True)


def test_default_names_count_per_class():
    first, second = Sprite(0, 0, 1, 1), Sprite(0, 0, 1, 1)
    assert first.name.startswith('Sprite_') and first.name != second.name


def test_non_interactive_widget_ignores_input_but_reports_it():
    events = []
    button = Button(0, 0, 1, 1, interactive = False)
    button.on(Changed, events.append)
    button.tap(0, 0)
    assert button.value == 0.0
    assert [e.value for e in events] == [1.0, 0.0]
