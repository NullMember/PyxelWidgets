import numpy
import pytest

from pyxelwidgets import Colors, Text
from pyxelwidgets.font import GLYPHS, HEIGHT, glyph, text_bitmap, text_width


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def lit(widget):
    """Rows from the top as strings, '#' where the text color is."""
    widget.render()
    return [''.join('#' if tuple(widget.buffer[x, y]) == tuple(Colors.White.rgba) else '.' for x in range(widget.rect.w))
            for y in reversed(range(widget.rect.h))]


def test_every_glyph_is_five_rows_of_equal_width():
    for char, rows in GLYPHS.items():
        assert len(rows) == HEIGHT, char
        assert len({len(row) for row in rows}) == 1, char


def test_bitmap_layout():
    assert text_width('1') == 3 and text_width('11') == 7 and text_width('') == 0
    bitmap = text_bitmap('1.')
    assert bitmap.shape == (5, 5)
    # x from the left, y from the bottom: the dot is at the bottom of the last column
    assert bitmap[4, 0] and not bitmap[4, 4]
    assert numpy.array_equal(glyph('a'), glyph('A'))
    assert numpy.array_equal(glyph('é'), glyph('?'))


def test_draws_text_centered_vertically():
    text = Text(0, 0, 4, 7, text = '7')
    assert lit(text) == ['....', '###.', '..#.', '..#.', '.#..', '.#..', '....']


@pytest.mark.parametrize('align, row', [
    (Text.Align.Left, '###....'),
    (Text.Align.Center, '..###..'),
    (Text.Align.Right, '....###'),
])
def test_alignment(align, row):
    assert lit(Text(0, 0, 7, 5, text = '7', align = align))[0] == row


def test_right_alignment_shows_the_end_when_scrolling_is_off():
    text = Text(0, 0, 3, 5, text = '17', align = Text.Align.Right, scroll = Text.Scroll.Off)
    assert lit(text)[0] == '###'


def test_scrolls_when_too_wide():
    clock = Clock()
    text = Text(0, 0, 3, 5, text = '17', speed = 2, clock = clock)
    assert text.scrolling
    first = lit(text)
    assert not text.render()
    clock.now = 0.5    # one column
    assert text.render()
    assert lit(text)[0] == first[0][1:] + '.'
    # Loops after the text, the gap, and back
    clock.now = (text_width('17') + Text.GAP) / 2
    text.render()
    assert lit(text) == first


def test_fitting_text_doesnt_scroll_unless_always():
    clock = Clock()
    text = Text(0, 0, 8, 5, text = '1', clock = clock)
    assert not text.scrolling
    text.scroll = Text.Scroll.Always
    clock.now = 1
    assert text.scrolling and text.render()


def test_changing_text_restarts_scrolling():
    clock = Clock()
    text = Text(0, 0, 3, 5, text = 'HELLO', speed = 4, clock = clock)
    clock.now = 1
    text.render()
    text.text = 'BYE'
    assert text.render() and text._offset == 0
    text.text = 120
    assert text.text == '120'


def test_transparent_background_and_passes_presses():
    from pyxelwidgets import PadPressed, Propagation
    text = Text(0, 0, 3, 5, text = '1')
    text.render()
    assert text.buffer[2, 4][3] == 0   # unlit: transparent
    assert text.propagation is Propagation.Pass
    assert not text.input(PadPressed(None, 0, 0, 1.0))
