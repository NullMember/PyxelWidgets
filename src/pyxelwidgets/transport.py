"""
Musical time. A Transport keeps the tempo, time signature, play state and
position, and calls subscribers at musical rates::

    transport = Transport(120)
    transport.every('1/16', sequencer.play)   # called with the 16th note count
    transport.play()

Rates are note values: ``'1/4'``, ``'1/16'``, dotted ``'1/8.'``, triplet
``'1/8T'``, whole notes ``'1'`` or ``'2'``, and ``'beat'`` or ``'bar'`` from
the time signature.

The internal timer calls subscribers in order from one thread, which runs only
while playing. To follow an external clock instead (e.g. a DAW's MIDI clock),
create the Transport with ``sync = True`` and forward the MIDI realtime
messages: Timing Clock → ``pulse()``, Start → ``locate(0)`` and ``play()``,
Continue → ``play()``, Stop → ``stop()``, Song Position → ``locate(sixteenths / 4)``.
"""

import collections
import fractions
import math
import threading
import time
import traceback
import typing

import pyxelwidgets.events
from pyxelwidgets.rate import parse_rate, parse_signature

__all__ = ['Transport', 'Subscription', 'parse_rate', 'parse_signature']

class Subscription:
    """A callback made every ``rate`` by a Transport; ``cancel()`` removes it."""

    def __init__(self, transport, rate, callback: typing.Callable, offset, divisions: int = 1) -> None:
        self.transport = transport
        self.rate = rate
        self.offset = offset
        self.divisions = divisions
        self.callback = callback
        self.interval = fractions.Fraction(1)
        self.start = fractions.Fraction(0)
        self.last = -1
        # The first tick whose count isn't ``last`` (whole ticks: compared every tick)
        self.next = 0
        # (start, interval) as ints when both are whole ticks, for cheaper counting
        self.whole = None

    def cancel(self) -> None:
        self.transport.cancel(self)

