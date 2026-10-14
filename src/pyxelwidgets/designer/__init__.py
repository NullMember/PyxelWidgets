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
import ipaddress
import importlib.resources
import json
import os
import mimetypes
import pathlib
import re
import platform
import threading
import time
import urllib.parse

import pyxelwidgets.buffer
import pyxelwidgets.codegen
import pyxelwidgets.color
import pyxelwidgets.devices
import pyxelwidgets.events
import pyxelwidgets.message
import pyxelwidgets.parser
import pyxelwidgets.transport
import pyxelwidgets.widgets

from .dialogs import Unavailable, pick_file

__all__ = ['Preview', 'Designer', 'new_layout', 'catalog']

DEVICE_MODULES = ['novation', 'akai', 'ableton', 'arturia', 'presonus', 'virtual', 'web']
OUTPUT_MODULES = ['midi_port', 'rtp_midi', 'ble_midi', 'mackie', 'osc', 'desktop']

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
    info['doc'] = pyxelwidgets.parser._doc(cls)
    info['options'] = pyxelwidgets.parser.option_schema(cls)
    # Connected in the designer only when asked (the keyboard and mouse)
    info['auto_connect'] = getattr(cls, 'auto_connect', True)
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
    'PianoRoll': ((4, 4), {'octave': 4}),
    'ChordPads': ((4, 3), {}),
    'Arpeggiator': ((4, 2), {}),
    'Euclidean': ((4, 3), {}),
    'Automaton': ((4, 4), {}),
    'TapTempo': ((2, 2), {}),
    'Stepper': ((4, 1), {'value': 0.5}),
    'MeterBank': ((4, 4), {}),
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
        elif name == 'PianoRoll':
            for step, row, length in ((0, 0, 2), (2, 2, 1), (3, 1, 1)):
                widget.add_note(step, widget.rows()[row], length)
        elif name == 'ChordPads':
            widget._held[(1, 0)] = []
        elif name == 'Arpeggiator':
            widget.held[:] = [widget.note_at(0, 0), widget.note_at(2, 0)]
            widget._sounding = widget.note_at(2, 0)
        elif name == 'Euclidean':
            widget.pulses[:] = [3, 2, 1]
        elif name == 'Automaton':
            for x, y in ((1, 2), (2, 1), (0, 0), (1, 0), (2, 0)):
                widget.cells[x, y] = True
        elif name == 'MeterBank':
            for channel, level in enumerate((0.5, 0.95, 0.7, 0.3)):
                widget.set_level(channel, level)
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
            'link': schema['link'], 'expression': schema['expression'], 'colors': colors}

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
        # `_learn`: the message as layout JSON, for the page's Learn buttons (not shown)
        self.preview._log(self.name, f'← {type(event.message).__name__}',
                          {**_message_json(event.message), '_learn': pyxelwidgets.parser.message_to_json(event.message)})
        self.emit(pyxelwidgets.events.MessageReceived(self, event.message))

class _PreviewActions:
    """Binding and link actions for the preview: its transport only exists while playing."""

    def __init__(self, preview):
        self.preview = preview

    @property
    def playing(self) -> bool:
        # Lights bound play/toggle buttons (Surface.control_light)
        return self.preview.playing

    # Called from device threads holding the surface lock; play/stop take the preview lock first
    def _later(self, action) -> None:
        threading.Thread(target = action, daemon = True).start()

    def play(self) -> None:
        self._later(self.preview.play)

    def stop(self) -> None:
        self._later(self.preview.stop)

    def toggle(self) -> None:
        self._later(lambda: self.preview.stop() if self.preview.playing else self.preview.play())

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

def _layout_value(entry: dict | None, key: str):
    """A widget entry's position, size or option ``key`` (None: the default)."""
    entry = entry or {}
    if key in ('x', 'y', 'width', 'height'):
        return entry.get(key, 0 if key in ('x', 'y') else 1)
    return (entry.get('options') or {}).get(key)

