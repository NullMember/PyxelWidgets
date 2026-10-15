"""The docs stay true: the guides' code runs, the API reference builds."""

import importlib.util
import pathlib
import re
import sys

import pytest

DOCS = pathlib.Path(__file__).resolve().parent.parent / 'docs'


def first_code(guide):
    return re.search(r'```python\n(.*?)```', (DOCS / guide).read_text(), re.S).group(1)


@pytest.fixture
def clean_registry(monkeypatch):
    import pyxelwidgets.parser
    monkeypatch.setattr(pyxelwidgets.parser, '_WIDGETS', {})
    monkeypatch.setattr(pyxelwidgets.parser, '_DEVICES', {})


def load(name, code):
    namespace = {'__name__': name}
    exec(compile(code, f'<{name}>', 'exec'), namespace)
    return namespace


def test_widget_guide(clean_registry):
    from pyxelwidgets import Colors, parser
    dice = load('dice', first_code('writing-a-widget.md'))
    rolled = []
    die = dice['Dice']()
    die.on(dice['Rolled'], rolled.append)
    die.press(1, 1)
    die.render()
    assert rolled[0].value == die.value and 'Dice' in parser.widget_types()
    assert parser.schema()['widgets']['Dice']['actions'] == {'roll': None}


def test_driver_guide(clean_registry):
    from pyxelwidgets import Colors, buffer, parser
    from pyxelwidgets.events import ControlTurned, Event, PadPressed
    padbox = load('padbox', first_code('writing-a-driver.md'))
    test = re.findall(r'```python\n(.*?)```', (DOCS / 'writing-a-driver.md').read_text(), re.S)[1]
    namespace = {**padbox, 'Event': Event, 'buffer': buffer, 'Colors': Colors, 'print': lambda *args: None}
    exec(test, namespace)
    box = namespace['box']
    assert [0x90, 41, 1] in box._midi_output.sent
    assert 'padbox.PadBox' in parser.registered_devices()


def test_api_reference_builds():
    spec = importlib.util.spec_from_file_location('build_api', DOCS / 'build_api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = module.build()
    assert 'Not documented' not in text
    for name in ('`Link`', '`ClipLauncher`', '`WebGrid`', '`Surface`', '`register(cls: type)`'):
        assert name in text, name


def test_snippets_page_is_up_to_date():
    spec = importlib.util.spec_from_file_location('build_guide', DOCS / 'build_guide.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text, pictures = module.snippets_markdown()
    assert (DOCS / 'snippets.md').read_text() == text, 'run python docs/build_guide.py'
    # Pictures can differ (the Life snippet starts at random): they only have to be there
    for name in pictures:
        assert (DOCS / 'images' / 'snippets' / name).is_file(), 'run python docs/build_guide.py'
    # The guide's pictures are there
    for image in re.findall(r'\]\((images/[^)]+)\)', (DOCS / 'getting-started.md').read_text()):
        assert (DOCS / image).is_file(), image
