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
are handled); REAPER's own Mackie Control support has no plug-in mode.
"""

import enum
import re
import threading
import time

import pyxelwidgets.devices.midi_port
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

class MackieControl(_ControlSurface):
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

    messages = _ControlSurface.messages + ('PluginParameter',)

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
        #: What went wrong reaching a plug-in parameter last, if anything
        self.warning = None
        # Scans: track names (as the display shows them) and labels (made unique), plug-ins as
        # (label, strip) by track, parameters as (label, page, strip) by (track, plugin)
        self._track_names = []
        self.tracks = []
        self._plugins = {}
        self._parameters = {}
        # What the DAW shows: 'channels', 'plugins', 'parameters' or None (not known), the bank
        # of tracks in the channels view, and (track, plugin, page) in the parameters view
        self._view = None
        self._bank = None
        self._focus = None
        # The buttons that page parameters (next, previous), once found
        self._paging = None
        self._display = threading.Condition()
        self._display_changes = 0
        self._display_time = 0.0
        self._navigation = threading.RLock()
        # Parameter turns waiting for the DAW to get there: (track, plugin, parameter) → steps
        self._turns = {}
        self._turns_lock = threading.Lock()
        self._turned = threading.Event()
        self._worker = None
        self._closing = False

    @property
    def header(self) -> list:
        return [0x00, 0x00, 0x66, self.mode.value]

    def send(self, message) -> None:
        if isinstance(message, pyxelwidgets.message.PluginParameter):
            return self._turn_later(message)
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
                self._received(name, 1.0 if velocity else 0.0, velocity == 1)
        elif status == 0xE0 and len(midi) == 3:
            channel = midi[0] & 0x0F
            name = 'Master Fader' if channel == 8 else f'Fader {channel + 1}'
            self._received(name, (midi[1] | (midi[2] << 7)) / 16383)
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
            parameter = self._shown_parameter(strip)
            if parameter is not None:
                message = pyxelwidgets.message.PluginParameter(*parameter, (position - 1) / 10 if position else 0.0)
                self.emit(pyxelwidgets.events.MessageReceived(self, message))
        elif 0x40 <= number < 0x4A:
            # Timecode digits, right to left
            self.timecode[9 - (number - 0x40)] = self._character(value)
            self._received('Timecode', ''.join(self.timecode).strip())
        elif number in (0x4A, 0x4B):
            self.assignment[0x4B - number] = self._character(value)
            self._received('Assignment', ''.join(self.assignment).strip())

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
            if self.lcd[:56] != before[:56] and not _has_message(self.lcd[:56]):
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

    def close(self) -> None:
        self._closing = True
        self._turned.set()
        super().close()

    def row(self, line: int = 0) -> list:
        """
        The 8 strips' texts on the display's top (0) or bottom (1) line; the top
        line without a passing message over it (Logic's "Page 2/12" for 2 seconds).
        """
        text = ''.join(self._real_top if line == 0 else self.lcd[56:])
        return [text[strip * 7:strip * 7 + 7].strip() for strip in range(8)]

    def scanned(self) -> dict:
        """What the scans found: ``tracks``, ``plugins`` by track and ``parameters`` by track and plug-in."""
        with self._navigation:
            return {'tracks': list(self.tracks),
                    'plugins': {track: [label for label, _ in plugins] for track, plugins in self._plugins.items()},
                    'parameters': {f'{track}/{plugin}': [label for label, _, _ in parameters]
                                   for (track, plugin), parameters in self._parameters.items()}}

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
            names = []
            for bank in range(self.most_pages):
                shown = self.row(0)
                names += shown
                if not any(shown) or not self._tap('Bank Right', lambda: self.row(0) != shown):
                    break
                self._bank = bank + 1
            while names and not names[-1]:
                names.pop()
            self._track_names = [name or f'Track {index + 1}' for index, name in enumerate(names)]
            self.tracks = _labels(self._track_names)
            self._plugins, self._parameters = {}, {}
            return list(self.tracks)

    def scan_plugins(self, track: str) -> list:
        """The plug-ins on ``track`` (a name from ``scan_tracks``), as the DAW's plug-in mode shows them."""
        with self._navigation:
            self._show_plugins(track)
            names = self._plugin_names()
            strips = [strip for strip, name in enumerate(names) if name]
            self._plugins[track] = list(zip(_labels([names[strip] for strip in strips]), strips))
            return [label for label, _ in self._plugins[track]]

    def scan_parameters(self, track: str, plugin: str) -> list:
        """The parameters of ``plugin`` on ``track``: opens it and pages through its parameters, 8 at a time."""
        with self._navigation:
            self._open(track, plugin)
            found, previous = [], None
            for page in range(self.most_pages):
                shown, values = self.row(0), self.row(1)
                last = not self._next_page(shown)
                # Logic's last page ends at the last parameter, showing some of the page before again
                skip = _overlap(previous, (shown, values)) if last else 0
                found += [(name, page, strip) for strip, name in enumerate(shown) if name and strip >= skip]
                if last:
                    break
                previous = (shown, values)
                self._focus = (track, plugin, page + 1)
            labels = _labels([name for name, _, _ in found])
            self._parameters[(track, plugin)] = [(label, page, strip) for label, (_, page, strip) in zip(labels, found)]
            self._to_page(0)
            return labels

    def _require(self) -> None:
        if self._midi_output is None or self._midi_input is None:
            raise ConnectionError('Mackie Control is not connected to the DAW')

    def _tap(self, name: str, changed = None, *, read: bool = True) -> bool:
        """
        Press and release ``name``; True once the DAW changed its display and
        settled (and ``changed()`` says it changed what matters), False if it
        didn't answer. To ``read`` the result, a passing message hiding it
        (Logic's "Page 2/12") is waited out.
        """
        with self._display:
            before = self._display_changes
            real_before = self._real_changes
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
            if read and self._real_changes == real_before and _has_message(self.lcd[:56]):
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
            shown = self.row(0)
            self._tap(self.channel_button, lambda: self.row(0) != shown)
            if self.assignment[-1].endswith('.'):
                # Logic: a dot is its one-track view, and the button switches between them
                shown = self.row(0)
                self._tap(self.channel_button, lambda: self.row(0) != shown)
            self._view, self._focus = 'channels', None

    def _first_bank(self) -> None:
        for _ in range(self.most_pages):
            shown = self.row(0)
            if not self._tap('Bank Left', lambda: self.row(0) != shown):
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
        self._require()
        index = self._track_index(track)
        self._to_channels()
        for attempt in range(2):
            bank, strip = divmod(index, 8)
            if self._bank is None:
                self._first_bank()
            while self._bank < bank:
                self._tap('Bank Right')
                self._bank += 1
            while self._bank > bank:
                self._tap('Bank Left')
                self._bank -= 1
            if self.row(0)[strip] == self._track_names[index] or attempt:
                break
            # The tracks changed in the DAW: scan them again
            self.scan_tracks()
            index = self._track_index(track)
        self._press(f'Select {strip + 1}')

    def _open(self, track: str, plugin: str) -> None:
        """Show the parameters of ``plugin`` on ``track`` (first page)."""
        if self._view == 'parameters' and self._focus is not None and self._focus[:2] == (track, plugin):
            return
        plugins = dict(self._plugins.get(track) or [])
        if plugin not in plugins:
            self.scan_plugins(track)
            plugins = dict(self._plugins[track])
            if plugin not in plugins:
                raise LookupError(f'no plug-in {plugin!r} on {track!r} (plug-ins: {", ".join(plugins) or "none found"})')
        else:
            self._show_plugins(track)
        shown = self.row(0)
        if not self._tap(f'V-Select {plugins[plugin] + 1}', lambda: self.row(0) != shown):
            self._view = None
            raise LookupError(f'the DAW didn\'t show the parameters of {plugin!r} when its V-Pot was pressed')
        self._view, self._focus = 'parameters', (track, plugin, 0)

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
        self._view = 'plugins'

    def _plugin_names(self) -> list:
        """The plug-ins on the strips: on the bottom line if it has them (Logic labels the slots on top)."""
        def names(line):
            return ['' if name in _EMPTY_SLOTS else name for name in self.row(line)]
        bottom = names(1)
        return bottom if any(bottom) else names(0)

    def _next_page(self, shown: list) -> bool:
        """Show the next page of parameters; False if there is none. The cursor buttons page in Logic."""
        if self._paging is not None:
            return self._tap(self._paging[0], lambda: self.row(0) != shown)
        for paging in ((self.next_page, self.previous_page), ('Right', 'Left')):
            if self._tap(paging[0], lambda: self.row(0) != shown):
                self._paging = paging
                return True
        return False

    def _to_page(self, page: int) -> None:
        track, plugin, shown = self._focus
        forward, back = self._paging or (self.next_page, self.previous_page)
        while shown < page:
            self._tap(forward, read = False)
            shown += 1
        while shown > page:
            self._tap(back, read = False)
            shown -= 1
        self._focus = (track, plugin, page)

    def _shown_parameter(self, strip: int):
        """(track, plugin, parameter) on ``strip`` in the parameters view, else None."""
        focus = self._focus
        if self._view != 'parameters' or focus is None:
            return None
        track, plugin, page = focus
        for label, on_page, on_strip in self._parameters.get((track, plugin), ()):
            if on_page == page and on_strip == strip:
                return track, plugin, label
        return None

    def _turn_later(self, message) -> None:
        """Queue a parameter turn: the DAW is driven there on a thread of its own (it takes a while)."""
        if isinstance(message.value, str) or self._closing:
            return
        steps = int(round(float(message.value)))
        if not steps:
            return
        key = (message.track, message.plugin, message.parameter)
        with self._turns_lock:
            self._turns[key] = self._turns.get(key, 0) + steps
            if self._worker is None:
                self._worker = threading.Thread(target = self._work, name = 'MackiePlugins', daemon = True)
                self._worker.start()
        self._turned.set()

    def _work(self) -> None:
        while True:
            self._turned.wait()
            if self._closing:
                return
            with self._turns_lock:
                turns, self._turns = self._turns, {}
                self._turned.clear()
            for (track, plugin, parameter), steps in turns.items():
                try:
                    self._turn(track, plugin, parameter, steps)
                except Exception as error:
                    self.warning = f'{track} / {plugin} / {parameter}: {error}'

    def _turn(self, track: str, plugin: str, parameter: str, steps: int) -> None:
        with self._navigation:
            self._require()
            if (track, plugin) not in self._parameters:
                self.scan_parameters(track, plugin)
            found = {label: (page, strip) for label, page, strip in self._parameters[(track, plugin)]}
            if parameter not in found:
                raise LookupError(f'no parameter {parameter!r} (parameters: {", ".join(found) or "none found"})')
            page, strip = found[parameter]
            self._open(track, plugin)
            self._to_page(page)
            while steps:
                step = max(-63, min(63, steps))
                self.send(pyxelwidgets.message.Command(f'V-Pot {strip + 1}', step))
                steps -= step
            self.warning = None

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

def _labels(names: list) -> list:
    """Names made unique: a repeated one gets " (2)", " (3)"..."""
    counts, labels = {}, []
    for name in names:
        counts[name] = counts.get(name, 0) + 1
        labels.append(name if counts[name] == 1 else f'{name} ({counts[name]})')
    return labels

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
_HUI_RELATIVE = {**{f'V-Pot {i + 1}': 0x40 + i for i in range(8)}, 'Jog': 0x0D}

class HUI(_ControlSurface):
    """
    HUI (Pro Tools, REAPER, Logic): 8 channel strips, transport and edit
    switches, the jog wheel, and feedback for LEDs, faders, V-Pot rings,
    meters, the timecode, the strips' 4 character names (``Name 1``-``8``)
    and the main display (``Display``). Answers the host's pings.
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._zone = None
        self._fader_high = [0] * 8
        self.display = [' '] * 80
        self.timecode = [' '] * 8

    def send(self, message) -> None:
        if not isinstance(message, pyxelwidgets.message.Command):
            return super().send(message)
        if self._midi_output is None:
            return
        name, value = message.name, message.value
        if name in _HUI_SWITCHES:
            zone, port = _HUI_SWITCHES[name]
            self.send_control_change(0x0F, zone)
            self.send_control_change(0x2F, (0x40 if value > 0 else 0x00) | port)
        elif name.startswith('Fader ') and name[6:].isdigit() and 1 <= int(name[6:]) <= 8:
            strip = int(name[6:]) - 1
            position = int(round(min(1.0, max(0.0, float(value))) * 16383))
            self.send_control_change(strip, position >> 7)
            self.send_control_change(0x20 + strip, position & 0x7F)
        elif name in _HUI_RELATIVE:
            steps = _steps(value)
            if steps:
                self.send_control_change(_HUI_RELATIVE[name], 0x40 | steps if steps > 0 else -steps)

    def decode(self, midi: list) -> None:
        if not midi:
            return
        status = midi[0] & 0xF0
        if midi[0] == 0xF0:
            self._sysex(midi[1:-1] if midi[-1] == 0xF7 else midi[1:])
        elif status == 0x90 and midi[1:] == [0x00, 0x00]:
            # Ping: answer to stay online
            self.send_note_on(0x00, 0x7F)
        elif status == 0xB0 and len(midi) == 3:
            self._control(midi[1], midi[2])
        elif status == 0xA0 and len(midi) == 3:
            strip, side, level = midi[1], midi[2] >> 4, midi[2] & 0x0F
            if strip < 8 and side == 0 and level <= 0x0C:
                self._received(f'Meter {strip + 1}', level / 12)

    def _control(self, number: int, value: int) -> None:
        if number == 0x0C:
            self._zone = value
        elif number == 0x2C and self._zone is not None:
            name = _HUI_PORTS.get((self._zone, value & 0x0F))
            if name is not None:
                self._received(name, 1.0 if value & 0x40 else 0.0)
        elif number < 0x08:
            self._fader_high[number] = value
        elif 0x20 <= number < 0x28:
            strip = number - 0x20
            self._received(f'Fader {strip + 1}', ((self._fader_high[strip] << 7) | value) / 16383)
        elif 0x10 <= number < 0x18:
            position = value & 0x0F
            self._received(f'V-Pot {number - 0x10 + 1}', (position - 1) / 10 if position else 0.0)

    def _sysex(self, data: list) -> None:
        if data[:5] != self.header or len(data) < 6:
            return
        command, body = data[5], data[6:]
        if command == 0x10 and len(body) >= 5 and body[0] < 8:
            self._received(f'Name {body[0] + 1}', ''.join(chr(c) if 0x20 <= c < 0x7F else ' ' for c in body[1:5]).strip())
        elif command == 0x11:
            # Timecode digits, right to left; 0x10 adds a dot
            for i, code in enumerate(body[:8]):
                self.timecode[7 - i] = str(code & 0x0F) + ('.' if code & 0x10 else '')
            self._received('Timecode', ''.join(self.timecode).strip())
        elif command == 0x12:
            # 10 characters per zone: zones 0-3 are the top line, 4-7 the bottom
            for start in range(0, len(body) - 10, 11):
                zone = body[start]
                if zone < 8:
                    for i, code in enumerate(body[start + 1:start + 11]):
                        self.display[zone * 10 + i] = chr(code) if 0x20 <= code < 0x7F else ' '
            text = ''.join(self.display)
            self._received('Display', f'{text[:40].rstrip()}\n{text[40:].rstrip()}')
