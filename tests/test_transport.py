import fractions
import threading
import time

import pytest

import pyxelwidgets.transport
from pyxelwidgets import (PageChanged, RowPlayed, Sequencer, StepEnded, StepPlayed, TempoChanged, Tracker, Transport,
                          TransportLocated, TransportStarted, TransportStopped)
from pyxelwidgets.color import Color
from pyxelwidgets.transport import parse_rate, parse_signature
from pyxelwidgets.widgets import Follow


def pulses(transport, count):
    for _ in range(count):
        transport.pulse()


def recorder(transport, rate, **kwargs):
    calls = []
    transport.every(rate, lambda count: calls.append((count, transport.tick)), **kwargs)
    return calls


@pytest.mark.parametrize('rate, length', [
    ('1/4', fractions.Fraction(1, 4)),
    ('1/16', fractions.Fraction(1, 16)),
    ('1', 1),
    ('2', 2),
    ('3/4', fractions.Fraction(3, 4)),
    ('1/8.', fractions.Fraction(3, 16)),
    ('1/8T', fractions.Fraction(1, 12)),
    ('1/8t', fractions.Fraction(1, 12)),
    (' 1 / 16 ', fractions.Fraction(1, 16)),
    (fractions.Fraction(1, 3), fractions.Fraction(1, 3)),
    ('beat', fractions.Fraction(1, 4)),
    ('bar', 1),
])
def test_parse_rate(rate, length):
    assert parse_rate(rate) == length


def test_parse_rate_uses_signature():
    assert parse_rate('beat', (6, 8)) == fractions.Fraction(1, 8)
    assert parse_rate('bar', (6, 8)) == fractions.Fraction(3, 4)


@pytest.mark.parametrize('rate', ['', '1/0', '0', 'x', '1/4x', '-1/4', 0.25, None, True])
def test_parse_rate_rejects(rate):
    with pytest.raises(ValueError):
        parse_rate(rate)


def test_parse_signature():
    assert parse_signature([6, 8]) == (6, 8)
    for bad in ([4], (0, 4), 'x', None):
        with pytest.raises(ValueError):
            parse_signature(bad)


def test_ticks():
    transport = Transport(ppq = 96, signature = (7, 8))
    assert transport.ticks('1/16') == 24
    assert transport.ticks('1/8T') == 32
    assert transport.ticks('bar') == 7 * 48


def test_every_counts_at_rate():
    transport = Transport(sync = True, ppq = 24)
    sixteenths = recorder(transport, '1/16')
    quarters = recorder(transport, '1/4')
    transport.play()
    pulses(transport, 49)
    assert sixteenths == [(i, i * 6) for i in range(9)]
    assert quarters == [(0, 0), (1, 24), (2, 48)]


def test_nothing_plays_while_stopped():
    transport = Transport(sync = True, ppq = 24)
    calls = recorder(transport, '1/16')
    pulses(transport, 30)
    assert calls == [] and transport.tick == 0


def test_stop_and_continue():
    transport = Transport(sync = True, ppq = 24)
    calls = recorder(transport, '1/16')
    transport.play()
    pulses(transport, 8)
    transport.stop()
    pulses(transport, 8)
    assert transport.tick == 8
    transport.play()
    pulses(transport, 5)
    # Continues from tick 8: the next 16th is at tick 12
    assert calls == [(0, 0), (1, 6), (2, 12)]


def test_locate_plays_the_new_position_next():
    transport = Transport(sync = True, ppq = 24)
    calls = recorder(transport, '1/16')
    transport.play()
    pulses(transport, 3)
    transport.locate(2)  # quarter notes
    pulses(transport, 1)
    transport.locate(0.1)  # between 16ths: wait for the next one
    pulses(transport, 6)
    assert calls == [(0, 0), (8, 48), (1, 6)]


