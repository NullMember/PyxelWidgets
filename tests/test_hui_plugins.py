"""
Plug-in parameters through HUI, against a simulated Pro Tools (as probed on
Pro Tools, 2026-10-14): a strip's Insert switch shows its track's inserts
list ("Insert 1-4    Audio 1" over the slots' names, the selected one
blinking), 18 SCROLL ticks switch to slot 5 and back, Param Select opens a
slot on the page shown last with a header covering the top line for a while,
9 SCROLL ticks a page, switches on the top line (Param Select presses them),
knobs on the bottom line (rings on CC 0x18-0x1B), Param Insert back to the list.
"""

import threading
import time

import pytest

from pyxelwidgets import Changed, Knob, MessageReceived, Surface
from pyxelwidgets.devices.mackie import _HUI_PORTS, HUI
from pyxelwidgets.message import PluginParameter, Source
from pyxelwidgets import parser

STRIP = [(['Byps', 'Phas', 'vPre', 'Ordr'], ['Trim', 'Vol']),
         # Pro Tools keeps the knobs a page doesn't use
         (['EqOn', 'FlOn', 'Dyn', 'vOff'], ['Trim', 'Vol']),
         (['xIn', 'Lisn'], ['xRat', 'xThr', 'xAtk', 'xDpt']),
         ([], ['LmF', 'LmG', 'LmQ']),
         # Pro Tools labels the high-mid Q like the low-mid one
         ([], ['HmF', 'HmG', 'LmQ'])]
EQ = [(['In'], ['Freq', 'Gain', 'Q'])]

TRACKS = [
    ('Audio 1', [('Channel Strip=2', 'ChnnlSt=2', STRIP), ('DownMixer', 'DownMixer', [([], ['Mix'])])]),
    ('Snare', []),
    *[(f'Pad {n}', []) for n in range(1, 8)],
    ('Audio 9', [('EQ37Bnd=2', 'EQ37Bnd=2', EQ), ('D-Verb=2', 'D-Verb=2', [([], ['Mix', 'Size'])]),
                 None, ('ModDelay', 'ModDlyIII', [([], ['Time'])]), ('ElevenLite', 'ElevenLit', [(['MByp'], ['Amp', 'Cab'])]),
                 # Slots 6-8 are named only while selected, 9 and 10 can't be reached
                 ('Channel Strip', 'ChnnlStrp', STRIP), ('Sci-Fi', 'Sci-Fi', [([], ['Inpt', 'ETyp'])]), None,
                 ('Recti-Fi', 'Recti-Fi', [([], ['Mix'])])]),
    ('Bass', [('EQ37Bnd=2', 'EQ37Bnd=2', EQ)]),
]


