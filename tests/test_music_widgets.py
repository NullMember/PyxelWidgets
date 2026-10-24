"""Note widgets: velocity options, Keyboard, Sequencer step data and the melodic and generative widgets."""

import random

import pytest

from pyxelwidgets import Color, Colors, Keyboard, NoteOff, NoteOn, Sequencer, StepEnded, StepPlayed, Transport
from pyxelwidgets.widgets import DrumPads, Follow, Root, Scale, VelocityCurve, scale_notes


def pulses(transport, count):
    for _ in range(count):
        transport.pulse()


def notes(widget):
    played = []
    widget.on(NoteOn, lambda e: played.append(('on', e.note, round(e.velocity, 3))))
    widget.on(NoteOff, lambda e: played.append(('off', e.note)))
    return played


# Scales

def test_scales_are_shared():
    assert Keyboard.Scale is Scale and Keyboard.Root is Root
    assert scale_notes(Scale.MajorPentatonic, Root.A)[:5] == [1, 4, 6, 9, 11]
    assert len(scale_notes(Scale.Chromatic, Root.C)) == 128


# Velocity options

@pytest.mark.parametrize('curve, hit, expected', [
    (VelocityCurve.Linear, 0.25, 0.25), (VelocityCurve.Soft, 0.25, 0.5), (VelocityCurve.Hard, 0.5, 0.25),
    (VelocityCurve.Fixed, 0.1, 0.8)])
def test_velocity_curves(curve, hit, expected):
    pads = DrumPads(0, 0, 2, 2, velocity_curve = curve, fixed_velocity = 0.8)
    played = notes(pads)
    pads.press(0, 0, hit)
    assert played == [('on', 36, expected)]


def test_velocity_random_stays_a_note_on():
    pads = DrumPads(0, 0, 1, 1, velocity_random = 1.0)
    pads._random = random.Random(1)
    played = notes(pads)
    for _ in range(50):
        pads.tap(0, 0, 0.1)
    velocities = {event[2] for event in played if event[0] == 'on'}
    assert len(velocities) > 10 and all(0 < velocity <= 1 for velocity in velocities)


def test_velocity_options_are_checked():
    for options in ({'fixed_velocity': 0}, {'fixed_velocity': 1.5}, {'velocity_random': -0.1}, {'velocity_random': 2}):
        with pytest.raises(ValueError):
            Keyboard(0, 0, 4, 4, **options)


# Keyboard

def test_keyboard_transpose_and_held_notes_end_after_a_layout_change():
    keyboard = Keyboard(0, 0, 8, 1, octave = 4, transpose = 2)
    played = notes(keyboard)
    keyboard.press(0, 0, 1.0)
    # The layout moves while the pad is held: the note played still ends
    keyboard.configure(octave = 5)
    keyboard.release(0, 0, 0.0)
    keyboard.tap(0, 0, 1.0)
    assert played == [('on', 50, 1.0), ('off', 50), ('on', 62, 1.0), ('off', 62)]


def test_keyboard_in_key_fourths():
    # Push-like: only the key's notes, each row a fourth (3 scale notes) above the one below
    keyboard = Keyboard(0, 0, 8, 2, type = Keyboard.Type.DiatonicVertical, octave = 4)
    assert [int(keyboard.notes[x, 0]) for x in range(4)] == [48, 50, 52, 53]
    assert int(keyboard.notes[0, 1]) == 53


# Sequencer step data

def test_sequencer_press_turns_on_with_velocity_and_release_turns_off():
    sequencer = Sequencer(0, 0, 4, 1)
    sequencer.press(1, 0, 0.5)
    sequencer.release(1, 0)
    assert sequencer.state[1, 0] and sequencer.velocities[1, 0] == 0.5
    sequencer.press(1, 0, 1.0)
    assert sequencer.state[1, 0]
    sequencer.release(1, 0)
    assert not sequencer.state[1, 0]


def test_sequencer_edits_held_steps():
    sequencer = Sequencer(0, 0, 4, 1, note = 40)
    sequencer.press(0, 0)
    sequencer.press(2, 0)
    sequencer.release(0, 0)
    sequencer.release(2, 0)
    # Held active steps stay on when edited
    sequencer.press(0, 0)
    sequencer.press(2, 0)
    sequencer.set_velocity(0.25)
    sequencer.set_note(60)
    sequencer.release(0, 0)
    sequencer.release(2, 0)
    assert sequencer.state[0, 0] and sequencer.state[2, 0]
    # Without held steps, the last one pressed
    sequencer.set_velocity(0.75)
    played = []
    sequencer.on(StepPlayed, lambda e: played.append((e.step, e.active, e.velocity, e.note)))
    for step in range(3):
        sequencer.play(step)
    assert played == [(0, True, 0.25, 60), (1, False, 0.0, 40), (2, True, 0.75, 60)]
    ended = []
    sequencer.on(StepEnded, lambda e: ended.append((e.step, e.note)))
    sequencer.silence()
    assert ended == [(2, 60)]
    sequencer.set_note(-1)
    assert sequencer.note_of(2) == 40


