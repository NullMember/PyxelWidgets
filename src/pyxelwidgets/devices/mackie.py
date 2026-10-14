"""
DAW control surface protocols over MIDI: Mackie Control (also Logic Control)
and HUI. Widgets send and receive ``Command``s by name (see ``commands``)::

    mackie = MackieControl()
    mackie.connect_virtual('PyxelWidgets MCU')   # pick it in the DAW (REAPER: Preferences >
                                                # Control/OSC/web > Add > Mackie Control Universal)
    surface.map(play, mackie, Command('Play'), on = Pressed, feedback = True)
    surface.map(play, mackie, Command('Play', 0.0), on = Released)
    surface.map(volume, mackie, Command('Fader 1', Source('value')), on = Changed, feedback = True)
    surface.map(pan, mackie, Command('V-Pot 1', Source('delta')), on = Changed, feedback = True)
    surface.map(clock, mackie, Command('Timecode', Source('text')), feedback = True)

Buttons are pressed while the value is above 0; received LEDs come back as 1.0
or 0.0 (``flash`` when blinking). Faders are 0.0-1.0. V-Pots and the jog wheel
send steps (negative turns left) and receive their LED ring position 0.0-1.0.
Received displays (``Timecode``, ``Name 1``, ``Display``...) carry text and
meters (``Meter 1``) 0.0-1.0.

Mackie Control also reaches plug-in parameters through the DAW's plug-in
mode, by name: ``scan_tracks()``, ``scan_plugins(track)`` and
``scan_parameters(track, plugin)`` press its buttons and read its display,
and ``PluginParameter`` messages turn a parameter's V-Pot::

    mackie.scan_tracks()                       # ['Drums', 'Bass', ...] (7 characters at most)
    mackie.scan_plugins('Bass')                # ['ReaEQ', 'ReaComp']
    mackie.scan_parameters('Bass', 'ReaComp')  # ['Thresh', 'Ratio', ...]
    surface.map(knob, mackie, PluginParameter('Bass', 'ReaComp', 'Ratio'), on = Changed, feedback = True)

Works with Logic Pro (its plug-in views, cursor paging and passing messages
are handled) and Cubase (track names on the bottom line, one insert slot at a
time picked with V-Pot 1, Channel Left/Right paging, names cut to 7
characters); REAPER's own Mackie Control support has no plug-in mode (its
OSC has: ``osc.REAPER``). HUI reaches Pro Tools' plug-in parameters the same
way (see ``HUI``).
"""

import enum
import operator
import re
import threading
import time

import pyxelwidgets.devices.midi_port
import pyxelwidgets.devices.plugins
import pyxelwidgets.events
import pyxelwidgets.message

__all__ = ['MackieControl', 'HUI']

def _steps(value) -> int:
    """V-Pot/jog steps from a command value, at most 63 either way."""
    return max(-63, min(63, int(round(float(value)))))

class _ControlSurface(pyxelwidgets.devices.midi_port.MidiPort):
    """Shared by the protocols: ``commands`` maps names to kinds for editors."""

    #: Command name → kind: button, fader, relative, display, meter
    commands: dict = {}
    messages = ('Command',) + pyxelwidgets.devices.midi_port.MidiPort.messages

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['commands'] = [{'name': name, 'kind': kind} for name, kind in cls.commands.items()]
        return info

    def _received(self, name: str, value, flash: bool = False) -> None:
        self.emit(pyxelwidgets.events.MessageReceived(self, pyxelwidgets.message.Command(name, value, flash)))

# Mackie Control

_MCU_STRIP = [('Rec', 0x00), ('Solo', 0x08), ('Mute', 0x10), ('Select', 0x18), ('V-Select', 0x20), ('Fader Touch', 0x68)]
_MCU_BUTTONS = {f'{name} {i + 1}': base + i for name, base in _MCU_STRIP for i in range(8)}
_MCU_BUTTONS.update({
    'Track': 0x28, 'Send': 0x29, 'Pan': 0x2A, 'Plug-in': 0x2B, 'EQ': 0x2C, 'Instrument': 0x2D,
    'Bank Left': 0x2E, 'Bank Right': 0x2F, 'Channel Left': 0x30, 'Channel Right': 0x31,
    'Flip': 0x32, 'Global View': 0x33, 'Name/Value': 0x34, 'SMPTE/Beats': 0x35,
    **{f'F{i + 1}': 0x36 + i for i in range(8)},
    'MIDI Tracks': 0x3E, 'Inputs': 0x3F, 'Audio Tracks': 0x40, 'Audio Instruments': 0x41, 'Aux': 0x42,
    'Busses': 0x43, 'Outputs': 0x44, 'User': 0x45,
    'Shift': 0x46, 'Option': 0x47, 'Control': 0x48, 'Alt': 0x49,
    'Read': 0x4A, 'Write': 0x4B, 'Trim': 0x4C, 'Touch': 0x4D, 'Latch': 0x4E, 'Group': 0x4F,
    'Save': 0x50, 'Undo': 0x51, 'Cancel': 0x52, 'Enter': 0x53,
    'Markers': 0x54, 'Nudge': 0x55, 'Cycle': 0x56, 'Drop': 0x57, 'Replace': 0x58, 'Click': 0x59, 'Solo': 0x5A,
    'Rewind': 0x5B, 'Fast Forward': 0x5C, 'Stop': 0x5D, 'Play': 0x5E, 'Record': 0x5F,
    'Up': 0x60, 'Down': 0x61, 'Left': 0x62, 'Right': 0x63, 'Zoom': 0x64, 'Scrub': 0x65,
    'User A': 0x66, 'User B': 0x67, 'Master Fader Touch': 0x70,
    'SMPTE LED': 0x71, 'Beats LED': 0x72, 'Rude Solo LED': 0x73,
})
_MCU_NOTES = {note: name for name, note in _MCU_BUTTONS.items()}
_MCU_FADERS = {**{f'Fader {i + 1}': i for i in range(8)}, 'Master Fader': 8}
_MCU_RELATIVE = {**{f'V-Pot {i + 1}': 0x10 + i for i in range(8)}, 'Jog': 0x3C}