def _carry_state(old_ui, old_layout: dict, ui, layout: dict) -> None:
    """Give the widgets of a rebuilt layout the state of the ones they replace (same name and type)."""
    entries = pyxelwidgets.parser.widget_entries
    before, after = entries(old_layout.get('widgets')), entries(layout.get('widgets'))
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
        # Following a DAW's clock (the layout's transport.sync): {'key', 'input' (a MidiClockInput or None), 'error'}
        self.sync = None
        # A device being checked (check_device): its test pattern and what it reported
        self.check = None
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
        # Connected devices' knobs, faders and buttons (for the page's Learn buttons too)
        ui.surface.on(pyxelwidgets.events.ControlEvent, self._control)
        # Mappings send to stand-ins that log, and forward to the connected outputs
        proxies = {entry['name']: _OutputProxy(self, entry['name']) for entry in ui.output_settings()}
        ui.mappings = ui.map(proxies)
        # Transport actions play and stop the preview
        ui.links += ui.link(_PreviewActions(self), widgets = False)
        # Debug links write to the event log
        ui.debug = lambda widget, text: self._log(widget, 'Debug', {'text': text})
        with self.lock:
            # A DAW's clock keeps playing across edits; the preview's own transport restarts
            followed = self.transport if self.synced else None
            playing = self.transport is not None and not self.synced
            if followed is None:
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
            if self.check is not None:
                # The new surface shows the check's test pattern too
                self._show_check()
            self._hide(set(), self.hidden)
            ui.surface.transport = self._idle(ui)
            # Widgets with clocks of their own run while editing
            ui.start_clocks(lock = ui.surface.lock)
            self._follow(ui, followed)
            if playing:
                self.play()

    def set_hidden(self, names) -> None:
        """Hide widgets (by name) in the preview only, e.g. to see what's underneath; the layout is unchanged."""
        with self.lock:
            before, self.hidden = self.hidden, set(names)
            self._hide(before, self.hidden)

    def _hide(self, before: set, after: set) -> None:
        widgets = pyxelwidgets.parser.widget_entries(self.layout.get('widgets'))
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
        entry = _event_json(event)
        if isinstance(event, pyxelwidgets.events.PresetStored) and event.widget.save:
            # The page puts them in the layout, so saving keeps them
            entry['presets'] = event.widget.stored()
        self._append(entry)

    def _control(self, event) -> None:
        index = next((i for i, entry in enumerate(self.hardware) if entry['device'] is event.device), None)
        if index is None:
            return
        entry = _event_json(event)
        entry.pop('device', None)
        self._append({**entry, 'widget': f'{index + 1}. {type(event.device).__name__}', '_device': index})

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
                if connected and getattr(device, 'warning', None):
                    status['warning'] = device.warning
                # A browser grid's address
                if connected and getattr(device, 'url', None):
                    status['url'] = device.url
                # Who is connected to a network or Bluetooth output
                if connected and getattr(device, 'status_text', None):
                    status['text'] = device.status_text
                found.append(status)
            return found
        sync = None
        if self.sync is not None:
            clock = self.sync['input']
            connected = clock is not None and clock.connected
            error = self.sync['error']
            if clock is not None and not connected and getattr(clock, 'lost', False):
                error = f'waiting for the port {self.ui.sync_settings().get("input")!r}'
            sync = {'connected': connected, 'error': error}
        found = {'devices': status(self.hardware), 'outputs': status(self.outputs)}
        if sync is not None:
            found['sync'] = sync
        return found

    def scan(self, index: int, what: str, track: str | None = None, plugin: str | None = None) -> dict:
        """
        Scan the DAW through connected output ``index`` (Mackie Control): ``what``
        is ``tracks``, ``plugins`` (of ``track``), ``parameters`` (of ``plugin``
        on ``track``) or ``known`` (what earlier scans found). Returns the names
        found and everything scanned so far. Takes seconds: the DAW is driven.
        """
        with self.lock:
            entry = self.outputs[index] if 0 <= index < len(self.outputs) else None
            output = entry['device'] if entry is not None else None
        if output is None or not callable(getattr(output, 'scan_tracks', None)):
            if what == 'known':
                return {'names': [], 'scanned': None}
            raise ValueError('Connect the output first (Connect on its row), so the DAW can be scanned')
        if what == 'tracks':
            names = output.scan_tracks()
        elif what == 'plugins':
            names = output.scan_plugins(str(track))
        elif what == 'parameters':
            names = output.scan_parameters(str(track), str(plugin))
        elif what == 'known':
            names = []
        else:
            raise ValueError(f'nothing to scan called {what!r}')
        return {'names': names, 'scanned': output.scanned()}

    def _wanted(self, spec: dict) -> bool:
        automatic = self.connect
        if automatic:
            try:
                # Some outputs (the keyboard and mouse) wait for Connect
                automatic = getattr(pyxelwidgets.parser.device_class(spec), 'auto_connect', True)
            except pyxelwidgets.parser.LayoutError:
                pass
        return self.choices.get(_device_key(spec), automatic)

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
        if self.check is not None and all(entry['device'] is not self.check['device'] for entry in self.hardware):
            # The device checked is gone (disconnected or removed)
            self.check = None
        for entries in (*pool.values(), *outputs.values()):
            for entry in entries:
                entry.close()
        if any(entry['device'] is not None for entry in self.hardware):
            self._start_render()

    def _start_render(self) -> None:
        if self._render_stop is None:
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

    # Checking a device: test patterns on it, and what it reports (the page's device check)

    #: Test patterns a check shows
    CHECK_PATTERNS = ('corners', 'colors', 'pads', 'off')
    #: Colors of the 'colors' pattern's rows, from the bottom
    CHECK_COLORS = ('Red', 'Lime', 'Blue', 'Yellow', 'White', 'Cyan', 'Magenta', 'Orange')
    #: Raw MIDI messages a check keeps
    check_limit = 400

    def check_device(self, index: int, pattern: str | None) -> dict:
        """
        Check connected layout device ``index``: show test ``pattern`` on it
        (``CHECK_PATTERNS``) and record its pads, controls and raw MIDI; None
        ends the check. Returns ``check_status()``.
        """
        with self.lock:
            if pattern is None:
                self._end_check()
                return {}
            if pattern not in self.CHECK_PATTERNS:
                raise ValueError(f'unknown pattern {pattern!r} (patterns: {", ".join(self.CHECK_PATTERNS)})')
            device = self.hardware[index]['device'] if 0 <= index < len(self.hardware) else None
            if device is None or not device.connected:
                raise ValueError('connect the device first')
            if self.check is None or self.check['device'] is not device:
                self._end_check()
                self.check = {'device': device, 'index': index, 'pressed': [], 'held': set(), 'controls': {}, 'raw': [],
                              'start': time.monotonic()}
                device.on(pyxelwidgets.events.PadEvent, self._check_pad)
                device.on(pyxelwidgets.events.ControlEvent, self._check_control)
                if hasattr(device, 'raw_listeners'):
                    device.raw_listeners.append(self._check_raw)
            self.check['pattern'] = pattern
            self._show_check()
            return self.check_status()

    def check_status(self) -> dict:
        """What the device being checked reported: pads pressed (in order) and held, controls, raw MIDI."""
        with self.lock:
            check = self.check
            if check is None:
                return {}
            device = check['device']
            return {'index': check['index'], 'pattern': check['pattern'], 'type': pyxelwidgets.parser.device_type(type(device)),
                    'model': getattr(device, 'model', type(device).__name__), 'width': device.width, 'height': device.height,
                    'ports': [getattr(device, '_midi_input_name', None), getattr(device, '_midi_output_name', None)],
                    'pressed': list(check['pressed']), 'held': sorted(check['held']),
                    'controls': dict(check['controls']), 'raw': list(check['raw']),
                    'system': {'platform': platform.platform(), 'python': platform.python_version(),
                               'pyxelwidgets': getattr(pyxelwidgets, '__version__', '?')}}

    def _check_pad(self, event) -> None:
        check = self.check
        if check is None:
            return
        if isinstance(event, pyxelwidgets.events.PadPressed):
            check['pressed'] = (check['pressed'] + [[event.x, event.y]])[-200:]
            check['held'].add((event.x, event.y))
        elif isinstance(event, pyxelwidgets.events.PadReleased):
            check['held'].discard((event.x, event.y))
        if check['pattern'] == 'pads':
            self._show_check()

    def _check_control(self, event) -> None:
        check = self.check
        if check is None:
            return
        seen = check['controls'].setdefault(event.control, {'events': 0})
        seen['events'] += 1
        seen['last'] = type(event).__name__
        for field in ('value', 'delta', 'velocity'):
            if hasattr(event, field):
                seen[field] = getattr(event, field)

    def _check_raw(self, midi: list) -> None:
        check = self.check
        if check is not None:
            check['raw'] = (check['raw'] + [[round(time.monotonic() - check['start'], 3), midi]])[-self.check_limit:]

    def _show_check(self) -> None:
        check = self.check
        device = check['device']
        width, height = device.width, device.height
        colors = pyxelwidgets.color.Colors
        frame = pyxelwidgets.buffer.new(width, height, colors.Black)
        if check['pattern'] == 'corners':
            frame[0, 0] = colors.Red
            frame[0, height - 1] = colors.Lime
            frame[width - 1, height - 1] = colors.Blue
        elif check['pattern'] == 'colors':
            for y in range(height):
                frame[:, y] = getattr(colors, self.CHECK_COLORS[y % len(self.CHECK_COLORS)])
        elif check['pattern'] == 'pads':
            for x, y in {tuple(place) for place in check['pressed']}:
                if 0 <= x < width and 0 <= y < height:
                    frame[x, y] = pyxelwidgets.color.Color(48, 48, 48)
            for x, y in check['held']:
                if 0 <= x < width and 0 <= y < height:
                    frame[x, y] = colors.White
        self.ui.surface.test_pattern(device, frame)

    def _end_check(self) -> None:
        check, self.check = self.check, None
        if check is None:
            return
        device = check['device']
        device.off(pyxelwidgets.events.PadEvent, self._check_pad)
        device.off(pyxelwidgets.events.ControlEvent, self._check_control)
        if self._check_raw in getattr(device, 'raw_listeners', []):
            device.raw_listeners.remove(self._check_raw)
        self.ui.surface.test_pattern(device, None)

    #: Seconds between checks for unplugged and plugged in hardware
    check_interval = 1.0

    def _watch(self, stop: threading.Event) -> None:
        """Let connected (and waiting) devices and outputs notice being unplugged or plugged in."""
        while not stop.wait(self.check_interval):
            with self.lock:
                ui = self.ui
                devices = [entry['device'] for entry in (*self.hardware, *self.outputs) if entry['device'] is not None]
                if self.sync is not None and self.sync['input'] is not None:
                    devices.append(self.sync['input'])
            if ui is None or not devices:
                continue
            for device in ui.surface.check_devices(devices):
                state = 'reconnected' if device.connected else 'unplugged'
                self._log(device.name, f'device {state}', {})

    def _render(self, stop: threading.Event) -> None:
        """Send frames to the hardware (the browser only renders when it asks for a frame; in Perform mode it doesn't)."""
        while not stop.wait(1.0 / self.fps):
            with self.lock:
                if stop.is_set():
                    return
                self.ui.surface.update()

    def close(self) -> None:
        self._watch_stop.set()
        self.stop()
        with self.lock:
            self._end_check()
            self._unfollow()
            self.ui.close_clocks()
            self.connect = False
            self.choices = {}
            self._attach(self.ui)
            if self._render_stop is not None:
                self._render_stop.set()
                self._render_stop = None

    def frame(self, since: int = 0, pixels: bool = True) -> dict:
        """
        Render; pixels are ``#rrggbb`` rows from the top, plus events after
        ``since``. Without ``pixels`` (the designer's Perform mode, no grid
        shown) nothing is rendered for the browser and pixels is None: the
        render thread keeps the widgets updating at ``fps`` instead.
        """
        with self.lock:
            surface = self.ui.surface
            if pixels:
                surface.update()
            else:
                self._start_render()
            buffer = surface.buffer
            rows = None
            if pixels:
                rows = [[f'#{int(buffer[x, y, 0]):02x}{int(buffer[x, y, 1]):02x}{int(buffer[x, y, 2]):02x}' for x in range(buffer.shape[0])]
                        for y in reversed(range(buffer.shape[1]))]
            with self._events_lock:
                events = [dict(event, id = number) for number, event in self.events if number > since]
            playing = self.playing
            transport = self.transport
            return {'width': buffer.shape[0], 'height': buffer.shape[1], 'pixels': rows, 'events': events,
                    'playing': playing, 'synced': self.synced,
                    # The tempo measured from the DAW's clock
                    'bpm': round(transport.bpm, 1) if self.synced and transport is not None else None,
                    'position': f'{transport.bar + 1}.{transport.beat + 1}' if playing else None,
                    # The page each Pages container shows now (pressing may have changed it)
                    'pages': {name: widget.page for name, widget in self.ui.widgets.items()
                              if isinstance(widget, pyxelwidgets.group.Pages)},
                    # Options written as formulas that can't be computed now
                    'formulas': [{'widget': formula.target.name, 'option': formula.option, 'error': formula.error}
                                 for formula in surface.formulas if formula.error],
                    'hardware': self.hardware_status()}

    def input(self, x: int, y: int, velocity: float) -> None:
        """Press (``velocity`` > 0) or release the surface pad at ``x``, ``y``."""
        with self.lock:
            self.device.set_button(x, y, velocity)

    def play(self) -> None:
        """Play the layout's transport from the start so Sequencers and Trackers play (not while a DAW plays it)."""
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

    @property
    def synced(self) -> bool:
        """Following a DAW's clock: the DAW plays and stops the transport."""
        return self.sync is not None and self.sync['input'] is not None

    @property
    def playing(self) -> bool:
        return self.transport is not None and self.transport.playing

    def _follow(self, ui, followed) -> None:
        """Follow the layout's ``transport.sync`` (keeping the open port), with a new transport for ``ui`` carrying on from ``followed``."""
        spec = ui.sync_settings()
        key = json.dumps(spec, sort_keys = True) if spec is not None else None
        wanted = spec is not None and self.connect
        if self.sync is not None and (self.sync['key'] != key or not wanted):
            self._unfollow()
        if followed is not None and (not wanted or self.sync is None):
            followed.close()
            followed = None
        if not wanted:
            self.sync = None if spec is None else {'key': key, 'input': None, 'error': 'not connected (the designer is offline)'}
            return
        settings = self._settings(ui)
        transport = pyxelwidgets.transport.Transport(followed.bpm if followed is not None else settings['bpm'], signature = settings['signature'],
                                                     sync = True, lock = ui.surface.lock)
        ui.attach(transport)
        ui.surface.transport = transport
        if followed is not None:
            transport.locate(followed.beats)
            if followed.playing:
                transport.play()
            followed.close()
        if self.sync is not None and self.sync['input'] is not None:
            self.sync['input'].transport = transport
        else:
            try:
                self.sync = {'key': key, 'input': ui.sync_input(transport), 'error': None}
            except Exception as error:
                self.sync = {'key': key, 'input': None, 'error': str(error) or type(error).__name__}
                transport.close()
                ui.surface.transport = self._idle(ui)
                return
        self.transport = transport

    def _unfollow(self) -> None:
        if self.sync is not None and self.sync['input'] is not None:
            self.sync['input'].close()
        self.sync = None
        if self.transport is not None and self.transport.sync:
            transport, self.transport = self.transport, None
            transport.close()
            if self.ui is not None:
                self.ui.surface.transport = self._idle(self.ui)

    def stop(self) -> None:
        with self.lock:
            if self.synced:
                # The DAW stops it
                return
            transport, self.transport = self.transport, None
            if self.ui is not None:
                self.ui.surface.transport = self._idle(self.ui)
        if transport is not None:
            transport.close()