def test_sequencer_probability():
    sequencer = Sequencer(0, 0, 1, 1)
    sequencer._random = random.Random(2)
    sequencer.press(0, 0)
    sequencer.set_probability(0.5)
    played = []
    sequencer.on(StepPlayed, lambda e: played.append(e.active))
    for _ in range(200):
        sequencer.play(0)
    assert 60 < played.count(True) < 140


def test_sequencer_ratchets():
    transport = Transport(sync = True)
    sequencer = Sequencer(0, 0, 2, 1, gate = 1.0)
    sequencer.press(0, 0)
    sequencer.set_ratchets(3)
    events = []
    sequencer.on(StepPlayed, lambda e: events.append((transport.tick, 'played', e.step, round(e.gate, 3))))
    sequencer.on(StepEnded, lambda e: events.append((transport.tick, 'ended', e.step)))
    transport.every(sequencer.rate, sequencer.tick, divisions = sequencer.divisions)
    transport.play()
    pulses(transport, 7)
    # Three hits in a 16th (24 ticks), each a third of the gate
    assert events == [(0, 'played', 0, 0.333), (8, 'ended', 0), (8, 'played', 0, 0.333), (16, 'ended', 0),
                      (16, 'played', 0, 0.333), (24, 'ended', 0), (24, 'played', 1, 0.0)]


@pytest.mark.parametrize('direction, expected', [
    (Sequencer.Direction.Forward, [0, 1, 2, 0, 1, 2, 0]),
    (Sequencer.Direction.Backward, [2, 1, 0, 2, 1, 0, 2]),
    (Sequencer.Direction.PingPong, [0, 1, 2, 1, 0, 1, 2])])
def test_sequencer_directions_over_its_length(direction, expected):
    # By the transport's count, and one by one (advance)
    sequencer = Sequencer(0, 0, 4, 1, direction = direction, length = 3)
    assert [sequencer._order(count) for count in range(7)] == expected
    sequencer.configure(step = expected[0])
    played = [sequencer.step]
    for _ in range(6):
        sequencer.advance()
        played.append(sequencer.step)
    assert played == expected


def test_sequencer_random_direction_stays_within_length():
    sequencer = Sequencer(0, 0, 8, 1, direction = Sequencer.Direction.Random, length = 5)
    sequencer._random = random.Random(4)
    steps = set()
    for _ in range(100):
        sequencer.advance()
        steps.add(sequencer.step)
    assert steps == {0, 1, 2, 3, 4}


def test_sequencer_draws_velocity_and_steps_past_its_length():
    sequencer = Sequencer(0, 0, 4, 1, length = 2, step = 3, active_color = Colors.White, follow = Follow.Off, page = 0)
    sequencer.play(0)
    sequencer.press(1, 0, 0.0)
    sequencer.press(2, 0, 1.0)
    sequencer.render()
    assert Color.from_array(sequencer.buffer[1, 0]) == Colors.White * 0.25
    assert Color.from_array(sequencer.buffer[2, 0]) == Colors.White * 0.25


def test_sequencer_keeps_steps_when_steps_change():
    sequencer = Sequencer(0, 0, 4, 1)
    sequencer.press(3, 0, 0.5)
    sequencer.steps = 12
    assert sequencer.pages == 3 and sequencer.state[3, 0] and sequencer.velocities[3, 0] == 0.5
    state = sequencer.save_state()
    other = Sequencer(0, 0, 4, 1, steps = 12)
    other.load_state(state)
    assert other.velocities[3, 0] == 0.5


# PianoRoll

from pyxelwidgets import (Arpeggiator, Automaton, ButtonGroup, Changed, ChordPads, Euclidean, Fader, MeterBank, PageChanged,
                          PianoRoll, PresetRecalled, Presets, Stepper, TapTempo, TempoTapped, Tracker, XY, Group)
from pyxelwidgets.events import PadHeld, PadPressed, PadReleased, RowPlayed
from pyxelwidgets.widgets import euclidean, parse_rule


def test_piano_roll_rows_follow_the_scale():
    roll = PianoRoll(0, 0, 4, 4, octave = 4, scale = Scale.MinorPentatonic, root = Root.A)
    assert roll.rows() == [57, 60, 62, 64]
    roll.configure(row = 2)
    assert roll.rows() == [62, 64, 67, 69]
    roll.configure(row = -100)
    assert roll.rows()[0] == 0


