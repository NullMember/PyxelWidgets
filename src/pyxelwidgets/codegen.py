"""
Python code for a layout, as the designer's Python tab shows it: a program
loading the layout file (``loader``), or one building the same surface in
code without it (``standalone``), to start from when a layout outgrows the
designer.

    print(pyxelwidgets.codegen.standalone(json.load(open('layout.json'))))
"""

import dataclasses
import enum
import importlib
import keyword
import re
import sys

import pyxelwidgets
import pyxelwidgets.app
import pyxelwidgets.color
import pyxelwidgets.events
import pyxelwidgets.link
import pyxelwidgets.message
import pyxelwidgets.parser
import pyxelwidgets.surface
import pyxelwidgets.widgets

# The event each widget type's handler prints, with what it prints
HANDLERS = {
    'Button': ('Changed', 'e.value'), 'Fader': ('Changed', 'e.value'), 'Knob': ('Changed', 'e.value'), 'XY': ('Changed', 'e.value'),
    'Keyboard': ('NoteOn', 'e.note, e.velocity'), 'DrumPads': ('NoteOn', 'e.note, e.velocity'), 'ButtonGroup': ('Toggled', 'e.x, e.y, e.state'),
    'ClipLauncher': ('ClipStarted', 'e.x, e.y'), 'Sequencer': ('StepPlayed', 'e.step, e.active'), 'Tracker': ('RowPlayed', 'e.row, e.columns'),
}

# Transport actions as code, given the transport's expression
_ACTIONS = {
    'transport.play': '{}.play',
    'transport.stop': '{}.stop',
    'transport.toggle': '{}.toggle',
    'transport.rewind': 'lambda: {}.locate(0)',
    'transport.tempo': "lambda bpm: setattr({0}, 'bpm', max(1.0, float(bpm)))",
    'transport.tempo_add': "lambda amount: setattr({0}, 'bpm', max(1.0, {0}.bpm + amount))",
}

# Lines longer than this put each argument on a line of its own
_WIDTH = 110

# Letters Sprite frames are drawn with ('.' is transparent)
_LETTERS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%&*+=?!'

_PICTURE = '''def picture(rows, colors):
    """A Sprite frame from rows of letters (the top row first), each one of colors; '.' is transparent."""
    return [[colors.get(row[x], Colors.Invisible) for row in reversed(rows)] for x in range(len(rows[0]))]'''

def loader(layout: dict, file: str = 'layout.json', *, handlers: bool = False) -> str:
    """A program loading ``file`` (holding ``layout``) and running it; ``handlers`` prints each widget's main event."""
    used, lines = set(), []
    for item in _walk(layout.get('widgets', [])):
        if handlers and item.get('type') in HANDLERS:
            event, fields = HANDLERS[item['type']]
            used.add(event)
            lines.append(f'ui[{item["name"]!r}].on({event}, lambda e: print({item["name"]!r}, {fields}))')
    code = ['from pyxelwidgets import parser']
    if used:
        code.append(f'from pyxelwidgets.events import {", ".join(sorted(used))}')
    code += ['', f'ui = parser.load({file!r})']
    if lines:
        code += ['', *lines]
    code.append('')
    if _played(layout):
        code += ['app = ui.app()  # Sequencers and Trackers follow app.transport', 'app.transport.play()', 'app.run()']
    else:
        if (layout.get('transport') or {}).get('sync'):
            code.append("# The transport follows the DAW's MIDI clock (the layout's transport.sync)")
        code.append('ui.app().run()')
    return '\n'.join(code) + '\n'

def standalone(layout: dict, *, handlers: bool = False, run: bool = True) -> str:
    """
    A program building ``layout`` in code: the surface, devices, widgets,
    outputs, mappings, bindings and links, then running it (without ``run``
    it stops before creating the App's loop). Raises LayoutError for an
    invalid layout.
    """
    return _Writer(layout).write(handlers = handlers, run = run)

def _walk(widgets: list):
    for item in widgets:
        yield item
        yield from _walk(item.get('widgets') or [])