class Designer:
    """The designer's state: the preview and the file it saves to."""

    def __init__(self, path: str | None = None, *, connect: bool = True, snippets: str | None = None, dialogs: bool = True):
        self.path = pathlib.Path(path) if path else None
        layout = json.loads(self.path.read_text()) if self.path and self.path.exists() else new_layout()
        self.preview = Preview(layout, connect = connect)
        self.catalog = catalog()
        #: Where the snippets you save go
        self.snippets = pathlib.Path(snippets).expanduser() if snippets else USER_SNIPPETS
        #: Shows the system's file dialog for Open and Save As: ``pick(mode, path)`` → a path or None (cancelled);
        #: None asks for paths in the page instead
        self.pick = pick_file if dialogs else None

    def close(self) -> None:
        """Stop the transport and close connected hardware."""
        self.preview.close()

    def save(self, layout: dict, path: str | None = None) -> None:
        """Save to the layout file, or to ``path``, which becomes the layout file (Save As)."""
        target = _path(path) if path else self.path
        if target is None:
            raise ValueError('Choose where to save it (Save As)')
        self.preview.load(layout)
        target.parent.mkdir(parents = True, exist_ok = True)
        target.write_text(json.dumps(self.preview.layout, indent = 2) + '\n')
        self.path = target

    def open(self, path: str) -> None:
        """Open the layout file at ``path``; it becomes the layout file."""
        target = _path(path)
        try:
            layout = json.loads(target.read_text())
        except FileNotFoundError:
            raise ValueError(f'No file {target}') from None
        except json.JSONDecodeError as error:
            raise ValueError(f'{target} is not a layout: {error}') from None
        self.preview.load(layout)
        self.path = target

    def new(self, template: str | None = None, layout: dict | None = None) -> None:
        """Start a layout: empty, from one of ``templates()``, or ``layout`` (imported); it has no file until saved."""
        if layout is not None:
            pass
        elif template:
            entry = next((entry for entry in templates() if entry['name'] == template), None)
            if entry is None:
                raise ValueError(f'No template {template!r}')
            layout = json.loads((TEMPLATES / f'{template}.json').read_text())
        else:
            layout = new_layout()
        self.preview.load(layout)
        self.path = None

