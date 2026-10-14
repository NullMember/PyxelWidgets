"""
Devices: grids of pads with LEDs, plus named controls (buttons, knobs, faders,
encoders). A device works on its own: subscribe to its pad and control events
with ``on`` and show frames on it with ``show``. A Surface connects devices to
widgets.

Concrete devices live in submodules (``pyxelwidgets.devices.novation``,
``.akai``, ``.ableton``, ``.arturia``, ``.presonus``, ``.virtual``); importing this package
doesn't load MIDI or GUI libraries.
"""

import dataclasses
import threading

import numpy

import pyxelwidgets.buffer
import pyxelwidgets.events
import pyxelwidgets.rectangle
from pyxelwidgets.devices.colors import ColorModel, Levels, Palette, PassThrough, RGB
from pyxelwidgets.devices.input import PadInput

__all__ = ['Control', 'Device', 'ColorModel', 'Levels', 'Palette', 'PassThrough', 'RGB']

@dataclasses.dataclass(frozen = True)
class Control:
    """
    A named non-grid control, for ``describe()``. ``kind`` is one of:
    ``button`` (ControlPressed/Released), ``absolute`` (ControlChanged, 0.0-1.0),
    ``relative`` (ControlTurned) or ``touch`` (ControlPressed/Released).
    """
    name: str
    kind: str