class MackieControl(pyxelwidgets.devices.plugins.PluginParameters, _ControlSurface):
    """
    Mackie Control Universal (or Logic Control, or an extender, by ``mode``):
    8 channel strips, transport and function buttons, the jog wheel, and
    feedback for LEDs, faders, V-Pot rings, meters, the timecode and
    assignment displays and the 2x56 character LCD (``Name 1``-``8``,
    ``Value 1``-``8`` for the strips' top and bottom lines, ``Display`` for
    both). Answers the Logic Control connection handshake.
    """

    class Mode(enum.Enum):
        """The model it presents itself as (its SysEx device ID)."""
        MackieControl = 0x14
        MackieControlExtender = 0x15
        LogicControl = 0x10
        LogicControlExtender = 0x11

    model = 'Mackie Control'
    vendor = 'Control surface'
    commands = {
        **{name: 'button' for name in _MCU_BUTTONS},
        **{name: 'fader' for name in _MCU_FADERS},
        **{name: 'relative' for name in _MCU_RELATIVE},
        **{f'Meter {i + 1}': 'meter' for i in range(8)},
        'Timecode': 'display', 'Assignment': 'display', 'Display': 'display',
        **{f'Name {i + 1}': 'display' for i in range(8)},
        **{f'Value {i + 1}': 'display' for i in range(8)},
    }
    #: Answered to the connection query
    serial = [0x50, 0x57, 0x30, 0x30, 0x30, 0x30, 0x31]

    messages = _ControlSurface.messages + ('PluginParameter', 'TrackParameter')

    #: Seconds without display changes after which the DAW has answered a button
    settle = 0.15
    #: Seconds to wait for the DAW to answer a button at all
    timeout = 0.8
    #: Seconds a passing message may hide the display (Logic's last 2)
    message_time = 3.0
    #: The most banks of tracks, or pages of parameters, a scan goes through
    most_pages = 64

    def __init__(self, *, mode: Mode = Mode.MackieControl,
                 plugin_button: str = 'Plug-in',
                 channel_button: str = 'Pan',
                 next_page: str = 'Bank Right',
                 previous_page: str = 'Bank Left',
                 **kwargs):
        """
        plugin_button: str = 'Plug-in', optional
            The button showing the selected track's plug-ins on the strips (a
            V-Pot press opens one's parameters).
        channel_button: str = 'Pan', optional
            The button going back to the tracks on the strips.
        next_page: str = 'Bank Right', optional
            The button showing a plug-in's next 8 parameters.
        previous_page: str = 'Bank Left', optional
            The button showing a plug-in's previous 8 parameters.
        """
        for name in (plugin_button, channel_button, next_page, previous_page):
            if name not in _MCU_BUTTONS:
                raise ValueError(f'{name!r} is not a Mackie Control button')
        super().__init__(**kwargs)
        self.mode = mode
        self.plugin_button = plugin_button
        self.channel_button = channel_button
        self.next_page = next_page
        self.previous_page = previous_page
        self.lcd = [' '] * 112
        # The top line without the DAW's passing messages (Logic's "Page 2/12")
        self._real_top = [' '] * 56
        self._real_changes = 0
        self.timecode = [' '] * 10
        self.assignment = [' ', ' ']
        #: Button LEDs the DAW lit: name → 1.0 (on), 0.0 (off)
        self.leds = {}
        # The strips' faders and V-Pot rings as the DAW last sent them: strip → 0.0-1.0
        self._faders = {}
        self._pans = {}
        # The strip whose Select was pressed for the plug-ins shown, while they are
        self._selected_strip = None
        # The names on each page of a plug-in's parameters, as scanned: (track, plugin) → [names]
        self._page_names = {}
        # Scans: track names as the display shows them (labels are made unique), plug-ins as
        # (label, strip) by track, parameters as (label, page, strip) by (track, plugin)
        self._track_names = []
        # Where each track shows: (bank, strip)
        self._track_places = []
        # What the DAW shows: 'channels', 'plugins', 'parameters' or None (not known), the bank
        # of tracks in the channels view, and (track, plugin, page) in the parameters view
        self._view = None
        self._bank = None
        self._focus = None
        # The buttons that page parameters (next, previous), once found
        self._paging = None
        # Cubase's layout, known by its page counter ("Page:01/13"): track names on the bottom
        # line, a header on top, one insert slot at a time (V-Pot 1 picks it), names filling the strips
        self._cubase = False
        # Cubase's header for an open plug-in (its name and the track's, as the bottom line shows them)
        self._headers = {}
        # Cubase's V-Pot rings, which come before the display says whose they are: strip → position
        self._rings = {}
        self._rings_lock = threading.Lock()
        self._display = threading.Condition()
        self._display_changes = 0
        self._display_time = 0.0

    @property
    def header(self) -> list:
        return [0x00, 0x00, 0x66, self.mode.value]

    def send(self, message) -> None:
        if isinstance(message, pyxelwidgets.message.TrackParameter):
            if isinstance(message.value, str):
                return
            if message.parameter == 'Pan':
                # V-Pot steps, summed while the DAW gets there
                steps = int(round(float(message.value)))
                if steps:
                    self._turn_later(message, steps, operator.add)
            else:
                self._turn_later(message, min(1.0, max(0.0, float(message.value))))
            return
        if isinstance(message, pyxelwidgets.message.PluginParameter):
            # V-Pot steps, summed while the DAW gets there
            steps = 0 if isinstance(message.value, str) else int(round(float(message.value)))
            if steps:
                self._turn_later(message, steps, operator.add)
            return
        if not isinstance(message, pyxelwidgets.message.Command):
            return super().send(message)
        if self._midi_output is None:
            return
        name, value = message.name, message.value
        if name in _MCU_BUTTONS:
            self.send_note_on(_MCU_BUTTONS[name], 0x7F if value > 0 else 0)
        elif name in _MCU_FADERS:
            position = int(round(min(1.0, max(0.0, float(value))) * 16383))
            self.send_pitch_bend(position, _MCU_FADERS[name])
        elif name in _MCU_RELATIVE:
            steps = _steps(value)
            if steps:
                self.send_control_change(_MCU_RELATIVE[name], steps if steps > 0 else 0x40 | -steps)

    def decode(self, midi: list) -> None:
        if not midi:
            return
        status = midi[0] & 0xF0
        if midi[0] == 0xF0:
            self._sysex(midi[1:-1] if midi[-1] == 0xF7 else midi[1:])
        elif status in (0x80, 0x90) and len(midi) == 3:
            name = _MCU_NOTES.get(midi[1])
            if name is not None:
                velocity = midi[2] if status == 0x90 else 0
                self.leds[name] = 1.0 if velocity else 0.0
                self._selection_changed(name, velocity > 0)
                self._received(name, 1.0 if velocity else 0.0, velocity == 1)
                kind, _, strip = name.rpartition(' ')
                if kind in _TRACK_BUTTONS and strip.isdigit():
                    self._track_feedback(int(strip) - 1, _TRACK_BUTTONS[kind], 1.0 if velocity else 0.0)
        elif status == 0xE0 and len(midi) == 3:
            channel = midi[0] & 0x0F
            name = 'Master Fader' if channel == 8 else f'Fader {channel + 1}'
            self._received(name, (midi[1] | (midi[2] << 7)) / 16383)
            if channel < 8:
                self._faders[channel] = (midi[1] | (midi[2] << 7)) / 16383
                self._track_feedback(channel, 'Volume', self._faders[channel])
        elif status == 0xB0 and len(midi) == 3:
            self._control(midi[1], midi[2])
        elif status == 0xD0 and len(midi) >= 2:
            strip, level = midi[1] >> 4, midi[1] & 0x0F
            if strip < 8 and level <= 0x0C:
                self._received(f'Meter {strip + 1}', level / 12)

    def _control(self, number: int, value: int) -> None:
        if 0x30 <= number < 0x38:
            # LED ring: position 1-11, 0 is off
            position = value & 0x0F
            strip = number - 0x30
            self._received(f'V-Pot {strip + 1}', (position - 1) / 10 if position else 0.0)
            self._pans[strip] = (position - 1) / 10 if position else 0.0
            if not self._cubase:
                return self._ring(strip, position)
            # Cubase sends a page's rings before its header: checked once the display settled
            with self._rings_lock:
                if not self._rings:
                    threading.Timer(self.settle, self._settled_rings).start()
                # With the page it came on: a ring is dropped if another page shows by then
                self._rings[strip] = (position, self._view, self._focus)
        elif 0x40 <= number < 0x4A:
            # Timecode digits, right to left
            self.timecode[9 - (number - 0x40)] = self._character(value)
            self._received('Timecode', ''.join(self.timecode).strip())
        elif number in (0x4A, 0x4B):
            self.assignment[0x4B - number] = self._character(value)
            self._received('Assignment', ''.join(self.assignment).strip())

    def _ring(self, strip: int, position: int) -> None:
        """A V-Pot ring on a parameter's strip, received as its PluginParameter (or a track's pan)."""
        self._track_feedback(strip, 'Pan', (position - 1) / 10 if position else 0.0)
        parameter = self._shown_parameter(strip)
        if parameter is not None:
            message = pyxelwidgets.message.PluginParameter(*parameter, (position - 1) / 10 if position else 0.0)
            self.emit(pyxelwidgets.events.MessageReceived(self, message))

    def _settled_rings(self) -> None:
        with self._rings_lock:
            rings, self._rings = self._rings, {}
        for strip, (position, view, focus) in rings.items():
            if (view, focus) == (self._view, self._focus):
                self._ring(strip, position)

    @staticmethod
    def _character(value: int) -> str:
        """A 7-segment display character: 0x40 adds a dot."""
        code = value & 0x3F
        text = chr(code + 0x40) if code < 0x20 else chr(code)
        return text + '.' if value & 0x40 else text

    def _sysex(self, data: list) -> None:
        if data[:3] != [0x00, 0x00, 0x66] or len(data) < 5 or data[3] != self.mode.value:
            return
        command, body = data[4], data[5:]
        if command == 0x00:
            # Connection query: answer with the serial number and a challenge
            self.send_sysex(self.header + [0x01] + self.serial + [0x00, 0x00, 0x00, 0x00])
        elif command == 0x02:
            self.send_sysex(self.header + [0x03] + self.serial)
        elif command == 0x13:
            self.send_sysex(self.header + [0x14] + [ord(c) for c in 'V1.0'])
        elif command == 0x12 and body:
            offset = body[0]
            before = list(self.lcd)
            for i, code in enumerate(body[1:]):
                if 0 <= offset + i < len(self.lcd):
                    self.lcd[offset + i] = chr(code) if 0x20 <= code < 0x7F else ' '
            if not self._cubase and _CUBASE_PAGE.search(''.join(self.lcd)):
                self._cubase = True
            if self.lcd[:56] != before[:56] and (self._cubase or not _has_message(self.lcd[:56])):
                self._real_top = self.lcd[:56]
                self._real_changes += 1
            if self.lcd != before:
                with self._display:
                    self._display_changes += 1
                    self._display_time = time.monotonic()
                    self._display.notify_all()
            top, bottom = ''.join(self.lcd[:56]), ''.join(self.lcd[56:])
            # Each strip has 7 characters per line
            for strip in range(8):
                self._received(f'Name {strip + 1}', top[strip * 7:strip * 7 + 7].strip())
                self._received(f'Value {strip + 1}', bottom[strip * 7:strip * 7 + 7].strip())
            self._received('Display', f'{top.rstrip()}\n{bottom.rstrip()}')

    # Plug-in parameters: the DAW's plug-in mode, driven by buttons and read from the display

    def row(self, line: int = 0) -> list:
        """
        The 8 strips' texts on the display's top (0) or bottom (1) line; the top
        line without a passing message over it (Logic's "Page 2/12" for 2 seconds).
        """
        text = ''.join(self._real_top if line == 0 else self.lcd[56:])
        return [text[strip * 7:strip * 7 + 7].strip() for strip in range(8)]

    def scan_tracks(self) -> list:
        """
        The DAW's track names: banks through the strips from the first, reading
        the display (a DAW shows at most 7 characters; repeated names get " (2)").
        Blocks for a while; don't call it from a MIDI or widget event handler.
        """
        with self._navigation:
            self._require()
            self._to_channels()
            self._first_bank()
            banks = []
            for bank in range(self.most_pages):
                shown = self.row(self._names_line)
                banks.append(shown)
                if not any(shown) or not self._tap('Bank Right', lambda: self.row(self._names_line) != shown):
                    break
                self._bank = bank + 1
            places = [(bank, strip) for bank in range(len(banks) - 1) for strip in range(8)]
            names = [name for shown in banks[:-1] for name in shown]
            if banks:
                # Cubase's last bank ends at the last track, showing some of the bank before again
                last = banks[-1]
                previous = (banks[-2],) * 2 if len(banks) > 1 and all(last) else None
                skip = _overlap(previous, (last, last))
                names += last[skip:]
                places += [(len(banks) - 1, strip) for strip in range(skip, 8)]
            while names and not names[-1]:
                names.pop()
            self._track_places = places[:len(names)]
            self._track_names = [name or f'Track {index + 1}' for index, name in enumerate(names)]
            self.tracks = pyxelwidgets.devices.plugins.labels(self._track_names)
            # Scans of tracks still there stay (their plug-ins are checked by name when used)
            self._plugins = {track: plugins for track, plugins in self._plugins.items() if track in self.tracks}
            self._parameters = {key: found for key, found in self._parameters.items() if key[0] in self.tracks}
            return list(self.tracks)

    def scan_plugins(self, track: str) -> list:
        """The plug-ins on ``track`` (a name from ``scan_tracks``), as the DAW's plug-in mode shows them."""
        with self._navigation:
            self._show_plugins(track)
            return self._read_plugins(track)

    def _read_plugins(self, track: str) -> list:
        """
        The plug-ins the display shows for ``track``, kept as (label, strip, name);
        in Cubase (label, insert slot, name), going through its slots with V-Pot 1.
        """
        if self._cubase:
            slots = self._slots()
            labels = pyxelwidgets.devices.plugins.labels([name for _, name in slots])
            self._plugins[track] = [(label, slot, name) for label, (slot, name) in zip(labels, slots)]
            return labels
        names = self._plugin_names()
        strips = [strip for strip, name in enumerate(names) if name]
        labels = pyxelwidgets.devices.plugins.labels([names[strip] for strip in strips])
        self._plugins[track] = [(label, strip, names[strip]) for label, strip in zip(labels, strips)]
        return labels

    def scan_parameters(self, track: str, plugin: str) -> list:
        """The parameters of ``plugin`` on ``track``: opens it and pages through its parameters, 8 at a time."""
        with self._navigation:
            self._open(track, plugin)
            self._to_page(0)
            found, previous, pages = [], None, []
            for page in range(self.most_pages):
                shown, values = self.row(0), self.row(1)
                pages.append(shown)
                # The page's V-Pot rings come with it
                self._focus = (track, plugin, page + 1)
                last = not self._next_page()
                # Logic's last page ends at the last parameter, showing some of the page before again
                skip = _overlap(previous, (shown, values)) if last and not self._cubase else 0
                found += [(name, page, strip) for strip, name in enumerate(shown) if name and strip >= skip]
                if last:
                    self._focus = (track, plugin, page)
                    break
                previous = (shown, values)
            labels = pyxelwidgets.devices.plugins.labels([name for name, _, _ in found])
            self._parameters[(track, plugin)] = [(label, page, strip) for label, (_, page, strip) in zip(labels, found)]
            self._page_names[(track, plugin)] = pages
            self._to_page(0)
            return labels

    @property
    def _names_line(self) -> int:
        """The display line with the track names in the channels view (Cubase's bottom)."""
        return 1 if self._cubase else 0

    def _require(self) -> None:
        if self._midi_output is None or self._midi_input is None:
            raise ConnectionError('Mackie Control is not connected to the DAW')

    def _tap(self, name: str, changed = None, *, read: bool = True, steps: int | None = None) -> bool:
        """
        Press and release ``name`` (or turn it by ``steps``); True once the DAW
        changed its display and settled (and ``changed()`` says it changed what
        matters), False if it didn't answer. To ``read`` the result, a passing
        message hiding it (Logic's "Page 2/12") is waited out.
        """
        with self._display:
            before = self._display_changes
            real_before = self._real_changes
        if steps is not None:
            self.send(pyxelwidgets.message.Command(name, steps))
        else:
            self.send(pyxelwidgets.message.Command(name, 1.0))
            self.send(pyxelwidgets.message.Command(name, 0.0))
        start = time.monotonic()
        with self._display:
            while True:
                now = time.monotonic()
                if self._display_changes != before:
                    quiet = self._display_time + self.settle - now
                    # A display that keeps changing (e.g. values moving) counts as settled after a while
                    if quiet <= 0 or now - start > 3 * self.timeout:
                        break
                    self._display.wait(quiet)
                elif now - start >= self.timeout:
                    return False
                else:
                    self._display.wait(self.timeout - (now - start))
            if read and not self._cubase and self._real_changes == real_before and _has_message(self.lcd[:56]):
                # What changed is under a message: it shows when the message goes
                end = time.monotonic() + self.message_time
                while _has_message(self.lcd[:56]) and time.monotonic() < end:
                    self._display.wait(end - time.monotonic())
        return changed() if changed is not None else True

    def _press(self, name: str) -> None:
        """Press and release a button that may not change the display (e.g. Select), then give the DAW a moment."""
        self.send(pyxelwidgets.message.Command(name, 1.0))
        self.send(pyxelwidgets.message.Command(name, 0.0))
        time.sleep(self.settle)

    def _to_channels(self) -> None:
        if self._view != 'channels':
            if self._view is None:
                # Another view first, so the DAW draws the channels view in full (it sends
                # only what changes, and may have drawn it before the connection)
                self._tap('Send')
            shown = self._lines()
            self._tap(self.channel_button, lambda: self._lines() != shown)
            if self.assignment[-1].endswith('.'):
                # Logic: a dot is its one-track view, and the button switches between them
                shown = self._lines()
                self._tap(self.channel_button, lambda: self._lines() != shown)
            self._view, self._focus = 'channels', None

    def _lines(self) -> tuple:
        return tuple(self.row(0)), tuple(self.row(1))

    def _first_bank(self) -> None:
        for _ in range(self.most_pages):
            shown = self.row(self._names_line)
            if not self._tap('Bank Left', lambda: self.row(self._names_line) != shown):
                break
        self._bank = 0

    def _track_index(self, track: str) -> int:
        if track not in self.tracks:
            self.scan_tracks()
        if track not in self.tracks:
            raise LookupError(f'no track {track!r} (tracks: {", ".join(self.tracks) or "none found"})')
        return self.tracks.index(track)

    def _select(self, track: str) -> None:
        """Show ``track`` in the channels view and press its Select."""
        strip = self._show_track(track)
        self._press(f'Select {strip + 1}')
        self._selected_strip = strip

    def _selection_changed(self, name: str, lit: bool) -> None:
        """
        Another track selected in the DAW (a click, or a fader moved in
        Cubase) while plug-ins are shown: the DAW shows that track's now (Logic,
        Cubase), so the plug-in shown isn't known any more.
        """
        if self._view not in ('plugins', 'parameters') or self._selected_strip is None or not name.startswith('Select '):
            return
        # Another track's lit (Logic turns the selected one's off by itself in its plug-in view)
        if lit and int(name[7:]) - 1 != self._selected_strip:
            self._view, self._focus, self._selected_strip = None, None, None

    def _show_track(self, track: str) -> int:
        """Show ``track`` in the channels view (checked by name) and return its strip."""
        self._require()
        index = self._track_index(track)
        self._to_channels()
        for attempt in range(2):
            bank, strip = self._track_places[index]
            if self._bank is None:
                self._first_bank()
            while self._bank < bank:
                self._tap('Bank Right')
                self._bank += 1
            while self._bank > bank:
                self._tap('Bank Left')
                self._bank -= 1
            if self.row(self._names_line)[strip] == self._track_names[index] or attempt:
                break
            # The tracks changed in the DAW: scan them again
            self.scan_tracks()
            index = self._track_index(track)
        # The DAW sent the bank's faders and lights while it changed: now known as the tracks'
        for shown in range(8):
            if shown in self._faders:
                self._track_feedback(shown, 'Volume', self._faders[shown])
            if shown in self._pans:
                self._track_feedback(shown, 'Pan', self._pans[shown])
            for button, parameter in _TRACK_BUTTONS.items():
                if f'{button} {shown + 1}' in self.leds:
                    self._track_feedback(shown, parameter, self.leds[f'{button} {shown + 1}'])
        return strip

    def _set_track(self, track: str, parameter: str, value) -> None:
        """Set a TrackParameter on the track's strip: its fader, V-Pot (Pan) or button."""
        with self._navigation:
            strip = self._show_track(track)
            if parameter == 'Volume':
                self.send(pyxelwidgets.message.Command(f'Fader Touch {strip + 1}', 1.0))
                self.send(pyxelwidgets.message.Command(f'Fader {strip + 1}', value))
                self.send(pyxelwidgets.message.Command(f'Fader Touch {strip + 1}', 0.0))
            elif parameter == 'Pan':
                while value:
                    step = max(-63, min(63, value))
                    self.send(pyxelwidgets.message.Command(f'V-Pot {strip + 1}', step))
                    value -= step
            else:
                # The buttons switch: pressed when the LED says otherwise
                button = f'{_TRACK_BUTTON_NAMES[parameter]} {strip + 1}'
                if (self.leds.get(button, 0.0) > 0) != (value > 0.5):
                    self._press(button)

    def _strip_track(self, strip: int) -> str | None:
        """The scanned track on ``strip`` in the channels view, checked by its name shown there."""
        if self._view != 'channels' or self._bank is None:
            return None
        shown = self.row(self._names_line)[strip]
        named = [index for index, name in enumerate(self._track_names) if name == shown]
        for index in named:
            if self._track_places[index] == (self._bank, strip):
                return self.tracks[index]
        # Shown again in Cubase's last bank (scanned in the bank before): known by its name if only one has it
        return self.tracks[named[0]] if len(named) == 1 else None

    def _track_feedback(self, strip: int, parameter: str, value: float) -> None:
        """A strip's fader, V-Pot ring (pan) or button LED, received as the track's TrackParameter."""
        track = self._strip_track(strip)
        if track is not None and (parameter != 'Pan' or self.channel_button == 'Pan'):
            message = pyxelwidgets.message.TrackParameter(track, parameter, value)
            self.emit(pyxelwidgets.events.MessageReceived(self, message))

    def _open(self, track: str, plugin: str) -> None:
        """Show the parameters of ``plugin`` on ``track`` (first page)."""
        if self._view == 'parameters' and self._focus is not None and self._focus[:2] == (track, plugin):
            return
        if plugin in self._plugin_strips(track):
            self._show_plugins(track)
        else:
            self.scan_plugins(track)
        if plugin in self._plugin_strips(track):
            strip, name = self._plugin_strips(track)[plugin]
            if self._cubase:
                self._to_slot(strip)
            if (self._slot() or (0, ''))[1] != name if self._cubase else self._plugin_names()[strip] != name:
                # Plug-ins were added, removed or moved on the track: read them again
                self._read_plugins(track)
        else:
            self._read_plugins(track)
        plugins = self._plugin_strips(track)
        if plugin not in plugins:
            raise LookupError(f'no plug-in {plugin!r} on {track!r} (plug-ins: {", ".join(plugins) or "none found"})')
        shown = self._lines()
        if self._cubase:
            # The slot's page, then its parameters on the next pages
            self._to_slot(plugins[plugin][0])
            self._paging = ('Channel Right', 'Channel Left')
            # Its pages will name the plug-in and the track (the slot's page names the track too),
            # known before the first page's rings come
            bottom = ''.join(self.lcd[56:])
            counter = _CUBASE_PAGE.search(bottom)
            self._headers[(track, plugin)] = (plugins[plugin][1][:16].strip(), bottom[16:counter.start()].strip() if counter else None)
            self._view, self._focus = 'parameters', (track, plugin, 0)
            opened = self._slot() == plugins[plugin] and self._tap('Channel Right', lambda: self._lines() != shown)
        else:
            opened = self._tap(f'V-Select {plugins[plugin][0] + 1}', lambda: self.row(0) != shown[0])
        if not opened:
            self._view = None
            raise LookupError(f'the DAW didn\'t show the parameters of {plugin!r}')
        page = 0
        if not self._cubase:
            # Logic opens a plug-in on the page shown last: known by its names, else back to the first
            pages = self._page_names.get((track, plugin), [])
            matches = [index for index, names in enumerate(pages) if names == self.row(0)]
            if len(matches) == 1:
                page = matches[0]
            else:
                self._first_page()
        self._view, self._focus = 'parameters', (track, plugin, page)

    def _first_page(self) -> None:
        """
        Back to a plug-in's first page of parameters: Logic opens one on the
        page shown last. Stops when the page doesn't change, Logic's page
        message says page 1, or its assignment display (P3: slot 3) changes.
        """
        assignment = list(self.assignment)
        for back in ([self._paging[1]] if self._paging else [self.previous_page, 'Left']):
            moved = False
            for _ in range(self.most_pages):
                shown = self._lines()
                if not self._tap(back, lambda: self._lines() != shown) or self.assignment != assignment:
                    break
                moved = True
                page = _PAGE_MESSAGE.search(''.join(self.lcd[:56]))
                if page and page[0].replace(' ', '').startswith('Page1/'):
                    break
            if moved or self.assignment != assignment:
                break

    def _slot(self):
        """Cubase's insert slot shown: (number, plug-in name or ''), None when it shows none."""
        match = _CUBASE_SLOT.match(''.join(self.lcd[:56]))
        if match is None:
            return None
        name = match[2].strip()
        return int(match[1]), '' if name == 'No Effect' else name

    def _slots(self) -> list:
        """Cubase's insert slots with a plug-in, as (number, name): V-Pot 1 goes through them from the first."""
        self._to_slot(1)
        found = []
        for _ in range(self.most_pages):
            shown = self._slot()
            if shown is None:
                break
            if shown[1]:
                found.append(shown)
            if not self._tap('V-Pot 1', lambda: self._slot() != shown, steps = 1):
                break
        return found

    def _to_slot(self, slot: int) -> None:
        """Show Cubase's insert ``slot`` (it stops at the first)."""
        for _ in range(3):
            shown = self._slot()
            if shown is not None and shown[0] == slot:
                return
            steps = -63 if shown is None or slot == 1 else slot - shown[0]
            if not self._tap('V-Pot 1', lambda: self._slot() != shown, steps = steps):
                return

    def _plugin_strips(self, track: str) -> dict:
        """Scanned plug-ins of ``track``: label → (strip, name as shown)."""
        return {label: (strip, name) for label, strip, name in self._plugins.get(track) or []}

    def _show_plugins(self, track: str) -> None:
        """Select ``track`` and show its plug-ins on the strips."""
        self._select(track)
        tracks = self.row(0)
        shown = (self.row(0), self.row(1))
        if not self._tap(self.plugin_button, lambda: (self.row(0), self.row(1)) != shown):
            self._view = None
            raise LookupError(f'the DAW showed no plug-ins after {self.plugin_button} (it may have no plug-in mode for '
                              'Mackie Control: REAPER\'s own support has none, its CSI or Klinke extensions do)')
        if sum(name == shown and bool(name) for name, shown in zip(self.row(0), tracks)) >= 2:
            # Still the tracks, with one insert slot of each (Logic's plug-in mixer): again
            # for the selected track's plug-ins
            shown = (self.row(0), self.row(1))
            self._tap(self.plugin_button, lambda: (self.row(0), self.row(1)) != shown)
        for _ in range(self.most_pages):
            # Cubase stays on a plug-in's page of parameters: back to its slot's page
            if self._slot() is not None or not self._cubase:
                break
            shown = self._lines()
            if not self._tap('Channel Left', lambda: self._lines() != shown):
                break
        self._view = 'plugins'

    def _plugin_names(self) -> list:
        """The plug-ins on the strips: on the bottom line if it has them (Logic labels the slots on top)."""
        def names(line):
            return ['' if name in _EMPTY_SLOTS else name for name in self.row(line)]
        bottom = names(1)
        return bottom if any(bottom) else names(0)

    def _next_page(self) -> bool:
        """
        Show the next page of parameters; False if there is none. The cursor
        buttons page in Logic, Channel Left/Right in Cubase (whose pages may
        have the same names: its page counter changes).
        """
        shown = self._lines()
        if self._paging is not None:
            return self._tap(self._paging[0], lambda: self._lines() != shown)
        for paging in ((self.next_page, self.previous_page), ('Right', 'Left')):
            if self._tap(paging[0], lambda: self._lines() != shown):
                self._paging = paging
                return True
        return False

    def _to_page(self, page: int) -> None:
        track, plugin, shown = self._focus
        if self._cubase and self._page() is not None:
            shown = self._page()
        forward, back = self._paging or (self.next_page, self.previous_page)
        # The page's V-Pot rings come with it
        while shown < page:
            shown += 1
            self._focus = (track, plugin, shown)
            self._tap(forward, read = False)
        while shown > page:
            shown -= 1
            self._focus = (track, plugin, shown)
            self._tap(back, read = False)

    def _header(self):
        """Cubase's plug-in, track and page on the bottom line of a page of parameters, else None."""
        bottom = ''.join(self.lcd[56:])
        match = _CUBASE_PAGE.search(bottom)
        if match is None or bottom.startswith('Inserts'):
            return None
        return bottom[:16].strip(), bottom[16:match.start()].strip()

    def _page(self) -> int | None:
        """The page of parameters Cubase shows (0 is its first), from its page counter."""
        match = _CUBASE_PAGE.search(''.join(self.lcd[56:]))
        return int(match[0][5:].split('/')[0]) - 2 if match else None

    def _still_shown(self) -> bool:
        """
        Whether the DAW still shows the plug-in opened last: Cubase shows
        another track's when that track gets selected (touching its fader does).
        """
        focus = self._focus
        if self._view != 'parameters' or focus is None:
            return False
        return not self._cubase or (self._header() == self._headers.get(focus[:2]) and self._page() == focus[2])

    def _shown_parameter(self, strip: int):
        """(track, plugin, parameter) on ``strip`` in the parameters view, else None."""
        focus = self._focus
        if not self._still_shown():
            return None
        track, plugin, page = focus
        for label, on_page, on_strip in self._parameters.get((track, plugin), ()):
            if on_page == page and on_strip == strip:
                return track, plugin, label
        return None

    def _turn(self, track: str, plugin: str, parameter: str, steps: int) -> None:
        with self._navigation:
            self._require()
            if (track, plugin) not in self._parameters:
                self.scan_parameters(track, plugin)
            found = {label: (page, strip) for label, page, strip in self._parameters[(track, plugin)]}
            if parameter not in found:
                raise LookupError(f'no parameter {parameter!r} (parameters: {", ".join(found) or "none found"})')
            page, strip = found[parameter]
            if self._cubase and self._view == 'parameters' and self._header() != self._headers.get(self._focus[:2]):
                # Not the plug-in opened last any more: there again
                self._view = None
            self._open(track, plugin)
            self._to_page(page)
            while steps:
                step = max(-63, min(63, steps))
                self.send(pyxelwidgets.message.Command(f'V-Pot {strip + 1}', step))
                steps -= step

