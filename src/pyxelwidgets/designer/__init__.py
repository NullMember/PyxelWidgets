"""
A web based designer for layouts::

    python -m pyxelwidgets.designer layout.json

opens a browser where widgets are placed on the surface, configured, and tried
out on a live preview rendered by the real widgets. The layout is saved as JSON
for ``pyxelwidgets.parser.load``.
"""

import collections
import copy
import dataclasses
import http.server
import importlib
import importlib.resources
import json
import mimetypes
import pathlib
import threading
import urllib.parse

import pyxelwidgets.color
import pyxelwidgets.devices
import pyxelwidgets.events
import pyxelwidgets.message
import pyxelwidgets.parser
import pyxelwidgets.transport
import pyxelwidgets.widgets

__all__ = ['Preview', 'Designer', 'new_layout', 'catalog']

DEVICE_MODULES = ['novation', 'akai', 'ableton', 'presonus', 'virtual', 'web']
OUTPUT_MODULES = ['midi_port', 'mackie', 'osc']

def new_layout(width: int = 9, height: int = 9) -> dict:
    return {
        'format': pyxelwidgets.parser.FORMAT,
        'version': pyxelwidgets.parser.VERSION,
        'surface': {'width': width, 'height': height},
        'transport': {'bpm': 120, 'signature': [4, 4]},
        'devices': [],
        'widgets': [],
    }

def _describe_classes(modules: list, outputs: bool) -> list:
    found = []
    for module_name in modules:
        try:
            module = importlib.import_module(f'pyxelwidgets.devices.{module_name}')
        except ImportError:
            continue
        for name in getattr(module, '__all__', []):
            cls = getattr(module, name)
            if isinstance(cls, type) and issubclass(cls, pyxelwidgets.devices.Device) and bool(getattr(cls, 'messages', None)) == outputs:
                found.append(_describe(cls, f'{module_name}.{name}', outputs))
    return found

def _describe(cls, kind: str, outputs: bool) -> dict:
    info = cls.describe()
    info['type'] = kind
    info['options'] = pyxelwidgets.parser.option_schema(cls)
    # MIDI outputs connect to ports or a virtual port; OSC by its options
    info['midi'] = hasattr(cls, 'connect_virtual') if outputs else None
    return info

# Palette previews: each widget drawn small, at this size, with these options (containers get none)
PREVIEWS = {
    'Button': ((2, 2), {'value': 1.0, 'active_color': pyxelwidgets.color.Colors.Lime}),
    'ButtonGroup': ((4, 1), {}),
    'ClipLauncher': ((4, 3), {}),
    'DrumPads': ((4, 4), {}),
    'Fader': ((1, 4), {'value': 0.6, 'active_color': pyxelwidgets.color.Colors.Cyan}),
    'Keyboard': ((4, 3), {}),
    'Knob': ((3, 3), {'value': 0.6}),
    'Meter': ((1, 4), {'value': 0.9}),
    'Sequencer': ((4, 2), {}),
    'Sprite': ((3, 3), {}),
    'Text': ((4, 5), {'text': 'A', 'scroll': 'Off'}),
    'Tracker': ((3, 4), {}),
    'XY': ((3, 3), {'value': (0.6, 0.4)}),
}

def _preview(cls, name: str) -> list | None:
    """``cls`` drawn small: rows from the top of ``#rrggbb`` (None where transparent), or None."""
    size, options = PREVIEWS.get(name, (None, None))
    if size is None:
        return None
    options = dict(options)
    if name == 'Text':
        options['scroll'] = pyxelwidgets.widgets.Text.Scroll.Off
    try:
        widget = cls(0, 0, *size, **options)
        if name == 'Sequencer':
            for x, y in ((0, 1), (2, 1), (1, 0), (3, 0)):
                widget.state[x, y] = True
        elif name == 'Tracker':
            for x, y in ((0, 0), (1, 1), (2, 2), (0, 3)):
                widget.states[0, x, y] = True
        elif name == 'ClipLauncher':
            widget.clips[0, 2] = widget.clips[2, 1] = pyxelwidgets.widgets.ClipLauncher.Playing
        elif name == 'DrumPads':
            widget.levels[1, 1] = widget.levels[2, 2] = 1.0
        elif name == 'Sprite':
            heart = [[0, 1, 0], [1, 1, 1], [1, 0, 1]]
            widget.configure(frames = [[[pyxelwidgets.color.Colors.Red if heart[2 - y][x] else pyxelwidgets.color.Colors.Invisible
                                         for y in range(3)] for x in range(3)]])
        widget.render()
    except Exception:
        return None
    buffer = widget.buffer
    return [[f'#{int(buffer[x, y, 0]):02x}{int(buffer[x, y, 1]):02x}{int(buffer[x, y, 2]):02x}' if buffer[x, y, 3] else None
             for x in range(buffer.shape[0])] for y in reversed(range(buffer.shape[1]))]