def test_piano_roll_adds_stretches_and_deletes_notes():
    roll = PianoRoll(0, 0, 8, 2, octave = 4)
    roll.press(1, 0, 0.5)
    roll.press(4, 0)                  # held start, then further along: longer
    roll.release(4, 0)
    roll.release(1, 0)
    assert roll.notes == {(1, 48): [4, 0.5]}
    roll.tap(3, 0)                    # a note's pad: deleted
    assert roll.notes == {}
    roll.tap(2, 1)
    roll.press(2, 1)                  # held to edit: kept
    roll.set_velocity(0.25)
    roll.release(2, 1)
    assert roll.notes == {(2, 50): [1, 0.25]}


def test_piano_roll_plays_notes_for_their_length():
    roll = PianoRoll(0, 0, 4, 2, steps = 4, octave = 4)
    roll.add_note(0, 48, 2, 0.5)
    roll.add_note(1, 50, 1)
    roll.add_note(3, 48, 1)
    played = notes(roll)
    for step in range(5):
        roll.play(step)
    roll.silence()
    assert played == [('on', 48, 0.5), ('on', 50, 1.0), ('off', 48), ('off', 50), ('on', 48, 1.0), ('off', 48),
                      ('on', 48, 0.5), ('off', 48)]


def test_piano_roll_pages_and_state():
    roll = PianoRoll(0, 0, 4, 2, steps = 8)
    pages = []
    roll.on(PageChanged, lambda e: pages.append(e.page))
    roll.play(5)
    assert roll.page == 1 and pages == [1]
    roll.tap(0, 0)
    assert (4, roll.rows()[0]) in roll.notes
    other = PianoRoll(0, 0, 4, 2, steps = 8)
    other.load_state(roll.save_state())
    assert other.notes == roll.notes and other.step == 5
    roll.render()


def test_page_shown_tells_the_ends_for_page_buttons():
    from pyxelwidgets import Button, Colors, PageShown, Pages, Sequencer
    from pyxelwidgets.link import Condition, Link
    from pyxelwidgets.message import Source
    roll = PianoRoll(0, 0, 8, 8, steps = 32, follow = Follow.Off)
    shown = []
    roll.on(PageShown, lambda e: shown.append((e.page, e.first, e.last)))
    previous, following = Button(0, 0, 1, 1), Button(1, 0, 1, 1)
    for button, end in ((previous, 'first'), (following, 'last')):
        Link(roll, button, 'inactive_color', Condition(Source(end), '==', 1, then = Colors.Black, otherwise = Colors.White),
             on = PageShown)
    for _ in range(4):
        roll.next_page()
    # Stops at the last page
    assert roll.page == 3 and shown == [(1, False, False), (2, False, False), (3, False, True)]
    assert following.inactive_color == Colors.Black and previous.inactive_color == Colors.White
    for _ in range(4):
        roll.previous_page()
    assert roll.page == 0 and previous.inactive_color == Colors.Black and following.inactive_color == Colors.White
    # Fewer pages make another the last; playing doesn't move the view without follow
    roll.configure(steps = 8)
    assert shown[-1] == (0, True, True)
    roll.play(10)
    assert shown[-1] == (0, True, True)
    # Following the playing step, the other paged widgets
    sequencer = Sequencer(0, 0, 4, 4, steps = 32)
    sequencer.on(PageShown, lambda e: shown.append(('sequencer', e.page, e.last)))
    sequencer.play(20)
    assert shown[-1] == ('sequencer', 1, True)
    tracker = Tracker(0, 0, 4, 4, bars = 8, pages = 3)
    tracker.on(PageShown, lambda e: shown.append(('tracker', e.page, e.last)))
    tracker.play(17)
    assert shown[-1] == ('tracker', 2, True)
    pages = Pages(0, 0, 4, 4)
    pages.on(PageShown, lambda e: shown.append(('pages', e.page, e.first, e.last)))
    pages.add(Group(0, 0, 4, 3))
    pages.add(Group(0, 0, 4, 3))
    pages.next_page()
    pages.next_page()
    assert shown[-3:] == [('pages', 0, True, True), ('pages', 0, True, False), ('pages', 1, False, True)]


