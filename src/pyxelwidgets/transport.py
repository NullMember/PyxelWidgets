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
import re
import threading
import time
import traceback
import typing

import pyxelwidgets.events

__all__ = ['Transport', 'Subscription', 'parse_rate', 'parse_signature']

_RATE = re.compile(r'^\s*(\d+)\s*(?:/\s*(\d+))?\s*([.tT])?\s*$')

def parse_rate(rate, signature: tuple = (4, 4)) -> fractions.Fraction:
    """Length of ``rate`` in whole notes, e.g. ``'1/8.'`` → 3/16. Raises ValueError."""
    if isinstance(rate, (int, fractions.Fraction)) and not isinstance(rate, bool):
        length = fractions.Fraction(rate)
    elif rate == 'beat':
        length = fractions.Fraction(1, signature[1])
    elif rate == 'bar':
        length = fractions.Fraction(signature[0], signature[1])
    else:
        match = _RATE.match(rate) if isinstance(rate, str) else None
        if match is None:
            raise ValueError(f"expected a note value like '1/16', '1/8.', '1/8T', 'beat' or 'bar', got {rate!r}")
        numerator, denominator, modifier = match.groups()
        if denominator is not None and int(denominator) == 0:
            raise ValueError(f'rate {rate!r} divides by zero')
        length = fractions.Fraction(int(numerator), int(denominator or 1))
        if modifier == '.':
            length *= fractions.Fraction(3, 2)
        elif modifier in ('t', 'T'):
            length *= fractions.Fraction(2, 3)
    if length <= 0:
        raise ValueError(f'rate {rate!r} must be longer than zero')
    return length

def parse_signature(signature) -> tuple:
    """A time signature as (beats per bar, beat note value), e.g. ``[6, 8]`` → (6, 8). Raises ValueError."""
    try:
        beats, note = (int(value) for value in signature)
    except (TypeError, ValueError):
        raise ValueError(f'signature must be (beats, note value), got {signature!r}') from None
    if beats < 1 or note < 1:
        raise ValueError(f'signature must be positive, got {signature!r}')
    return (beats, note)

class Subscription:
    """A callback made every ``rate`` by a Transport; ``cancel()`` removes it."""

    def __init__(self, transport, rate, callback: typing.Callable, offset) -> None:
        self.transport = transport
        self.rate = rate
        self.offset = offset
        self.callback = callback
        self.interval = fractions.Fraction(1)
        self.start = fractions.Fraction(0)
        self.last = -1

    def cancel(self) -> None:
        self.transport.cancel(self)

class Transport(pyxelwidgets.events.Emitter):
    """
    Tempo, time signature, play/stop and the position, counted in ``tick``
    (``ppq`` ticks per quarter note). Emits TransportStarted, TransportStopped,
    TransportLocated and TempoChanged.

    ``lock`` (e.g. a Surface's lock) is held while calling subscribers and
    handlers; it must be reentrant so they may control the transport.
    """

    MIDI_PPQ = 24

    def __init__(self, bpm: float = 120.0, *,
                 signature: tuple = (4, 4),
                 ppq: int = 24,
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
        self._pulses = collections.deque(maxlen = self.MIDI_PPQ + 1)

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
        """Length of ``rate`` in ticks, e.g. ``'1/16'`` → 6 at 24 ppq."""
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

    def every(self, rate, callback: typing.Callable | None = None, *, offset = 0):
        """
        Call ``callback(count)`` every ``rate`` while playing, where ``count``
        is the number of ``rate`` lengths since the start (e.g. the 16th note
        number), so the callback follows ``locate`` too. ``offset`` (a rate,
        e.g. ``'1/32'``) delays the calls. Returns a Subscription; usable as a
        decorator, which returns the function.
        """
        if callback is None:
            def decorator(callback):
                self.every(rate, callback, offset = offset)
                return callback
            return decorator
        subscription = Subscription(self, rate, callback, offset)
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
        """One MIDI Timing Clock (24 per quarter note): measures the tempo and, while playing, advances."""
        with self.lock:
            now = time.perf_counter()
            self._pulses.append(now)
            if len(self._pulses) == self._pulses.maxlen:
                # The duration of the last quarter note
                bpm = round(60.0 / (now - self._pulses[0]), 2)
                self._pulses.clear()
                self._pulses.append(now)
                if bpm > 0:
                    self.bpm = bpm
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
            subscription.interval = self.ticks(subscription.rate)
            subscription.start = self.ticks(subscription.offset) if subscription.offset else fractions.Fraction(0)
            subscription.last = math.ceil((self._tick - subscription.start) / subscription.interval) - 1

    def _advance(self) -> None:
        """Play the current tick, then move to the next."""
        tick = self._tick
        for subscription in list(self._subscriptions):
            if self._tick != tick:
                # A subscriber moved the position; the new one plays next
                return
            count = math.floor((tick - subscription.start) / subscription.interval)
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
