"""
Writes docs/api.md, the API reference, from the package's docstrings and
signatures. Standard library only:

    python docs/build_api.py

Run it after changing public classes or docstrings.
"""

import enum
import importlib
import inspect
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'src'))

import pyxelwidgets.color  # noqa: E402

# In layer order, as in the architecture: small pieces first
SECTIONS = [
    ('Basics', ['color', 'rectangle', 'rate', 'events', 'font', 'buffer', 'animation', 'message']),
    ('Widgets', ['widgets', 'group']),
    ('Time, controls and outputs', ['transport', 'binding', 'mapping', 'link']),
    ('Putting it together', ['surface', 'app', 'parser', 'codegen']),
    ('Devices', ['devices', 'devices.colors', 'devices.input', 'devices.midi', 'devices.novation', 'devices.akai',
                 'devices.ableton', 'devices.arturia', 'devices.presonus', 'devices.virtual', 'devices.web', 'devices.midi_clock',
                 'devices.midi_port', 'devices.plugins', 'devices.mackie', 'devices.osc', 'devices.desktop']),
    ('Designer', ['designer']),
]

def value_text(value) -> str:
    """A default value as it would be written in code."""
    if isinstance(value, enum.Enum):
        return f'{type(value).__qualname__}.{value.name}'
    if isinstance(value, pyxelwidgets.color.Color):
        for name, color in vars(pyxelwidgets.color.Colors).items():
            if color == value and isinstance(color, pyxelwidgets.color.Color):
                return f'Colors.{name}'
        return f'Color({value.r}, {value.g}, {value.b}{"" if value.a == 1 else f", {value.a:g}"})'
    if callable(value) and hasattr(value, '__name__'):
        return f'{getattr(value, "__module__", "")}.{value.__name__}'.lstrip('.')
    return repr(value)

def annotation_text(annotation) -> str:
    if isinstance(annotation, str):
        return annotation
    if isinstance(annotation, type):
        return annotation.__qualname__
    return str(annotation).replace('typing.', '').replace('pyxelwidgets.', '').replace('color.Color', 'Color')

def signature(function, skip_self: bool = True) -> str:
    try:
        parameters = list(inspect.signature(function).parameters.values())
    except (TypeError, ValueError):
        return '(...)'
    if skip_self and parameters and parameters[0].name in ('self', 'cls'):
        parameters = parameters[1:]
    parts, keyword_only = [], False
    for parameter in parameters:
        if parameter.kind == parameter.KEYWORD_ONLY and not keyword_only:
            parts.append('*')
            keyword_only = True
        text = parameter.name
        if parameter.kind == parameter.VAR_POSITIONAL:
            text, keyword_only = '*' + text, True
        elif parameter.kind == parameter.VAR_KEYWORD:
            text = '**' + text
        if parameter.annotation is not parameter.empty:
            text += f': {annotation_text(parameter.annotation)}'
        if parameter.default is not parameter.empty:
            text += f' = {value_text(parameter.default)}'
        parts.append(text)
    return '(' + ', '.join(parts) + ')'

def markdown(doc: str) -> str:
    """
    Docstring markup as Markdown: ``code`` → `code`, "text::" before a code
    block → "text:", numpy style sections ("Parameters" over "----") → bold,
    and "name: type" lines with an indented description → list items.
    """
    lines = [line[:-1] if line.endswith('::') else line for line in doc.replace('``', '`').splitlines()]
    out, index = [], 0
    while index < len(lines):
        line = lines[index]
        following = lines[index + 1] if index + 1 < len(lines) else ''
        if line.strip() and re.fullmatch(r'-{3,}', following.strip()):
            out += [f'**{line.strip()}**', '']
            index += 2
            continue
        if re.match(r'^[A-Za-z_][\w, ]*: \S', line) and following.startswith('    ') and following.strip():
            description = []
            index += 1
            while index < len(lines) and lines[index].startswith('    ') and lines[index].strip():
                description.append(lines[index].strip())
                index += 1
            out.append(f'- `{line.strip()}`: {" ".join(description)}')
            continue
        out.append(line)
        index += 1
    return '\n'.join(out)