def test_piano_roll_scrolls_a_column_at_a_time():
    from pyxelwidgets import PageShown
    roll = PianoRoll(0, 0, 4, 2, steps = 10, follow = Follow.Off)
    shown = []
    roll.on(PageShown, lambda e: shown.append((e.page, e.first, e.last)))
    roll.scroll_forward()
    assert roll.column == 1 and shown == [(0, False, False)]
    roll.tap(0, 0)
    assert (1, roll.rows()[0]) in roll.notes
    # The last page ends at the last step
    roll.next_page()
    assert roll.column == 4 and roll.page == 1
    roll.next_page()
    assert roll.column == 6 and roll.page == 2 and shown[-1] == (2, False, True)
    roll.scroll_forward()
    roll.next_page()
    assert roll.column == 6
    # Back a page: the start of the page it's scrolled into
    roll.scroll_back()
    roll.previous_page()
    assert roll.column == 4
    roll.page = 2
    assert roll.column == 6
    roll.configure(column = 3)
    assert roll.column == 3 and roll.page == 0
    # Pages a screen apart turn with the playing step
    roll.configure(follow = Follow.Page)
    roll.play(5)
    assert roll.column == 4
    roll.play(9)
    assert roll.column == 6
    other = PianoRoll(0, 0, 4, 2, steps = 10)
    other.load_state(roll.save_state())
    assert other.column == 6


def test_follow_playhead_keeps_the_step_in_the_middle():
    roll = PianoRoll(0, 0, 4, 2, steps = 10, follow = Follow.Playhead)
    columns = []
    for step in range(10):
        roll.play(step)
        columns.append(roll.column)
        roll.render()
        # The playing column is lit
        assert (roll.buffer[step - roll.column, 1] == roll.current_color).all()
    # The step one left of the middle (more ahead), never past the ends
    assert columns == [0, 0, 1, 2, 3, 4, 5, 6, 6, 6]
    # Sequencer rows go up the same way
    sequencer = Sequencer(0, 0, 2, 4, steps = 16, follow = Follow.Playhead)
    rows = []
    for step in range(16):
        sequencer.play(step)
        rows.append(sequencer.row)
    assert rows == [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 4, 4, 4, 4]
    assert sequencer.pages == 2 and sequencer.page == 1
    sequencer.render()
    # Step 15 (row 7) is on the top pad row
    assert (sequencer.buffer[1, 3] == sequencer.current_color).all()


def test_sequencer_scrolls_a_row_at_a_time():
    sequencer = Sequencer(0, 0, 4, 2, steps = 16, follow = Follow.Off)
    assert sequencer.pages == 2 and sequencer.row == 0
    sequencer.scroll_forward()
    sequencer.press(2, 0, 1.0)              # row 1: step 6
    sequencer.release(2, 0)
    assert sequencer.state[sequencer._cell(6)] and sequencer.row == 1
    sequencer.next_page()
    assert sequencer.row == 2 and sequencer.page == 1
    sequencer.scroll_forward()
    assert sequencer.row == 2
    sequencer = Sequencer(0, 0, 4, 2, steps = 16, row = 1, page = 1)
    assert sequencer.row == 1
    sequencer.play(14)
    assert sequencer.row == 2


# ChordPads

def test_chord_pads_play_chords_in_key():
    pads = ChordPads(0, 0, 7, 8, octave = 4)
    played = notes(pads)
    pads.press(0, 0)                  # I triad: C E G
    pads.press(4, 1)                  # V seventh: G B D F, G already sounds
    pads.release(0, 0)
    pads.release(4, 1)
    assert [event[:2] for event in played] == [('on', 48), ('on', 52), ('on', 55), ('on', 59), ('on', 62), ('on', 65),
                                               ('off', 48), ('off', 52), ('off', 55), ('off', 59), ('off', 62), ('off', 65)]
    assert pads.chord_at(1, 0) == [50, 53, 57]          # ii: D minor
    assert pads.chord_at(0, 2) == [52, 55, 60]          # first inversion
    pads.render()


# Arpeggiator

def test_arpeggiator_modes_and_octaves():
    arp = Arpeggiator(0, 0, 7, 2, octave = 4, clock = __import__('pyxelwidgets').Clock.Off)
    arp.press(0, 0)
    arp.press(4, 0)
    arp.press(2, 0)
    assert arp.sequence() == [48, 52, 55]
    arp.configure(mode = Arpeggiator.Mode.Played)
    assert arp.sequence() == [48, 55, 52]
    arp.configure(mode = Arpeggiator.Mode.UpDown, octaves = 2)
    assert arp.sequence() == [48, 52, 55, 60, 64, 67, 64, 60, 55, 52]
    arp.configure(mode = Arpeggiator.Mode.Down, octaves = 1)
    played = notes(arp)
    arp.advance()
    arp.advance()
    arp.release(0, 0)
    arp.release(2, 0)
    arp.release(4, 0)
    assert [event[:2] for event in played] == [('on', 55), ('off', 55), ('on', 52), ('off', 52)]


