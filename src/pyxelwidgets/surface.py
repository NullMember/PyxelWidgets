from __future__ import annotations

import pyxelwidgets.buffer
import pyxelwidgets.color
import pyxelwidgets.enums
import pyxelwidgets.events
import pyxelwidgets.group
import pyxelwidgets.rectangle
import threading
import typing

# Only for type hints: a surface works with any controller like object
if typing.TYPE_CHECKING:
    import pyxelwidgets.controllers
    import pyxelwidgets.widgets

class Surface(pyxelwidgets.events.Emitter):
    """
    Maps a tree of widgets onto controllers: routes their input to the topmost
    widget under each press, and sends the composed frame back on ``update()``.

    Widgets live in ``root``, a Group covering the whole surface; ``add``,
    ``remove`` and ``find`` are shortcuts for it. Controllers are placed at an
    offset, so several devices can form one larger surface.

    Emits ``Frame`` before rendering each frame and ``Control`` for input from
    non-grid controls (knobs, faders, encoders, extra buttons).

    ``lock`` is held while processing input and rendering. Hold it when changing
    widgets from another thread, e.g. a MIDI callback of your own.
    """

    _count = 0

    def __init__(self, width: int, height: int, *, name: str | None = None):
        self.name = name if name is not None else f'Surface_{Surface._count}'
        self.rect = pyxelwidgets.rectangle.Rectangle2D(0, 0, width, height)
        self.root = pyxelwidgets.group.Group(0, 0, width, height, name = f'{self.name}_root')
        self.controllers = {}
        self.buffer = pyxelwidgets.buffer.new(width, height, pyxelwidgets.color.Colors.Black)
        self.frame_counter = 0
        self.lock = threading.RLock()
        Surface._count += 1

    # Widgets

    def add(self, widget: pyxelwidgets.widgets.Widget) -> pyxelwidgets.widgets.Widget:
        with self.lock:
            return self.root.add(widget)

    def remove(self, widget) -> None:
        with self.lock:
            self.root.remove(widget)

    def find(self, name: str):
        return self.root.find(name)

    def __getitem__(self, name: str):
        return self.root[name]

    # Controllers

    def add_controller(self, controller: pyxelwidgets.controllers.Controller, x: int = 0, y: int = 0) -> None:
        with self.lock:
            self.controllers[controller.name] = {
                'controller': controller,
                'rect': pyxelwidgets.rectangle.Rectangle2D(x, y, controller.rect.w, controller.rect.h),
            }
            controller.set_callback(self.process)

    def remove_controller(self, controller) -> None:
        """Remove a controller, given the controller or its name."""
        name = controller if isinstance(controller, str) else controller.name
        with self.lock:
            self.controllers.pop(name)

    def force_update(self) -> None:
        """Resend every pixel on the next update, e.g. after a device reconnected."""
        with self.lock:
            for entry in self.controllers.values():
                entry['controller'].buffer[:] = 0

    def process(self, name, event, data) -> None:
        """Controller callback: route grid input to widgets, emit Control for other controls."""
        with self.lock:
            if event == pyxelwidgets.enums.Event.Custom:
                control, action, value = data
                self.emit(pyxelwidgets.events.Control(self, name, control, action, value))
                return
            entry = self.controllers.get(name)
            if entry is None:
                # Input still arriving from a controller that was just removed
                return
            x, y, velocity = data
            offset = entry['rect']
            x, y = x + offset.x, y + offset.y
            if 0 <= x < self.rect.w and 0 <= y < self.rect.h:
                self.root.input(event, x, y, velocity)

    # Rendering

    def update(self) -> None:
        """Render changed widgets and send changed pixels to every controller."""
        with self.lock:
            self.emit(pyxelwidgets.events.Frame(self, self.frame_counter))
            self.frame_counter += 1
            if self.root.render():
                # Transparent areas show as black on the devices
                self.buffer[:] = pyxelwidgets.color.Colors.Black
                pyxelwidgets.buffer.composite(self.buffer, self.root.buffer)
            # Always called: controllers diff against what they sent, and
            # some (Virtual) also process their own events here
            for entry in list(self.controllers.values()):
                intersect = self.rect.intersect(entry['rect'])
                if intersect:
                    entry['controller'].update((intersect - entry['rect'], self.buffer[intersect.slice]))

    def close(self) -> None:
        """Close all controllers."""
        with self.lock:
            controllers = [entry['controller'] for entry in self.controllers.values()]
            self.controllers.clear()
        # Closed outside the lock: closing waits for clock targets that may need it
        for controller in controllers:
            controller.close()
