from pyxelwidgets.devices.input import PadInput
from pyxelwidgets.events import PadDoublePressed, PadHeld, PadPressed, PadReleased


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def kinds(events):
    return [event[0] for event in events]


def test_press_release_and_double_press():
    clock = Clock()
    pads = PadInput(double_press_time = 0.15, clock = clock)
    assert kinds(pads.press(1, 2, 0.8)) == [PadPressed]
    assert pads.pressed == {(1, 2)}
    assert kinds(pads.release(1, 2)) == [PadReleased]
    clock.now += 0.1
    assert kinds(pads.press(1, 2, 1.0)) == [PadPressed, PadDoublePressed]
    clock.now += 0.5
    assert kinds(pads.press(1, 2, 1.0)) == [PadPressed]


def test_hold_reported_once_and_only_while_down():
    clock = Clock()
    pads = PadInput(held_time = 1.0, clock = clock)
    pads.press(0, 0, 0.5)
    pads.press(3, 3, 1.0)
    clock.now += 0.5
    pads.release(3, 3)
    assert pads.poll() == []
    clock.now += 0.6
    assert pads.poll() == [(PadHeld, 0, 0, 0.5)]
    clock.now += 5
    assert pads.poll() == []


def test_release_without_press():
    assert kinds(PadInput().release(4, 4)) == [PadReleased]