def _path(path: str) -> pathlib.Path:
    path = pathlib.Path(path).expanduser()
    if path.suffix != '.json':
        path = path.with_suffix('.json')
    return path.resolve()

#: Layouts to start from
TEMPLATES = pathlib.Path(__file__).parent / 'templates'
_TEMPLATE_INFO = {
    'drums': ('Drum controller', '4x4 drum pads, program changes and four faders on a MIDI port'),
    'keyboard': ('MIDI keyboard', 'Scales, octaves and a mod wheel, rearranged by links'),
    'mixer': ('DAW mixer', 'Eight faders, mutes and transport for Mackie Control (REAPER, Logic...)'),
    'performance': ('Performance', 'Clip launcher, drum pads, a beat sequencer and a meter'),
    'macros': ('Macro board', 'Shortcuts, media keys, typing, scrolling and the mouse pointer'),
}

def templates() -> list:
    """Layouts to start from: name, title, description."""
    found = []
    for name, (title, doc) in _TEMPLATE_INFO.items():
        if (TEMPLATES / f'{name}.json').is_file():
            found.append({'name': name, 'title': title, 'doc': doc})
    return found

#: Pieces of layouts to add (widgets with their links, messages and outputs): built in, and your own
SNIPPETS = pathlib.Path(__file__).parent / 'snippets'
USER_SNIPPETS = pathlib.Path.home() / '.pyxelwidgets' / 'snippets'
SNIPPET_FORMAT = 'pyxelwidgets.snippet'