def catalog() -> dict:
    """Everything the designer UI offers: widget and binding options, devices, outputs, messages, links and named colors."""
    devices = _describe_classes(DEVICE_MODULES, False)
    outputs = _describe_classes(OUTPUT_MODULES, True)
    # Devices of your own (parser.register)
    for kind, cls in pyxelwidgets.parser.registered_devices().items():
        is_output = bool(getattr(cls, 'messages', None))
        (outputs if is_output else devices).append(_describe(cls, kind, is_output))
    colors = {name: pyxelwidgets.parser.color_to_text(value) for name, value in vars(pyxelwidgets.color.Colors).items()
              if isinstance(value, pyxelwidgets.color.Color)}
    schema = pyxelwidgets.parser.schema()
    for name, cls in pyxelwidgets.parser.widget_types().items():
        schema['widgets'][name]['preview'] = _preview(cls, name)
    return {'widgets': schema['widgets'], 'animations': schema['animations'], 'binding': schema['binding'],
            'devices': devices, 'outputs': outputs, 'events': schema['events'], 'messages': schema['messages'],
            'link': schema['link'], 'colors': colors}

class PreviewDevice(pyxelwidgets.devices.Device):
    """Covers the whole surface so clicks in the browser reach widgets like real pad presses."""

    def send_pixel(self, x, y, value) -> None:
        pass

def _event_json(event) -> dict:
    data = {'event': type(event).__name__}
    for field in dataclasses.fields(event):
        value = getattr(event, field.name)
        if field.name == 'widget':
            data['widget'] = value.name
        elif isinstance(value, (int, float, str, bool, type(None))):
            data[field.name] = value
        elif isinstance(value, tuple):
            data[field.name] = list(value)
        else:
            data[field.name] = str(value)
    return data

def _device_key(device: dict) -> str:
    """What makes two layout device (or output) entries the same connection (position and name aside)."""
    return json.dumps({key: device.get(key) for key in ('type', 'options', 'input', 'output', 'virtual')}, sort_keys = True)

def _message_json(message) -> dict:
    if isinstance(message, pyxelwidgets.message.OscMessage):
        return {'address': message.address, 'args': list(message.args)}
    return {field.name: getattr(message, field.name) for field in dataclasses.fields(message)
            if field.name != 'flash' or message.flash}

class _OutputProxy(pyxelwidgets.events.Emitter):
    """
    Stands in for a layout output in the preview: logs what mappings send and,
    when the output is connected, forwards it there and its replies back.
    """

    def __init__(self, preview, name: str):
        self.preview = preview
        self.name = name
        self.target = None

    def attach(self, output) -> None:
        self.detach()
        self.target = output
        output.on(pyxelwidgets.events.MessageReceived, self._received)

    def detach(self) -> None:
        if self.target is not None:
            self.target.off(pyxelwidgets.events.MessageReceived, self._received)
            self.target = None

    def send(self, message) -> None:
        self.preview._log(self.name, f'→ {type(message).__name__}', _message_json(message))
        if self.target is not None:
            self.target.send(message)

    def _received(self, event) -> None:
        self.preview._log(self.name, f'← {type(event.message).__name__}', _message_json(event.message))
        self.emit(pyxelwidgets.events.MessageReceived(self, event.message))

class _PreviewActions:
    """Binding and link actions for the preview: its transport only exists while playing."""

    def __init__(self, preview):
        self.preview = preview

    # Called from device threads holding the surface lock; play/stop take the preview lock first
    def _later(self, action) -> None:
        threading.Thread(target = action, daemon = True).start()

    def play(self) -> None:
        self._later(self.preview.play)

    def stop(self) -> None:
        self._later(self.preview.stop)

    def toggle(self) -> None:
        self._later(lambda: self.preview.stop() if self.preview.transport is not None else self.preview.play())

    def locate(self, beats: float) -> None:
        transport = self.preview.transport
        if transport is not None:
            transport.locate(beats)

    @property
    def bpm(self) -> float:
        return self.preview.bpm

    @bpm.setter
    def bpm(self, value: float) -> None:
        self.preview.set_tempo(value)