def test_arpeggiator_gates_on_the_transport_and_latch():
    transport = Transport(sync = True)
    arp = Arpeggiator(0, 0, 7, 1, octave = 4, gate = 0.5, latch = True)
    arp.press(0, 0)
    arp.press(2, 0)
    arp.release(0, 0)
    arp.release(2, 0)
    assert arp.held == [48, 52]
    events = []
    arp.on(NoteOn, lambda e: events.append((transport.tick, 'on', e.note)))
    arp.on(NoteOff, lambda e: events.append((transport.tick, 'off', e.note)))
    transport.every(arp.rate, arp.tick, divisions = arp.divisions)
    transport.play()
    pulses(transport, 13)
    assert events == [(0, 'on', 48), (12, 'off', 48), (24, 'on', 52), (36, 'off', 52), (48, 'on', 48)]
    # Latched: a new press after letting go starts new notes
    arp.tap(1, 0)
    assert arp.held == [50]
    arp.configure(latch = False)
    assert arp.held == []


def test_arpeggiator_takes_notes_from_links():
    arp = Arpeggiator(0, 0, 4, 1)
    arp.add(60)
    arp.add(64)
    arp.remove(60)
    assert arp.held == [64]


# Euclidean

def test_euclidean_patterns():
    assert euclidean(3, 8) == [True, False, False, True, False, False, True, False]
    assert euclidean(3, 8, 1) == [False, True, False, False, True, False, False, True]
    assert euclidean(0, 4) == [False] * 4 and euclidean(9, 4) == [True] * 4


def test_euclidean_pads_set_hits_rotation_and_length():
    euc = Euclidean(0, 0, 8, 2, length = 4)
    euc.tap(2, 0)
    assert euc.pulses[0] == 3 and euc.pattern(0) == [True, False, True, True]
    euc.tap(2, 0)
    assert euc.pulses[0] == 0
    euc.tap(6, 1)                     # past the row's end: longer
    assert euc.row_length(1) == 7
    euc.tap(1, 1)
    euc.press(0, 1)
    euc.press(2, 1)                   # held, then two along: turned by 2
    euc.release(2, 1)
    euc.release(0, 1)
    assert euc.rotations[1] == 2 and euc.pulses[1] == 2
    euc.set_length(3)
    assert euc.row_length(1) == 3


def test_euclidean_plays_rows_as_notes():
    euc = Euclidean(0, 0, 4, 2, note = 36)
    euc.pulses[:] = [2, 1]
    played = notes(euc)
    for count in range(3):
        euc.play(count)
    assert [event[:2] for event in played] == [('on', 36), ('on', 37), ('off', 36), ('off', 37), ('on', 36)]
    euc.render()


# Automaton

def test_automaton_life_and_born_notes():
    life = Automaton(0, 0, 5, 5, reseed = False, scale = Scale.Major, octave = 4)
    for x in (1, 2, 3):
        life.cells[x, 2] = True       # a blinker
    played = notes(life)
    life.advance()
    assert [tuple(map(int, cell)) for cell in sorted(map(tuple, numpy_argwhere(life.cells)))] == [(2, 1), (2, 2), (2, 3)]
    assert [event[1] for event in played if event[0] == 'on'] == [50, 53]   # born on rows 1 and 3
    life.advance()
    assert life.cells[1, 2] and life.cells[3, 2]
    assert ('off', 50) in played
    with pytest.raises(ValueError):
        Automaton(0, 0, 4, 4, rule = 'X')
    assert parse_rule('B36/S23') == ({3, 6}, {2, 3})


def numpy_argwhere(array):
    import numpy
    return numpy.argwhere(array)


def test_automaton_reseeds_when_everything_dies():
    life = Automaton(0, 0, 4, 4, reseed = True, density = 0.5)
    life._random = random.Random(5)
    life.cells[0, 0] = True
    life.advance()
    assert life.cells.any()


# TapTempo

def test_tap_tempo():
    now = [0.0]
    tap = TapTempo(0, 0, 1, 1, clock = lambda: now[0])
    tempos = []
    tap.on(TempoTapped, lambda e: tempos.append(e.bpm))
    for _ in range(4):
        tap.tap(0, 0)
        now[0] += 0.5
    assert tempos == [120.0, 120.0, 120.0]
    now[0] += 5
    tap.tap(0, 0)
    now[0] += 0.25
    tap.tap(0, 0)
    assert tempos[-1] == 240.0 and tap.bpm == 240.0
    tap.render()


