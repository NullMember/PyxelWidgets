import pyxelwidgets.events
import pyxelwidgets.surface
import pyxelwidgets.transport
import pyxelwidgets.widgets
import time

class App():
    """
    Runs a Surface: renders at a fixed frame rate, owns a Transport whose
    subscribers run under the Surface's lock, and closes everything on exit.

    Input from devices and transport subscribers are handled immediately on
    their own threads; the shared lock keeps them from interleaving with
    rendering. The transport doesn't play until ``app.transport.play()``, or
    with ``sync = True`` it follows an external clock (see
    ``pyxelwidgets.devices.midi_clock``).

    Every ``check_interval`` seconds devices notice being unplugged and
    reconnect when they're back (``Surface.check_devices``); None doesn't.
    """

    def __init__(self, surface: pyxelwidgets.surface.Surface, fps: float = 60.0, *,
                 bpm: float = 120, signature: tuple = (4, 4), sync: bool = False,
                 check_interval: float | None = 1.0):
        self.surface = surface
        self.fps = fps
        self.check_interval = check_interval
        self.transport = pyxelwidgets.transport.Transport(bpm, signature = signature, sync = sync, lock = surface.lock)
        if surface.transport is None:
            # Animations follow the music
            surface.transport = self.transport
        #: Other clocks to close with the App (e.g. widgets' own, see Parser.start_clocks)
        self.clocks = []
        self.running = False
        self._closed = False

    @property
    def lock(self):
        """Hold this when changing widgets from a thread the App doesn't manage."""
        return self.surface.lock

    def attach(self, widget):
        """
        Play ``widget`` (a Sequencer, Tracker or ClipLauncher) on its clock: the
        app's transport (``clock = Clock.Transport``) or a clock of its own
        following its ``bpm`` (``Clock.Own``, closed with the App). Returns the
        Subscription, or None for ``Clock.Off``.
        """
        divisions = getattr(widget, 'divisions', 1)
        if widget.clock == pyxelwidgets.widgets.Clock.Transport:
            # A Sequencer's sounding step ends when the transport stops
            self.transport.on(pyxelwidgets.events.TransportStopped, lambda event: widget.silence())
            return self.transport.every(widget.rate, widget.tick, divisions = divisions)
        if widget.clock != pyxelwidgets.widgets.Clock.Own:
            return None
        clock = pyxelwidgets.transport.Transport(widget.bpm, signature = self.transport.signature, lock = self.lock)
        def tick(count):
            # The widget's tempo may change (e.g. from a link)
            clock.bpm = widget.bpm
            widget.tick(count)
        subscription = clock.every(widget.rate, tick, divisions = divisions)
        clock.on(pyxelwidgets.events.TransportStopped, lambda event: widget.silence())
        clock.play()
        self.clocks.append(clock)
        return subscription

    def step(self) -> None:
        """Render one frame; use this to drive the App from your own loop."""
        self.surface.update()

    def run(self) -> None:
        """Run until stop(), Ctrl+C, or a device closes (e.g. the Virtual window); then close()."""
        self.running = True
        period = 1.0 / self.fps
        next_frame = next_check = time.perf_counter()
        try:
            while self.running and not self._device_closed():
                if self.check_interval is not None and time.perf_counter() >= next_check:
                    next_check = time.perf_counter() + self.check_interval
                    self.surface.check_devices()
                    # A DAW's clock input (Parser.app with sync)
                    inputs = [clock for clock in self.clocks if callable(getattr(clock, 'check', None))]
                    if inputs:
                        self.surface.check_devices(inputs)
                self.step()
                next_frame += period
                delay = next_frame - time.perf_counter()
                if delay > 0.0:
                    time.sleep(delay)
                else:
                    # Running behind; don't try to catch up with a burst of frames
                    next_frame = time.perf_counter()
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def stop(self) -> None:
        """Make run() return after the current frame; safe to call from any thread."""
        self.running = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.running = False
        # Stop the clocks first: their subscribers may be waiting for the lock
        self.transport.close()
        for clock in self.clocks:
            clock.close()
        self.surface.close()

    def _device_closed(self) -> bool:
        with self.surface.lock:
            return any(entry["device"].terminated for entry in self.surface.devices.values())