def snippet_layout(snippet: dict) -> dict:
    """A layout of the snippet's size holding just the snippet, e.g. to check or draw it."""
    width, height = snippet['size']
    layout = new_layout(width, height)
    layout['widgets'] = snippet['widgets']
    for key in ('outputs', 'mappings', 'links'):
        if snippet.get(key):
            layout[key] = snippet[key]
    return layout

def check_snippet(snippet) -> dict:
    """``snippet`` checked (it loads as a layout of its size); raises ValueError saying what's wrong."""
    if not isinstance(snippet, dict) or snippet.get('format') != SNIPPET_FORMAT:
        raise ValueError(f'A snippet has "format": "{SNIPPET_FORMAT}"')
    widgets = snippet.get('widgets')
    if not isinstance(widgets, list) or not widgets:
        raise ValueError('A snippet has widgets')
    if not str(snippet.get('title') or '').strip():
        raise ValueError('A snippet has a title')
    size = snippet.get('size')
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in size)):
        raise ValueError('A snippet has a size: [width, height]')
    for widget in widgets:
        if not isinstance(widget, dict):
            raise ValueError('Widgets are objects')
        if widget.get('x', 0) + widget.get('width', 1) > size[0] or widget.get('y', 0) + widget.get('height', 1) > size[1]:
            raise ValueError(f'{widget.get("name")!r} is outside the snippet\'s {size[0]}x{size[1]}')
    try:
        pyxelwidgets.parser.Parser(snippet_layout(snippet), devices = False)
    except pyxelwidgets.parser.LayoutError as error:
        raise ValueError(f'The snippet doesn\'t load: {error}') from None
    return snippet