class ProTools:
    """Pro Tools' side of the HUI ports."""

    header_time = 0.2
    blink = 0.02
    # Switching the inserts list between slots 1-4 and 5-8 (Pro Tools takes up to a second or so)
    list_lag = 0.0
    # Param Insert lights after the header (and the switches are the list's until then)
    lag = 0.03

    def __init__(self, tracks):
        self.tracks = tracks
        self.bank = 0
        self.selected = 0
        self.view = None
        self.part = '1-4'
        self.slot = None
        # The slot selected in the inserts list (its name blinks)
        self.chosen = 1
        self.shown_pages = {}
        self.values = {}
        self.switches = {}
        self.zone = None
        self.ticks = 0
        self.zones = [' ' * 10] * 8
        # Each page shown: a header timer from before doesn't end a newer header
        self.shows = 0
        # What Pro Tools thinks the top line shows: a page header passes, so it doesn't count,
        # and going back to the same list doesn't redraw it
        self.list_top = None
        self.presses = []
        # Param Select presses Pro Tools drops (right after the list changed)
        self.drop = 0
        self.hui = None

    def connect(self, hui):
        self.hui = hui
        hui._midi_output = hui._midi_input = self
        self.send_names()

    def close_port(self):
        pass

    def cancel_callback(self):
        pass

    # To the surface

    def write(self, zone, text):
        text = f'{text:<10}'[:10]
        if self.zones[zone] != text:
            self.zones[zone] = text
            self.hui.decode([0xF0, 0x00, 0x00, 0x66, 0x05, 0x00, 0x12, zone, *map(ord, text), 0xF7])

    def line(self, first, text):
        text = f'{text:<40}'[:40]
        for zone in range(4):
            self.write(first + zone, text[zone * 10:zone * 10 + 10])

    def led(self, name, on):
        zone, port = next(place for place, named in _HUI_PORTS.items() if named == name)
        self.hui.decode([0xB0, 0x0C, zone])
        self.hui.decode([0xB0, 0x2C, (0x40 if on else 0) | port])

    def send_names(self):
        for strip in range(8):
            index = self.bank + strip
            name = self.tracks[index][0].replace(' ', '')[:4] if index < len(self.tracks) else ''
            self.hui.decode([0xF0, 0x00, 0x00, 0x66, 0x05, 0x00, 0x10, strip, *map(ord, f'{name:<4}'), 0xF7])

    # From the surface

    def send_message(self, message):
        if message[0] & 0xF0 != 0xB0:
            return
        control, value = message[1], message[2]
        steps = (value & 0x3F) * (1 if value & 0x40 else -1)
        if control == 0x0F:
            self.zone = value
        elif control == 0x2F and value & 0x40:
            name = _HUI_PORTS.get((self.zone, value & 0x0F))
            if name is not None:
                self.presses.append(name)
                self.press(name)
        elif 0x48 <= control < 0x4C:
            self.turn(control - 0x48, steps)
        elif control == 0x4C:
            self.scroll(steps)

    def plugins(self):
        return self.tracks[self.selected][1]

    def plugin(self):
        return self.plugins()[self.slot - 1]

    def press(self, name):
        if name.startswith('Insert ') and name[7:].isdigit():
            index = self.bank + int(name[7:]) - 1
            if self.view != 'parameters' and index < len(self.tracks):
                self.selected, self.view = index, 'list'
                self.show_list()
        elif name == 'Param Insert':
            if self.view == 'parameters':
                self.view = 'list'
                self.show_list()
        elif name.startswith('Param Select '):
            column = int(name[13:]) - 1
            if self.view == 'list' and self.drop:
                self.drop -= 1
            elif self.view == 'list':
                slot = column + 5 if self.part == '5' else column + 1
                plugins = self.plugins()
                self.chosen = slot
                if slot <= len(plugins) and plugins[slot - 1] is not None:
                    self.open(slot)
                else:
                    self.show_list()
            elif self.view == 'parameters':
                switches = self.page()[0]
                if column < len(switches):
                    key = (self.selected, self.slot, switches[column])
                    self.switches[key] = not self.switches.get(key, False)
                    self.write(column, self.text(switches[column], 'On' if self.switches[key] else 'Off'))
                    self.list_top = None
        elif name in ('Bank Left', 'Bank Right'):
            last = max(0, len(self.tracks) - 8)
            # The last bank ends at the last track
            self.bank = max(0, min(last, self.bank + (8 if name == 'Bank Right' else -8)))
            self.send_names()

    def show_list(self):
        self.led('Param Insert', False)
        top = f'{"Insert " + self.part:<14}{self.tracks[self.selected][0]}'
        if top != self.list_top:
            self.line(0, top)
        self.list_top = top
        plugins = self.plugins() + [None] * 10
        first = 1 if self.part == '1-4' else 5
        names = [plugin[1] if plugin else 'No Insert' for plugin in plugins[first - 1:first + 3]]
        if self.part == '5':
            # Past slot 5 only the selected slot is named
            names = [name if slot in (5, self.chosen) else '' for slot, name in zip(range(5, 9), names)]
        # The selected slot blinks
        blinking = self.chosen - first if first <= self.chosen < first + 4 else None
        for zone, name in enumerate(names):
            self.write(4 + zone, '' if zone == blinking else name)
        self.shows += 1
        shown = self.shows
        if blinking is not None:
            threading.Timer(self.blink, lambda: self.shows == shown and self.write(4 + blinking, names[blinking])).start()

    def open(self, slot):
        self.slot = self.chosen = slot
        self.show_page()

        def opened():
            self.view = 'parameters'
            self.led('Param Insert', True)
        threading.Timer(self.lag, opened).start()

    def page(self):
        pages = self.plugin()[2]
        return pages[self.shown_pages.get((self.selected, self.slot), 1) - 1]

    def text(self, name, value):
        return f'{name:<4} {value}'

    def value(self, name):
        return self.values.get((self.selected, self.slot, name), 0.0)

    def show_page(self):
        name, _, pages = self.plugin()
        page = self.shown_pages.get((self.selected, self.slot), 1)
        switches, knobs = self.page()
        self.line(0, f'Page {page:2}/{len(pages):<2}    {name:<19}(Ins {self.slot if self.slot <= 5 else "?"})')
        for column in range(4):
            self.write(4 + column, self.text(knobs[column], f'{self.value(knobs[column]):.2f}') if column < len(knobs) else '')
            ring = 1 + round(self.value(knobs[column]) * 10) if column < len(knobs) else 0
            self.hui.decode([0xB0, 0x18 + column, 0x20 | ring])
        self.shows += 1
        shown = self.shows

        def switches_shown():
            if self.view == 'parameters' and self.shows == shown:
                self.list_top = None
                for column in range(4):
                    on = self.switches.get((self.selected, self.slot, switches[column]), False) if column < len(switches) else None
                    self.write(column, self.text(switches[column], 'On' if on else 'Off') if column < len(switches) else '')
        threading.Timer(self.header_time, switches_shown).start()

    def scroll(self, steps):
        self.ticks += steps
        if self.view == 'list' and abs(self.ticks) >= 18:
            part, self.ticks = ('5' if self.ticks > 0 else '1-4'), 0
            if part != self.part:
                def switched():
                    self.part = part
                    self.show_list()
                if self.list_lag:
                    threading.Timer(self.list_lag, switched).start()
                else:
                    switched()
        elif self.view == 'parameters':
            key = (self.selected, self.slot)
            while abs(self.ticks) >= 9:
                sign = 1 if self.ticks > 0 else -1
                self.ticks -= 9 * sign
                page = self.shown_pages.get(key, 1) + sign
                if 1 <= page <= len(self.plugin()[2]):
                    self.shown_pages[key] = page
                    self.show_page()

    def move(self, track, first, second):
        """Swap two insert slots of ``track`` (1-5), as dragging them in Pro Tools does."""
        plugins = self.tracks[track][1]
        plugins[first - 1], plugins[second - 1] = plugins[second - 1], plugins[first - 1]
        if self.view == 'parameters' and self.selected == track and self.slot in (first, second):
            # The plug-in shown keeps showing, at its new slot
            key = (track, self.slot)
            self.slot = second if self.slot == first else first
            self.shown_pages[(track, self.slot)] = self.shown_pages.pop(key, 1)
            self.show_page()
        elif self.view == 'list' and self.selected == track:
            self.show_list()

    def turn(self, column, steps):
        if self.view != 'parameters':
            return
        knobs = self.page()[1]
        if column < len(knobs):
            key = (self.selected, self.slot, knobs[column])
            self.values[key] = min(1.0, max(0.0, self.values.get(key, 0.0) + steps / 100))
            self.write(4 + column, self.text(knobs[column], f'{self.values[key]:.2f}'))
            self.hui.decode([0xB0, 0x18 + column, 0x20 | (1 + round(self.values[key] * 10))])


