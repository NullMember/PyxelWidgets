from __future__ import annotations

import pyxelwidgets.animation
import pyxelwidgets.binding
import pyxelwidgets.buffer
import pyxelwidgets.color
import pyxelwidgets.events
import pyxelwidgets.group
import pyxelwidgets.link
import pyxelwidgets.mapping
import pyxelwidgets.rectangle
import pyxelwidgets.widgets
import dataclasses
import threading
import time
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
    device's controls to widgets or actions, ``map`` sends widget events to
    other software and ``link`` lets widgets change each other's options
    (``control`` gives a device's control to them in place of a widget);
    ``formula`` keeps an option at what an expression of others computes.

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
        self.mappings = []
        self.links = []
        self.formulas = []
        #: Times animations: anything with bpm, beats, playing and signature (App sets its Transport)
        self.transport = None
        self.buffer = pyxelwidgets.buffer.new(width, height, pyxelwidgets.color.Colors.Black)
        self.frame_counter = 0
        self.lock = threading.RLock()
        #: Set when a device's pad or control reaches the surface: a render loop waiting on it
        #: draws the answer at once instead of at the next frame (App.run does)
        self.input_arrived = threading.Event()
        # Until when reveal() shows the widgets' areas (time.monotonic), or None
        self._revealed = None
        # Frames shown on devices instead of the widgets (test_pattern), by device name
        self._patterns = {}
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
            self.input_arrived.set()
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

    def control(self, device, control: str) -> pyxelwidgets.events.ControlInput:
        """
        ``device``'s ``control`` (a device or its name) as a source for ``map``
        and ``link``: ``surface.link(surface.control(launchpad, 'Knob1'), ...)``.
        """
        return pyxelwidgets.events.ControlInput(self, control, device = device)

    # Mappings

    def map(self, widget, output, message, *, on: type | None = None, feedback: bool = False) -> pyxelwidgets.mapping.Mapping:
        """
        Send ``message`` to ``output`` on each ``on`` event of ``widget``; with
        ``feedback`` matching messages from the output update the widget. See
        ``pyxelwidgets.mapping``.
        """
        with self.lock:
            mapping = pyxelwidgets.mapping.Mapping(widget, output, message, on = on, feedback = feedback, lock = self.lock)
            self.mappings.append(mapping)
            return mapping

    def unmap(self, mapping: pyxelwidgets.mapping.Mapping) -> None:
        with self.lock:
            mapping.close()
            self.mappings.remove(mapping)

    # Links

    def link(self, widget, target, option: str | None = None, value = None, *, on: type, **kwargs) -> pyxelwidgets.link.Link:
        """
        Change ``option`` of ``target`` on each ``on`` event of ``widget``; see
        ``pyxelwidgets.link`` for ``value``, ``change``, ``minimum`` and ``maximum``.
        """
        with self.lock:
            link = pyxelwidgets.link.Link(widget, target, option, value, on = on, **kwargs)
            self.links.append(link)
            return link

    def unlink(self, link: pyxelwidgets.link.Link) -> None:
        with self.lock:
            link.close()
            self.links.remove(link)

    def formula(self, target, option: str, expression) -> pyxelwidgets.link.Formula:
        """
        Keep ``option`` of ``target`` at what ``expression`` computes (see
        ``pyxelwidgets.link.Formula``): now, and on every ``update()``.
        """
        with self.lock:
            formula = pyxelwidgets.link.Formula(target, option, expression)
            self.formulas.append(formula)
            self._refresh_formulas()
            return formula

    def remove_formula(self, formula: pyxelwidgets.link.Formula) -> None:
        with self.lock:
            self.formulas.remove(formula)

    #: Rounds of formulas each update, so formulas reading other formulas' options settle (cycles stop)
    formula_rounds = 4

    def _refresh_formulas(self) -> None:
        for _ in range(self.formula_rounds):
            changed = False
            for formula in self.formulas:
                changed = formula.refresh() or changed
            if not changed:
                break

    def check_devices(self, devices = None) -> list:
        """
        Let ``devices`` (default: the surface's devices and its mappings'
        outputs) notice being unplugged and plugged back in, with their
        ``check()`` (MIDI devices have one). Ports are listed once, outside the
        lock; each check holds it. Returns the devices whose connection changed.
        App calls this about once a second.
        """
        if devices is None:
            with self.lock:
                devices = [entry['device'] for entry in self.devices.values()] + [mapping.output for mapping in self.mappings]
        devices = [device for device in dict.fromkeys(devices) if callable(getattr(device, 'check', None))]
        lister = next((device for device in devices if hasattr(device, 'available_ports')), None)
        try:
            ports = lister.available_ports() if lister is not None else None
        except Exception:
            return []
        changed = []
        for device in devices:
            with self.lock:
                if device.check(ports) if ports is not None else device.check():
                    changed.append(device)
        return changed

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
        self.input_arrived.set()

    # Rendering

    def update(self) -> None:
        """Render changed widgets and send changed pixels to every device."""
        with self.lock:
            self.emit(pyxelwidgets.events.Frame(self, self.frame_counter))
            self.frame_counter += 1
            for binding in self.bindings:
                binding.update()
            self._refresh_formulas()
            if self.root.render(pyxelwidgets.animation.now(self.transport)):
                # Transparent areas show as black on the devices
                self.buffer[:] = pyxelwidgets.color.Colors.Black
                pyxelwidgets.buffer.composite(self.buffer, self.root.buffer)
            frame = self.buffer
            if self._revealed is not None:
                if time.monotonic() < self._revealed:
                    frame = self._reveal_frame()
                else:
                    self._revealed = None
            # Always called: devices diff against what they show, poll held
            # pads, and some (Virtual) also process their own events here
            for entry in list(self.devices.values()):
                pattern = self._patterns.get(entry['device'].name)
                if pattern is not None:
                    entry['device'].show(pattern)
                    continue
                area = self.rect.intersect(entry['rect'])
                if area:
                    entry['device'].show(frame[area.slice], area.x - entry['rect'].x, area.y - entry['rect'].y)
            self._light_controls()

    def test_pattern(self, device, frame = None) -> None:
        """
        Show ``frame`` (a buffer the device's size) on ``device`` instead of
        its part of the widgets, e.g. to check its lights; None goes back.
        Its pads still reach the widgets.
        """
        with self.lock:
            if frame is None:
                self._patterns.pop(device.name, None)
            else:
                self._patterns[device.name] = frame

    #: Colors reveal() paints widgets in, one after another
    REVEAL_COLORS = ('Red', 'Lime', 'Blue', 'Yellow', 'Cyan', 'Magenta', 'Orange', 'White')

    def reveal(self, seconds: float = 2.0) -> None:
        """
        Show on the devices, for ``seconds``, where the widgets are: each shown
        widget's area in a color of its own (later widgets over earlier ones).
        Called again while showing, it stops. A binding action
        (``surface.reveal`` in layouts) for finding your way on a busy grid.
        """
        with self.lock:
            now = time.monotonic()
            self._revealed = None if self._revealed is not None and self._revealed > now else now + seconds

    def _reveal_frame(self):
        frame = pyxelwidgets.buffer.new(self.rect.w, self.rect.h, pyxelwidgets.color.Colors.Black)
        count = 0
        def paint(group, ox, oy, clip):
            nonlocal count
            for child in group.children:
                if not child.visible:
                    continue
                area = clip.intersect(pyxelwidgets.rectangle.Rectangle2D(ox + child.rect.x, oy + child.rect.y, child.rect.w, child.rect.h))
                if area is None:
                    continue
                # Plain groups only hold widgets; Pages and Presets have their strips
                if type(child) is not pyxelwidgets.group.Group:
                    name = self.REVEAL_COLORS[count % len(self.REVEAL_COLORS)]
                    frame[area.slice] = getattr(pyxelwidgets.color.Colors, name)
                    count += 1
                if isinstance(child, pyxelwidgets.group.Group):
                    paint(child, ox + child.rect.x, oy + child.rect.y, area)
        paint(self.root, 0, 0, self.rect)
        return frame

    def _light_controls(self) -> None:
        """Bound controls with a light (a Launchpad's side buttons...) show what they control."""
        for binding in self.bindings:
            device = binding.device
            lights = getattr(device, 'lights', None)
            if lights is None or not lights():
                continue
            color = self.control_light(binding)
            if color is not None:
                device.set_control(binding.control, color)

    @staticmethod
    def control_light(binding):
        """
        The color a bound control shows: a Button's active or inactive color, another
        widget's active color dimmed by its value, lime for play/toggle while the
        transport plays; None leaves it as it is.
        """
        target = binding.target
        if isinstance(target, pyxelwidgets.widgets.ValueWidget):
            value = target.value
            if isinstance(value, tuple):
                value = value[binding.axis or 0]
            active = getattr(target, 'active_color', pyxelwidgets.color.Colors.White)
            inactive = getattr(target, 'inactive_color', pyxelwidgets.color.Colors.Black)
            if not value:
                return inactive
            return active if isinstance(target, pyxelwidgets.widgets.Button) else active * max(0.2, float(value))
        owner = getattr(target, '__self__', None)
        if getattr(target, '__name__', None) in ('play', 'toggle') and hasattr(owner, 'playing'):
            return pyxelwidgets.color.Colors.Lime if owner.playing else pyxelwidgets.color.Colors.Black
        return None

    def close(self) -> None:
        """Close all devices, and the outputs of the mappings."""
        with self.lock:
            devices = [entry['device'] for entry in self.devices.values()]
            for name in list(self.devices):
                self.remove_device(name)
            for mapping in list(self.mappings):
                if mapping.output not in devices:
                    devices.append(mapping.output)
                self.unmap(mapping)
        # Closed outside the lock: closing may wait for threads that need it
        for device in devices:
            device.close()
