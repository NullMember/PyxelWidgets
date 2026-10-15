import numpy
"""DrumPads, Meter and ClipLauncher."""

import pytest

from pyxelwidgets import (ClipLauncher, Knob, ClipQueued, ClipStarted, ClipStopped, Clock, Color, Colors, DrumPads, Meter,
                          NoteOff, NoteOn, Transport)
from pyxelwidgets.events import Changed, WidgetEvent
from pyxelwidgets.parser import load, schema, FORMAT, VERSION


def recorded(widget):
    events = []
    widget.on(WidgetEvent, lambda e: events.append(e))
    return events


def test_drum_pads_play_notes():
    pads = DrumPads(0, 0, 4, 4)
    events = recorded(pads)
    pads.press(1, 1, 0.5)
    pads.render()
    assert Color.from_array(pads.buffer[1, 1]) == Colors.Orange * 0.65
    pads.release(1, 1)
    notes = [(type(e), e.note) for e in events if isinstance(e, (NoteOn, NoteOff))]
    assert notes == [(NoteOn, 41), (NoteOff, 41)]
    # Banks move every note; notes beyond 127 are dark and silent
    pads.configure(bank = 5)
    assert pads.note_at(0, 0) == 116 and pads.note_at(3, 3) is None
    pads.press(3, 3, 1.0)
    assert not [e for e in events[4:] if isinstance(e, NoteOn)]


def test_drum_pads_show_received_notes():
    pads = DrumPads(0, 0, 4, 4, velocity = False)
    pads.receive({'note': 38, 'velocity': 0.2})
    assert pads.levels[2, 0] == 1.0
    pads.receive({'note': 38, 'velocity': 0.0})
    assert pads.levels[2, 0] == 0.0


def test_meter_zones_peak_and_falloff():
    now = [0.0]
    meter = Meter(0, 0, 1, 10, hold = 1.0, falloff = 2.0, clock = lambda: now[0])
    meter.value = 0.95
    meter.render()
    colors = [Color.from_array(meter.buffer[0, y]) for y in range(10)]
    assert colors[0] == Colors.Lime and colors[6] == Colors.Yellow and colors[9] == Colors.Red * 0.5
    meter.value = 0.0
    now[0] = 0.25
    meter.render()
    assert meter.level == pytest.approx(0.45) and meter.peak == 0.95
    # The peak stays lit above the bar
    assert Color.from_array(meter.buffer[0, 9]) == Colors.Red
    now[0] = 1.5
    meter.render()
    assert meter.level == 0.0 and meter.peak == 0.0
    horizontal = Meter(0, 0, 4, 1, direction = Meter.Direction.Horizontal, value = 0.5)
    horizontal.render()
    assert Color.from_array(horizontal.buffer[1, 0]) == Colors.Lime and Color.from_array(horizontal.buffer[2, 0]) == Colors.Black


def test_meter_takes_values_from_feedback():
    meter = Meter(0, 0, 1, 8)
    meter.receive({'value': 0.5})
    assert meter.value == 0.5 and meter.events() and not meter.interactive


def test_clips_launch_on_the_clock():
    clips = ClipLauncher(0, 0, 4, 3)
    events = recorded(clips)
    clips.press(0, 2, 1.0)                      # queued
    assert clips.queued == {0: (2, True)} and (0, 2) in clips.cell_animations
    clips.tick(1)
    assert clips.playing(0) == 2 and not clips.cell_animations
    clips.press(0, 1, 1.0)
    clips.tick(2)                               # one clip per track
    assert clips.playing(0) == 1
    clips.press(0, 1, 1.0)                      # stop
    clips.tick(3)
    assert clips.playing(0) is None
    kinds = [type(e).__name__ for e in events if not type(e).__name__.startswith(('Pressed', 'Released'))]
    assert kinds == ['ClipQueued', 'ClipStarted', 'ClipQueued', 'ClipStopped', 'ClipStarted', 'ClipQueued', 'ClipStopped']


def test_scenes_tracks_and_empty_slots():
    clips = ClipLauncher(0, 0, 3, 2, filled = False, clock = Clock.Off)
    clips.press(0, 1, 1.0)
    assert clips.playing(0) is None             # empty slot
    clips.receive({'x': 0, 'y': 1, 'value': 1.0})
    clips.receive({'x': 1, 'y': 1, 'value': 0.0})
    assert clips.playing(0) == 1 and clips.clips[1, 1] == ClipLauncher.Stopped
    clips.receive({'x': 0, 'y': 0, 'value': 0.0})
    clips.launch_scene(1)                       # the bottom row: track 0 has a clip there, the others stop
    assert clips.playing(0) == 0 and clips.playing(1) is None
    clips.launch_scene(0)
    assert clips.playing(0) == 1 and clips.playing(1) == 1
    clips.stop_track(1)
    assert clips.playing(1) is None
    clips.stop_all()
    assert clips.playing(0) is None