def _played(layout: dict) -> bool:
    # Widgets the transport plays: started with app.transport.play() (unless a DAW starts it)
    if (layout.get('transport') or {}).get('sync'):
        return False
    return any(item.get('type') in ('Sequencer', 'Tracker', 'ClipLauncher') and (item.get('options') or {}).get('clock', 'Transport') == 'Transport'
               for item in _walk(layout.get('widgets', [])))

def _same(a, b) -> bool:
    # 1 == True and 0 == 0.0, but they are written differently
    return type(a) is type(b) and a == b

class _Writer:

    def __init__(self, layout: dict) -> None:
        # Checks the layout, without opening ports
        self.ui = pyxelwidgets.parser.Parser(layout, devices = False)
        self.layout = self.ui.json
        self.imports = {}
        # Modules whose classes are written through the module (message.NoteOn)
        self.qualified = set()
        self.reserved = {'surface', 'app', 'picture', 'message', 'events', 'print', 'max', 'setattr', 'float'}
        self.names = set(self.reserved)
        self.variables = {}

    # Names

    def name(self, cls) -> str:
        """``cls``'s name in the code, imported (from the package when it exports it)."""
        outer = cls.__qualname__.split('.')[0]
        if cls.__module__ in self.qualified and cls is not pyxelwidgets.message.Source:
            package, _, alias = cls.__module__.rpartition('.')
            self.imports[alias] = package
            return f'{alias}.{cls.__qualname__}'
        module = _module(_outer(cls))
        if self.imports.get(outer, module) != module:
            # Two classes of one name (the message NoteOn and the event NoteOn): messages are
            # written through their module (message.NoteOn), on the next pass
            other = self.imports[outer]
            self.qualified.add('pyxelwidgets.message' if 'pyxelwidgets.message' in (cls.__module__, _source(other, outer)) else cls.__module__)
            return cls.__qualname__
        self.imports[outer] = module
        return cls.__qualname__

    def variable(self, key, wanted: str) -> str:
        """A unique Python name for ``key`` (a widget, device or output), like ``wanted``."""
        text = re.sub(r'\W+', '_', wanted).strip('_') or 'widget'
        if text[0].isdigit():
            text = '_' + text
        text = text if text.isascii() else 'widget'
        if keyword.iskeyword(text):
            text += '_'
        candidate, number = text, 2
        while candidate in self.names or keyword.iskeyword(candidate) or candidate in pyxelwidgets.__all__:
            candidate = f'{text}_{number}'
            number += 1
        self.names.add(candidate)
        self.variables[key] = candidate
        return candidate

    # Values

    def value(self, value) -> str:
        if isinstance(value, pyxelwidgets.color.Color):
            for name, color in vars(pyxelwidgets.color.Colors).items():
                if not name.startswith('_') and color == value:
                    return f'{self.name(pyxelwidgets.color.Colors)}.{name}'
            alpha = f', {value.a:g}' if value.a != 1.0 else ''
            return f'{self.name(pyxelwidgets.color.Color)}({value.r}, {value.g}, {value.b}{alpha})'
        if isinstance(value, enum.Enum):
            return f'{self.name(type(value))}.{value.name}'
        if isinstance(value, pyxelwidgets.message.Source):
            return self.call(self.name(pyxelwidgets.message.Source), [repr(value.name)],
                             [(key, repr(getattr(value, key))) for key, default in (('min', None), ('max', None), ('offset', 0))
                              if not _same(getattr(value, key), default)])
        if isinstance(value, pyxelwidgets.link.Condition):
            options = [(key, self.value(getattr(value, key))) for key, default in (('then', True), ('otherwise', False))
                       if not _same(getattr(value, key), default)]
            return self.call(self.name(pyxelwidgets.link.Condition), [self.value(value.source), repr(value.op), repr(value.to)], options)
        if isinstance(value, pyxelwidgets.message.OscMessage):
            return self.call(self.name(type(value)), [repr(value.address), *[self.value(arg) for arg in value.args]])
        if isinstance(value, pyxelwidgets.message.Message):
            fields = [(field.name, self.value(getattr(value, field.name))) for field in dataclasses.fields(value)
                      if not _same(getattr(value, field.name), field.default)]
            return self.call(self.name(type(value)), [], fields)
        if isinstance(value, tuple):
            return repr(tuple(value))
        return repr(value)

    def call(self, function: str, args: list, kwargs: list = (), indent: str = '') -> str:
        """``function(args, key = value)``, an argument per line if it gets long."""
        keywords = [f'{key} = {text}' for key, text in kwargs]
        line = f'{function}({", ".join([*args, *keywords])})'
        if len(indent) + len(line) <= _WIDTH or len(args) + len(keywords) < 2:
            return line
        # The positional arguments on the first line, a keyword per line
        inner = indent + '    '
        lines = [inner + ', '.join(args) + ','] if args else []
        return f'{function}(\n' + ''.join(f'{line}\n' for line in lines) + ''.join(f'{inner}{part},\n' for part in keywords) + f'{indent})'

    def frames(self, widget: str, frames: list) -> tuple:
        """Lines defining a Sprite's frames as letter pictures, and the expression for them."""
        encoded = pyxelwidgets.parser.frames_to_json(frames)
        colors = list(dict.fromkeys(color for frame in encoded for row in frame for color in row if color is not None))
        if len(colors) > len(_LETTERS):
            return [], repr(encoded) + ' and too many colors'
        letters = dict(zip(colors, _LETTERS))
        palette = f'{widget}_colors'
        lines = [f'{palette} = {{']
        lines += [f'    {letter!r}: {self.value(pyxelwidgets.parser.text_to_color(color))},' for color, letter in letters.items()]
        lines.append('}')
        pictures = []
        for frame in encoded:
            width = max(len(row) for row in frame)
            rows = [''.join(letters[color] if color else '.' for color in row).ljust(width, '.') for row in frame]
            pictures.append('    picture([\n' + ''.join(f'        {row!r},\n' for row in rows) + f'    ], {palette}),\n')
        lines.append(f'{widget}_frames = [\n' + ''.join(pictures) + ']')
        self.picture = True
        return lines, f'{widget}_frames'

    # Sections

    def write(self, *, handlers: bool, run: bool) -> str:
        while True:
            qualified = set(self.qualified)
            self.imports, self.names, self.variables = {}, set(self.reserved), {}
            code = self._write(handlers = handlers, run = run)
            if self.qualified == qualified:
                return code

    def _write(self, *, handlers: bool, run: bool) -> str:
        self.picture = False
        sections = [self.surface(), self.devices(), self.widgets(), self.outputs(), self.app(), self.bindings(), self.links(),
                    self.clocks(), self.handlers() if handlers else []]
        body = []
        for section in sections:
            if section:
                body += ['', *section]
        if run:
            body += ['', *(['app.transport.play()'] if _played(self.layout) else []), 'app.run()']
        imports = {}
        for name, module in self.imports.items():
            imports.setdefault(module, []).append(name)
        head = []
        for module in sorted(imports, key = lambda module: (module != 'pyxelwidgets', module)):
            names = ', '.join(sorted(imports[module], key = str.lower))
            line = f'from {module} import {names}'
            if len(line) > _WIDTH:
                line = f'from {module} import (\n' + '\n'.join(_wrap(names, '    ')) + '\n)'
            head.append(line)
        if self.picture:
            body = ['', '', _PICTURE, '', *body]
        return '\n'.join(head + body) + '\n'

    def surface(self) -> list:
        size = self.layout['surface']
        return [f'surface = {self.name(pyxelwidgets.surface.Surface)}({int(size["width"])}, {int(size["height"])})']

    def devices(self) -> list:
        lines = []
        for index, entry in enumerate(self.layout.get('devices') or []):
            cls = pyxelwidgets.parser.device_class(entry, f'devices[{index}]')
            options = pyxelwidgets.parser._options(cls, entry.get('options'), f'devices[{index}]')
            variable = self.variable(('device', index), _snake(cls.__name__))
            if lines:
                lines.append('')
            lines.append(f'{variable} = ' + self.call(self.name(cls), [], [(key, self.value(value)) for key, value in options.items()]))
            if entry.get('input') or entry.get('output'):
                lines.append(f'{variable}.connect({entry.get("input")!r}, {entry.get("output")!r})')
            else:
                lines.append(f'{variable}.connect()')
            lines.append(f'surface.add_device({variable}, {entry.get("x", 0)}, {entry.get("y", 0)})')
        return lines

    def widgets(self) -> list:
        lines = []
        def add(parent: str, items: list, where: str) -> None:
            types = pyxelwidgets.parser.widget_types()
            for index, item in enumerate(items):
                path = f'{where}[{index}]'
                cls = types[item['type']]
                options = pyxelwidgets.parser._options(cls, item.get('options'), path)
                variable = self.variable(('widget', item['name']), item['name'])
                arguments = []
                for key, value in options.items():
                    if key == 'frames' and value:
                        frame_lines, value = self.frames(variable, value)
                        lines.extend(frame_lines)
                        arguments.append((key, value))
                    else:
                        arguments.append((key, self.value(value)))
                geometry = [str(int(item.get(key, default))) for key, default in (('x', 0), ('y', 0), ('width', 1), ('height', 1))]
                constructor = self.call(self.name(cls), geometry, [('name', repr(item['name'])), *arguments])
                lines.append(f'{variable} = {parent}.add({constructor})')
                if item.get('animation') is not None:
                    animation = self.ui._animation(item['animation'], f'{path}.animation')
                    lines.append(f'{variable}.animation = ' + self.call(self.name(type(animation)), [], [
                        (key, self.value(value)) for key, value in pyxelwidgets.parser._options(
                            type(animation), item['animation'].get('options'), path).items()]))
                if item.get('widgets'):
                    add(variable, item['widgets'], f'{path}.widgets')
        add('surface', self.layout.get('widgets') or [], 'widgets')
        return lines

    def outputs(self) -> list:
        lines = []
        for index, entry in enumerate(self.ui.output_settings()):
            cls = pyxelwidgets.parser.device_class(entry, f'outputs[{index}]')
            options = pyxelwidgets.parser._options(cls, entry.get('options'), f'outputs[{index}]')
            variable = self.variable(('output', entry['name']), entry['name'])
            lines.append(f'{variable} = ' + self.call(self.name(cls), [], [('name', repr(entry['name'])),
                                                                         *[(key, self.value(value)) for key, value in options.items()]]))
            if entry.get('virtual'):
                lines.append(f'{variable}.connect_virtual({entry["virtual"]!r})')
            elif entry.get('input') or entry.get('output'):
                lines.append(f'{variable}.connect({entry.get("input")!r}, {entry.get("output")!r})')
            else:
                lines.append(f'{variable}.connect()')
        for widget, on, output, message, feedback in self.ui.mapping_settings():
            options = ([('on', self.name(on))] if on is not None else []) + ([('feedback', 'True')] if feedback else [])
            lines.append(self.call('surface.map', [self.variables[('widget', widget)], self.variables[('output', output)], self.value(message)], options))
        return lines

    def app(self) -> list:
        settings = self.ui.transport_settings()
        options = [(key, self.value(tuple(value) if key == 'signature' else value)) for key, value in settings.items()
                   if not _same(tuple(value) if key == 'signature' else value, {'bpm': 120, 'signature': (4, 4)}[key])]
        sync = self.ui.sync_settings()
        if sync is None:
            return [f'app = {self.call(self.name(pyxelwidgets.app.App), ["surface"], options)}']
        clock_input = importlib.import_module('pyxelwidgets.devices.midi_clock').MidiClockInput
        options.append(('sync', 'True'))
        variable = self.variable(('clock', 'input'), 'daw_clock')
        connect = f'connect_virtual({sync["virtual"]!r})' if 'virtual' in sync else f'connect({sync["input"]!r}, None)'
        return [f'app = {self.call(self.name(pyxelwidgets.app.App), ["surface"], options)}',
                "# The transport follows the DAW's MIDI clock: tempo, start, stop and position",
                f'{variable} = {self.name(clock_input)}(app.transport)',
                f'{variable}.{connect}',
                f'app.clocks.append({variable})  # closed with the app']

    def bindings(self) -> list:
        lines = []
        for device, control, widget, action, options in self.ui.binding_settings():
            target = self.variables[('widget', widget)] if widget is not None else _ACTIONS[action].format('app.transport')
            lines.append(self.call('surface.bind', [self.variables[('device', device)], repr(control), target],
                                   [(key, self.value(value)) for key, value in options.items()]))
        return lines

    def links(self) -> list:
        lines = []
        for setting in self.ui.link_settings():
            widget, action, value = self.variables[('widget', setting['widget'])], setting['action'], setting['value']
            if action == 'debug':
                args, keywords = [f'lambda text: print({setting["widget"] + ":"!r}, text)'], [('value', repr(value))]
            elif action is not None and action.startswith('transport.'):
                args, keywords = [_ACTIONS[action].format('app.transport')], [] if value is None else [('value', self.value(value))]
            elif action is not None:
                args, keywords = [f'{self.variables[("widget", setting["target"])]}.{action}'], [] if value is None else [('value', self.value(value))]
            else:
                args = [self.variables[('widget', setting['target'])], repr(setting['option'])] + ([] if value is None else [self.value(value)])
                keywords = []
            keywords.append(('on', self.name(setting['on'])))
            if setting['change'] != pyxelwidgets.link.Link.Change.Set:
                keywords.append(('change', self.value(setting['change'])))
            for key in ('minimum', 'maximum'):
                if setting[key] is not None:
                    keywords.append((key, self.value(setting[key])))
            lines.append(self.call('surface.link', [widget, *args], keywords))
        return lines

    def clocks(self) -> list:
        # Sequencers, Trackers and ClipLaunchers on the transport or a clock of their own
        return [f'app.attach({self.variables[("widget", name)]})' for name, widget in self.ui.widgets.items()
                if isinstance(widget, pyxelwidgets.widgets.Timed) and widget.clock != pyxelwidgets.widgets.Clock.Off]

    def handlers(self) -> list:
        lines = []
        for item in _walk(self.layout.get('widgets') or []):
            if item['type'] in HANDLERS:
                event, fields = HANDLERS[item['type']]
                event = self.name(getattr(pyxelwidgets.events, event))
                lines.append(f'{self.variables[("widget", item["name"])]}.on({event}, lambda e: print({item["name"]!r}, {fields}))')
        return lines