def own_doc(item) -> str:
    """The item's own docstring (not one inherited from a base class), as Markdown."""
    doc = item.__dict__.get('__doc__') if isinstance(item, type) else getattr(item, '__doc__', None)
    return markdown(inspect.cleandoc(doc)) if isinstance(doc, str) else ''

def anchor(text: str) -> str:
    return ''.join(c for c in text.lower().replace(' ', '-') if c.isalnum() or c in '-_')

def public(module) -> list:
    names = getattr(module, '__all__', None)
    if names is None:
        names = [name for name, value in vars(module).items()
                 if not name.startswith('_') and getattr(value, '__module__', None) == module.__name__
                 and (inspect.isclass(value) or inspect.isfunction(value))]
    return [name for name in names if hasattr(module, name)]

def document_class(cls, lines: list, level: str) -> None:
    bases = [base.__name__ for base in cls.__bases__ if base is not object]
    lines.append(f'{level} `{cls.__name__}`' + (f' ({", ".join(bases)})' if bases else ''))
    lines.append('')
    if issubclass(cls, enum.Enum):
        lines.append(own_doc(cls) or 'An enum.')
        lines.append('')
        lines.append('Members: ' + ', '.join(f'`{member.name}`' for member in cls) + '.')
        lines.append('')
        return
    init = cls.__dict__.get('__init__')
    if init is not None and not inspect.isdatadescriptor(cls):
        lines.append(f'```python\n{cls.__name__}{signature(init)}\n```')
        lines.append('')
    elif hasattr(cls, '__dataclass_fields__'):
        fields = ', '.join(f'{name}' for name in cls.__dataclass_fields__)
        lines.append(f'```python\n{cls.__name__}({fields})\n```')
        lines.append('')
    if own_doc(cls):
        lines.append(own_doc(cls))
        lines.append('')
    if init is not None and own_doc(init):
        lines.append(own_doc(init))
        lines.append('')
    nested = [value for name, value in vars(cls).items() if inspect.isclass(value) and not name.startswith('_')]
    for name, value in vars(cls).items():
        if name.startswith('_') or name == '__init__':
            continue
        if isinstance(value, property):
            doc = own_doc(value.fget) if value.fget else ''
            settable = ' (settable)' if value.fset else ''
            lines.append(f'- **`{name}`**{settable}' + (f': {doc.splitlines()[0]}' if doc else ''))
        elif isinstance(value, (staticmethod, classmethod)) or inspect.isfunction(value):
            function = value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
            prefix = 'classmethod ' if isinstance(value, classmethod) else ''
            doc = own_doc(function)
            lines.append(f'- {prefix}**`{name}{signature(function, not isinstance(value, staticmethod))}`**'
                         + (': ' + doc.replace('\n\n', ' ').replace('\n', ' ') if doc else ''))
    if lines[-1] != '':
        lines.append('')
    for value in nested:
        document_class(value, lines, level + '#')

def document_module(name: str, lines: list, toc: list) -> None:
    try:
        module = importlib.import_module(f'pyxelwidgets.{name}')
    except ImportError as error:
        lines += [f'## `pyxelwidgets.{name}`', '', f'*Not documented here: {error}*', '']
        return
    title = f'pyxelwidgets.{name}'
    toc.append(f'  - [`{title}`](#{anchor(title)})')
    lines += [f'## `{title}`', '']
    doc = inspect.getdoc(module)
    if doc:
        lines += [markdown(doc), '']
    for item_name in public(module):
        item = getattr(module, item_name)
        if inspect.isclass(item):
            document_class(item, lines, '###')
        elif inspect.isfunction(item):
            lines.append(f'### `{item_name}{signature(item, False)}`')
            lines.append('')
            if own_doc(item):
                lines += [own_doc(item), '']

def build() -> str:
    lines, toc = [], []
    for section, modules in SECTIONS:
        toc.append(f'- {section}')
        lines += [f'# {section}', '']
        for name in modules:
            document_module(name, lines, toc)
    head = ['# PyxelWidgets API reference', '',
            'Generated from the docstrings by `docs/build_api.py`; see the [guides](README.md) for how the pieces fit.', '']
    return '\n'.join(head + toc + [''] + lines).rstrip() + '\n'

if __name__ == '__main__':
    (ROOT / 'api.md').write_text(build())
    print(f'Wrote {ROOT / "api.md"}')
