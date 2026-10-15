"""The designer's advanced snippets work as their descriptions say (loaded as layouts, pads pressed through the surface)."""

import json
import pathlib

import pytest

from pyxelwidgets import Changed, Choice, Link, Sequencer, Source, Transport, parser
from pyxelwidgets.designer import SNIPPETS, snippet_layout
from pyxelwidgets.events import PadPressed, PadReleased, Toggled
from pyxelwidgets.widgets import ButtonGroup


def load(name):
    return parser.load(snippet_layout(json.loads((SNIPPETS / f'{name}.json').read_text())), devices = False)


def tap(ui, x, y):
    """A press and release on the surface at ``x``, ``y``, as a device's pad would."""
    for kind in (PadPressed, PadReleased):
        ui.surface.root.input(kind(None, x, y, 1.0))


def press(ui, x, y, kind = PadPressed):
    ui.surface.root.input(kind(None, x, y, 1.0))


# Choice values and ButtonGroup's starting cell

def test_choice_picks_by_index_or_spreads_a_unit_value():
    choice = Choice(Source('x'), (8, 16, 24, 32))
    assert [choice.choose({'x': x}) for x in (-1, 0, 2, 9)] == [8, 8, 24, 32]
    unit = Choice(Source('value'), ('a', 'b', 'c'))
    assert [unit.choose({'value': v}) for v in (0.0, 0.4, 1.0)] == ['a', 'b', 'c']
    with pytest.raises(ValueError):
        Choice(Source('x'), ())


def test_choice_links_and_layout_errors():
    sequencer, row = Sequencer(0, 0, 8, 4), ButtonGroup(0, 0, 4, 1)
    Link(row, sequencer, 'length', Choice(Source('x'), (8, 16, 24, 32)), on = Toggled)
    row.tap(2, 0)
    assert sequencer.length == 24
    layout = {'format': parser.FORMAT, 'version': parser.VERSION, 'surface': {'width': 8, 'height': 5},
              'widgets': [{'type': 'Sequencer', 'name': 's', 'x': 0, 'y': 1, 'width': 8, 'height': 4},
                          {'type': 'ButtonGroup', 'name': 'row', 'x': 0, 'y': 0, 'width': 4, 'height': 1}],
              'links': [{'widget': 'row', 'on': 'Toggled', 'target': 's', 'option': 'direction', 'value': {'choose': ['Backward', 'Nope'], 'by': 'x'}}]}
    with pytest.raises(parser.LayoutError, match = r'choose\[1\]'):
        parser.load(layout, devices = False)
    layout['links'][0]['value'] = {'choose': ['Backward'], 'by': 'note'}
    with pytest.raises(parser.LayoutError, match = 'by'):
        parser.load(layout, devices = False)


def test_button_group_selected():
    group = ButtonGroup(0, 0, 4, 2, selected = 5)
    assert group.selected == 5 and group.state[1, 1]
    events = []
    group.on(Toggled, events.append)
    group.configure(selected = 0)
    assert group.selected == 0 and not group.state[1, 1] and events == []
    assert ButtonGroup(0, 0, 2, 1, allow_none = True).selected is None


# The advanced snippets

def test_sixteen_sequencers():
    ui = load('sixteen-sequencers-8x8')
    tracks = ui['tracks']
    shown = lambda: [n for n in range(1, 17) if ui[f'track{n}'].visible]
    assert shown() == [1]
    tap(ui, 2, 1)                     # cell 6 of the 4x4: the seventh sequencer
    assert tracks.page == 6 and shown() == [7]
    # Its rows: length 16, ping-pong, swing 58, full gate
    for x, y in ((5, 3), (6, 2), (6, 1), (7, 0)):
        tap(ui, x, y)
    seq = ui['seq7']
    assert (seq.length, seq.direction, seq.swing, seq.gate) == (16, Sequencer.Direction.PingPong, 58.0, 1.0)
    assert (ui['seq1'].length, ui['seq1'].gate) == (32, 0.5)
    # Its steps are on the top half; every sequencer is played by the transport
    tap(ui, 0, 7)
    assert seq.state[0, 3] and not ui['seq1'].state.any()
    assert len(ui.attach(Transport())) == 16
    # The rows show the sequencer's settings from the start: length 32, gate 0.5
    assert ui['length1'].selected == 3 and ui['gate1'].selected == 2


def test_step_editor():
    ui = load('step-editor-8x8')
    steps = ui['steps']
    tap(ui, 2, 7)                     # step 26 on (top row)
    press(ui, 2, 7)                   # held...
    for x, y in ((3, 3), (1, 2), (2, 1), (1, 0)):
        tap(ui, x, y)
    press(ui, 2, 7, PadReleased)      # ...stays on, edited
    cell = (2, 3)
    assert steps.state[cell]
    assert (steps.velocities[cell], steps.probabilities[cell], steps.ratchets[cell], steps.note_of(26)) == (0.5, 0.25, 3, 38)


def test_euclidean_workstation():
    ui = load('euclidean-workstation-8x8')
    tap(ui, 2, 3)                     # voice 3
    tap(ui, 4, 2)                     # 5 hits
    tap(ui, 1, 1)                     # turned by 1
    tap(ui, 6, 0)                     # 7 steps
    euclid = ui['euclid']
    assert (euclid.pulses[2], euclid.rotations[2], euclid.row_length(2)) == (5, 1, 7)
    assert euclid.pulses[0] == 0


def test_melody_workstation():
    ui = load('melody-workstation-8x8')
    roll = ui['roll']
    tap(ui, 6, 1)                     # minor pentatonic
    tap(ui, 3, 0)                     # octave up
    tap(ui, 5, 0)                     # a row up
    assert (roll.scale.name, roll.octave, roll.row) == ('MinorPentatonic', 5, 1)
    assert ui['octave'].number == 5


def test_arp_station():
    ui = load('arp-station-8x8')
    arp = ui['arp']
    press(ui, 0, 3)
    press(ui, 2, 3)
    assert arp.held == [48, 52]
    tap(ui, 7, 1)                     # three octaves
    tap(ui, 1, 1)                     # down
    tap(ui, 0, 0)                     # short gate
    assert (arp.octaves, arp.mode.name, arp.gate) == (3, 'Down', 0.1)
    tap(ui, 4, 0)                     # latch: letting go keeps them
    press(ui, 0, 3, PadReleased)
    press(ui, 2, 3, PadReleased)
    assert arp.held == [48, 52]
    tap(ui, 5, 0)
    assert arp.held == []


def test_snapshot_mixer():
    ui = load('snapshot-mixer-8x8')
    level = ui['level1']
    level.value = 0.8
    tap(ui, 0, 7)                     # stored in slot 1
    level.value = 0.2
    sent = []
    level.on(Changed, lambda e: sent.append(e.value))
    tap(ui, 0, 7)
    assert level.value == 0.8 and sent == [0.8]
