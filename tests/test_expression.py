import pytest

from pyxelwidgets import (ColumnChanged, Expression, Formula, PianoRoll, RowChanged, Sequencer, Stepper, Surface, Template,
                          Text, codegen, parser)
from pyxelwidgets.expression import ExpressionError, is_expression, parse
from pyxelwidgets.message import NoteOn
from pyxelwidgets.widgets import Follow


# The evaluator

def test_expressions_compute_from_names_and_event_values():
    roll = PianoRoll(0, 0, 8, 8, steps = 32)
    assert Expression('{roll.steps - roll.width}', {'roll': roll}).evaluate() == 24
    assert Expression('value * 8').evaluate({'value': 0.5}) == 4.0
    assert Expression('clamp(x * 2, 0, 5) + min(1, 2)').evaluate({'x': 4}) == 6
    assert Expression("'on' if state else 'off'").evaluate({'state': 0.0}) == 'off'
    # Choices read as their names; floats compare with a tolerance
    assert Expression("roll.follow == 'Page' and 0.1 + 0.2 == 0.3", {'roll': roll}).evaluate() is True
    # Event values come before names
    assert Expression('x + 1', {'x': 10}).evaluate({'x': 1}) == 2
    assert Expression('x + roll.width', {'roll': roll}).free == ['x']

def test_templates_fill_in_their_formulas():
    roll = PianoRoll(0, 0, 4, 1, steps = 10)
    template = Template('Step {roll.column + 1} of {roll.steps} {{literal}}', {'roll': roll})
    assert template.evaluate() == 'Step 1 of 10 {literal}'
    roll.scroll_forward()
    assert template.evaluate() == 'Step 2 of 10 {literal}'
    assert Template('{velocity}').evaluate({'velocity': 0.5}) == '0.5'
    assert Template('{x} {nothing}').evaluate({'x': 1}, keep_unknown = True) == '1 {nothing}'
    assert isinstance(parse('{a}'), Expression) and isinstance(parse('{a} and {b}'), Template)
    assert parse('plain') is None and parse('{{not one}}') is None
    assert is_expression(' {x + 1} ') and not is_expression('{x} {y}')

@pytest.mark.parametrize('text', ['__import__("os")', 'roll.__class__', '[1, 2]', 'lambda: 1', 'roll.steps.bit_length()',
                                  'x := 1', 'open("f")', 'min(*x)', '"a" * 10 ** 6', '2 ** 1000', '1 / 0', 'nothing', 'roll.reset'])
def test_only_formulas_run(text):
    roll = PianoRoll(0, 0, 8, 8)
    with pytest.raises(ExpressionError):
        Expression(text, {'roll': roll}).evaluate({'x': (1,)})


# Formulas

def test_a_formula_keeps_an_option_computed():
    surface = Surface(8, 9)
    roll = surface.add(PianoRoll(0, 0, 8, 8, steps = 32))
    stepper = surface.add(Stepper(0, 8, 8, 1))
    formula = surface.formula(stepper, 'maximum', Expression('roll.steps - roll.width', {'roll': roll}))
    assert stepper.maximum == 24
    stepper.set_number(20)
    # A new range keeps the number, as far as it can
    roll.configure(steps = 16)
    surface.update()
    assert (stepper.maximum, stepper.number) == (8, 8)
    # Results the option refuses (maximum not above minimum) leave it, with the reason
    roll.configure(steps = 8)
    surface.update()
    assert stepper.maximum == 8 and 'maximum must be more than minimum' in formula.error
    roll.configure(steps = 64)
    surface.update()
    assert stepper.maximum == 56 and formula.error is None

def test_formulas_convert_to_what_the_option_holds():
    roll = PianoRoll(0, 0, 8, 8)
    for option, text, expected in (('column', '7 / 2', 4), ('follow', "'Playhead'", Follow.Playhead), ('follow', '0', Follow.Off),
                                   ('active_color', "'#ff0000'", parser.text_to_color('#ff0000')), ('visible', '0', False)):
        Formula(roll, option, Expression(text)).refresh()
        assert getattr(roll, option) == expected, option
    with pytest.raises(ValueError):
        Formula(roll, 'column', Expression('missing + 1'))


# Events

def test_column_and_row_changed():
    roll = PianoRoll(0, 0, 4, 2, steps = 10, follow = Follow.Off)
    seen = []
    roll.on(ColumnChanged, lambda e: seen.append(('column', e.column, e.first, e.last)))
    roll.on(RowChanged, lambda e: seen.append(('row', e.row, e.first)))
    roll.scroll_forward()
    roll.configure(column = 6)
    roll.scroll_forward()               # at the end: nothing
    roll.row = -100
    roll.row = 1
    assert seen == [('column', 1, False, False), ('column', 6, False, True), ('row', -100, True), ('row', 1, False)]
    sequencer = Sequencer(0, 0, 4, 2, steps = 16, follow = Follow.Playhead)
    rows = []
    sequencer.on(RowChanged, lambda e: rows.append((e.row, e.last)))
    for step in [*range(16), 0]:
        sequencer.play(step)
    assert rows == [(1, False), (2, True), (0, False)]


# Layouts