def _entries(widgets, found = None) -> dict:
    """Layout widget entries by name, nested ones included."""
    found = {} if found is None else found
    for entry in widgets or []:
        found[entry.get('name')] = entry
        _entries(entry.get('widgets'), found)
    return found

def _layout_value(entry: dict | None, key: str):
    """A widget entry's position, size or option ``key`` (None: the default)."""
    entry = entry or {}
    if key in ('x', 'y', 'width', 'height'):
        return entry.get(key, 0 if key in ('x', 'y') else 1)
    return (entry.get('options') or {}).get(key)

def _carry_state(old_ui, old_layout: dict, ui, layout: dict) -> None:
    """Give the widgets of a rebuilt layout the state of the ones they replace (same name and type)."""
    before, after = _entries(old_layout.get('widgets')), _entries(layout.get('widgets'))
    linked = {(link.get('target'), link.get('option')) for link in layout.get('links') or []}
    for name, widget in ui.widgets.items():
        old = old_ui.widgets.get(name)
        if old is None or type(old) is not type(widget):
            continue
        state = old.save_state()
        old_options, new_options = (before.get(name) or {}).get('options') or {}, (after.get(name) or {}).get('options') or {}
        # An option set in the designer (e.g. a new value or page) wins over the old state
        for key in list(state):
            if old_options.get(key) != new_options.get(key):
                del state[key]
        widget.load_state(state)
        # Options links changed, while still linked, unless the layout changed them too
        changed = {key: value for key, value in old.configured.items()
                   if (name, key) in linked and _layout_value(before.get(name), key) == _layout_value(after.get(name), key)}
        if changed:
            widget.configure(**changed)