# TrackParameter's buttons: the strip buttons' names → parameters, and back
_TRACK_BUTTONS = {'Mute': 'Mute', 'Solo': 'Solo', 'Rec': 'Record'}
_TRACK_BUTTON_NAMES = {parameter: button for button, parameter in _TRACK_BUTTONS.items()}

# Cubase's page counter ("Page:02/13") and insert slot page (" IFX 2    On         Pro-C 3")
_CUBASE_PAGE = re.compile(r'Page:\d+/\d+')
_CUBASE_SLOT = re.compile(r'\s*IFX\s*(\d+)\s+(?:On\s+|Off\s+)?(.*)')

# Logic's page message, which may fit the strips ("   Page 10/12")
_PAGE_MESSAGE = re.compile(r'Page\s+\d+\s*/\s*\d+')

# What DAWs show for an empty insert slot
_EMPTY_SLOTS = {'-', '--', '---'}

def _has_message(top: list) -> bool:
    """
    Whether the top line shows a passing message (Logic's "Page 2/12", "Pan/Surround
    parameter: Pan"): text running across a border between strips, which names
    (6 characters and a space) don't.
    """
    if _PAGE_MESSAGE.search(''.join(top)):
        return True
    return any(top[border - 1] != ' ' and top[border] != ' ' for border in range(7, 56, 7))