@pytest.fixture
def daw(monkeypatch):
    monkeypatch.setattr(HUI, 'settle', 0.01)
    monkeypatch.setattr(HUI, 'timeout', 0.2)
    monkeypatch.setattr(HUI, 'header_time', 0.5)
    monkeypatch.setattr(HUI, 'blink_time', 0.3)
    hui = HUI()
    daw = ProTools([(name, list(plugins)) for name, plugins in TRACKS])
    daw.connect(hui)
    yield daw
    hui.close()


def test_scan_tracks(daw):
    # The last bank ends at the last track: Pad 3-7 are shown again there
    assert daw.hui.scan_tracks() == ['Audio 1', 'Snare'] + [f'Pad {n}' for n in range(1, 8)] + ['Audio 9', 'Bass']


def test_scan_plugins_up_to_slot_8(daw):
    assert daw.hui.scan_plugins('Audio 9') == ['EQ37Bnd=2', 'D-Verb=2', 'ModDelay', 'ElevenLite', 'Channel Strip', 'Sci-Fi']
    assert daw.hui.scan_plugins('Audio 1') == ['Channel Strip=2', 'DownMixer']
    assert daw.hui.scanned()['plugins']['Audio 9'][-1] == 'Sci-Fi'


def test_dropped_press_is_repeated(daw):
    daw.drop = 1
    assert daw.hui.scan_plugins('Audio 1') == ['Channel Strip=2', 'DownMixer']
    # Nothing pressed in the parameters (that would switch a parameter)
    assert daw.switches == {}