class Preview:
    """
    A layout built without hardware, with a preview device, an event log and a
    transport to play it. The layout's devices and outputs can be connected
    one by one (``set_connected``), or all as they're added (``connect``):
    devices mirror the preview and their pads work the widgets, outputs send
    what the widgets' mappings send.
    """

    #: Frames per second sent to connected hardware
    fps = 30

    def __init__(self, layout: dict | None = None, *, connect: bool = False):
        """``connect``: connect the layout's devices and outputs as they are added (unless disconnected)."""
        self.lock = threading.RLock()
        # Separate from ``lock``: events arrive from device and transport threads holding the surface lock
        self._events_lock = threading.Lock()
        self.layout = None
        self.ui = None
        self.device = None
        self.transport = None
        self.events = collections.deque(maxlen = 500)
        self.event_counter = 0
        # A tempo set by a link, until the layout's tempo changes
        self.tempo = None
        # Widgets hidden in the designer only (by name), to see what's underneath
        self.hidden = set()
        self.connect = connect
        # Connections switched on or off by hand, by connection key: True or False
        self.choices = {}
        # One entry per layout device and output: {'key', 'device' (or None), 'error'}
        self.hardware = []
        self.outputs = []
        self.proxies = {}
        self._render_stop = None
        self.load(layout or new_layout())
        self._watch_stop = threading.Event()
        threading.Thread(target = self._watch, args = (self._watch_stop,), name = 'DesignerHotplug', daemon = True).start()

    def load(self, layout: dict) -> None:
        """
        Rebuild from ``layout`` (upgraded to the current version); raises
        LayoutError and keeps the previous layout if it is invalid. Widgets keep
        what input changed (values, steps...) unless their options changed it.
        """
        layout = pyxelwidgets.parser.upgrade(layout)
        ui = pyxelwidgets.parser.load(copy.deepcopy(layout), devices = False)
        device = PreviewDevice(width = ui.surface.rect.w, height = ui.surface.rect.h, held_time = 0.6)
        device.connect()
        ui.surface.add_device(device)
        for widget in ui.widgets.values():
            widget.on(pyxelwidgets.events.WidgetEvent, self._record)
        # Mappings send to stand-ins that log, and forward to the connected outputs
        proxies = {entry['name']: _OutputProxy(self, entry['name']) for entry in ui.output_settings()}
        ui.mappings = ui.map(proxies)
        # Transport actions play and stop the preview
        ui.links += ui.link(_PreviewActions(self), widgets = False)
        with self.lock:
            playing = self.transport is not None
            self.stop()
            old = self.ui
            if old is not None:
                _carry_state(old, self.layout, ui, layout)
                old.close_clocks()
                if (self.layout.get('transport') or {}).get('bpm') != (layout.get('transport') or {}).get('bpm'):
                    self.tempo = None
            for proxy in self.proxies.values():
                proxy.detach()
            self.layout, self.ui, self.device, self.proxies = copy.deepcopy(layout), ui, device, proxies
            self._attach(old)
            self._hide(set(), self.hidden)
            ui.surface.transport = self._idle(ui)
            # Widgets with clocks of their own run while editing
            ui.start_clocks(lock = ui.surface.lock)
            if playing:
                self.play()

    def set_hidden(self, names) -> None:
        """Hide widgets (by name) in the preview only, e.g. to see what's underneath; the layout is unchanged."""
        with self.lock:
            before, self.hidden = self.hidden, set(names)
            self._hide(before, self.hidden)

    def _hide(self, before: set, after: set) -> None:
        widgets = _entries(self.layout.get('widgets'))
        with self.ui.surface.lock:
            for name in before | after:
                widget = self.ui.widgets.get(name)
                if widget is None:
                    continue
                if name in after:
                    widget.visible = False
                else:
                    widget.visible = ((widgets.get(name) or {}).get('options') or {}).get('visible', True)

    def _record(self, event) -> None:
        self._append(_event_json(event))

    def _log(self, name: str, kind: str, fields: dict) -> None:
        self._append({'event': kind, 'widget': name, **fields})

    def _append(self, entry: dict) -> None:
        with self._events_lock:
            self.event_counter += 1
            self.events.append((self.event_counter, entry))

    # Hardware: the layout's devices mirror the preview, its outputs send

    def set_connected(self, kind: str, index: int, connected: bool) -> dict:
        """Connect or disconnect layout ``devices[index]`` or ``outputs[index]`` (``kind``); returns the status."""
        entries = self.layout.get(kind) or []
        if kind not in ('devices', 'outputs') or not 0 <= index < len(entries):
            raise ValueError(f'no {kind} entry {index}')
        with self.lock:
            self.choices[_device_key(entries[index])] = bool(connected)
            self._attach(self.ui)
            return self.hardware_status()

    def set_hardware(self, enabled: bool) -> dict:
        """Connect (or close) every device and output of the layout, and the ones added later."""
        with self.lock:
            self.connect = enabled
            self.choices = {}
            self._attach(self.ui)
            return self.hardware_status()

    def hardware_status(self) -> dict:
        def status(entries):
            found = []
            for entry in entries:
                device = entry['device']
                connected = device is not None and device.connected
                error = entry['error']
                if device is not None and not connected and getattr(device, 'lost', False):
                    error = f'not plugged in: connects when it is (ports matching {", ".join(type(device).ports) or "its ports"})'
                status = {'connected': connected, 'error': error}
                # A browser grid's address
                if connected and getattr(device, 'url', None):
                    status['url'] = device.url
                found.append(status)
            return found
        return {'devices': status(self.hardware), 'outputs': status(self.outputs)}

    def _wanted(self, spec: dict) -> bool:
        return self.choices.get(_device_key(spec), self.connect)

    def _attach(self, old_ui) -> None:
        """Connect the current layout's devices and outputs as wanted, reusing open ones for unchanged entries."""
        pool = {}
        for entry in self.hardware:
            if entry['device'] is not None:
                if old_ui is not None:
                    old_ui.surface.remove_device(entry['device'])
                pool.setdefault(entry['key'], []).append(entry['device'])
        self.hardware = []
        for index, spec in enumerate(self.layout.get('devices', [])):
            device, error = self._take(pool, spec, index, self._open)
            if device is not None:
                self.ui.surface.add_device(device, spec.get('x', 0), spec.get('y', 0))
                device.invalidate()
            self.hardware.append({'key': _device_key(spec), 'device': device, 'error': error})
        # Removing devices from the old surface removed their bindings
        self.ui.bind([entry['device'] for entry in self.hardware], _PreviewActions(self))
        outputs = {}
        for entry in self.outputs:
            if entry['device'] is not None:
                outputs.setdefault(entry['key'], []).append(entry['device'])
        self.outputs = []
        for proxy in self.proxies.values():
            proxy.detach()
        for index, spec in enumerate(self.layout.get('outputs') or []):
            output, error = self._take(outputs, spec, index, self._open_output)
            if output is not None and spec['name'] in self.proxies:
                self.proxies[spec['name']].attach(output)
            self.outputs.append({'key': _device_key(spec), 'device': output, 'error': error})
        for entries in (*pool.values(), *outputs.values()):
            for entry in entries:
                entry.close()
        if any(entry['device'] is not None for entry in self.hardware) and self._render_stop is None:
            self._render_stop = threading.Event()
            threading.Thread(target = self._render, args = (self._render_stop,), name = 'DesignerHardware', daemon = True).start()

    def _take(self, pool: dict, spec: dict, index: int, open) -> tuple:
        """(connection, None), (None, why not) or (None, None) when it's disconnected on purpose."""
        if not self._wanted(spec):
            return None, None
        reused = pool.get(_device_key(spec))
        if reused:
            return reused.pop(0), None
        return open(spec, index)

    @staticmethod
    def _open(spec: dict, index: int) -> tuple:
        """(device, None) or (None, why it couldn't be connected)."""
        if spec.get('type', '').startswith('virtual.'):
            return None, 'on-screen device: shown in the browser only'
        try:
            device = pyxelwidgets.parser.build_device(spec, f'devices[{index}]')
        except Exception as error:
            return None, str(error) or type(error).__name__
        if not device.connected and not getattr(device, 'lost', False):
            cls = type(device)
            return None, f'no MIDI port found (looked for {", ".join(cls.ports) or "nothing"})'
        # A device not plugged in yet is kept: it connects when it is (see _watch)
        return device, None

    @staticmethod
    def _open_output(spec: dict, index: int) -> tuple:
        try:
            output = pyxelwidgets.parser.build_output(spec, f'outputs[{index}]')
        except Exception as error:
            return None, str(error) or type(error).__name__
        if not output.connected and not getattr(output, 'lost', False):
            output.close()
            return None, 'no port: give it a virtual port name, or input/output ports'
        return output, None

    #: Seconds between checks for unplugged and plugged in hardware
    check_interval = 1.0

    def _watch(self, stop: threading.Event) -> None:
        """Let connected (and waiting) devices and outputs notice being unplugged or plugged in."""
        while not stop.wait(self.check_interval):
            with self.lock:
                ui = self.ui
                devices = [entry['device'] for entry in (*self.hardware, *self.outputs) if entry['device'] is not None]
            if ui is None or not devices:
                continue
            for device in ui.surface.check_devices(devices):
                state = 'reconnected' if device.connected else 'unplugged'
                self._log(device.name, f'device {state}', {})

    def _render(self, stop: threading.Event) -> None:
        """Send frames to the hardware (the browser only renders when it asks for a frame)."""
        while not stop.wait(1.0 / self.fps):
            with self.lock:
                if stop.is_set():
                    return
                self.ui.surface.update()

    def close(self) -> None:
        self._watch_stop.set()
        self.stop()
        with self.lock:
            self.ui.close_clocks()
            self.connect = False
            self.choices = {}
            self._attach(self.ui)
            if self._render_stop is not None:
                self._render_stop.set()
                self._render_stop = None

    def frame(self, since: int = 0) -> dict:
        """Render; pixels are ``#rrggbb`` rows from the top, plus events after ``since``."""
        with self.lock:
            surface = self.ui.surface
            surface.update()
            buffer = surface.buffer
            rows = [[f'#{int(buffer[x, y, 0]):02x}{int(buffer[x, y, 1]):02x}{int(buffer[x, y, 2]):02x}' for x in range(buffer.shape[0])]
                    for y in reversed(range(buffer.shape[1]))]
            with self._events_lock:
                events = [dict(event, id = number) for number, event in self.events if number > since]
            transport = self.transport
            return {'width': buffer.shape[0], 'height': buffer.shape[1], 'pixels': rows, 'events': events,
                    'playing': transport is not None,
                    'position': f'{transport.bar + 1}.{transport.beat + 1}' if transport is not None else None,
                    'hardware': self.hardware_status()}

    def input(self, x: int, y: int, velocity: float) -> None:
        """Press (``velocity`` > 0) or release the surface pad at ``x``, ``y``."""
        with self.lock:
            self.device.set_button(x, y, velocity)

    def play(self) -> None:
        """Play the layout's transport from the start so Sequencers and Trackers play."""
        with self.lock:
            if self.transport is not None:
                return
            self.transport = pyxelwidgets.transport.Transport(**self._settings(self.ui), lock = self.ui.surface.lock)
            self.ui.attach(self.transport)
            # Animations follow the music while playing
            self.ui.surface.transport = self.transport
            self.transport.play()

    def _settings(self, ui) -> dict:
        settings = ui.transport_settings()
        if self.tempo is not None:
            settings['bpm'] = self.tempo
        return settings

    def _idle(self, ui):
        # A stopped transport: animations run at the layout's tempo while not playing
        return pyxelwidgets.transport.Transport(**self._settings(ui))

    @property
    def bpm(self) -> float:
        """The tempo: the layout's, or one a link set."""
        return self.tempo if self.tempo is not None else self.ui.transport_settings()['bpm']

    def set_tempo(self, bpm: float) -> None:
        """Change the tempo (from a link) until the layout's tempo changes."""
        self.tempo = float(bpm)
        transport = self.transport if self.transport is not None else self.ui.surface.transport
        if transport is not None:
            transport.bpm = self.tempo

    def stop(self) -> None:
        with self.lock:
            transport, self.transport = self.transport, None
            if self.ui is not None:
                self.ui.surface.transport = self._idle(self.ui)
        if transport is not None:
            transport.close()

