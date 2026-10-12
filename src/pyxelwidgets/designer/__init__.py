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
import pyxelwidgets.parser
import pyxelwidgets.transport

__all__ = ['Preview', 'Designer', 'new_layout', 'catalog']

DEVICE_MODULES = ['novation', 'akai', 'ableton', 'presonus', 'virtual']

def new_layout(width: int = 9, height: int = 9) -> dict:
    return {
        'format': pyxelwidgets.parser.FORMAT,
        'version': pyxelwidgets.parser.VERSION,
        'surface': {'width': width, 'height': height},
        'transport': {'bpm': 120, 'signature': [4, 4]},
        'devices': [],
        'widgets': [],
    }

def catalog() -> dict:
    """Everything the designer UI offers: widget and binding options, devices and named colors."""
    devices = []
    for module_name in DEVICE_MODULES:
        try:
            module = importlib.import_module(f'pyxelwidgets.devices.{module_name}')
        except ImportError:
            continue
        for name in getattr(module, '__all__', []):
            cls = getattr(module, name)
            if isinstance(cls, type) and issubclass(cls, pyxelwidgets.devices.Device):
                info = cls.describe()
                info['type'] = f'{module_name}.{name}'
                info['options'] = pyxelwidgets.parser.option_schema(cls)
                devices.append(info)
    colors = {name: pyxelwidgets.parser.color_to_text(value) for name, value in vars(pyxelwidgets.color.Colors).items()
              if isinstance(value, pyxelwidgets.color.Color)}
    schema = pyxelwidgets.parser.schema()
    return {'widgets': schema['widgets'], 'animations': schema['animations'], 'binding': schema['binding'],
            'devices': devices, 'colors': colors}

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
    """What makes two layout device entries the same connection (position aside)."""
    return json.dumps({key: device.get(key) for key in ('type', 'options', 'input', 'output')}, sort_keys = True)

class _PreviewActions:
    """Binding actions for the preview: its transport only exists while playing."""

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