def test_tap_tempo_links_to_the_transport_tempo():
    from pyxelwidgets.parser import Parser
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 2, 'height': 1},
              'widgets': [{'type': 'TapTempo', 'name': 'tap', 'x': 0, 'y': 0, 'width': 1, 'height': 1}],
              'links': [{'widget': 'tap', 'on': 'TempoTapped', 'action': 'transport.tempo', 'value': {'source': 'bpm'}}]}
    ui = Parser(layout, devices = False)
    transport = Transport()
    ui.link(transport, widgets = False)
    ui['tap'].emit(TempoTapped(ui['tap'], 93.5))
    assert transport.bpm == 93.5
    transport.close()


# Stepper

def test_stepper_steps_wraps_and_jumps():
    stepper = Stepper(0, 0, 6, 1, minimum = 1, maximum = 5)
    changes = []
    stepper.on(Changed, lambda e: changes.append(stepper.number))
    stepper.tap(5, 0)
    stepper.tap(5, 0)
    stepper.tap(0, 0)
    assert changes == [2, 3, 2]
    stepper.tap(4, 0)                 # the last pad between: the maximum
    assert stepper.number == 5 and stepper.value == 1.0
    stepper.tap(5, 0)
    assert stepper.number == 5
    stepper.configure(wrap = True)
    stepper.tap(5, 0)
    assert stepper.number == 1
    stepper.render()


def test_stepper_repeats_while_held():
    now = [0.0]
    stepper = Stepper(0, 0, 3, 1, maximum = 10, repeat = 0.1, clock = lambda: now[0])
    stepper.press(2, 0)
    stepper.hold(2, 0)
    for _ in range(3):
        now[0] += 0.1
        stepper.render()
    stepper.release(2, 0)
    now[0] += 0.1
    stepper.render()
    assert stepper.number == 4


def test_stepper_pads_between_follow_a_point_of_light():
    stepper = Stepper(0, 0, 4, 1, maximum = 4, active_color = Color(200, 200, 200))
    shown = []
    for number in range(5):
        stepper.set_number(number)
        stepper.render()
        shown.append(tuple(int(stepper.buffer[x, 0, 0]) for x in (1, 2)))
    # The point at -0.5, 0, 0.5, 1 and 1.5 pads
    assert shown == [(100, 0), (200, 0), (100, 100), (0, 200), (0, 100)]
    stepper.configure(width = 2)
    shown = []
    for number in range(5):
        stepper.set_number(number)
        stepper.render()
        shown.append(tuple(int(stepper.buffer[x, 0, 0]) for x in (0, 1)))
    assert shown == [(100, 0), (200, 0), (100, 100), (0, 200), (0, 100)]


# MeterBank

def test_meter_bank_levels_from_feedback():
    bank = MeterBank(0, 0, 4, 4, clock = lambda: 0.0)
    bank.receive({'x': 2, 'value': 0.5})
    bank.receive({'cell': 0, 'value': 1.0})
    assert bank.levels == [1.0, 0.0, 0.5, 0.0]
    bank.render()
    assert Color.from_array(bank.buffer[2, 1]) == bank.active_color
    assert Color.from_array(bank.buffer[2, 2]) == bank.inactive_color
    assert Color.from_array(bank.buffer[0, 3]) == bank.danger_color
    bank.configure(width = 6)
    assert len(bank.levels) == 6


def test_meters_with_decay_fade_hits_away():
    from pyxelwidgets import Meter
    now = [0.0]
    meter = Meter(0, 0, 1, 4, decay = 0.5, hold = 0.0, clock = lambda: now[0])
    meter.configure(value = 0.8)
    meter.render()
    assert meter.level == 0.8
    now[0] = 0.2
    meter.render()
    assert meter.value == pytest.approx(0.4) and meter.level == pytest.approx(0.4)
    now[0] = 1.0
    meter.render()
    assert meter.value == 0.0 and not meter.buffer[:, :, :3].any()
    bank = MeterBank(0, 0, 2, 4, decay = 1.0, clock = lambda: now[0])
    bank.set_level(1, 1.0)
    now[0] = 1.25
    bank.render()
    assert bank.levels == [0.0, 0.75]
    # Without decay a value stays
    still = Meter(0, 0, 1, 4, clock = lambda: now[0])
    still.configure(value = 0.5)
    now[0] = 9.0
    still.render()
    assert still.value == 0.5


# Presets