def _snippet_preview(snippet: dict) -> list | None:
    """The snippet drawn: rows from the top of ``#rrggbb`` (None where nothing is), or None."""
    try:
        ui = pyxelwidgets.parser.Parser(snippet_layout(snippet), devices = False)
        root = ui.surface.root
        root.render()
    except Exception:
        return None
    buffer = root.buffer
    return [[f'#{int(buffer[x, y, 0]):02x}{int(buffer[x, y, 1]):02x}{int(buffer[x, y, 2]):02x}' if buffer[x, y, 3] else None
             for x in range(buffer.shape[0])] for y in reversed(range(buffer.shape[1]))]

def _snippet_entry(path: pathlib.Path, builtin: bool) -> dict | None:
    try:
        snippet = check_snippet(json.loads(path.read_text()))
    except (OSError, ValueError):
        # A broken file of your own is left out
        return None
    return {'id': ('' if builtin else 'user/') + path.stem, 'title': snippet['title'], 'doc': snippet.get('doc', ''),
            'category': snippet.get('category') or ('Snippets' if builtin else 'My snippets'), 'size': snippet['size'],
            'builtin': builtin, 'preview': _snippet_preview(snippet), 'snippet': snippet}

_BUILTIN_SNIPPETS = None

def snippets(user: pathlib.Path = USER_SNIPPETS) -> list:
    """Every snippet: the built-in ones, then yours from ``user``; each with an id, title, doc, category, size and preview."""
    global _BUILTIN_SNIPPETS
    if _BUILTIN_SNIPPETS is None:
        _BUILTIN_SNIPPETS = [entry for path in sorted(SNIPPETS.glob('*.json')) if (entry := _snippet_entry(path, True))]
    own = [entry for path in sorted(user.glob('*.json')) if (entry := _snippet_entry(path, False))] if user.is_dir() else []
    return _BUILTIN_SNIPPETS + own