def test_locate_from_a_subscriber():
    transport = Transport(sync = True, ppq = 24)

    @transport.every('1')
    def loop(count):
        if count == 1:
            transport.locate(0)

    calls = recorder(transport, '1/4')
    transport.play()
    pulses(transport, 98)
    assert transport.tick == 1
    # Subscribers after the one that moved the position skip that tick; the new position plays next
    assert calls == [(0, 0), (1, 24), (2, 48), (3, 72), (0, 0)]


def test_offset():
    transport = Transport(sync = True, ppq = 24)
    calls = recorder(transport, '1/4', offset = '1/16')
    transport.play()
    pulses(transport, 60)
    assert calls == [(0, 6), (1, 30), (2, 54)]


def test_rate_that_is_not_a_whole_number_of_ticks():
    # A 1/64 note is 1.5 ticks at 24 ppq: calls land on the following tick
    transport = Transport(sync = True, ppq = 24)
    calls = recorder(transport, '1/64')
    transport.play()
    pulses(transport, 7)
    assert calls == [(0, 0), (1, 2), (2, 3), (3, 5), (4, 6)]


def test_bar_and_beat():
    transport = Transport(sync = True, ppq = 24, signature = (3, 4))
    bars = []
    transport.every('beat', lambda count: bars.append((transport.bar, transport.beat)))
    transport.play()
    pulses(transport, 24 * 4)
    assert bars == [(0, 0), (0, 1), (0, 2), (1, 0)]
    transport.signature = (6, 8)
    transport.locate(3)
    assert (transport.bar, transport.beat, transport.beats) == (1, 0, 3.0)


def test_bar_rate_follows_signature_changes():
    transport = Transport(sync = True, ppq = 24)
    calls = recorder(transport, 'bar')
    transport.play()
    transport.signature = (2, 4)
    pulses(transport, 24 * 4 + 1)
    assert [tick for _, tick in calls] == [0, 48, 96]


def test_cancel():
    transport = Transport(sync = True, ppq = 24)
    calls = []
    subscription = transport.every('1/16', calls.append)
    transport.every('1/16', calls.append)
    transport.every('1/8', print)
    subscription.cancel()
    assert len(transport.subscriptions) == 2
    transport.cancel(calls.append)
    assert [s.callback for s in transport.subscriptions] == [print]


def test_decorator_returns_function():
    transport = Transport(sync = True, ppq = 24)

    @transport.every('1/4')
    def beat(count):
        pass

    assert callable(beat) and transport.subscriptions[0].callback is beat


def test_subscriber_errors_are_reported_and_playing_continues(capsys):
    transport = Transport(sync = True, ppq = 24)
    calls = []

    @transport.every('1/16')
    def broken(count):
        raise RuntimeError('boom')

    transport.every('1/16', calls.append)
    transport.play()
    pulses(transport, 7)
    assert calls == [0, 1]
    assert 'boom' in capsys.readouterr().err


def test_events():
    transport = Transport(sync = True, ppq = 24)
    events = []
    transport.on(pyxelwidgets.events.TransportEvent, events.append)
    transport.play()
    transport.play()
    pulses(transport, 3)
    transport.stop()
    transport.stop()
    transport.locate(1)
    transport.bpm = 90
    transport.bpm = 90
    transport.toggle()
    assert [type(e) for e in events] == [TransportStarted, TransportStopped, TransportLocated, TempoChanged, TransportStarted]
    assert (events[1].tick, events[2].tick, events[3].bpm) == (3, 24, 90)