LAYOUT = {
    'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 8, 'height': 10},
    'outputs': [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'Synth'}],
    'widgets': [
        {'type': 'PianoRoll', 'name': 'roll', 'x': 0, 'y': 0, 'width': 8, 'height': 8, 'options': {'steps': 32}},
        {'type': 'Stepper', 'name': 'position', 'x': 0, 'y': 8, 'width': 8, 'height': 1, 'options': {'maximum': '{roll.steps - roll.width}'}},
        {'type': 'Text', 'name': 'label', 'x': 0, 'y': 9, 'width': 8, 'height': 1, 'options': {'text': '{roll.column + 1}/{self.width}'}},
    ],
    'links': [
        {'widget': 'position', 'on': 'Changed', 'target': 'roll', 'option': 'column', 'value': '{position.number}'},
        {'widget': 'roll', 'on': 'ColumnChanged', 'target': 'position', 'option': 'value', 'value': '{column / position.maximum}'},
        {'widget': 'roll', 'on': 'ColumnChanged', 'action': 'debug', 'value': 'column {column} of {roll.steps}'},
    ],
    'mappings': [{'widget': 'roll', 'on': 'NoteOn', 'output': 'synth',
                  'message': {'type': 'NoteOn', 'note': '{note + 12}', 'velocity': '{velocity * 100}'}}],
}

def test_layout_formulas_links_and_messages():
    ui = parser.Parser(LAYOUT, devices = False)
    written = []
    ui.debug = lambda widget, text: written.append(text)
    roll, position, label = ui['roll'], ui['position'], ui['label']
    assert position.maximum == 24 and label.text == '1/8'
    position.set_number(5)
    assert roll.column == 5 and written[-1] == 'column 5 of 32'
    ui.surface.update()
    assert label.text == '6/8'
    roll.scroll_forward()
    assert position.number == 6
    message = ui.mapping_settings()[0][3]
    assert message.resolve({'note': 60, 'velocity': 0.5}) == NoteOn(72, 50) and message.needs == ['note', 'velocity']
    # Received messages match whatever a formula field has
    assert message.match(NoteOn(1, 2)) == {}
    # The designer gets formulas back as written
    assert parser.message_to_json(message)['note'] == '{note + 12}'

@pytest.mark.parametrize('where, value, error', [
    (('widgets', 1, 'maximum'), '{rol.steps}', "widgets[1].options.maximum: {rol.steps}: unknown name 'rol'"),
    (('widgets', 1, 'maximum'), '{roll.stepz}', "roll (PianoRoll) has no option 'stepz'"),
    (('widgets', 1, 'maximum'), '{roll.reset}', "has no option 'reset'"),
    (('widgets', 1, 'maximum'), '{roll.steps -}', 'widgets[1].options.maximum: {roll.steps -} is not an expression'),
    (('links', 0, 'value'), '{velocity}', "links[0].value: {velocity}: unknown name 'velocity'"),
    (('mappings', 0, 'note'), '{x}', "mappings[0].message.note: {x}: unknown name 'x'"),
])
def test_layout_formula_errors_name_the_spot(where, value, error):
    import copy
    layout = copy.deepcopy(LAYOUT)
    kind, index, key = where
    if kind == 'widgets':
        layout['widgets'][index]['options'][key] = value
    elif kind == 'links':
        layout['links'][index]['value'] = value
    else:
        layout['mappings'][index]['message'][key] = value
    with pytest.raises(parser.LayoutError, match = error.replace('{', r'\{').replace('}', r'\}').replace('[', r'\[').replace(']', r'\]').replace('(', r'\(').replace(')', r'\)')):
        parser.Parser(layout, devices = False)

def test_formulas_read_the_transport():
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 8, 'height': 1}, 'transport': {'bpm': 96},
              'widgets': [{'type': 'Text', 'name': 'tempo', 'x': 0, 'y': 0, 'width': 8, 'height': 1, 'options': {'text': '{round(transport.bpm)}'}}]}
    ui = parser.Parser(layout, devices = False)
    # No transport yet: the text stays, the formula says why
    assert ui.formulas[0].error
    app = ui.app()
    app.transport.close()
    ui.surface.update()
    assert ui['tempo'].text == '96' and ui.formulas[0].error is None

def test_code_computes_like_the_layout(monkeypatch):
    import pyxelwidgets.devices.midi
    monkeypatch.setattr(pyxelwidgets.devices.midi.MIDI, 'connect_virtual', lambda self, port: None)
    code = codegen.standalone(LAYOUT, run = False)
    assert "surface.formula(position, 'maximum', Expression('roll.steps - roll.width', {'roll': roll}))" in code
    assert "surface.formula(label, 'text', Template('{roll.column + 1}/{self.width}', {'roll': roll, 'self': label}))" in code
    assert "message.NoteOn(note = Expression('note + 12'), velocity = Expression('velocity * 100'))" in code
    namespace = {}
    exec(compile(code, 'standalone.py', 'exec'), namespace)
    namespace['app'].transport.close()
    namespace['position'].set_number(3)
    namespace['surface'].update()
    assert namespace['roll'].column == 3 and namespace['label'].text == '4/8' and namespace['position'].maximum == 24