class Preview:
    """
    A layout built without hardware, with a preview device, an event log and a
    transport to play it. With ``set_hardware(True)`` the layout's devices are
    connected too: they mirror the preview and their pads work the widgets.
    """

    #: Frames per second sent to connected hardware
    fps = 30

    def __init__(self, layout: dict | None = None):
        self.lock = threading.RLock()
        # Separate from ``lock``: events arrive from device and transport threads holding the surface lock
        self._events_lock = threading.Lock()
        self.layout = None
        self.ui = None
        self.device = None
        self.transport = None
        self.events = collections.deque(maxlen = 500)
        self.event_counter = 0
        self.hardware_enabled = False
        # One entry per layout device: {'key', 'device' (or None), 'error'}
        self.hardware = []
        self._render_stop = None
        self.load(layout or new_layout())

    def load(self, layout: dict) -> None:
        """Rebuild from ``layout`` (upgraded to the current version); raises LayoutError and keeps the previous layout if it is invalid."""
        layout = pyxelwidgets.parser.upgrade(layout)
        ui = pyxelwidgets.parser.load(copy.deepcopy(layout), devices = False)
        device = PreviewDevice(width = ui.surface.rect.w, height = ui.surface.rect.h, held_time = 0.6)
        device.connect()
        ui.surface.add_device(device)
        ui.surface.transport = self._idle(ui)
        for widget in ui.widgets.values():
            widget.on(pyxelwidgets.events.WidgetEvent, self._record)
        with self.lock:
            playing = self.transport is not None
            self.stop()
            old = self.ui
            self.layout, self.ui, self.device = copy.deepcopy(layout), ui, device
            if self.hardware_enabled:
                self._attach_hardware(old)
            if playing:
                self.play()

    def _record(self, event) -> None:
        with self._events_lock:
            self.event_counter += 1
            self.events.append((self.event_counter, _event_json(event)))

    # Hardware

    def set_hardware(self, enabled: bool) -> list:
        """Connect (or close) the layout's devices; returns their status."""
        with self.lock:
            if enabled and not self.hardware_enabled:
                self.hardware_enabled = True
                self._attach_hardware(None)
                self._render_stop = threading.Event()
                threading.Thread(target = self._render, args = (self._render_stop,), name = 'DesignerHardware', daemon = True).start()
            elif not enabled and self.hardware_enabled:
                self.hardware_enabled = False
                self._render_stop.set()
                for entry in self.hardware:
                    if entry['device'] is not None:
                        self.ui.surface.remove_device(entry['device'])
                        entry['device'].close()
                self.hardware = []
            return self.hardware_status()

    def hardware_status(self) -> list:
        return [{'connected': entry['device'] is not None, 'error': entry['error']} for entry in self.hardware]

    def _attach_hardware(self, old_ui) -> None:
        """Connect the current layout's devices, reusing the ones already open for unchanged entries."""
        pool = {}
        for entry in self.hardware:
            if entry['device'] is not None:
                if old_ui is not None:
                    old_ui.surface.remove_device(entry['device'])
                pool.setdefault(entry['key'], []).append(entry['device'])
        self.hardware = []
        for index, spec in enumerate(self.layout.get('devices', [])):
            key = _device_key(spec)
            reused = pool.get(key)
            device, error = (reused.pop(0) if reused else None), None
            if device is None:
                device, error = self._open(spec, index)
            if device is not None:
                self.ui.surface.add_device(device, spec.get('x', 0), spec.get('y', 0))
                device.invalidate()
            self.hardware.append({'key': key, 'device': device, 'error': error})
        for devices in pool.values():
            for device in devices:
                device.close()
        # Removing devices from the old surface removed their bindings
        self.ui.bind([entry['device'] for entry in self.hardware], _PreviewActions(self))

    @staticmethod
    def _open(spec: dict, index: int) -> tuple:
        """(device, None) or (None, why it couldn't be connected)."""
        if spec.get('type', '').startswith('virtual.'):
            return None, 'on-screen device: shown in the browser only'
        try:
            device = pyxelwidgets.parser.build_device(spec, f'devices[{index}]')
        except Exception as error:
            return None, str(error) or type(error).__name__
        if not device.connected:
            cls = type(device)
            return None, f'no MIDI port found (looked for {", ".join(cls.ports) or "nothing"})'
        return device, None

    def _render(self, stop: threading.Event) -> None:
        """Send frames to the hardware (the browser only renders when it asks for a frame)."""
        while not stop.wait(1.0 / self.fps):
            with self.lock:
                if stop.is_set():
                    return
                self.ui.surface.update()

    def close(self) -> None:
        self.stop()
        self.set_hardware(False)

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
                    'hardware': {'enabled': self.hardware_enabled, 'devices': self.hardware_status()}}

    def input(self, x: int, y: int, velocity: float) -> None:
        """Press (``velocity`` > 0) or release the surface pad at ``x``, ``y``."""
        with self.lock:
            self.device.set_button(x, y, velocity)

    def play(self) -> None:
        """Play the layout's transport from the start so Sequencers and Trackers play."""
        with self.lock:
            if self.transport is not None:
                return
            self.transport = pyxelwidgets.transport.Transport(**self.ui.transport_settings(), lock = self.ui.surface.lock)
            self.ui.attach(self.transport)
            # Animations follow the music while playing
            self.ui.surface.transport = self.transport
            self.transport.play()

    @staticmethod
    def _idle(ui):
        # A stopped transport: animations run at the layout's tempo while not playing
        return pyxelwidgets.transport.Transport(**ui.transport_settings())

    def stop(self) -> None:
        with self.lock:
            transport, self.transport = self.transport, None
            if self.ui is not None:
                self.ui.surface.transport = self._idle(self.ui)
        if transport is not None:
            transport.close()

class Designer:
    """The designer's state: the preview and the file it saves to."""

    def __init__(self, path: str | None = None, *, hardware: bool = False):
        self.path = pathlib.Path(path) if path else None
        layout = json.loads(self.path.read_text()) if self.path and self.path.exists() else new_layout()
        self.preview = Preview(layout)
        self.catalog = catalog()
        if hardware:
            self.preview.set_hardware(True)

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
            elif path == '/api/hardware':
                self._json({'ok': True, 'devices': preview.set_hardware(bool(body.get('enabled')))})
                return
            else:
                self._send(404, b'Not found', 'text/plain')
                return
        except (pyxelwidgets.parser.LayoutError, ValueError, TypeError, KeyError) as error:
            self._json({'ok': False, 'error': str(error)}, 400)
            return
        self._json({'ok': True})

def serve(path: str | None = None, port: int = 8765, host: str = '127.0.0.1', *, hardware: bool = False) -> http.server.ThreadingHTTPServer:
    """
    Start the designer's web server (not yet serving: call ``serve_forever``).
    With ``hardware``, the layout's devices mirror the preview from the start.
    """
    handler = type('DesignerHandler', (Handler,), {'designer': Designer(path, hardware = hardware)})
    return http.server.ThreadingHTTPServer((host, port), handler)
