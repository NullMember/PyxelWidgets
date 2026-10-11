import pyxelwidgets.events
import threading
import time

class PadInput:
    """
    Turns raw pad presses and releases into pad events: PadPressed (followed by
    PadDoublePressed for a quick second press), PadReleased, and PadHeld once a
    pad stays down for ``held_time``. Holds are found by ``poll()``, so no
    thread is started per press; call it regularly (Device.show does).

    Methods return ``(event_class, x, y, velocity)`` tuples; the caller emits them.
    """

    def __init__(self, held_time: float = 1.0, double_press_time: float = 0.15, clock = time.monotonic):
        self.held_time = held_time
        self.double_press_time = double_press_time
        self.clock = clock
        self._down = {}
        self._last_press = {}
        self._lock = threading.Lock()

    def press(self, x: int, y: int, velocity: float) -> list:
        now = self.clock()
        with self._lock:
            events = [(pyxelwidgets.events.PadPressed, x, y, velocity)]
            last = self._last_press.get((x, y))
            if last is not None and now - last < self.double_press_time:
                events.append((pyxelwidgets.events.PadDoublePressed, x, y, velocity))
            self._last_press[x, y] = now
            self._down[x, y] = [now, velocity, False]
        return events

    def release(self, x: int, y: int, velocity: float = 0.0) -> list:
        with self._lock:
            self._down.pop((x, y), None)
        return [(pyxelwidgets.events.PadReleased, x, y, velocity)]

    def poll(self) -> list:
        """PadHeld for every pad that just passed ``held_time``."""
        now = self.clock()
        events = []
        with self._lock:
            for (x, y), state in self._down.items():
                pressed_at, velocity, held = state
                if not held and now - pressed_at >= self.held_time:
                    state[2] = True
                    events.append((pyxelwidgets.events.PadHeld, x, y, velocity))
        return events

    @property
    def pressed(self) -> set:
        """Pads currently down."""
        with self._lock:
            return set(self._down)