def test_clips_in_layouts_follow_the_transport():
    ui = load({'format': FORMAT, 'version': VERSION, 'surface': {'width': 8, 'height': 8}, 'widgets': [
        {'type': 'ClipLauncher', 'name': 'clips', 'x': 0, 'y': 0, 'width': 8, 'height': 4},
        {'type': 'Button', 'name': 'scene', 'x': 0, 'y': 7}],
        'links': [{'widget': 'scene', 'on': 'Pressed', 'target': 'clips', 'action': 'launch_scene', 'value': 2}]}, devices = False)
    transport = Transport()
    [subscription] = ui.attach(transport)
    assert subscription.rate == 'bar'
    ui['scene'].tap(0, 0)
    subscription.callback(1)
    assert ui['clips'].playing(5) == 1
    widgets = schema()['widgets']
    assert widgets['ClipLauncher']['actions']['launch_scene'] == 'int' and 'ClipStarted' in widgets['ClipLauncher']['events']
    assert {'note', 'bank'} <= {option['name'] for option in widgets['DrumPads']['options']}
    assert widgets['Meter']['bindable']


@pytest.mark.parametrize('size', [(3, 3), (5, 5), (3, 5), (4, 4), (4, 3), (1, 3), (1, 4)])
def test_knob_pads_turn_symmetrically(size):
    width, height = size
    knob = Knob(0, 0, width, height)
    weight = lambda x, y: knob._calc_knob_weight(knob._calc_knob_index(x, y))
    for y in range(height):
        for x in range(width):
            mirrored = (x, height - 1 - y) if width == 1 else (width - 1 - x, y)
            assert weight(x, y) == -weight(*mirrored)
    assert min(weight(x, y) for x in range(width) for y in range(height)) == -0.5
    if width == 1 and height % 2:
        assert weight(0, height // 2) == 0.0
    elif width > 1 and width % 2:
        # The middle column's pads don't turn the knob
        assert weight(width // 2, 0) == 0.0 and weight(width // 2, height - 1) == 0.0


def test_knob_middle_pads_do_nothing_and_opposite_sides_centre():
    now = [0.0]
    knob = Knob(0, 0, 3, 3, value = 0.2, clock = lambda: now[0])
    knob.press(1, 2, 1.0)
    now[0] += 0.1
    knob.render()
    knob.release(1, 2, 0.0)
    assert knob.value == 0.2
    knob.press(0, 0, 1.0)
    now[0] += 0.1
    knob.render()
    assert knob.value < 0.2
    knob.press(2, 1, 1.0)
    assert knob.value == 0.5


def test_knob_turns_by_time_not_frames():
    now = [0.0]
    changes = []
    knob = Knob(0, 0, 3, 3, value = 0.5, speed = 1.0, clock = lambda: now[0])
    knob.on(Changed, lambda e: changes.append(e.value))
    # The bottom-right pad is one of the fastest: a full turn per second
    knob.press(2, 0, 1.0)
    for _ in range(10):
        knob.render()
    assert knob.value == 0.5 and changes == []
    now[0] += 0.25
    knob.render()
    assert knob.value == pytest.approx(0.75)
    now[0] += 1.0
    knob.render()
    assert knob.value == 1.0
    # Nothing more to report at the end of the range
    count = len(changes)
    now[0] += 0.5
    knob.render()
    assert len(changes) == count
    knob.release(2, 0, 0.0)
    now[0] += 1.0
    knob.render()
    assert knob.value == 1.0


@pytest.mark.parametrize('type', list(Knob.Type))
def test_odd_knob_shows_the_middle_on_top_and_never_lights_the_bottom_middle(type):
    for value in (0.0, 0.25, 0.5, 0.75, 1.0):
        knob = Knob(0, 0, 3, 3, type = type, value = value, active_color = Colors.White)
        knob.draw()
        assert tuple(knob.buffer[1, 0]) == tuple(numpy.asarray(knob.inactive_color))
        # Mirrored values light mirrored pads (Single and Wrap aren't symmetric)
        if type in (Knob.Type.Spread, Knob.Type.Collapse):
            for x, y in ((0, 0), (0, 1), (0, 2)):
                left, right = knob.buffer[x, y].astype(int), knob.buffer[2 - x, y].astype(int)
                assert numpy.abs(left - right).max() <= 1  # pad bounds are rounded
    knob = Knob(0, 0, 3, 3, type = Knob.Type.BoostCut, value = 0.5, active_color = Colors.White)
    knob.draw()
    assert tuple(knob.buffer[1, 2]) == tuple(numpy.asarray(Colors.White))