def test_slow_list_and_a_header_left_on_screen(daw, monkeypatch):
    monkeypatch.setattr(HUI, 'list_time', 0.6)
    # Longer than a switch's timeout
    daw.list_lag = 0.3
    # Slot 8 is empty: Sci-Fi's header (slot 7, "Ins ?") is still on the top line when it's pressed
    assert daw.hui.scan_plugins('Audio 9') == ['EQ37Bnd=2', 'D-Verb=2', 'ModDelay', 'ElevenLite', 'Channel Strip', 'Sci-Fi']


def test_scan_parameters(daw):
    hui = daw.hui
    # Opened on the page shown last: scanned from the first
    daw.shown_pages[(0, 1)] = 3
    names = hui.scan_parameters('Audio 1', 'Channel Strip=2')
    assert names == ['Byps', 'Phas', 'vPre', 'Ordr', 'Trim', 'Vol', 'EqOn', 'FlOn', 'Dyn', 'vOff',
                     'xIn', 'Lisn', 'xRat', 'xThr', 'xAtk', 'xDpt', 'LmF', 'LmG', 'LmQ', 'HmF', 'HmG', 'LmQ (2)']
    assert daw.shown_pages[(0, 1)] == 1
    assert hui.scan_parameters('Audio 9', 'ElevenLite') == ['MByp', 'Amp', 'Cab']


def test_knob_turns_a_parameter_with_feedback(daw):
    hui = daw.hui
    surface = Surface(8, 8)
    knob = Knob(0, 0, 2, 2)
    surface.add(knob)
    surface.map(knob, hui, PluginParameter('Audio 1', 'Channel Strip=2', 'xThr', Source('delta')), on = Changed, feedback = True)
    received = []
    hui.on(MessageReceived, lambda event: received.append(event.message))
    knob.set_value(0.2)
    deadline = time.monotonic() + 10
    while daw.values.get((0, 1, 'xThr')) is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert daw.values[(0, 1, 'xThr')] == pytest.approx(round(0.2 * 127) / 100)
    assert daw.shown_pages[(0, 1)] == 3
    time.sleep(0.05)
    # The ring: 11 positions
    [ring] = [message.value for message in received if isinstance(message, PluginParameter) and message.parameter == 'xThr'][-1:]
    assert ring == pytest.approx(round(daw.values[(0, 1, 'xThr')] * 10) / 10)
    assert knob.value == pytest.approx(ring)
    assert hui.warning is None


def test_repeated_label_is_another_parameter(daw):
    hui = daw.hui
    hui.scan_parameters('Audio 1', 'Channel Strip=2')
    hui._turn('Audio 1', 'Channel Strip=2', 'LmQ (2)', 20)
    assert daw.shown_pages[(0, 1)] == 5


