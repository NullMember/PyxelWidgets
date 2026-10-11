import pyxelwidgets.clock
import pyxelwidgets.window
import time

class App():
    """
    Runs a Manager: renders at a fixed frame rate, owns a Clock whose targets
    run under the Manager's lock, and closes everything on exit.

    Input from controllers and clock ticks are handled immediately on their
    own threads; the shared lock keeps them from interleaving with rendering.
    """

    def __init__(self, manager: pyxelwidgets.window.Manager, fps: float = 60.0, *, bpm: float = 120, ppq: int = 24):
        self.manager = manager
        self.fps = fps
        self.clock = pyxelwidgets.clock.Clock(bpm, ppq, lock = manager.lock)
        self.running = False
        self._closed = False

    @property
    def lock(self):
        """Hold this when changing widgets from a thread the App doesn't manage."""
        return self.manager.lock

    def step(self) -> None:
        """Render one frame; use this to drive the App from your own loop."""
        self.manager.update()

    def run(self) -> None:
        """Run until stop(), Ctrl+C, or a controller closes (e.g. the Virtual window); then close()."""
        self.running = True
        if not self.clock.is_alive():
            self.clock.start()
        period = 1.0 / self.fps
        next_frame = time.perf_counter()
        try:
            while self.running and not self._controller_closed():
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
        # Stop the clock first: its targets may be waiting for the lock
        self.clock.terminate()
        self.manager.destroy()

    def _controller_closed(self) -> bool:
        with self.manager.lock:
            return any(entry['controller'].terminated for entry in self.manager.controllers.values())