def save_snippet(snippet: dict, user: pathlib.Path = USER_SNIPPETS) -> str:
    """Keep ``snippet`` in ``user`` (named after its title, replacing one of the same name); returns its id."""
    check_snippet(snippet)
    stem = re.sub(r'[^a-z0-9]+', '-', snippet['title'].lower()).strip('-') or 'snippet'
    user.mkdir(parents = True, exist_ok = True)
    (user / f'{stem}.json').write_text(json.dumps(snippet, indent = 2) + '\n')
    return f'user/{stem}'

def delete_snippet(id: str, user: pathlib.Path = USER_SNIPPETS) -> None:
    """Delete one of your snippets (built-in ones stay)."""
    stem = id.removeprefix('user/')
    if not id.startswith('user/') or not re.fullmatch(r'[a-z0-9-]+', stem):
        raise ValueError(f'Only your own snippets can be deleted, not {id!r}')
    (user / f'{stem}.json').unlink(missing_ok = True)

def detect_devices() -> list:
    """Layout device types whose MIDI ports are present now (devices plugged in)."""
    try:
        import pyxelwidgets.devices.midi
        inputs, outputs = pyxelwidgets.devices.midi.MIDI.available_ports()
    except ImportError:
        return []
    # Type → (model, longest matching pattern, matching ports)
    matches = {}
    for module_name in DEVICE_MODULES:
        try:
            module = importlib.import_module(f'pyxelwidgets.devices.{module_name}')
        except ImportError:
            continue
        for name in getattr(module, '__all__', []):
            cls = getattr(module, name)
            if not (isinstance(cls, type) and issubclass(cls, pyxelwidgets.devices.midi.MIDI) and cls.ports):
                continue
            ports = [port for port in inputs + outputs if any(pattern in port for pattern in cls.ports)]
            if ports:
                length = max(len(pattern) for pattern in cls.ports if any(pattern in port for port in ports))
                matches[f'{module_name}.{name}'] = (cls.model, length, ports)
    # A generic match on another port of a more specific device doesn't count: a Launchpad
    # Mini MK3's "DAW" port contains the first Launchpad Mini's "Launchpad Mini"
    def shadowed(kind):
        _, length, ports = matches[kind]
        def specific(other, other_length, other_ports):
            # A longer pattern, or the same length on fewer of the same ports
            return other != kind and (other_length > length or set(other_ports) < set(ports))
        return all(any(specific(other, other_length, other_ports) and len(os.path.commonprefix([port, other_port])) > length
                       for other, (_, other_length, other_ports) in matches.items() for other_port in other_ports)
                   for port in ports)
    found = {kind: model for kind, (model, _, _) in matches.items() if not shadowed(kind)}
    return [{'type': kind, 'model': model} for kind, model in found.items()]

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
        elif url.path == '/api/templates':
            self._json({'templates': templates()})
        elif url.path == '/api/snippets':
            self._json({'snippets': snippets(self.designer.snippets)})
        elif url.path == '/api/detect':
            self._json({'devices': detect_devices()})
        elif url.path == '/api/ports':
            try:
                import pyxelwidgets.devices.midi
                inputs, outputs = pyxelwidgets.devices.midi.MIDI.available_ports()
            except Exception:
                inputs, outputs = [], []
            self._json({'inputs': list(inputs), 'outputs': list(outputs)})
        elif url.path == '/api/layout':
            self._json({'layout': preview.layout, 'file': str(self.designer.path) if self.designer.path else None})
        elif url.path == '/api/check':
            self._json({'check': preview.check_status()})
        elif url.path == '/api/frame':
            query = urllib.parse.parse_qs(url.query)
            since = int(query.get('since', ['0'])[0])
            self._json(preview.frame(since, query.get('pixels', ['1'])[0] != '0'))
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
                # {"layout", "path"} (Save As), or the layout itself
                if isinstance(body, dict) and 'layout' in body:
                    self.designer.save(body['layout'], body.get('path'))
                else:
                    self.designer.save(body)
                self._json({'ok': True, 'file': str(self.designer.path), 'layout': preview.layout})
                return
            elif path in ('/api/open', '/api/new'):
                if path == '/api/open':
                    self.designer.open(str(body['path']))
                else:
                    body = body if isinstance(body, dict) else {}
                    self.designer.new(body.get('template'), body.get('layout'))
                self._json({'ok': True, 'file': str(self.designer.path) if self.designer.path else None, 'layout': preview.layout})
                return
            elif path == '/api/pick':
                # {"mode": open|save, "path"}: the system's file dialog, only for a browser on this computer
                pick = self.designer.pick
                if pick is None or not ipaddress.ip_address(self.client_address[0]).is_loopback:
                    self._json({'ok': False, 'unavailable': True})
                    return
                try:
                    chosen = pick(str(body['mode']), body.get('path') or (str(self.designer.path) if self.designer.path else None))
                except Unavailable as error:
                    self._json({'ok': False, 'unavailable': True, 'error': str(error)})
                    return
                self._json({'ok': True, 'path': chosen})
                return
            elif path == '/api/python':
                # {"layout", "file", "handlers"}: the Python tab's code, loading the layout file and building it in code
                layout, handlers = body['layout'], bool(body.get('handlers'))
                file = str(body.get('file') or 'layout.json')
                self._json({'ok': True, 'loader': pyxelwidgets.codegen.loader(layout, file, handlers = handlers),
                            'standalone': pyxelwidgets.codegen.standalone(layout, handlers = handlers)})
                return
            elif path == '/api/scan':
                # {"output": index, "what", "track", "plugin"}: names from the DAW (Mackie Control's plug-in mode)
                try:
                    found = preview.scan(int(body['output']), str(body['what']), body.get('track'), body.get('plugin'))
                except (LookupError, ConnectionError, ValueError) as error:
                    # The DAW's answer, not a bad request
                    self._json({'ok': False, 'error': str(error).strip("'")})
                    return
                self._json({'ok': True, **found})
                return
            elif path == '/api/snippets':
                # {"snippet"}: keep one of your own; {"delete": id}: delete one
                if isinstance(body, dict) and 'delete' in body:
                    delete_snippet(str(body['delete']), self.designer.snippets)
                    self._json({'ok': True, 'snippets': snippets(self.designer.snippets)})
                else:
                    id = save_snippet(body['snippet'], self.designer.snippets)
                    self._json({'ok': True, 'id': id, 'snippets': snippets(self.designer.snippets)})
                return
            elif path == '/api/view':
                preview.set_hidden([str(name) for name in body.get('hidden', [])])
            elif path == '/api/connect':
                self._json({'ok': True, **preview.set_connected(str(body['kind']), int(body['index']), bool(body['connected']))})
                return
            elif path == '/api/check':
                # {"index", "pattern"}: check a connected device (pattern null: done)
                pattern = body.get('pattern')
                self._json({'ok': True, 'check': preview.check_device(int(body.get('index', -1)), None if pattern is None else str(pattern))})
                return
            else:
                self._send(404, b'Not found', 'text/plain')
                return
        except (pyxelwidgets.parser.LayoutError, ValueError, TypeError, KeyError) as error:
            self._json({'ok': False, 'error': str(error)}, 400)
            return
        self._json({'ok': True})

def serve(path: str | None = None, port: int = 8765, host: str = '127.0.0.1', *, connect: bool = True,
          snippets: str | None = None, dialogs: bool = True) -> http.server.ThreadingHTTPServer:
    """
    Start the designer's web server (not yet serving: call ``serve_forever``).
    With ``connect`` (default), the layout's devices and outputs connect as they're added.
    ``snippets`` is where snippets you save go (default ``~/.pyxelwidgets/snippets``).
    With ``dialogs`` (default), Open and Save As show the system's file dialog (to a browser on this computer).
    """
    handler = type('DesignerHandler', (Handler,), {'designer': Designer(path, connect = connect, snippets = snippets, dialogs = dialogs)})
    return http.server.ThreadingHTTPServer((host, port), handler)