def _overlap(previous, page) -> int:
    """How many strips at the start of ``page`` (names, values) repeat the end of the ``previous`` one."""
    if previous is None:
        return 0
    for count in range(7, 0, -1):
        if all(previous[line][8 - count:] == page[line][:count] for line in (0, 1)) and any(page[0][:count]):
            return count
    return 0

# HUI: switches are (zone, port) pairs

_HUI_STRIP = ['Fader Touch', 'Select', 'Mute', 'Solo', 'Auto', 'V-Select', 'Insert', 'Rec']
_HUI_ZONES = [
    (0x08, ['Ctrl', 'Shift', 'Edit Mode', 'Undo', 'Alt', 'Option', 'Edit Tool', 'Save']),
    (0x09, ['Mix', 'Edit', 'Transport Window', 'Mem-Loc', 'Status', 'Alt Window']),
    (0x0A, ['Channel Left', 'Bank Left', 'Channel Right', 'Bank Right']),
    (0x0B, ['Output', 'Input', 'Pan', 'Send E', 'Send D', 'Send C', 'Send B', 'Send A']),
    (0x0C, ['Assign', 'Default', 'Suspend', 'Assign Shift', 'Assign Mute', 'Bypass', 'Rec Ready All']),
    (0x0D, ['Down', 'Left', 'Mode', 'Right', 'Up', 'Scrub', 'Shuttle']),
    (0x0E, ['Talkback', 'Rewind', 'Fast Forward', 'Stop', 'Play', 'Record']),
    (0x0F, ['Return to Zero', 'To End', 'Online', 'Loop', 'Quick Punch']),
    (0x10, ['Audition', 'Pre', 'In', 'Out', 'Post']),
    (0x16, ['Timecode LED', 'Feet LED', 'Beats LED', 'Rude Solo LED']),
    (0x17, ['Auto Plug-in', 'Auto Pan', 'Auto Fader', 'Auto Send Mute', 'Auto Send', 'Auto Mute']),
    (0x18, ['Trim', 'Latch', 'Read', 'Off', 'Write', 'Touch']),
    (0x19, ['Phase', 'Monitor', 'Auto Status', 'Suspend Status', 'Create', 'Group']),
    (0x1A, ['Paste', 'Cut', 'Capture', 'Delete', 'Copy', 'Separate']),
    (0x1B, [f'F{i + 1}' for i in range(8)]),
    (0x1C, ['Param Insert', 'Param Assign', 'Param Select 1', 'Param Select 2', 'Param Select 3', 'Param Select 4', 'Param Bypass', 'Param Compare']),
]
_HUI_SWITCHES = {f'{name} {strip + 1}': (strip, port) for strip in range(8) for port, name in enumerate(_HUI_STRIP)}
_HUI_SWITCHES.update({name: (zone, port) for zone, names in _HUI_ZONES for port, name in enumerate(names)})
_HUI_PORTS = {place: name for name, place in _HUI_SWITCHES.items()}
# The strips' V-Pots, the DSP section's 4 parameter knobs and its SCROLL knob, the jog wheel
_HUI_RELATIVE = {**{f'V-Pot {i + 1}': 0x40 + i for i in range(8)}, **{f'Param {i + 1}': 0x48 + i for i in range(4)},
                 'Scroll': 0x4C, 'Jog': 0x0D}