def test_presets_store_and_recall_with_pads():
    presets = Presets(0, 0, 4, 4)
    fader = presets.add(Fader(0, 0, 1, 3, name = 'fader'))
    inner = presets.add(Group(1, 0, 3, 3, name = 'inner'))
    switch = inner.add(ButtonGroup(0, 0, 3, 1, name = 'choice'))
    pad = lambda kind, x, y = 3: presets.input(kind(None, x, y, 1.0))
    fader.value = 0.7
    switch.tap(2, 0)
    pad(PadPressed, 0)
    pad(PadReleased, 0)               # an empty slot stores
    fader.value = 0.1
    switch.tap(0, 0)
    sent = []
    fader.on(Changed, lambda e: sent.append(e.value))
    recalled = []
    presets.on(PresetRecalled, lambda e: recalled.append(e.slot))
    pad(PadPressed, 0)
    pad(PadReleased, 0)               # a stored one comes back
    assert fader.value == 0.7 and switch.state[2, 0] and not switch.state[0, 0]
    assert sent == [0.7] and recalled == [0]
    # Holding stores over it
    fader.value = 0.3
    pad(PadPressed, 0)
    pad(PadHeld, 0)
    pad(PadReleased, 0)
    fader.value = 0.9
    presets.recall(0)
    assert fader.value == 0.3 and recalled == [0, 0]
    presets.render()
    assert Color.from_array(presets.buffer[0, 3]) == presets.current_color


def test_widget_states_as_json():
    import json
    from pyxelwidgets.widgets import Sequencer, state_from_json, state_to_json
    sequencer = Sequencer(0, 0, 4, 2)
    sequencer.press(1, 1)
    xy = XY(0, 0, 4, 4)
    xy.value = (0.25, 0.75)
    roll = PianoRoll(0, 0, 4, 4)
    roll.press(0, 0)
    roll.release(0, 0)
    for widget, other in ((sequencer, Sequencer(0, 0, 4, 2)), (xy, XY(0, 0, 4, 4)), (roll, PianoRoll(0, 0, 4, 4))):
        data = json.loads(json.dumps(state_to_json(widget.save_state())))
        other.load_state(state_from_json(data))
        restored, saved = other.save_state(), widget.save_state()
        assert json.dumps(state_to_json(restored)) == json.dumps(state_to_json(saved))
    assert xy.save_state()['value'] == state_from_json(state_to_json(xy.save_state()))['value'] == (0.25, 0.75)


def test_presets_option_takes_what_stored_gives():
    import json
    def build(**options):
        presets = Presets(0, 0, 4, 4, **options)
        inner = presets.add(Group(1, 0, 3, 3, name = 'inner'))
        return presets, presets.add(Fader(0, 0, 1, 3, name = 'fader')), inner.add(ButtonGroup(0, 0, 3, 1, name = 'choice'))
    presets, fader, choice = build()
    fader.value = 0.6
    choice.tap(1, 0)
    presets.store(2)
    stored = json.loads(json.dumps(presets.stored()))
    assert set(stored) == {'2'} and set(stored['2']) == {'fader', 'inner/choice'}
    again, fader, choice = build(presets = stored)
    again.recall(2)
    assert fader.value == 0.6 and choice.state[1, 0]
    # Links and configure take the layout form too
    again.configure(presets = {})
    assert again.presets == {}
    again.configure(presets = stored)
    assert set(again.presets) == {2}


# Improvements to existing widgets

def test_fader_slew_glides_by_time():
    now = [0.0]
    fader = Fader(0, 0, 1, 4, mode = Fader.Mode.Magnitude, slew = 2.0, clock = lambda: now[0])
    values = []
    fader.on(Changed, lambda e: values.append(e.value))
    fader.press(0, 3)                 # to 1.0, over 2 s for the whole range
    now[0] += 0.5
    fader.render()
    assert fader.value == 0.25
    now[0] += 5
    fader.render()
    assert fader.value == 1.0 and values == [0.25, 1.0]


def test_button_group_allow_none():
    group = ButtonGroup(0, 0, 3, 1, allow_none = True)
    assert not group.state.any()
    group.tap(1, 0)
    group.tap(1, 0)
    assert not group.state.any()
    group.tap(2, 0)
    group.tap(0, 0)
    assert group.state.tolist() == [[True], [False], [False]]


def test_xy_spring():
    xy = XY(0, 0, 4, 4, spring = True, rest = (0.5, 0.0))
    values = []
    xy.on(Changed, lambda e: values.append(e.value))
    xy.press(3, 3)
    xy.press(0, 0)
    xy.release(3, 3)
    assert xy.value != (0.5, 0.0)
    xy.release(0, 0)
    assert xy.value == (0.5, 0.0) and values[-1] == (0.5, 0.0)


def test_tracker_plays_notes():
    tracker = Tracker(0, 0, 3, 4, bars = 4, note = 40)
    tracker.tap(0, 3, 0.5)            # row 0, column 0
    tracker.tap(2, 3)
    tracker.press(2, 3)               # held and edited: kept on
    tracker.set_note(60)
    tracker.release(2, 3)
    rows = []
    tracker.on(RowPlayed, lambda e: rows.append((e.row, e.columns, e.notes)))
    played = notes(tracker)
    tracker.play(0)
    tracker.play(1)
    assert rows == [(0, (0, 2), (40, 60)), (1, (), ())]
    assert played == [('on', 40, 0.5), ('on', 60, 1.0), ('off', 40), ('off', 60)]