def _outer(cls):
    # The top-level class of a nested one (Fader for Fader.Mode)
    return getattr(sys.modules[cls.__module__], cls.__qualname__.split('.')[0])

def _module(cls) -> str:
    """Where to import ``cls`` from: the package if it exports it, else the shortest package path having it."""
    if cls.__name__ in getattr(pyxelwidgets, '_exports', {}) and getattr(pyxelwidgets, cls.__name__) is cls:
        return 'pyxelwidgets'
    parts = cls.__module__.split('.')
    for end in range(2, len(parts)):
        module = sys.modules.get('.'.join(parts[:end]))
        if module is not None and getattr(module, cls.__name__, None) is cls:
            return module.__name__
    return cls.__module__

def _source(module: str, name: str) -> str:
    # The module defining what ``from module import name`` imports
    return getattr(sys.modules[module], name).__module__

def _wrap(text: str, indent: str) -> list:
    lines, line = [], ''
    for word in text.split(' '):
        if line and len(indent) + len(line) + len(word) + 1 > _WIDTH:
            lines.append(indent + line.rstrip())
            line = ''
        line += word + ' '
    return lines + [indent + line.rstrip() + ',']

def _snake(name: str) -> str:
    """LaunchpadMiniMK3 → launchpad_mini_mk3"""
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', '_', name).lower()