class Transport(pyxelwidgets.events.Emitter):
    """
    Tempo, time signature, play/stop and the position, counted in ``tick``
    (``ppq`` ticks per quarter note: 96, so a 16th note's swing can move in
    24ths of it). Emits TransportStarted, TransportStopped,
    TransportLocated and TempoChanged.

    ``lock`` (e.g. a Surface's lock) is held while calling subscribers and
    handlers; it must be reentrant so they may control the transport.
    """

    MIDI_PPQ = 24

    def __init__(self, bpm: float = 120.0, *,
                 signature: tuple = (4, 4),
                 ppq: int = 96,
                 sync: bool = False,
                 lock = None) -> None:
        if bpm <= 0:
            raise ValueError(f'bpm must be positive, got {bpm}')
        if sync and ppq % self.MIDI_PPQ:
            raise ValueError(f'ppq must be a multiple of {self.MIDI_PPQ} to follow a MIDI clock, got {ppq}')
        self.lock = lock if lock is not None else threading.RLock()
        self._bpm = float(bpm)
        self._signature = parse_signature(signature)
        self._ppq = int(ppq)
        self._sync = sync
        self._tick = 0
        self._playing = False
        self._subscriptions = []
        self._stopped = None
        self._thread = None
        # Times of the last 4 beats of external clock, for measuring the tempo
        self._pulses = collections.deque(maxlen = 4 * self.MIDI_PPQ + 1)
        self._pulse_count = 0

    # Settings

    @property
    def bpm(self) -> float:
        return self._bpm

    @bpm.setter
    def bpm(self, value: float) -> None:
        if value <= 0:
            raise ValueError(f'bpm must be positive, got {value}')
        with self.lock:
            if value != self._bpm:
                self._bpm = float(value)
                self.emit(pyxelwidgets.events.TempoChanged(self, self._bpm))

    @property
    def signature(self) -> tuple:
        """Time signature as (beats per bar, beat note value), e.g. (6, 8)."""
        return self._signature

    @signature.setter
    def signature(self, value: tuple) -> None:
        with self.lock:
            self._signature = parse_signature(value)
            self._arm(*self._subscriptions)

    @property
    def ppq(self) -> int:
        return self._ppq

    @property
    def sync(self) -> bool:
        """Following an external clock through ``pulse()`` instead of the internal timer."""
        return self._sync

    # Position

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def tick(self) -> int:
        """The next tick to play."""
        return self._tick

    @property
    def beats(self) -> float:
        """Position in quarter notes."""
        return self._tick / self._ppq

    @property
    def bar(self) -> int:
        """Bar of the position, counted from 0."""
        return int(self._tick // self._ticks(fractions.Fraction(self._signature[0], self._signature[1])))

    @property
    def beat(self) -> int:
        """Beat within the bar, counted from 0, in the signature's beat note value."""
        return int(self._tick // self._ticks(fractions.Fraction(1, self._signature[1]))) % self._signature[0]

    def ticks(self, rate) -> fractions.Fraction:
        """Length of ``rate`` in ticks, e.g. ``'1/16'`` → 24 at 96 ppq."""
        return self._ticks(parse_rate(rate, self._signature))

    # Control

    def play(self) -> None:
        """Play from the current position; the first tick plays right away (with ``sync``, on the next ``pulse()``)."""
        with self.lock:
            if self._playing:
                return
            self._playing = True
            self._arm(*self._subscriptions)
            if not self._sync:
                self._stopped = threading.Event()
                self._thread = threading.Thread(target = self._run, args = (self._stopped,), name = 'Transport', daemon = True)
                self._thread.start()
            self.emit(pyxelwidgets.events.TransportStarted(self, self._tick))

    def stop(self) -> None:
        """Stop at the current position; ``play()`` continues from there."""
        with self.lock:
            if not self._playing:
                return
            self._playing = False
            if self._stopped is not None:
                self._stopped.set()
                self._stopped = None
            self.emit(pyxelwidgets.events.TransportStopped(self, self._tick))

    def toggle(self) -> None:
        with self.lock:
            if self._playing:
                self.stop()
            else:
                self.play()

    def locate(self, beats: float = 0) -> None:
        """Move to ``beats`` quarter notes from the start; while playing, that position plays next."""
        with self.lock:
            self._tick = max(0, round(beats * self._ppq))
            self._arm(*self._subscriptions)
            self.emit(pyxelwidgets.events.TransportLocated(self, self._tick))

    def close(self) -> None:
        """Stop and wait for the timer thread to finish."""
        self.stop()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout = 1.0)

    # Subscriptions

    def every(self, rate, callback: typing.Callable | None = None, *, offset = 0, divisions: int = 1):
        """
        Call ``callback(count)`` every ``rate`` while playing, where ``count``
        is the number of ``rate`` lengths since the start (e.g. the 16th note
        number), so the callback follows ``locate`` too. ``offset`` (a rate,
        e.g. ``'1/32'``) delays the calls. With ``divisions`` the callback is
        called that many times per ``rate`` (as often as ticks allow; counts in
        between may be skipped), counting divisions: a Sequencer times swing and
        gates with them. Returns a Subscription; usable as a decorator, which
        returns the function.
        """
        if not isinstance(divisions, int) or divisions < 1:
            raise ValueError(f'divisions must be a whole number of at least 1, got {divisions!r}')
        if callback is None:
            def decorator(callback):
                self.every(rate, callback, offset = offset, divisions = divisions)
                return callback
            return decorator
        subscription = Subscription(self, rate, callback, offset, divisions)
        with self.lock:
            self._arm(subscription)
            self._subscriptions.append(subscription)
        return subscription

    def cancel(self, subscription) -> None:
        """Remove a Subscription, or every subscription of a callback."""
        with self.lock:
            self._subscriptions = [s for s in self._subscriptions if s is not subscription and s.callback != subscription]

    @property
    def subscriptions(self) -> list:
        return list(self._subscriptions)

    # External clock

    def pulse(self) -> None:
        """
        One MIDI Timing Clock (24 per quarter note): advances while playing.
        The tempo is measured once a beat, averaged over up to 4 beats.
        """
        with self.lock:
            now = time.perf_counter()
            if self._pulses and now - self._pulses[-1] > 1.0:
                # The clock paused (slower than 2.5 bpm): start measuring again
                self._pulses.clear()
                self._pulse_count = 0
            self._pulses.append(now)
            self._pulse_count += 1
            if self._pulse_count % self.MIDI_PPQ == 0 and now > self._pulses[0]:
                beats = (len(self._pulses) - 1) / self.MIDI_PPQ
                self.bpm = round(60.0 * beats / (now - self._pulses[0]), 1)
            if self._playing:
                for _ in range(self._ppq // self.MIDI_PPQ):
                    self._advance()

    # Internals

    def _ticks(self, length: fractions.Fraction) -> fractions.Fraction:
        # A whole note is 4 quarter notes
        return length * 4 * self._ppq

    def _arm(self, *subscriptions) -> None:
        """Make each subscription's next call the first boundary at or after the position."""
        for subscription in subscriptions:
            subscription.interval = self.ticks(subscription.rate) / subscription.divisions
            subscription.start = self.ticks(subscription.offset) if subscription.offset else fractions.Fraction(0)
            subscription.last = math.ceil((self._tick - subscription.start) / subscription.interval) - 1
            subscription.next = math.ceil(subscription.start + (subscription.last + 1) * subscription.interval)
            whole = subscription.interval.denominator == 1 and fractions.Fraction(subscription.start).denominator == 1
            subscription.whole = (int(subscription.start), int(subscription.interval)) if whole else None

    def _advance(self) -> None:
        """Play the current tick, then move to the next."""
        tick = self._tick
        for subscription in list(self._subscriptions):
            if self._tick != tick:
                # A subscriber moved the position; the new one plays next
                return
            if tick < subscription.next:
                continue
            if subscription.whole is not None:
                start, interval = subscription.whole
                count = (tick - start) // interval
                subscription.next = start + (count + 1) * interval
            else:
                count = math.floor((tick - subscription.start) / subscription.interval)
                subscription.next = math.ceil(subscription.start + (count + 1) * subscription.interval)
            if count != subscription.last:
                subscription.last = count
                if count >= 0:
                    try:
                        subscription.callback(count)
                    except Exception:
                        traceback.print_exc()
        if self._tick == tick:
            self._tick += 1

    def _run(self, stopped: threading.Event) -> None:
        next_time = time.perf_counter()
        while True:
            with self.lock:
                if stopped.is_set():
                    return
                self._advance()
                period = 60.0 / (self._bpm * self._ppq)
            # Schedule against an absolute timeline so sleep overshoot doesn't drift the tempo
            next_time += period
            delay = next_time - time.perf_counter()
            if delay > 0.0:
                stopped.wait(delay)
            elif delay < -0.1:
                # Far behind (e.g. suspended): resync instead of bursting
                next_time = time.perf_counter()
