from __future__ import annotations

import pyxelwidgets.animation
import pyxelwidgets.binding
import pyxelwidgets.buffer
import pyxelwidgets.color
import pyxelwidgets.events
import pyxelwidgets.group
import pyxelwidgets.rectangle
import dataclasses
import threading
import typing

# Only for type hints: a surface works with any device like object
if typing.TYPE_CHECKING:
    import pyxelwidgets.devices
    import pyxelwidgets.widgets

class Surface(pyxelwidgets.events.Emitter):
    """
    Maps a tree of widgets onto devices: routes pad input to the topmost widget
    under each press, and shows the composed frame on the devices on ``update()``.

    Widgets live in ``root``, a Group covering the whole surface; ``add``,
    ``remove`` and ``find`` are shortcuts for it. Devices are placed at an
    offset, so several devices can form one larger surface.

    Emits ``Frame`` before rendering each frame, and re-emits every device's
    control events (ControlPressed, ControlChanged, ...). ``bind`` connects a
    device's controls to widgets or actions.

    ``lock`` is held while processing input and rendering. Hold it when changing
    widgets from another thread, e.g. a MIDI callback of your own.
    """

    _count = 0

    def __init__(self, width: int, height: int, *, name: str | None = None):
        self.name = name if name is not None else f'Surface_{Surface._count}'
        self.rect = pyxelwidgets.rectangle.Rectangle2D(0, 0, width, height)
        self.root = pyxelwidgets.group.Group(0, 0, width, height, name = f'{self.name}_root')
        self.devices = {}
        self.bindings = []
        #: Times animations: anything with bpm, beats, playing and signature (App sets its Transport)
        self.transport = None
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

    # Devices

    def add_device(self, device: pyxelwidgets.devices.Device, x: int = 0, y: int = 0) -> None:
        """Place ``device`` with its bottom left pad at surface ``x``, ``y``."""
        def pad(event):
            self._pad(event, x, y)
        def control(event):
            with self.lock:
                self.emit(event)
        with self.lock:
            device.on(pyxelwidgets.events.PadEvent, pad)
            device.on(pyxelwidgets.events.ControlEvent, control)
            self.devices[device.name] = {
                'device': device,
                'rect': pyxelwidgets.rectangle.Rectangle2D(x, y, device.rect.w, device.rect.h),
                'handlers': ((pyxelwidgets.events.PadEvent, pad), (pyxelwidgets.events.ControlEvent, control)),
            }

    def remove_device(self, device) -> None:
        """Remove a device, given the device or its name."""
        name = device if isinstance(device, str) else device.name
        with self.lock:
            entry = self.devices.pop(name)
            for event_type, handler in entry['handlers']:
                entry['device'].off(event_type, handler)
            for binding in [b for b in self.bindings if b.device is entry['device']]:
                self.unbind(binding)

    # Bindings

    def bind(self, device, control: str, target, **kwargs) -> pyxelwidgets.binding.Binding:
        """
        Connect ``device``'s ``control`` (e.g. ``'Knob1'``) to a widget or an
        action; see ``pyxelwidgets.binding`` for the options. Glides move every frame.
        """
        with self.lock:
            binding = pyxelwidgets.binding.Binding(self, control, target, device = device, **kwargs)
            self.bindings.append(binding)
            return binding

    def unbind(self, binding: pyxelwidgets.binding.Binding) -> None:
        with self.lock:
            binding.close()
            self.bindings.remove(binding)

    def force_update(self) -> None:
        """Resend every pixel on the next update, e.g. after a device reconnected."""
        with self.lock:
            for entry in self.devices.values():
                entry['device'].invalidate()

    def _pad(self, event: pyxelwidgets.events.PadEvent, x: int, y: int) -> None:
        with self.lock:
            x, y = event.x + x, event.y + y
            if 0 <= x < self.rect.w and 0 <= y < self.rect.h:
                self.root.input(dataclasses.replace(event, x = x, y = y))

    # Rendering

    def update(self) -> None:
        """Render changed widgets and send changed pixels to every device."""
        with self.lock:
            self.emit(pyxelwidgets.events.Frame(self, self.frame_counter))
            self.frame_counter += 1
            for binding in self.bindings:
                binding.update()
            if self.root.render(pyxelwidgets.animation.now(self.transport)):
                # Transparent areas show as black on the devices
                self.buffer[:] = pyxelwidgets.color.Colors.Black
                pyxelwidgets.buffer.composite(self.buffer, self.root.buffer)
            # Always called: devices diff against what they show, poll held
            # pads, and some (Virtual) also process their own events here
            for entry in list(self.devices.values()):
                area = self.rect.intersect(entry['rect'])
                if area:
                    entry['device'].show(self.buffer[area.slice], area.x - entry['rect'].x, area.y - entry['rect'].y)

    def close(self) -> None:
        """Close all devices."""
        with self.lock:
            devices = [entry['device'] for entry in self.devices.values()]
            for name in list(self.devices):
                self.remove_device(name)
        # Closed outside the lock: closing may wait for threads that need it
        for device in devices:
            device.close()