class Designer:
    """The designer's state: the preview and the file it saves to."""

    def __init__(self, path: str | None = None, *, connect: bool = True):
        self.path = pathlib.Path(path) if path else None
        layout = json.loads(self.path.read_text()) if self.path and self.path.exists() else new_layout()
        self.preview = Preview(layout, connect = connect)
        self.catalog = catalog()

    def close(self) -> None:
        """Stop the transport and close connected hardware."""
        self.preview.close()

    def save(self, layout: dict) -> None:
        if self.path is None:
            raise ValueError('The designer was started without a file; use Download instead')
        self.preview.load(layout)
        self.path.write_text(json.dumps(self.preview.layout, indent = 2) + '\n')

class Handler(http.server.BaseHTTPRequestHandler):
    designer: Designer = None
    static = importlib.resources.files(__name__) / 'static'

    def log_message(self, format, *args) -> None:
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data).encode(), 'application/json')

    def _body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length) or b'null')

    def do_GET(self) -> None:
        url = urllib.parse.urlparse(self.path)
        preview = self.designer.preview
        if url.path == '/api/catalog':
            self._json(self.designer.catalog)
        elif url.path == '/api/layout':
            self._json({'layout': preview.layout, 'file': str(self.designer.path) if self.designer.path else None})
        elif url.path == '/api/frame':
            since = int(urllib.parse.parse_qs(url.query).get('since', ['0'])[0])
            self._json(preview.frame(since))
        else:
            name = 'index.html' if url.path in ('/', '/index.html') else url.path.lstrip('/')
            resource = self.static / name
            if '..' in name or not resource.is_file():
                self._send(404, b'Not found', 'text/plain')
                return
            content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            if content_type.startswith('text/') or content_type.endswith('javascript'):
                content_type += '; charset=utf-8'
            self._send(200, resource.read_bytes(), content_type)

    def do_PUT(self) -> None:
        if urllib.parse.urlparse(self.path).path != '/api/layout':
            self._send(404, b'Not found', 'text/plain')
            return
        try:
            self.designer.preview.load(self._body())
        except (pyxelwidgets.parser.LayoutError, ValueError, TypeError, KeyError) as error:
            self._json({'ok': False, 'error': str(error)}, 400)
            return
        # The layout as loaded, e.g. upgraded from an older version
        self._json({'ok': True, 'layout': self.designer.preview.layout})

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        preview = self.designer.preview
        try:
            body = self._body()
            if path == '/api/input':
                preview.input(int(body['x']), int(body['y']), float(body['velocity']))
            elif path == '/api/play':
                preview.play() if body.get('playing') else preview.stop()
            elif path == '/api/save':
                self.designer.save(body)
            elif path == '/api/view':
                preview.set_hidden([str(name) for name in body.get('hidden', [])])
            elif path == '/api/connect':
                self._json({'ok': True, **preview.set_connected(str(body['kind']), int(body['index']), bool(body['connected']))})
                return
            else:
                self._send(404, b'Not found', 'text/plain')
                return
        except (pyxelwidgets.parser.LayoutError, ValueError, TypeError, KeyError) as error:
            self._json({'ok': False, 'error': str(error)}, 400)
            return
        self._json({'ok': True})

def serve(path: str | None = None, port: int = 8765, host: str = '127.0.0.1', *, connect: bool = True) -> http.server.ThreadingHTTPServer:
    """
    Start the designer's web server (not yet serving: call ``serve_forever``).
    With ``connect`` (default), the layout's devices and outputs connect as they're added.
    """
    handler = type('DesignerHandler', (Handler,), {'designer': Designer(path, connect = connect)})
    return http.server.ThreadingHTTPServer((host, port), handler)