class Device(pyxelwidgets.events.Emitter):
    """
    Base class of all devices. Subclasses set the class attributes describing the
    hardware and implement ``send_pixel`` (or ``send_pixels`` to batch).

    Input: call ``set_button(x, y, velocity)`` for grid pads (velocity 0 releases)
    and ``emit`` control events; the base turns pads into PadPressed, PadReleased,
    PadDoublePressed and PadHeld events.
    """

    vendor: str = ''
    model: str = 'Device'
    #: Substrings of the device's port names, used to find it
    ports: tuple = ()
    #: Default grid size (width, height)
    grid: tuple = (1, 1)
    color_model: ColorModel = PassThrough()
    #: Named controls besides the grid
    controls: tuple = ()

    # Per class counters for default names (LaunchpadX_0, Virtual_0, ...)
    _counts = {}

    def __init__(self, *,
                 name: str | None = None,
                 width: int | None = None,
                 height: int | None = None,
                 held_time: float = 1.0,
                 double_press_time: float = 0.15):
        if name is None:
            cls = type(self).__name__
            count = Device._counts.get(cls, 0)
            Device._counts[cls] = count + 1
            name = f'{cls}_{count}'
        self.name = name
        width = self.grid[0] if width is None else width
        height = self.grid[1] if height is None else height
        self.rect = pyxelwidgets.rectangle.Rectangle2D(0, 0, width, height)
        self.connected = False
        self.terminated = False
        # What the device currently shows; starts transparent so the first frame is sent in full
        self.buffer = pyxelwidgets.buffer.new(width, height)
        self.pads = PadInput(held_time, double_press_time)
        self._input_timer = None
        # What lit controls show (set_control), by name
        self._lit = {}

    @property
    def width(self) -> int:
        return self.rect.w

    @property
    def height(self) -> int:
        return self.rect.h

    @classmethod
    def describe(cls) -> dict:
        """The device's layout and capabilities as plain data (e.g. for a design tool)."""
        return {
            'class': cls.__name__,
            'vendor': cls.vendor,
            'model': cls.model,
            'ports': list(cls.ports),
            'grid': {'width': cls.grid[0], 'height': cls.grid[1]},
            'colors': cls.color_model.describe(),
            'controls': [{'name': control.name, 'kind': control.kind} for control in cls.controls],
        }

    # Lifecycle

    def connect(self) -> None:
        if self.connected:
            self.disconnect()
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def close(self) -> None:
        self.stop_input_timer()
        if self.connected:
            self.disconnect()
        self.terminated = True

    # Input

    def set_button(self, x: int, y: int, velocity: float) -> None:
        """Report a grid pad: ``velocity`` 0.0-1.0, where 0 is a release."""
        if not (0 <= x < self.rect.w and 0 <= y < self.rect.h):
            return
        velocity = min(1.0, max(0.0, velocity))
        events = self.pads.press(x, y, velocity) if velocity > 0.0 else self.pads.release(x, y, velocity)
        self._emit_pads(events)

    def set_pressure(self, x: int, y: int, pressure: float) -> None:
        """Report the pressure (polyphonic aftertouch) of a held grid pad, 0.0-1.0."""
        if (x, y) in self.pads.pressed:
            self.emit(pyxelwidgets.events.PadPressure(self, x, y, min(1.0, max(0.0, pressure))))

    def set_channel_pressure(self, pressure: float) -> None:
        """Report one pressure (channel aftertouch) for every held grid pad."""
        for x, y in sorted(self.pads.pressed):
            self.set_pressure(x, y, pressure)

    def poll_input(self) -> None:
        """Emit PadHeld for pads held long enough. ``show`` calls this every frame."""
        self._emit_pads(self.pads.poll())

    def start_input_timer(self, interval: float = 0.01) -> None:
        """Poll for held pads on a background thread, for devices used without ``show``."""
        if self._input_timer is not None:
            return
        stop = threading.Event()
        def run():
            while not stop.wait(interval):
                self.poll_input()
        thread = threading.Thread(target = run, name = f'{self.name}_input', daemon = True)
        self._input_timer = (thread, stop)
        thread.start()

    def stop_input_timer(self) -> None:
        if self._input_timer is not None:
            thread, stop = self._input_timer
            stop.set()
            if thread is not threading.current_thread():
                thread.join()
            self._input_timer = None

    def _emit_pads(self, events) -> None:
        for event_type, x, y, velocity in events:
            self.emit(event_type(self, x, y, velocity))

    # Output

    def show(self, frame: numpy.ndarray, x: int = 0, y: int = 0) -> None:
        """Show an RGBA ``frame`` with its bottom left at grid ``x``, ``y``; only changed pixels are sent."""
        self.poll_input()
        if not self.connected:
            return
        area = self.rect.intersect(pyxelwidgets.rectangle.Rectangle2D(x, y, frame.shape[0], frame.shape[1]))
        if area is None:
            return
        source = frame[(area - pyxelwidgets.rectangle.Rectangle2D(x, y)).slice]
        current = self.buffer[area.slice]
        changed = numpy.argwhere(numpy.any(source != current, axis = -1))
        if len(changed) == 0:
            return
        cells = source[changed[:, 0], changed[:, 1]]
        current[changed[:, 0], changed[:, 1]] = cells
        values = self.color_model.convert(cells)
        self.send_pixels([(area.x + dx, area.y + dy, value) for (dx, dy), value in zip(changed.tolist(), values)])

    def fill(self, color) -> None:
        """Show one color on the whole grid."""
        self.show(pyxelwidgets.buffer.new(self.rect.w, self.rect.h, color))

    def invalidate(self) -> None:
        """Forget what the device shows, so the next ``show`` sends every pixel."""
        self.buffer[:] = 0
        self._lit = {}

    def lights(self) -> tuple:
        """Names of the controls with a light ``set_control`` can set (e.g. a Launchpad's side buttons); none by default."""
        return ()

    def set_control(self, name: str, color) -> None:
        """
        Light control ``name`` in ``color`` (a Color); only changes are sent,
        and controls without a light (see ``lights``) are ignored.
        """
        if not self.connected or name not in self.lights():
            return
        cell = pyxelwidgets.buffer.new(1, 1, color)[0, 0]
        key = tuple(int(value) for value in cell)
        if self._lit.get(name) == key:
            return
        self._lit[name] = key
        self.send_control(name, self.color_model.convert(cell[None])[0])

    def send_control(self, name: str, value) -> None:
        """Send a control's light, ``value`` from ``color_model``. Override with ``lights``."""
        raise NotImplementedError(f'{type(self).__name__} has no control lights')

    def send_pixels(self, pixels: list) -> None:
        """Send ``(x, y, value)`` triples, values from ``color_model``. Override to batch."""
        for x, y, value in pixels:
            self.send_pixel(x, y, value)

    def send_pixel(self, x: int, y: int, value) -> None:
        raise NotImplementedError(f'{type(self).__name__} must implement send_pixel or send_pixels')
