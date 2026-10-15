import pytest

from pyxelwidgets import Button, Colors, Fader, Group, PageChanged, Pages, PadPressed, PadReleased, Surface
from pyxelwidgets.devices import Device


def press(widget, x, y):
    widget.input(PadPressed(None, x, y, 1.0))
    widget.input(PadReleased(None, x, y, 0.0))


def make(selector = Pages.Selector.Top):
    pages = Pages(0, 0, 4, 4, selector = selector)
    content = pages.content
    first = pages.add(Group(content.x, content.y, content.w, content.h, name = 'first'))
    second = pages.add(Group(content.x, content.y, content.w, content.h, name = 'second'))
    first.add(Button(0, 0, 1, 1, name = 'a'))
    second.add(Fader(0, 0, 1, 3, name = 'b'))
    return pages, first, second


def test_only_current_page_is_visible():
    pages, first, second = make()
    assert pages.pages == 2 and pages.current is first
    assert first.visible and not second.visible
    pages.next()
    assert pages.current is second and second.visible and not first.visible
    pages.next()
    assert pages.page == 0
    pages.previous()
    assert pages.page == 1


def test_page_changes_emit_once():
    pages, _, _ = make()
    seen = []
    pages.on(PageChanged, lambda e: seen.append(e.page))
    pages.page = 1
    pages.page = 1
    pages.page = 3
    assert seen == [1]


@pytest.mark.parametrize('selector, cells, content', [
    (Pages.Selector.Top, [(0, 3), (1, 3)], (0, 0, 4, 3)),
    (Pages.Selector.Bottom, [(0, 0), (1, 0)], (0, 1, 4, 3)),
    (Pages.Selector.Left, [(0, 3), (0, 2)], (1, 0, 3, 4)),
    (Pages.Selector.Right, [(3, 3), (3, 2)], (0, 0, 3, 4)),
    (Pages.Selector.Off, [], (0, 0, 4, 4)),
])
def test_selector(selector, cells, content):
    pages, _, _ = make(selector)
    c = pages.content
    assert (c.x, c.y, c.w, c.h) == content
    assert pages._cells() == cells
    pages.render()
    for index, cell in enumerate(cells):
        assert tuple(pages.buffer[cell][:3]) == ((255, 255, 255) if index == 0 else (48, 48, 48))
    if cells:
        press(pages, *cells[1])
        assert pages.page == 1
        pages.render()
        assert tuple(pages.buffer[cells[1]][:3]) == (255, 255, 255)


def test_input_goes_to_current_page_only():
    pages, first, second = make(Pages.Selector.Bottom)
    press(pages, 0, 1)
    assert first['a'].value == 0.0   # momentary: pressed and released
    pages.page = 1
    press(pages, 0, 3)
    assert second['b'].value > 0
    # Empty content doesn't pass presses to widgets underneath
    assert pages.input(PadPressed(None, 3, 3, 1.0))


def test_removing_pages():
    pages, first, second = make()
    pages.page = 1
    pages.remove(second)
    assert pages.page == 0 and first.visible
    pages.remove(first)
    assert pages.current is None


def test_on_surface():
    class Fake(Device):
        def send_pixel(self, x, y, color):
            pass
    surface = Surface(4, 4)
    device = Fake(width = 4, height = 4)
    device.connect()
    surface.add_device(device)
    pages, first, second = make()
    surface.add(pages)
    surface.update()
    device.set_button(1, 3, 1.0)
    assert pages.page == 1
    surface.update()
    assert tuple(surface.buffer[1, 3][:3]) == (255, 255, 255)
