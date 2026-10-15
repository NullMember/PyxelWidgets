from pyxelwidgets import Button, Colors, Frame, Pressed, Surface
from pyxelwidgets.devices import Device
from pyxelwidgets.events import ControlChanged


class FakeDevice(Device):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sent = {}

    def send_pixel(self, x, y, value):
        self.sent[x, y] = value


def connected(**kwargs):
    device = FakeDevice(**kwargs)
    device.connect()
    return device


def test_two_devices_form_one_surface():
    surface = Surface(16, 8)
    left, right = connected(width = 8, height = 8), connected(width = 8, height = 8)
    surface.add_device(left, 0, 0)
    surface.add_device(right, 8, 0)
    button = surface.add(Button(7, 0, 2, 1, inactive_color = Colors.Red))
    presses = []
    button.on(Pressed, lambda e: presses.append(e.x))
    surface.update()
    assert left.sent[7, 0] == Colors.Red and right.sent[0, 0] == Colors.Red
    assert left.sent[0, 0] == Colors.Black
    right.set_button(0, 0, 1.0)
    left.set_button(7, 0, 1.0)
    assert presses == [1, 0]


def test_widgets_see_which_device_was_pressed():
    surface = Surface(4, 4)
    device = connected(width = 4, height = 4)
    surface.add_device(device)
    pads = []
    surface.root.input = lambda event: pads.append(event)
    device.set_button(1, 2, 0.5)
    assert pads[0].device is device and (pads[0].x, pads[0].y, pads[0].velocity) == (1, 2, 0.5)


def test_control_events_and_frames():
    surface = Surface(4, 4)
    device = connected(width = 4, height = 4)
    surface.add_device(device)
    seen = []
    surface.on(ControlChanged, seen.append)
    surface.on(Frame, seen.append)
    device.emit(ControlChanged(device, 'Fader_1', 0.5))
    surface.update()
    control, frame = seen
    assert (control.device, control.control, control.value) == (device, 'Fader_1', 0.5)
    assert frame.frame == 0 and frame.surface is surface


def test_holds_are_detected_by_updates():
    surface = Surface(2, 2)
    device = connected(width = 2, height = 2, held_time = 0.0)
    surface.add_device(device)
    held = []
    button = surface.add(Button(0, 0, 2, 2))
    from pyxelwidgets import Held
    button.on(Held, held.append)
    device.set_button(1, 1, 1.0)
    surface.update()
    assert [(e.x, e.y) for e in held] == [(1, 1)]


def test_force_update_resends_everything():
    surface = Surface(2, 2)
    device = connected(width = 2, height = 2)
    surface.add_device(device)
    surface.update()
    device.sent.clear()
    surface.update()
    assert device.sent == {}
    surface.force_update()
    surface.update()
    assert len(device.sent) == 4


def test_removed_device_is_unsubscribed():
    surface = Surface(2, 2)
    device = connected(width = 2, height = 2)
    surface.add_device(device)
    surface.remove_device(device)
    seen = []
    surface.root.input = seen.append
    device.set_button(0, 0, 1.0)
    assert seen == []
    assert device._event_handlers() == []


def test_reveal_shows_where_widgets_are(monkeypatch):
    import time
    from pyxelwidgets import Button, Colors, Fader, Group, Pages, Surface
    from pyxelwidgets.devices import Device
    from pyxelwidgets.parser import Parser

    class Screen(Device):
        grid = (4, 4)
        def send_pixel(self, x, y, value):
            pass
    surface = Surface(4, 4)
    screen = Screen()
    screen.connect()
    surface.add_device(screen)
    group = surface.add(Group(0, 0, 4, 4))
    group.add(Fader(0, 0, 1, 4))
    group.add(Button(2, 2, 2, 2, visible = False))
    pages = surface.add(Pages(1, 0, 3, 2, selector = Pages.Selector.Bottom))
    pages.add(Button(0, 1, 1, 1))
    now = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])
    surface.reveal(2)
    surface.update()
    color = lambda x, y: tuple(int(v) for v in screen.buffer[x, y][:3])
    # Fader red, the Pages (strip and content) lime, its shown button blue; the hidden button nothing
    assert color(0, 3) == (255, 0, 0) and color(1, 0) == (0, 255, 0) and color(1, 1) == (0, 0, 255) and color(3, 3) == (0, 0, 0)
    now[0] += 3
    surface.update()
    assert color(0, 3) == tuple(int(v) for v in surface.buffer[0, 3][:3])
    # Pressed again while showing: stops
    surface.reveal(2)
    surface.reveal(2)
    assert surface._revealed is None
    # A layout binding action
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 4, 'height': 4}, 'widgets': [],
              'devices': [{'type': 'novation.LaunchpadMiniMK3', 'options': {'side_buttons': False}}],
              'bindings': [{'device': 0, 'control': 'Top1', 'action': 'surface.reveal'}]}
    ui = Parser(layout, devices = False)
    assert [b.target for b in ui.bind([screen], object(), widgets = False)] == [ui.surface.reveal]


def test_test_pattern_replaces_the_widgets_on_one_device():
    from pyxelwidgets import Button, Colors, Surface, buffer
    from pyxelwidgets.devices import Device

    class Screen(Device):
        grid = (2, 2)
        def send_pixel(self, x, y, value):
            pass
    surface = Surface(4, 2)
    left, right = Screen(), Screen()
    for device, x in ((left, 0), (right, 2)):
        device.connect()
        surface.add_device(device, x, 0)
    surface.add(Button(0, 0, 4, 2, value = True, active_color = Colors.Red))
    surface.test_pattern(left, buffer.new(2, 2, Colors.Blue))
    surface.update()
    assert tuple(left.buffer[0, 0][:3]) == (0, 0, 255) and tuple(right.buffer[0, 0][:3]) == (255, 0, 0)
    surface.test_pattern(left, None)
    surface.update()
    assert tuple(left.buffer[0, 0][:3]) == (255, 0, 0)