def test_parameter_shown_again_gets_feedback(daw):
    hui = daw.hui
    hui.scan_parameters('Audio 1', 'Channel Strip=2')
    received = []
    hui.on(MessageReceived, lambda event: received.append(event.message))
    hui._to_page(2)
    daw.turn(0, 50)
    assert PluginParameter('Audio 1', 'Channel Strip=2', 'Trim', 0.5) in received


def test_switch_is_pressed_and_reports_its_state(daw):
    hui = daw.hui
    received = []
    hui.on(MessageReceived, lambda event: received.append(event.message))
    hui._turn('Audio 1', 'Channel Strip=2', 'EqOn', 1)
    assert daw.switches[(0, 1, 'EqOn')] is True
    assert daw.presses[-1] == 'Param Select 1'
    assert PluginParameter('Audio 1', 'Channel Strip=2', 'EqOn', 1.0) in received
    hui._turn('Audio 1', 'Channel Strip=2', 'EqOn', -1)
    assert daw.switches[(0, 1, 'EqOn')] is False
    assert PluginParameter('Audio 1', 'Channel Strip=2', 'EqOn', 0.0) in received


def test_turns_on_another_plugin_and_slot_5(daw):
    hui = daw.hui
    hui._turn('Audio 1', 'Channel Strip=2', 'Trim', 10)
    hui._turn('Audio 9', 'ElevenLite', 'Cab', 20)
    hui._turn('Audio 1', 'Channel Strip=2', 'LmG', 30)
    hui._turn('Audio 9', 'Sci-Fi', 'ETyp', 40)
    hui._turn('Audio 9', 'Channel Strip', 'xThr', 50)
    assert daw.values == {(0, 1, 'Trim'): 0.1, (9, 5, 'Cab'): 0.2, (0, 1, 'LmG'): 0.3, (9, 7, 'ETyp'): 0.4,
                          (9, 6, 'xThr'): 0.5}


def test_moved_plugins_are_found_by_name(daw):
    hui = daw.hui
    hui._turn('Audio 9', 'ModDelay', 'Time', 10)
    # Moved to slot 2 in Pro Tools while it shows
    daw.move(9, 2, 4)
    hui._turn('Audio 9', 'ModDelay', 'Time', 10)
    # And back while the list shows
    daw.press('Param Insert')
    daw.move(9, 2, 4)
    hui._turn('Audio 9', 'ModDelay', 'Time', 10)
    assert daw.values[(9, 4, 'Time')] == pytest.approx(0.2)
    assert daw.values[(9, 2, 'Time')] == pytest.approx(0.1)
    assert not any(key[2] == 'Mix' for key in daw.values)


def test_unknown_parameter_is_a_warning(daw):
    hui = daw.hui
    hui.send(PluginParameter('Audio 1', 'Channel Strip=2', 'Nope', 3))
    deadline = time.monotonic() + 10
    while hui.warning is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert 'no parameter' in hui.warning


def test_needs_a_connection():
    with pytest.raises(ConnectionError):
        HUI().scan_tracks()


def test_layouts():
    layout = {'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 8, 'height': 8},
              'outputs': [{'name': 'daw', 'type': 'mackie.HUI', 'virtual': 'HUI'}],
              'widgets': [{'type': 'Knob', 'name': 'trim', 'x': 0, 'y': 0, 'width': 2, 'height': 2}],
              'mappings': [{'widget': 'trim', 'on': 'Changed', 'output': 'daw', 'feedback': True,
                            'message': {'type': 'PluginParameter', 'track': 'Audio 1', 'plugin': 'Channel Strip=2',
                                        'parameter': 'Trim', 'value': {'source': 'delta'}}}]}
    ui = parser.load(layout, devices = False)
    [(_, _, _, message, _)] = ui.mapping_settings()
    assert message == PluginParameter('Audio 1', 'Channel Strip=2', 'Trim')
