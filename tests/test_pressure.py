from pyxelwidgets import Button, Group, Pressure, Surface
from pyxelwidgets.events import PadPressure
from pyxelwidgets.devices.ableton import Push2
from pyxelwidgets.devices.novation import LaunchpadMiniMK3, LaunchpadProMK3, LaunchpadX


def pressures(device):
    seen = []
    device.on(PadPressure, lambda e: seen.append((e.x, e.y, round(e.velocity, 3))))
    return seen


def test_only_held_pads_report_pressure():
    device = LaunchpadX()
    seen = pressures(device)
    device.set_pressure(0, 0, 0.5)
    device.set_button(0, 0, 1.0)
    device.set_pressure(0, 0, 0.5)
    device.set_button(0, 0, 0.0)
    device.set_pressure(0, 0, 0.7)
    assert seen == [(0, 0, 0.5)]


def test_launchpad_poly_and_channel_pressure():
    device = LaunchpadX()
    seen = pressures(device)
    device.decode([0x90, 11, 100])       # bottom-left pad of the 8x8 area: grid (0, 0)
    device.decode([0x90, 22, 100])
    device.decode([0xA0, 11, 127])
    device.decode([0xD0, 64])
    assert seen == [(0, 0, 1.0), (0, 0, 0.504), (1, 1, 0.504)]


def test_launchpad_pressure_without_side_buttons():
    device = LaunchpadProMK3(side_buttons = False)
    seen = pressures(device)
    device.decode([0x90, 11, 100])
    device.decode([0xA0, 11, 127])
    assert seen == [(0, 0, 1.0)]


def test_mini_mk3_ignores_aftertouch_messages():
    device = LaunchpadMiniMK3()
    device.decode([0x90, 11, 127])
    device.decode([0xD0, 64])


def test_push2_pressure():
    device = Push2()
    seen = pressures(device)
    device.decode([0x90, 36 + 9, 100])
    device.decode([0xA0, 36 + 9, 127])
    device.decode([0xD0, 0])
    assert seen == [(1, 1, 1.0), (1, 1, 0.0)]


def test_pressure_reaches_the_widget():
    surface = Surface(9, 9)
    device = LaunchpadX()
    surface.add_device(device)
    group = surface.add(Group(2, 2, 4, 4))
    button = group.add(Button(1, 1, 1, 1))
    seen = []
    button.on(Pressure, lambda e: seen.append((e.x, e.y, e.pressure)))
    device.set_button(3, 3, 1.0)
    device.set_pressure(3, 3, 0.25)
    assert seen == [(0, 0, 0.25)]