# The shared key

KEY_LAYOUT = {
    'format': 'pyxelwidgets.layout', 'version': 5, 'surface': {'width': 8, 'height': 5},
    'key': {'root': 'D', 'scale': 'Dorian'},
    'widgets': [
        {'type': 'ButtonGroup', 'name': 'pads', 'x': 0, 'y': 0, 'width': 4, 'height': 1, 'options': {'mode': 'Button'}},
        {'type': 'ChordPads', 'name': 'chords', 'x': 0, 'y': 1, 'width': 8, 'height': 2, 'options': {'root': '{key.root}', 'scale': '{key.scale}'}},
        {'type': 'Keyboard', 'name': 'keys', 'x': 0, 'y': 3, 'width': 8, 'height': 2, 'options': {'root': '{key.root}', 'scale': '{key.scale}'}},
    ],
    'links': [
        {'widget': 'pads', 'on': 'Pressed', 'target': 'key', 'option': 'root', 'change': 'Add', 'value': 2},
        {'widget': 'pads', 'on': 'Pressed', 'target': 'key', 'option': 'scale', 'value': {'choose': ['Major', 'Minor', 'Dorian', 'MinorBlues'], 'by': 'x'}},
    ],
}

def test_key_options():
    from pyxelwidgets import Key
    key = Key(root = Root.E, scale = Scale.Minor)
    key.configure(root = Root.F)
    assert (key.root, key.scale, key.configured) == (Root.F, Scale.Minor, {'root': Root.F})
    with pytest.raises(TypeError):
        key.configure(root = 'F')
    with pytest.raises(TypeError):
        key.configure(octave = 3)

def test_widgets_follow_the_layout_s_key():
    from pyxelwidgets import codegen, parser
    ui = parser.Parser(KEY_LAYOUT, devices = False)
    assert all((ui[name].root, ui[name].scale) == (Root.D, Scale.Dorian) for name in ('chords', 'keys'))
    ui['pads'].tap(3, 0)                # two semitones up, blues
    ui.surface.update()
    assert all((ui[name].root, ui[name].scale) == (Root.E, Scale.MinorBlues) for name in ('chords', 'keys'))
    code = codegen.standalone(KEY_LAYOUT, run = False)
    assert 'key = Key(root = Root.D, scale = Scale.Dorian)' in code and "surface.link(pads, key, 'root', 2" in code
    namespace = {}
    exec(compile(code, 'standalone.py', 'exec'), namespace)
    namespace['pads'].tap(1, 0)
    namespace['surface'].update()
    assert (namespace['keys'].root, namespace['keys'].scale) == (Root.E, Scale.Minor)
    assert [option['name'] for option in parser.schema()['key']] == ['root', 'scale']

@pytest.mark.parametrize('change, message', [
    (lambda layout: layout.update(key = {'root': 'H'}), "key.root: .*'H'"),
    (lambda layout: layout.update(key = {'mode': 'Minor'}), 'key: unknown keys mode'),
    (lambda layout: layout['widgets'][1].update(name = 'key'), r"widgets\[1\]\.name: 'key' is taken"),
    (lambda layout: layout['widgets'][2]['options'].update(octave = '{key.octave}'), "the key has root and scale, not 'octave'"),
    (lambda layout: layout['links'][0].update(option = 'octave'), r'links\[0\]\.option: the key has the options root, scale'),
])
def test_key_errors_name_the_spot(change, message):
    import copy
    from pyxelwidgets import parser
    layout = copy.deepcopy(KEY_LAYOUT)
    change(layout)
    with pytest.raises(parser.LayoutError, match = message):
        parser.Parser(layout, devices = False)

def test_the_designer_keeps_the_key_links_changed():
    import copy
    from pyxelwidgets.designer import Preview
    preview = Preview(copy.deepcopy(KEY_LAYOUT))
    preview.ui['pads'].tap(1, 0)
    edited = copy.deepcopy(KEY_LAYOUT)
    edited['widgets'][0]['options']['mode'] = 'Switch'
    preview.load(edited)
    assert (preview.ui.key.root, preview.ui.key.scale) == (Root.E, Scale.Minor)
    # A key changed in the layout wins
    edited = copy.deepcopy(edited)
    edited['key'] = {'root': 'A', 'scale': 'Major'}
    preview.load(edited)
    assert (preview.ui.key.root, preview.ui.key.scale) == (Root.A, Scale.Major)
