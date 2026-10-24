import pytest

from pyxelwidgets import (Button, ButtonGroup, Changed, Fader, Mapping, MessageReceived, Pressed, Pressure, Released,
                          Source, Surface, Text, Toggled, XY)
from pyxelwidgets.events import Emitter
from pyxelwidgets.message import Command, ControlChange, NoteOff, NoteOn, OscMessage, PolyPressure


class Output(Emitter):
    """Records what's sent; ``receive`` plays a message from the other side."""

    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)

    def receive(self, message):
        self.emit(MessageReceived(self, message))


def test_button_sends_notes():
    out, button = Output(), Button(0, 0, 1, 1)
    Mapping(button, out, NoteOn(36), on = Pressed)
    Mapping(button, out, NoteOff(36), on = Released)
    button.press(0, 0, 0.5)
    button.release(0, 0)
    assert [m.to_midi() for m in out.sent] == [[0x90, 36, 64], [0x80, 36, 0]]


def test_cells_and_pressure():
    out, pads = Output(), ButtonGroup(0, 0, 4, 2, mode = ButtonGroup.Mode.Button)
    Mapping(pads, out, NoteOn(Source('cell', offset = 36)), on = Pressed)
    Mapping(pads, out, PolyPressure(Source('cell', offset = 36)), on = Pressure)
    pads.press(1, 1, 1.0)
    pads.pressure(1, 1, 0.5)
    assert [m.to_midi() for m in out.sent] == [[0x90, 41, 127], [0xA0, 41, 64]]


def test_unknown_source_is_an_error():
    with pytest.raises(ValueError, match = "Changed has no 'velocity'"):
        Mapping(Fader(0, 0, 1, 8), Output(), NoteOn(36), on = Changed)
    with pytest.raises(ValueError, match = 'needs an event'):
        Mapping(Fader(0, 0, 1, 8), Output(), NoteOn(36))


def test_fader_feedback_without_echo():
    out, fader = Output(), Fader(0, 0, 1, 8)
    Mapping(fader, out, ControlChange(7), on = Changed, feedback = True)
    fader.set_value(1.0)
    out.receive(ControlChange(7, 0, 1))
    out.receive(ControlChange(8, 127, 1))
    assert fader.value == 0.0 and out.sent == [ControlChange(7, 127, 1)]


def test_relative_delta():
    out, fader = Output(), Fader(0, 0, 1, 8)
    Mapping(fader, out, Command('V-Pot 1', Source('delta')), on = Changed, feedback = True)
    fader.set_value(0.5)
    out.receive(Command('V-Pot 1', 0.4))
    fader.set_value(0.5)
    assert [m.value for m in out.sent] == [64, 13]


def test_led_feedback_lights_and_flashes():
    out, play = Output(), Button(0, 0, 1, 1, mode = Button.Mode.Switch)
    Mapping(play, out, Command('Play'), on = Pressed, feedback = True)
    out.receive(Command('Play', 1.0))
    assert play.value == 1.0 and play.state and play.animation is None
    out.receive(Command('Play', 1.0, True))
    assert play.animation is not None
    out.receive(Command('Play', 0.0))
    assert play.value == 0.0 and not play.state and play.animation is None
    # The switch toggles from the state the DAW set
    play.press(0, 0)
    assert play.value == 1.0


def test_button_group_and_xy_and_text_feedback():
    out = Output()
    mutes = ButtonGroup(0, 0, 8, 1, mode = ButtonGroup.Mode.Multi)
    Mapping(mutes, out, Command('Mute {x+1}'), on = Toggled, feedback = True)
    seen = []
    mutes.on(Toggled, seen.append)
    out.receive(Command('Mute 3', 1.0))
    assert mutes.state[2, 0] and not seen
    xy = XY(0, 0, 4, 4)
    Mapping(xy, out, OscMessage('/xy', Source('value_x'), Source('value_y')), on = Changed, feedback = True)
    out.receive(OscMessage('/xy', 0.25, 0.75))
    assert xy.value == (0.25, 0.75)
    name = Text(0, 0, 8, 5)
    Mapping(name, out, Command('Name 1', Source('text')), feedback = True)
    out.receive(Command('Name 1', 'Drums'))
    assert name.text == 'Drums'


def test_surface_map_holds_the_lock():
    surface, out = Surface(8, 8), Output()
    fader = surface.add(Fader(0, 0, 1, 8))
    mapping = surface.map(fader, out, ControlChange(7), on = Changed, feedback = True)
    acquired = []
    original = surface.lock
    class Lock:
        def __enter__(self):
            acquired.append(True)
            return original.__enter__()
        def __exit__(self, *args):
            return original.__exit__(*args)
    mapping.lock = Lock()
    out.receive(ControlChange(7, 64, 1))
    assert acquired and surface.mappings == [mapping]
    surface.unmap(mapping)
    out.receive(ControlChange(7, 0, 1))
    assert fader.value == pytest.approx(64 / 127, abs = 1e-6)


def test_one_message_on_several_channels():
    out, fader = Output(), Fader(0, 0, 1, 8)
    Mapping(fader, out, ControlChange(91, channel = (1, 2, 10)), on = Changed, feedback = True)
    fader.set_value(1.0)
    assert out.sent == [ControlChange(91, 127, 1), ControlChange(91, 127, 2), ControlChange(91, 127, 10)]
    # Feedback from any of them
    out.receive(ControlChange(91, 0, 10))
    assert fader.value == 0.0
    out.receive(ControlChange(91, 127, 3))
    assert fader.value == 0.0


def test_channel_lists_in_layouts_and_code():
    from pyxelwidgets import codegen, parser
    layout = {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 1, 'height': 8},
              'outputs': [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'Synth'}],
              'widgets': [{'type': 'Fader', 'name': 'space', 'x': 0, 'y': 0, 'width': 1, 'height': 8}],
              'mappings': [{'widget': 'space', 'on': 'Changed', 'output': 'synth',
                            'message': {'type': 'ControlChange', 'control': 91, 'channel': [1, 2, 2, 10]}}]}
    message = parser.Parser(layout, devices = False).mapping_settings()[0][3]
    assert message.channel == (1, 2, 10) and parser.message_to_json(message)['channel'] == [1, 2, 10]
    assert 'channel = (1, 2, 10)' in codegen.standalone(layout, run = False)
    assert next(field for field in parser.message_schema()['NoteOn']['fields'] if field['name'] == 'channel')['many']
    for bad in ([], [0, 1], [1, 'two']):
        layout['mappings'][0]['message']['channel'] = bad
        with pytest.raises(parser.LayoutError, match = r'mappings\[0\]\.message\.channel: a list of channels'):
            parser.Parser(layout, devices = False)