# Pro Tools' plug-in page header ("Page  3/13    Channel Strip=2    (Ins 1)") and inserts list ("Insert 1-4    Audio 1")
_HUI_PAGE = re.compile(r'Page\s+(\d+)/(\d+)\s+(.*?)\s*\(Ins\s*(\d|\?)\)\s*$')
_HUI_LIST = re.compile(r'Insert (1-4|5)\s+(.*?)\s*$')
# What Pro Tools shows for an empty insert slot
_HUI_EMPTY = 'No Insert'
# Switch parameter values received as on (1.0) or off (0.0)
_HUI_STATES = {'On': 1.0, 'In': 1.0, 'Off': 0.0, 'Out': 0.0}

class HUI(pyxelwidgets.devices.plugins.PluginParameters, _ControlSurface):
    """
    HUI (Pro Tools, REAPER, Logic): 8 channel strips, transport and edit
    switches, the jog wheel, the DSP section's knobs (``Param 1``-``4``,
    ``Scroll``), and feedback for LEDs, faders, V-Pot and parameter knob
    rings, meters, the timecode, the strips' 4 character names (``Name
    1``-``8``) and the main display (``Display``). Answers the host's pings.

    Pro Tools ignores fader moves on strips that aren't touched, so ``Fader n``
    touches its strip (``Fader Touch n``) first and lets go ``touch_hold``
    seconds after the last move: a gliding Fader (``slew``) sends a move every
    frame, so the touch lasts as long as the glide. Touches sent as commands
    are kept until released by a command.

    Pro Tools' plug-in parameters are reached by name like Mackie Control's
    (``scan_tracks()``, ``scan_plugins(track)``, ``scan_parameters(track,
    plugin)``, ``PluginParameter``): a strip's Insert switch shows its track's
    insert slots (1-4, SCROLL to 5-8, where only 5 and the selected one are
    named; 9 and 10 can't be reached), Param Select opens one, and each page
    of parameters has up to 4 switches (top line, pressed with Param Select
    1-4) and 4 knob parameters (bottom line). Scanning a
    plug-in's parameters takes about 2 seconds a page: Pro Tools shows the
    switches once its page header goes. A knob parameter turns by the value's
    steps; a switch is pressed once per change and comes back as 1.0 (On/In)
    or 0.0 (Off/Out).
    """

    model = 'HUI'
    vendor = 'Control surface'
    commands = {
        **{name: 'button' for name in _HUI_SWITCHES},
        **{f'Fader {i + 1}': 'fader' for i in range(8)},
        **{name: 'relative' for name in _HUI_RELATIVE},
        **{f'Meter {i + 1}': 'meter' for i in range(8)},
        'Timecode': 'display', 'Display': 'display',
        **{f'Name {i + 1}': 'display' for i in range(8)},
    }
    header = [0x00, 0x00, 0x66, 0x05, 0x00]
    messages = _ControlSurface.messages + ('PluginParameter',)

    #: Seconds after a strip's last fader move until its touch is let go (longer than a frame)
    touch_hold = 0.15
    #: Seconds without changes after which Pro Tools has answered a switch
    settle = 0.15
    #: Seconds to wait for Pro Tools to answer a switch at all
    timeout = 0.8
    #: Seconds a page header may cover the switch parameters (Pro Tools shows it for 2)
    header_time = 3.0
    #: Seconds to wait for a blinking insert slot's name (the selected slot blinks)
    blink_time = 1.5
    #: SCROLL ticks to the next page of parameters, and between insert slots 1-4 and 5-8
    page_ticks = 9
    list_ticks = 18
    #: Seconds Pro Tools may take to switch the inserts list between slots 1-4 and 5-8
    list_time = 2.0
    #: The most banks of tracks a scan goes through
    most_pages = 64

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._zone = None
        self._fader_high = [0] * 8
        self.display = [' '] * 80
        self.timecode = [' '] * 8
        #: The strips' names (4 characters)
        self.names = [''] * 8
        #: Switch LEDs Pro Tools lit: name → 1.0 (on), 0.0 (off)
        self.leds = {}
        # Switches are two messages: one thread at a time
        self._send_lock = threading.RLock()
        # Strip → when its touch is let go (None: touched by a command)
        self._touched = {}
        self._touch_changed = threading.Condition(self._send_lock)
        self._touch_thread = None
        # Display and name changes; the time the top line or the names last changed
        self._display = threading.Condition()
        self._changed_time = 0.0
        # Scans: track names as the inserts list shows them and where they are (bank, strip);
        # plug-ins as (label, slot, short name, name) by track; parameters as (label, page,
        # 'switch' or 'knob', column) by (track, plugin)
        self._track_names = []
        self._track_places = []
        # Parameters shown again on a later page (Pro Tools keeps knobs): (track, plugin) → {(page, kind, column): label}
        self._again = {}
        # What Pro Tools shows: 'list', 'parameters' or None (not known), the bank of tracks, and
        # (track, plugin, page) with its header's (name, slot) in the parameters view
        self._view = None
        self._bank = None
        self._focus = None
        self._opened = None
        self._pages = 1
        # The inserts list's header last shown: ('1-4' or '5', track name)
        self._last_list = None
        # Messages writing the top line (Pro Tools writes a header again even when it's the same text)
        self._top_writes = 0
        # Switch values last received: (track, plugin, label) → 1.0 or 0.0
        self._states = {}

    def send(self, message) -> None:
        if isinstance(message, pyxelwidgets.message.PluginParameter):
            # Knob steps (a switch is pressed once), summed while Pro Tools gets there
            steps = 0 if isinstance(message.value, str) else int(round(float(message.value)))
            if steps:
                self._turn_later(message, steps, operator.add)
            return
        if not isinstance(message, pyxelwidgets.message.Command):
            return super().send(message)
        if self._midi_output is None:
            return
        name, value = message.name, message.value
        with self._send_lock:
            if name in _HUI_SWITCHES:
                zone, port = _HUI_SWITCHES[name]
                if port == 0 and zone < 8:
                    # Fader Touch n: kept until a command lets go
                    if value > 0:
                        self._touched[zone] = None
                    else:
                        self._touched.pop(zone, None)
                self._switch(zone, port, value > 0)
            elif name.startswith('Fader ') and name[6:].isdigit() and 1 <= int(name[6:]) <= 8:
                strip = int(name[6:]) - 1
                self._touch(strip)
                position = int(round(min(1.0, max(0.0, float(value))) * 16383))
                self.send_control_change(strip, position >> 7)
                self.send_control_change(0x20 + strip, position & 0x7F)
            elif name in _HUI_RELATIVE:
                steps = _steps(value)
                if steps:
                    self.send_control_change(_HUI_RELATIVE[name], 0x40 | steps if steps > 0 else -steps)

    def _switch(self, zone: int, port: int, on: bool) -> None:
        self.send_control_change(0x0F, zone)
        self.send_control_change(0x2F, (0x40 if on else 0x00) | port)

    def _touch(self, strip: int) -> None:
        """Touch the strip before a fader move, or keep it touched longer."""
        if strip in self._touched and self._touched[strip] is None:
            return
        if strip not in self._touched:
            self._switch(strip, 0, True)
        self._touched[strip] = time.monotonic() + self.touch_hold
        if self._touch_thread is None:
            self._touch_thread = threading.Thread(target = self._release_touches, name = 'HUITouch', daemon = True)
            self._touch_thread.start()
        self._touch_changed.notify()

    def on_disconnect(self) -> None:
        with self._send_lock:
            for strip in list(self._touched):
                self._switch(strip, 0, False)
            self._touched.clear()
        super().on_disconnect()

    def _release_touches(self) -> None:
        with self._send_lock:
            while True:
                now = time.monotonic()
                for strip, until in list(self._touched.items()):
                    if until is not None and until <= now:
                        del self._touched[strip]
                        if self._midi_output is not None:
                            self._switch(strip, 0, False)
                waits = [until - now for until in self._touched.values() if until is not None and until > now]
                self._touch_changed.wait(min(waits) if waits else None)

    def decode(self, midi: list) -> None:
        if not midi:
            return
        status = midi[0] & 0xF0
        if midi[0] == 0xF0:
            self._sysex(midi[1:-1] if midi[-1] == 0xF7 else midi[1:])
        elif status == 0x90 and midi[1:] == [0x00, 0x00]:
            # Ping: answer to stay online
            with self._send_lock:
                self.send_note_on(0x00, 0x7F)
        elif status == 0xB0 and len(midi) == 3:
            if not self._control(midi[1], midi[2]):
                super().decode(midi)
        elif status == 0xA0 and len(midi) == 3:
            strip, side, level = midi[1], midi[2] >> 4, midi[2] & 0x0F
            if strip < 8 and side == 0 and level <= 0x0C:
                self._received(f'Meter {strip + 1}', level / 12)
        elif status != 0x90:
            # Not part of HUI: received as plain MIDI
            super().decode(midi)

    def _control(self, number: int, value: int) -> bool:
        """Decode a HUI control change; False when it isn't one."""
        if number == 0x0C:
            self._zone = value
        elif number == 0x2C and self._zone is not None:
            name = _HUI_PORTS.get((self._zone, value & 0x0F))
            if name is not None:
                with self._display:
                    self.leds[name] = 1.0 if value & 0x40 else 0.0
                    if name == 'Param Insert' and not value & 0x40 and self._view == 'parameters':
                        # Back in the inserts list (its header may not be drawn again)
                        self._view = 'list'
                    self._display.notify_all()
                self._received(name, self.leds[name])
        elif number < 0x08:
            self._fader_high[number] = value
        elif 0x20 <= number < 0x28:
            strip = number - 0x20
            self._received(f'Fader {strip + 1}', ((self._fader_high[strip] << 7) | value) / 16383)
        elif 0x10 <= number < 0x18:
            position = value & 0x0F
            self._received(f'V-Pot {number - 0x10 + 1}', (position - 1) / 10 if position else 0.0)
        elif 0x18 <= number < 0x1C:
            # A parameter knob's ring: 1-11, the style in bits 4-5
            position = value & 0x0F
            column = number - 0x18
            self._received(f'Param {column + 1}', (position - 1) / 10 if position else 0.0)
            shown = self._shown('knob', column)
            if shown is not None:
                message = pyxelwidgets.message.PluginParameter(*shown, (position - 1) / 10 if position else 0.0)
                self.emit(pyxelwidgets.events.MessageReceived(self, message))
        else:
            return False
        return True

    def _sysex(self, data: list) -> None:
        if data[:5] != self.header or len(data) < 6:
            return
        command, body = data[5], data[6:]
        if command == 0x10 and len(body) >= 5 and body[0] < 8:
            name = ''.join(chr(c) if 0x20 <= c < 0x7F else ' ' for c in body[1:5]).strip()
            with self._display:
                if self.names[body[0]] != name:
                    self._changed_time = time.monotonic()
                self.names[body[0]] = name
                self._display.notify_all()
            self._received(f'Name {body[0] + 1}', name)
        elif command == 0x11:
            # Timecode digits, right to left; 0x10 adds a dot
            for i, code in enumerate(body[:8]):
                self.timecode[7 - i] = str(code & 0x0F) + ('.' if code & 0x10 else '')
            self._received('Timecode', ''.join(self.timecode).strip())
        elif command == 0x12:
            # 10 characters per zone: zones 0-3 are the top line, 4-7 the bottom
            states = []
            with self._display:
                top = self.display[:40]
                for start in range(0, len(body) - 10, 11):
                    zone = body[start]
                    if zone < 4:
                        self._top_writes += 1
                    if zone < 8:
                        for i, code in enumerate(body[start + 1:start + 11]):
                            self.display[zone * 10 + i] = chr(code) if 0x20 <= code < 0x7F else ' '
                if self.display[:40] != top:
                    self._changed_time = time.monotonic()
                    states = self._top_changed()
                self._display.notify_all()
            text = ''.join(self.display)
            self._received('Display', f'{text[:40].rstrip()}\n{text[40:].rstrip()}')
            for message in states:
                self.emit(pyxelwidgets.events.MessageReceived(self, message))

    # Plug-in parameters: Pro Tools' insert and parameter views, driven by switches and read from the display

    def _top(self) -> str:
        return ''.join(self.display[:40])

    def _zone_text(self, zone: int) -> str:
        return ''.join(self.display[zone * 10:zone * 10 + 10])

    def _header(self):
        """(page, pages, plug-in name, slot or None past 5) from the page header on the top line, else None."""
        match = _HUI_PAGE.match(self._top())
        if match is None:
            return None
        # Slots past 5 show as ?
        return int(match[1]), int(match[2]), match[3], int(match[4]) if match[4].isdigit() else None

    def _list(self):
        """
        ('1-4' or '5', track name) while the inserts list shows, else None.
        Pro Tools may leave a plug-in's page header on the top line when the
        list comes back (it only redraws what it thinks changed, and the header
        passes): then the list's last header counts, while Param Insert is off.
        """
        match = _HUI_LIST.match(self._top())
        if match:
            self._last_list = (match[1], match[2])
            return self._last_list
        if self._view == 'list' and not self.leds.get('Param Insert'):
            return self._last_list
        return None

    def _top_changed(self) -> list:
        """
        What the top line says about the view (called with the display lock
        held); returns the switches' states shown, as PluginParameters.
        """
        if self._list() is not None:
            self._view = 'list'
            return []
        header = self._header()
        if header is not None:
            if self._view == 'parameters' and self._opened is not None and header[2:] != self._opened:
                # Another plug-in (Pro Tools' own choice): not the one opened
                self._view = None
            return []
        if self._view != 'parameters' or self._top().startswith('Page'):
            return []
        states = []
        for column in range(4):
            text = self._zone_text(column)
            shown = self._shown('switch', column)
            state = _HUI_STATES.get(text[5:].strip())
            if shown is None or state is None or not _named(shown[2], text[:4].strip()):
                continue
            if self._states.get(shown) != state:
                self._states[shown] = state
                states.append(pyxelwidgets.message.PluginParameter(*shown, state))
        return states

    def _shown(self, kind: str, column: int):
        """(track, plugin, parameter) on the knob or switch ``column`` of the page shown, else None."""
        focus = self._focus
        if self._view != 'parameters' or focus is None:
            return None
        track, plugin, page = focus
        for label, on_page, on_kind, on_column in self._parameters.get((track, plugin), ()):
            if (on_page, on_kind, on_column) == (page, kind, column):
                return track, plugin, label
        label = self._again.get((track, plugin), {}).get((page, kind, column))
        return (track, plugin, label) if label is not None else None

    def _require(self) -> None:
        if self._midi_output is None or self._midi_input is None:
            raise ConnectionError('HUI is not connected to the DAW')

    def _wait(self, ready, timeout: float | None = None) -> bool:
        """Wait until ``ready()``, checked as the display changes; False after ``timeout``."""
        end = time.monotonic() + (self.timeout if timeout is None else timeout)
        with self._display:
            while not ready():
                left = end - time.monotonic()
                if left <= 0:
                    return False
                self._display.wait(left)
        return True

    def _settled(self) -> None:
        """Wait until the top line and the names have been unchanged for ``settle`` (Pro Tools writes a zone at a time)."""
        with self._display:
            while True:
                quiet = self._changed_time + self.settle - time.monotonic()
                if quiet <= 0:
                    return
                self._display.wait(quiet)

    def _press(self, name: str) -> None:
        self.send(pyxelwidgets.message.Command(name, 1.0))
        self.send(pyxelwidgets.message.Command(name, 0.0))

    def _scroll(self, ticks: int) -> None:
        while ticks:
            step = max(-63, min(63, ticks))
            self.send(pyxelwidgets.message.Command('Scroll', step))
            ticks -= step

    def _to_list(self) -> None:
        """Show the inserts list (leaving a plug-in's parameters)."""
        if self._view != 'parameters' and self._list() is not None:
            return
        # Param Insert lights a moment after a plug-in's header shows
        if self.leds.get('Param Insert') or self._view == 'parameters' or self._top().startswith('Page'):
            self._back_to_list()

    def _back_to_list(self) -> None:
        """Press Param Insert to leave a plug-in's parameters for the inserts list."""
        self._press('Param Insert')
        self._wait(lambda: self.leds.get('Param Insert') == 0.0)
        with self._display:
            self._view = 'list'
        self._settled()

    def _list_track(self, strip: int) -> str | None:
        """Show the inserts list of the track on ``strip``; its name, None if Pro Tools showed none."""
        for attempt in range(2):
            before = self._list()
            self._press(f'Insert {strip + 1}')
            # No change when that track's list already shows
            self._wait(lambda: self._list() is not None and self._list() != before)
            self._settled()
            if self._list() is not None or attempt:
                break
            # A plug-in's parameters show (Insert does nothing there): back to the list first
            self._back_to_list()
        shown = self._list()
        self._view = 'list' if shown is not None else None
        return shown[1] if shown is not None else None

    def _bank_tap(self, name: str) -> bool:
        """Press Bank Left or Right; True if the strips' names changed."""
        before = list(self.names)
        self._press(name)
        changed = self._wait(lambda: self.names != before)
        self._settled()
        return changed

    def _first_bank(self) -> None:
        for _ in range(self.most_pages):
            if not self._bank_tap('Bank Left'):
                break
        self._bank = 0

    def _to_bank(self, bank: int) -> None:
        if self._bank is None:
            self._first_bank()
        while self._bank < bank:
            self._bank_tap('Bank Right')
            self._bank += 1
        while self._bank > bank:
            self._bank_tap('Bank Left')
            self._bank -= 1

    def scan_tracks(self) -> list:
        """
        Pro Tools' track names: banks through the strips from the first, showing
        each track's inserts list for its full name (repeated names get " (2)").
        Blocks for a while; don't call it from a MIDI or widget event handler.
        """
        with self._navigation:
            self._require()
            self._to_list()
            self._first_bank()
            banks = []
            for bank in range(self.most_pages):
                banks.append([(self._list_track(strip) or '') if self.names[strip] else '' for strip in range(8)])
                if not any(self.names) or not self._bank_tap('Bank Right'):
                    break
                self._bank = bank + 1
            self._bank = len(banks) - 1
            names, places = [], []
            for bank, shown in enumerate(banks):
                # A last bank may end at the last track, showing some of the bank before again
                skip = 0
                if bank and bank == len(banks) - 1:
                    previous = banks[bank - 1]
                    skip = next((count for count in range(7, 0, -1)
                                 if previous[8 - count:] == shown[:count] and all(shown[:count])), 0)
                for strip in range(skip, 8):
                    if shown[strip]:
                        names.append(shown[strip])
                        places.append((bank, strip))
            self._track_names, self._track_places = names, places
            self.tracks = pyxelwidgets.devices.plugins.labels(names)
            # Scans of tracks still there stay (their plug-ins are checked by name when used)
            self._plugins = {track: plugins for track, plugins in self._plugins.items() if track in self.tracks}
            self._parameters = {key: found for key, found in self._parameters.items() if key[0] in self.tracks}
            return list(self.tracks)

    def _track_index(self, track: str) -> int:
        if track not in self.tracks:
            self.scan_tracks()
        if track not in self.tracks:
            raise LookupError(f'no track {track!r} (tracks: {", ".join(self.tracks) or "none found"})')
        return self.tracks.index(track)

    def _show_track(self, track: str) -> None:
        """Show the inserts list of ``track`` (checked by name)."""
        self._require()
        index = self._track_index(track)
        for attempt in range(2):
            bank, strip = self._track_places[index]
            self._to_bank(bank)
            self._to_list()
            if self._list_track(strip) == self._track_names[index]:
                return
            if not attempt:
                # The tracks changed in Pro Tools: scan them again
                self.scan_tracks()
                index = self._track_index(track)
        raise LookupError(f'Pro Tools didn\'t show the inserts of {track!r}')

    def _to_part(self, part: str) -> bool:
        """Show insert slots ``part`` ('1-4' or '5') in the inserts list."""
        shown = self._list()
        if shown is None:
            return False
        for _ in range(2):
            if shown[0] == part:
                return True
            # More ticks than needed are harmless: the list doesn't go past 5-8 or before 1-4
            self._scroll(self.list_ticks if part == '5' else -self.list_ticks)
            if self._wait(lambda: (self._list() or ('',))[0] == part, self.list_time):
                self._settled()
            shown = self._list() or ('',)
        return shown[0] == part

    def _read_zones(self, zones: list) -> list:
        """The texts of display ``zones``, waiting out the selected slot's blinking."""
        seen = {}
        def ready():
            for zone in zones:
                text = self._zone_text(zone).strip()
                if text:
                    seen[zone] = text
            return len(seen) == len(zones)
        self._wait(ready, self.blink_time)
        return [seen.get(zone, '') for zone in zones]

    def _slot_names(self) -> list:
        """
        The inserts list's slots that may have a plug-in, as (slot, name as
        shown); slots 6-8 have None: Pro Tools names only the selected one.
        """
        found = []
        if self._to_part('1-4'):
            found += [(slot + 1, name) for slot, name in enumerate(self._read_zones([4, 5, 6, 7]))]
        if self._to_part('5'):
            found += [(5, self._read_zones([4])[0])] + [(slot, None) for slot in (6, 7, 8)]
            self._to_part('1-4')
        return [(slot, name) for slot, name in found if name is None or (name and name != _HUI_EMPTY)]

    @staticmethod
    def _slot_zone(slot: int) -> int:
        """The display zone of insert ``slot`` in its part of the inserts list."""
        return 3 + slot if slot <= 4 else slot - 1

    def _open_slot(self, slot: int):
        """
        Open insert ``slot`` (1-8) from the inserts list; its page header, None
        if Pro Tools showed none (an empty slot). The header shows slots 6-8 as ?.
        """
        if not self._to_part('5' if slot >= 5 else '1-4'):
            return None
        shown = slot if slot <= 5 else None
        writes = self._top_writes
        def opened():
            # A header written since the press: one left on the top line from before (slots
            # past 5 all show as ?) isn't an answer
            return self._top_writes != writes and (self._header() or (0, 0, '', 0))[3] == shown
        def empty():
            return self._zone_text(self._slot_zone(slot)).strip() == _HUI_EMPTY
        for _ in range(3):
            # Pro Tools may drop a press that comes right after the list changed: again,
            # only while nothing opened (in the parameters, Param Select presses a switch);
            # an empty slot gets selected (its "No Insert" blinks)
            self._press(f'Param Select {slot if slot <= 4 else slot - 4}')
            if self._wait(lambda: opened() or bool(self.leds.get('Param Insert')) or empty()):
                break
        if not self._wait(opened, self.settle if empty() else None):
            return None
        # Pro Tools lights Param Insert and shows the knobs a moment after the header: its
        # switches would still be the list's until then
        self._view = 'parameters'
        self._wait(lambda: self.leds.get('Param Insert') == 1.0)
        self._settled()
        header = self._header()
        if header is not None:
            self._view, self._opened, self._pages = 'parameters', header[2:], header[1]
        return header

    def scan_plugins(self, track: str) -> list:
        """The plug-ins on ``track`` (a name from ``scan_tracks``): insert slots 1-8, opened for their full names."""
        with self._navigation:
            self._show_track(track)
            return self._read_plugins(track)

    def _read_plugins(self, track: str) -> list:
        found = []
        for slot, short in self._slot_names():
            header = self._open_slot(slot)
            if header is not None:
                found.append((slot, short, header[2]))
                self._to_list()
            elif short:
                found.append((slot, short, short))
        labels = pyxelwidgets.devices.plugins.labels([name for _, _, name in found])
        self._plugins[track] = [(label, *entry) for label, entry in zip(labels, found)]
        return labels

    def _open(self, track: str, plugin: str) -> None:
        """
        Show the parameters of ``plugin`` on ``track`` (on the page Pro Tools
        opens it on); its plug-ins are read again if it isn't where it was.
        """
        if self._view == 'parameters' and self._focus is not None and self._focus[:2] == (track, plugin):
            return
        self._show_track(track)
        for attempt in range(2):
            slots = {label: (slot, short, name) for label, slot, short, name in self._plugins.get(track) or []}
            fresh = attempt or plugin not in slots
            if not fresh and slots[plugin][1]:
                # Slots 1-5 show their names: plug-ins added, removed or moved show there
                slot, short, _ = slots[plugin]
                self._to_part('5' if slot >= 5 else '1-4')
                fresh = self._read_zones([self._slot_zone(slot)])[0] != short
            if fresh:
                self._read_plugins(track)
                slots = {label: (slot, short, name) for label, slot, short, name in self._plugins.get(track) or []}
            if plugin not in slots:
                raise LookupError(f'no plug-in {plugin!r} on {track!r} (plug-ins: {", ".join(slots) or "none found"})')
            slot, _, name = slots[plugin]
            self._to_list()
            header = self._open_slot(slot)
            if header is not None and header[2] == name:
                self._focus = (track, plugin, header[0])
                return
            self._to_list()
            if fresh:
                break
        self._view = None
        raise LookupError(f'Pro Tools didn\'t show the parameters of {plugin!r}')

    def _to_page(self, page: int) -> None:
        """Scroll to ``page`` (1 is the first) of the plug-in shown."""
        track, plugin, shown = self._focus
        while shown != page:
            step = 1 if page > shown else -1
            # The page's knob rings come with it
            self._focus = (track, plugin, shown + step)
            self._scroll(step * self.page_ticks)
            if not self._wait(lambda: (self._header() or (0,))[0] == shown + step):
                self._focus = (track, plugin, shown)
                raise LookupError(f'Pro Tools didn\'t show page {shown + step} of {plugin!r}')
            shown += step

    def _read_page(self) -> tuple:
        """The page's switches and knob parameters as names (columns without one are '')."""
        self._wait(lambda: not self._top().startswith('Page'), self.header_time)
        self._settled()
        def names(zones):
            return [self._zone_text(zone)[:4].strip() for zone in zones]
        return names(range(4)), names(range(4, 8))

    def scan_parameters(self, track: str, plugin: str) -> list:
        """
        The parameters of ``plugin`` on ``track``: opens it and scrolls through
        its pages, switches first on each. About 2 seconds a page.
        """
        with self._navigation:
            self._require()
            self._open(track, plugin)
            self._to_page(1)
            found, again, previous = [], {}, {}
            for page in range(1, self._pages + 1):
                if page > 1:
                    self._to_page(page)
                switches, knobs = self._read_page()
                shown = {}
                for kind, names in (('switch', switches), ('knob', knobs)):
                    for column, name in enumerate(names):
                        if not name:
                            continue
                        shown[(kind, column)] = name
                        if previous.get((kind, column)) == name:
                            # Still there from the page before (Pro Tools keeps knobs a page doesn't use)
                            again[(page, kind, column)] = name
                        else:
                            found.append((name, page, kind, column))
                previous = shown
            labels = pyxelwidgets.devices.plugins.labels([name for name, _, _, _ in found])
            entries = [(label, page, kind, column) for label, (_, page, kind, column) in zip(labels, found)]
            self._parameters[(track, plugin)] = entries
            # A parameter shown again is the one at the same place on the page before
            places = {(page, kind, column): label for label, page, kind, column in entries}
            for page, kind, column in sorted(again):
                places[(page, kind, column)] = places.get((page - 1, kind, column))
            self._again[(track, plugin)] = {place: places[place] for place in again if places[place] is not None}
            self._to_page(1)
            return labels

    def _turn(self, track: str, plugin: str, parameter: str, steps: int) -> None:
        with self._navigation:
            self._require()
            if (track, plugin) not in self._parameters:
                self.scan_parameters(track, plugin)
            found = {label: (page, kind, column) for label, page, kind, column in self._parameters[(track, plugin)]}
            if parameter not in found:
                raise LookupError(f'no parameter {parameter!r} (parameters: {", ".join(found) or "none found"})')
            page, kind, column = found[parameter]
            self._open(track, plugin)
            self._to_page(page)
            if kind == 'switch':
                self._press(f'Param Select {column + 1}')
                return
            while steps:
                step = max(-63, min(63, steps))
                self.send(pyxelwidgets.message.Command(f'Param {column + 1}', step))
                steps -= step

def _named(label: str, name: str) -> bool:
    """Whether a parameter's ``label`` is the ``name`` shown (labels of repeated names end in " (2)")."""
    return label == name or (label.startswith(name + ' (') and label.endswith(')'))
