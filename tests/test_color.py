import pytest

from pyxelwidgets.color import Color, Colors


def test_immutable_and_replace():
    p = Color(1, 2, 3)
    with pytest.raises(AttributeError):
        p.r = 10
    q = p.replace(r = 10, g = 20, b = 200)
    assert p.rgb == (1, 2, 3)
    assert q.rgb == (10, 20, 200)
    assert q.value == 0xFF0A14C8
    assert Color.from_value(q.value) == q


def test_shared_constants_cannot_change():
    with pytest.raises(AttributeError):
        Colors.Red.g = 255
    assert Colors.Red == Color(255, 0, 0)


def test_hashable():
    assert {Colors.Red: 'red'}[Color(255, 0, 0)] == 'red'
    assert len({Colors.Magenta, Colors.Fuchsia}) == 1


def test_clamps_out_of_range():
    assert Color(300, -5, 128, 2.0).rgba == (255, 0, 128, 255)


def test_alpha_change_matches_constructor_gamma():
    p = Color(255, 128, 64, 0.5).replace(a = 1.0)
    assert p.grgb == Color(255, 128, 64).grgb
    assert p.grgb[0] == 255


def test_float_getters_reach_one():
    assert Colors.White.frgb == (1.0, 1.0, 1.0)
    assert Colors.White.fargb == (1.0, 1.0, 1.0)
    assert Colors.White.fgrgb == (1.0, 1.0, 1.0)


@pytest.mark.parametrize('pixel', [Colors.Black, Colors.Gray, Colors.White, Colors.Invisible])
def test_hsl_achromatic(pixel):
    assert pixel.h == 0
    assert pixel.s == 0.0


def test_hsl_chromatic():
    assert Colors.Red.h == 0
    assert Colors.Lime.h == 120
    assert Colors.Blue.h == 240
    assert Colors.Red.s == 1.0


def test_gmono_spans_full_range():
    assert Colors.Black.gmono == 0
    assert Colors.White.gmono >= 250
    assert Colors.Gray.gmono < Colors.Silver.gmono < Colors.White.gmono


def test_comparisons_return_bool():
    assert (Colors.Black <= Colors.White) is True
    assert (Colors.White >= Colors.Black) is True
    assert (Colors.White <= Colors.Black) is False
    assert sorted([Colors.White, Colors.Black, Colors.Gray]) == [Colors.Black, Colors.Gray, Colors.White]


def test_minimum_maximum_blend():
    assert Color(10, 200, 30).minimum(Color(100, 20, 30)) == Color(10, 20, 30)
    assert Color(10, 200, 30).maximum(Color(100, 20, 30)) == Color(100, 200, 30)