def test_pulse_measures_tempo(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(pyxelwidgets.transport.time, 'perf_counter', lambda: now[0])
    transport = Transport(sync = True, ppq = 24)
    tempos = []
    transport.on(TempoChanged, lambda e: tempos.append(e.bpm))
    for _ in range(49):
        transport.pulse()
        now[0] += 60 / (100 * 24)
    assert tempos == [100.0]
    assert transport.tick == 0
    # A change shows within a beat and settles over 4 beats
    for _ in range(24 * 6):
        transport.pulse()
        now[0] += 60 / (120 * 24)
    assert tempos[-1] == 120.0 and 100 < tempos[1] < 120
    # After a pause the old pulses don't count
    now[0] += 5
    for _ in range(25):
        transport.pulse()
        now[0] += 60 / (90 * 24)
    assert tempos[-1] == 90.0


def test_sync_with_finer_resolution():
    transport = Transport(sync = True, ppq = 96)
    calls = recorder(transport, '1/16')
    transport.play()
    pulses(transport, 7)
    assert [tick for _, tick in calls] == [0, 24]
    with pytest.raises(ValueError):
        Transport(sync = True, ppq = 100)


def test_invalid_settings():
    with pytest.raises(ValueError):
        Transport(0)
    transport = Transport()
    with pytest.raises(ValueError):
        transport.bpm = -1
    with pytest.raises(ValueError):
        transport.signature = (4, 0)
    with pytest.raises(ValueError):
        transport.every('1/0', print)


def test_internal_timer_keeps_tempo():
    transport = Transport(1200, ppq = 24)
    times = []
    transport.every('1/4', lambda count: times.append(time.perf_counter()))
    transport.play()
    time.sleep(0.55)
    transport.close()
    # 1200 bpm: a quarter note every 50 ms
    assert 9 <= len(times) <= 13
    assert (times[-1] - times[0]) / (len(times) - 1) == pytest.approx(0.05, abs = 0.01)


def test_internal_timer_restarts_and_stops_from_subscriber():
    transport = Transport(2400, ppq = 24)
    done = threading.Event()

    @transport.every('1/16')
    def stop_after_four(count):
        if count == 3:
            transport.stop()
            done.set()

    transport.play()
    assert done.wait(1)
    time.sleep(0.05)
    assert not transport.playing and transport.tick == 19
    done.clear()
    transport.locate(0)
    transport.play()
    assert done.wait(1)
    transport.close()


def test_sync_mode_has_no_thread():
    transport = Transport(sync = True, ppq = 24)
    transport.play()
    assert transport._thread is None
    transport.close()


# Widgets played by a transport (they don't know about it)

def test_sequencer_play_and_advance():
    sequencer = Sequencer(0, 0, 4, 2, steps = 16)
    sequencer.press(1, 0, 1.0)
    played, pages = [], []
    sequencer.on(StepPlayed, lambda e: played.append((e.step, e.active)))
    sequencer.on(PageChanged, lambda e: pages.append(e.page))
    sequencer.play(1)
    sequencer.advance()
    sequencer.play(9)
    sequencer.play(17)
    assert played == [(1, True), (2, False), (9, False), (1, True)]
    assert pages == [1, 0]
    # Paused, its clock doesn't play it; calls still do
    sequencer.stop()
    sequencer.tick(5 * sequencer.divisions)
    assert sequencer.step == 1
    sequencer.advance()
    assert sequencer.step == 2
    sequencer.toggle()
    # The clock counts divisions of a step
    sequencer.tick(5 * sequencer.divisions)
    assert sequencer.step == 5


def test_sequencer_follows_transport():
    transport = Transport(sync = True, ppq = 24)
    sequencer = Sequencer(0, 0, 4, 1, rate = '1/8')
    steps = []
    sequencer.on(StepPlayed, lambda e: steps.append(e.step))
    transport.every(sequencer.rate, sequencer.play)
    transport.play()
    pulses(transport, 24 * 3)
    assert steps == [0, 1, 2, 3, 0, 1]


def test_tracker_play_scroll_and_pages():
    tracker = Tracker(0, 0, 2, 4, bars = 8, pages = 2)
    tracker.press(1, 3, 1.0)  # top row: row 0
    rows = []
    tracker.on(RowPlayed, lambda e: rows.append((e.row, e.columns)))
    tracker.play(0)
    tracker.advance()
    tracker.scroll(6)
    assert (tracker.current_bar, tracker.current_top) == (6, 4)
    tracker.play(8)
    assert tracker.current_page == 1 and tracker.step == 8
    tracker.play(16)
    assert rows == [(0, (1,)), (1, ()), (0, ()), (0, (1,))]
    assert tracker.render() is not None


def test_tracker_view_is_set_apart_from_the_playing_row():
    tracker = Tracker(0, 0, 2, 4, bars = 16, pages = 2, page = 1, bar = 8, follow = False)
    assert (tracker.page, tracker.bar, tracker.step) == (1, 8, 0)
    tracker.press(0, 3, 1.0)                # top row shown: page 1, row 8
    assert tracker.states[1, 0, 8]
    tracker.render()
    assert Color.from_array(tracker.buffer[0, 3]) == tracker.active_color
    # Playing elsewhere keeps the view; the playing row shows only where it is in view
    tracker.play(9)
    assert (tracker.page, tracker.bar) == (1, 8)
    tracker.play(16 + 9)
    tracker.render()
    assert Color.from_array(tracker.buffer[1, 2]) == tracker.current_color
    # bar stays within the rows
    tracker.bar = 30
    assert tracker.bar == 12
    # Following: the view jumps to the played row
    tracker.configure(follow = True)
    tracker.play(5)
    assert (tracker.page, tracker.bar) == (0, 4)
    tracker.configure(step = 20)
    assert (tracker.current_page, tracker.current_bar, tracker.page) == (1, 4, 1)


def test_sequencer_page_and_step():
    sequencer = Sequencer(0, 0, 4, 1, steps = 8, page = 1, follow = Follow.Off, step = 2)
    assert (sequencer.page, sequencer.step, sequencer.current_page) == (1, 2, 0)
    sequencer.press(1, 0, 1.0)              # on the page shown: step 5
    assert sequencer.state[1, 1]
    sequencer.play(3)
    assert sequencer.page == 1
    sequencer.configure(follow = Follow.Page)
    sequencer.play(4)
    assert sequencer.page == 1 and sequencer.current_page == 1
    sequencer.play(0)
    assert sequencer.page == 0
    sequencer.page = 1                      # look at another page until the next one plays
    sequencer.play(1)
    assert sequencer.page == 1


def test_own_clock_advances_and_resumes():
    from pyxelwidgets.widgets import Clock
    sequencer = Sequencer(0, 0, 4, 1, clock = Clock.Own, bpm = 90)
    sequencer.tick(7 * sequencer.divisions)
    sequencer.tick(7 * sequencer.divisions + 12)
    assert sequencer.step == 1
    sequencer.tick(8 * sequencer.divisions)
    assert sequencer.step == 2      # one on per step of its clock, wherever its clock is
    with pytest.raises(ValueError, match = 'bpm'):
        Sequencer(0, 0, 4, 1, bpm = 0)


def test_default_resolution_is_96_ppq():
    transport = Transport()
    assert transport.ppq == 96 and transport.ticks('1/16') == 24

def test_divisions():
    # 24 calls per 16th note, counting divisions; at 24 ppq they can only come every 4th
    transport = Transport(sync = True)
    calls = []
    transport.every('1/16', calls.append, divisions = 24)
    transport.play()
    pulses(transport, 3)
    assert calls == list(range(12))
    coarse = Transport(sync = True, ppq = 24)
    calls = []
    coarse.every('1/16', calls.append, divisions = 24)
    coarse.play()
    pulses(coarse, 3)
    assert calls == [0, 4, 8]
    with pytest.raises(ValueError):
        transport.every('1/16', calls.append, divisions = 0)


def played_by(transport, sequencer, quarters):
    """(tick, event) of the sequencer's StepPlayed/StepEnded over ``quarters`` quarter notes on a synced transport."""
    events = []
    sequencer.on(StepPlayed, lambda e: events.append((transport.tick, 'played', e.step, e.active)))
    sequencer.on(StepEnded, lambda e: events.append((transport.tick, 'ended', e.step)))
    transport.every(sequencer.rate, sequencer.tick, divisions = sequencer.divisions)
    transport.play()
    pulses(transport, round(24 * quarters))
    return events

def test_sequencer_gates():
    transport = Transport(sync = True)
    sequencer = Sequencer(0, 0, 4, 1, gate = 0.5)
    sequencer.press(0, 0)
    sequencer.press(1, 0)
    events = played_by(transport, sequencer, 1)
    # 16ths are 24 ticks: active steps end half way, inactive ones have no gate
    assert events == [(0, 'played', 0, True), (12, 'ended', 0), (24, 'played', 1, True), (36, 'ended', 1),
                      (48, 'played', 2, False), (72, 'played', 3, False)]

def test_sequencer_full_gate_ends_before_the_next_step():
    transport = Transport(sync = True)
    sequencer = Sequencer(0, 0, 2, 1, gate = 1.0)
    sequencer.press(0, 0)
    sequencer.press(1, 0)
    events = played_by(transport, sequencer, 0.75)
    assert events[:4] == [(0, 'played', 0, True), (24, 'ended', 0), (24, 'played', 1, True), (48, 'ended', 1)]

def test_sequencer_swing():
    transport = Transport(sync = True)
    sequencer = Sequencer(0, 0, 4, 1, swing = 75.0, gate = 1.0)
    for x in range(4):
        sequencer.press(x, 0)
    events = played_by(transport, sequencer, 1)
    # Every second step starts half a step late; gates still end at the step's end
    assert [(tick, step) for tick, kind, step, *_ in events if kind == 'played'] == [(0, 0), (36, 1), (48, 2), (84, 3)]
    assert [(tick, step) for tick, kind, step, *_ in events if kind == 'ended'] == [(24, 0), (48, 1), (72, 2)]

def test_sequencer_swing_amounts():
    for swing, tick in ((50.0, 24), (58.0, 28), (66.0, 32)):
        transport = Transport(sync = True)
        sequencer = Sequencer(0, 0, 2, 1, swing = swing)
        events = played_by(transport, sequencer, 1)
        # Ticks come 4 at a time from MIDI clock pulses
        assert [t for t, kind, step, *_ in events if kind == 'played' and step == 1][0] == tick

def test_sequencer_gate_random():
    import random
    transport = Transport(sync = True)
    sequencer = Sequencer(0, 0, 4, 1, gate = 0.5, gate_random = 0.4)
    sequencer._random = random.Random(3)
    for x in range(4):
        sequencer.press(x, 0)
    gates = []
    sequencer.on(StepPlayed, lambda e: gates.append(e.gate))
    events = played_by(transport, sequencer, 4)
    assert len(set(gates)) > 4 and all(0.1 - 1e-9 <= gate <= 0.9 + 1e-9 for gate in gates)
    # Each gate ends when its length says (to the 4 tick pulses of MIDI clock)
    starts = {step: tick for tick, kind, step, *_ in events if kind == 'played'}
    ends = [(tick, step) for tick, kind, step, *_ in events if kind == 'ended']
    for (tick, step), gate in zip(ends, gates):
        assert 0 <= tick - (tick // 24) * 24 - gate * 24 < 4 or tick % 24 == 0

def test_sequencer_ends_gates_when_stopped_paused_or_relocated():
    transport = Transport(sync = True)
    app_like = []
    sequencer = Sequencer(0, 0, 4, 1, gate = 1.0)
    sequencer.press(0, 0)
    transport.on(TransportStopped, lambda e: sequencer.silence())
    ended = []
    sequencer.on(StepEnded, lambda e: ended.append(e.step))
    transport.every(sequencer.rate, sequencer.tick, divisions = sequencer.divisions)
    transport.play()
    pulses(transport, 2)
    transport.stop()
    assert ended == [0]
    # Played again from the same place: the step plays again
    played = []
    sequencer.on(StepPlayed, lambda e: played.append(e.step))
    transport.locate(0)
    transport.play()
    pulses(transport, 1)
    assert played == [0]
    sequencer.stop()
    assert ended == [0, 0]

def test_sequencer_options_are_checked():
    for options in ({'swing': 40}, {'swing': 80}, {'gate': 0}, {'gate': 1.5}, {'gate_random': -0.1}):
        with pytest.raises(ValueError):
            Sequencer(0, 0, 4, 1, **options)
