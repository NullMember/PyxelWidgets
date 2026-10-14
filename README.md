# PyxelWidgets  
GUI Framework for low resolution devices (e.g. Novation Launchpad, LED Keyboards)  
This project is part of my master's thesis. Because of time constraints, this project is still in alpha phase.

## Installation

Requires Python 3.10 or newer.

```sh
pip install pyxelwidgets          # core + MIDI controllers
pip install "pyxelwidgets[osc]"   # also OSC controllers
```

## Designer

Lay out widgets in the browser, try them on a live preview, and save a layout:

```sh
pyxelwidgets-designer layout.json      # or: python -m pyxelwidgets.designer layout.json
pyxelwidgets-designer layout.json --offline    # don't connect devices and outputs on start
```

The layout's devices and outputs connect as they're added: devices show the
design as you edit it and their pads work the widgets, outputs send. Each has a
Connect/Disconnect button in its list, and *Detect* finds the devices plugged
in. An empty layout offers templates (drum controller, MIDI keyboard, DAW
mixer, performance) and your connected devices.

- **Widgets:** drag them from the palette onto the grid, or click to add.
  Widgets keep their values while you edit.
- **Snippets** (the tab next to Widgets): ready-made pieces with their links
  and messages, for common grid sizes: 8x8 (a drum machine, a melody editor,
  chords and arpeggios, a Mackie mixer...), 8x2 (Launchkey and Launch Control
  pads), 8x5 (APC40), 9x9 (a Launchpad with its side buttons), 4x4, and
  strips for a side of the grid. Pick a size, then click one or drag it onto
  the grid; its output is added unless the layout has one of the same kind.
  Bigger ones are small instruments: 16 sequencers picked from a 4x4 with
  rows setting the shown one's length, direction, swing and gate; a step
  editor (hold steps, tap velocity, chance, ratchets or the drum sound); a
  Euclidean, melody or arpeggiator workstation; a snapshot mixer.
  *Save selection* keeps the selected widgets as a snippet of your own (in
  `~/.pyxelwidgets/snippets`, or `--snippets FOLDER`).
- **Layers:** drag to reorder, or onto a group to move inside. Groups fold.
  Shift+click selects a range, Ctrl/Cmd+click adds or removes one.
  Search by name. The eye hides a widget in the designer only; the lock
  keeps it from being dragged on the grid.
- **Wiring:** select a widget to see what it changes (purple) and what
  changes it (green). Its *Behaviour* section lists the links, messages,
  bindings and feedback that change it. The drawer under the grid has
  *Connections*, a table of everything.
- **Messages and links window** (M, or *Edit…* under Behaviour): lists the
  selected widgets' messages and links, or every widget's. Click, Shift+click
  and Ctrl/Cmd+click pick them; several picked ones are edited as one (fields
  that differ are dashed and keep their own values until changed). Copy them
  and paste onto other selected widgets (each gets its own), duplicate,
  delete. *+ Message* and *+ Link* add one to each selected widget.
- **Drawer:** also *Events* (filter, pause; it opens in Try mode),
  *Python* and *Problems* (the ⚠ count in the toolbar).
- **Editing:** Ctrl/Cmd+C, X and V copy, cut and paste widgets with their
  messages and links, also between layouts. Alt+click presses a pad without
  leaving Edit mode.
- **Files:** the File menu has New (from a template), Open, recent files,
  Save As and Download.
- **View:** the grid fills the space it has. The wheel zooms around the
  pointer (the toolbar's *Wheel zooms* switches it to moving the grid), so do
  pinches, Ctrl/Cmd + wheel and Ctrl/Cmd +/-/0; *Fit* brings it back.
  Shift + wheel or the middle button moves it. Hide or resize the side
  panels; F shows the grid alone.
  `?` lists every shortcut.

Then load it and attach behaviour by widget name:

```python
from pyxelwidgets import Changed, parser

ui = parser.load('layout.json')
ui['volume'].on(Changed, lambda e: print(e.value))
app = ui.app()          # Sequencers and Trackers follow app.transport
app.transport.play()
app.run()
```

The designer shows each widget's options (generated from its constructor), the
devices the layout runs on, the events widgets emit while you try them (Try
mode, click pads), and Python code for the current layout: a program loading the
layout file, or a standalone one building the same surface in code
(`pyxelwidgets.codegen`), to continue from when a layout outgrows the designer.

Sprites are painted frame by frame in the designer, and any widget can get an
animation. Shift+click or drag over empty pads selects several widgets to move,
edit, duplicate or group together (Ctrl+G). Devices are moved by dragging their
name on the canvas.

## Playing a layout

A finished layout runs without the designer or any code:

```sh
pyxelwidgets run layout.json            # until Ctrl+C (or SIGTERM from a service manager)
pyxelwidgets run layout.json --play     # and start the transport
```

It connects the layout's devices and outputs, waits for devices that aren't
plugged in yet, and reconnects ones unplugged meanwhile. What a Presets group
stores is written back into the layout file (turn its `save` option off to keep
presets for the session only); in the designer, stored presets go into the
layout you save. `pyxelwidgets designer` is the same as `pyxelwidgets-designer`.

## Quick Start

A fader and a button on the virtual (on-screen) grid controller:

```python
from pyxelwidgets import App, Button, Changed, Colors, ControlPressed, Fader, Surface
from pyxelwidgets.devices.virtual import Virtual

surface = Surface(8, 8)
volume = surface.add(Fader(0, 0, 1, 8, active_color = Colors.Cyan, name = 'Volume'))
record = surface.add(Button(7, 0, 1, 1, active_color = Colors.Red))

volume.on(Changed, lambda e: print('volume', e.value))

@record.on(Changed)
def toggle_record(e):
    print('record', e.value)

device = Virtual(8, 8)
device.connect()
surface.add_device(device)

app = App(surface)
app.run()  # until Ctrl+C or the window is closed
```

Widgets added later are drawn on top; transparent pixels (`Colors.Invisible`)
show the widgets underneath. A press goes to the topmost widget under it, and
continues to the widgets underneath only if that widget's `propagation` is
`Propagation.Pass`. Use `Group` to build reusable panels; groups nest and can
be hidden with `visible = False`. `Pages` shows one of its children at a time,
with an optional selector strip (`selector = Pages.Selector.Top`) to switch:

```python
pages = surface.add(Pages(0, 0, 9, 9))          # top row selects the page
mixer = pages.add(Group(0, 0, 9, 8))
drums = pages.add(Group(0, 0, 9, 8))
pages.next()                                    # or pages.page = 1; emits PageChanged
```

`Presets` is a group that remembers what its widgets show (values, steps,
pages) in slots along a strip: press an empty slot to store, a stored one to
bring it back (its values are sent on, so a DAW follows), hold one to store
over it. `store(slot)` and `recall(slot)` are actions links can call too.

`Text` shows short text in a 3x5 pixel font and scrolls what doesn't fit:
`surface.add(Text(0, 3, 9, 5, text = '120 BPM'))`, then `text.text = ...`.

For playing live:

- **`DrumPads`:** one note per pad from `note` (36 by default), and a
  `bank` to switch kits. Pads light by how hard they're hit, and for notes
  sent back.
- **`ClipLauncher`:** tracks in columns, scenes in rows. A pressed clip
  blinks until the next bar, then plays and stops the track's other clip.
  `launch_scene`, `stop_track` and `stop_all` are actions links can call.
- **`Meter`:** a level meter with green, yellow and red zones, peak hold and
  an optional falloff. It shows values from links, mappings (a DAW's meters)
  or code. `MeterBank` is a row of them, one per column, picked by a
  received `x` (`Command('Meter {x+1}')` from Mackie Control).
- **`TapTempo`:** tap it in time; it emits `TempoTapped` with the tempo (link
  it to the transport's tempo) and blinks on the beat.
- **`Stepper`:** a whole number from `minimum` to `maximum`, one step at a
  time with the end pads (held, they repeat), shown by the pads between.

For making music:

- **`PianoRoll`:** a melody editor. Columns are steps, rows the notes of a
  `scale` from `octave` (scrolled by `row`). Press to add a note, hold its
  first pad and press further along to make it longer, press it to delete it.
- **`ChordPads`:** chords in key: a column per degree of the scale, a row per
  kind of chord (triads, sevenths, inversions, sus, ninths).
- **`Arpeggiator`:** plays the notes held on it (or `add`ed by links, e.g. from
  a `Keyboard`) one at a time: up, down, both, at random or as played, over
  `octaves`, with a `gate` and `latch`.
- **`Euclidean`:** each row spreads its hits evenly over its length. Press a
  pad to set the hits, press past the end for a longer row, hold one and
  press another to turn the rhythm.
- **`Automaton`:** Conway's Life (or another `rule`) where cells born play
  their row's note.

Widgets playing notes (`Keyboard`, `DrumPads`, `Sequencer`, `Tracker`,
`PianoRoll`, `ChordPads`, `Arpeggiator`, `Euclidean`, `Automaton`) share
`velocity_curve` (`Linear`, `Soft`, `Hard`, or `Fixed` at `fixed_velocity`)
and `velocity_random`, which makes each note louder or softer by up to that
much. Their scales (`Scale`, `Root`) are the same too.

Every piece also works on its own: a widget without a surface
(`fader.tap(0, 7); fader.render(); fader.buffer`), a device without an app.

### Hardware

Devices are in `pyxelwidgets.devices.novation`, `.akai`, `.ableton`,
`.arturia` and `.presonus`. `find()` connects by port name:

```python
from pyxelwidgets.devices.novation import LaunchpadMiniMK3

launchpad = LaunchpadMiniMK3.find()
surface.add_device(launchpad)
launchpad.on(ControlPressed, print)   # buttons, knobs, faders, encoders
```

Launchpads include their round side buttons in the grid (9x9, or 10x10 on the
Pro models); pass `side_buttons = False` to get the 8x8 pads only and receive
the side buttons as `ControlPressed` events named `Top1`-`Top8`, `Right1`-`Right8`.
`examples/DeviceCheck` lights a test pattern and prints every event, to check a device.

Unplugging a device and plugging it back in reconnects it (the App checks
once a second; `DeviceDisconnected`/`DeviceReconnected` events). A device
that isn't plugged in at start connects when it is.

Any browser can be a grid too, a tablet or a phone on the same network:
several fingers at once, sliding across pads. The corner button goes
fullscreen; on an iPhone, Add to Home Screen opens it as a fullscreen app.

```python
from pyxelwidgets.devices.web import WebGrid

tablet = WebGrid(columns = 9, rows = 9)       # port 8800
tablet.connect()
print('Open', tablet.url)
surface.add_device(tablet)                    # alongside a Launchpad, or alone
```

### Musical time

A `Transport` keeps tempo, time signature, play/stop and the position, and
calls subscribers at note values (`'1/16'`, dotted `'1/8.'`, triplet `'1/8T'`,
`'beat'`, `'bar'`). Sequencers and Trackers don't know about it: they play a
step when told to, so they can also follow your own timing.

```python
from pyxelwidgets import Sequencer, StepEnded, StepPlayed

drums = surface.add(Sequencer(0, 0, 8, 2, rate = '1/16', swing = 58.0, gate = 0.5, gate_random = 0.2))
app.attach(drums)                                 # played by app.transport
app.transport.every('bar', lambda bar: print('bar', bar + 1))
drums.on(StepPlayed, lambda e: e.active and print('hit', e.step, 'for', e.gate, 'steps'))
drums.on(StepEnded, lambda e: print('release', e.step))

app.transport.bpm = 128
app.transport.play()    # stop(), locate(beats), toggle()
```

To follow a DAW's MIDI clock (start, stop, continue and song position too),
or send one:

```python
from pyxelwidgets.devices.midi_clock import MidiClockInput, MidiClockOutput

app = App(surface, sync = True)                # the transport follows pulse() calls
clock = MidiClockInput(app.transport)
clock.connect_virtual('PyxelWidgets Clock')     # send the DAW's clock here
# or: MidiClockOutput(app.transport).connect(out_port = 'IAC Driver Bus 1')
```

The tempo is measured from the clock (`TempoChanged`). See `examples/ClockSync`.
In a layout, `"transport": {"sync": {"virtual": "PyxelWidgets Clock"}}` (or
`{"input": "IAC Driver Bus 1"}`) does this in `ui.app()`; in the designer it's
"Sync to a DAW" on the Surface panel, and the preview then plays with the DAW.
In the DAW, enable MIDI clock (and song position) output to that port: in
REAPER, Preferences → MIDI Devices → the port's output → "Send clock/SPP";
in Ableton Live, the port's "Sync" switch on the MIDI output; in Logic, MIDI
Sync settings → Clock to the port.

A Sequencer's `swing` (50-75 percent: where every second step starts within a
pair, 66 being a triplet feel) and `gate` (how long an active step sounds, in
steps; `StepEnded` follows, for a NoteOff) are timed by its clock, 24 times a
step. `gate_random` makes each hit's gate longer or shorter by up to that many
steps. Without a clock (`Clock.Off`) gates end when the next step plays.

Each step has a velocity (from the press), a probability, ratchets (hits
within the step) and a note (the Sequencer's `note` unless set): hold steps
and call `set_velocity`, `set_probability`, `set_ratchets` or `set_note`, e.g.
from a link on a fader's Changed. `StepPlayed` carries the step's `velocity`
and `note`. `direction` plays forward, backward, ping-pong or at random, over
the first `length` steps. A Tracker's cells have a note (`note + column`
unless set) and a velocity too, and it plays them as NoteOn/NoteOff.

Sequencers, Trackers, ClipLaunchers, PianoRolls, Arpeggiators, Euclideans
and Automatons have a `clock`:
- `Clock.Transport` (the default): the transport plays them.
- `Clock.Own`: a clock of their own at their `bpm`, running whether the
  transport plays or not.
- `Clock.Off`: only `play`/`advance` play them, from code or links.

`running = False` (or the `start`/`stop`/`toggle` actions) pauses one.
Layouts start these clocks for you (`ui.app()`).

### Animations

Blink, pulse or fade a widget, or single cells of it, without redrawing it:

```python
from pyxelwidgets import Blink, Fade, Pulse

record.animation = Blink('1/8')              # in time with app.transport
launcher.animate_cell(2, 3, Pulse('1/2'))    # one cell
page.animation = Fade(0.3)                   # seconds; removed when done
page.animation = Fade(0.3, out = True)       # hidden when done
```

Note value rates follow the transport while it plays and its tempo while it
doesn't; numbers are seconds.

Layouts store a widget's animation too (`"animation": {"type": "Blink", "options": {"rate": "1/8"}}`).
A `Sprite` shows `frames` and changes them every `rate` the same way:
`Sprite(0, 0, 2, 2, frames = [first, second], rate = '1/4')`.

### Knobs, faders and buttons

Bind a device's named controls (see `Device.describe()`) to widgets or actions:

```python
from pyxelwidgets import Takeover

surface.bind(xl, 'Fader_0', volume)                          # glides to the fader's position
surface.bind(xl, 'Knob_0', pan, takeover = Takeover.Pickup)  # or Takeover.Jump
surface.bind(push, 'Encoder1', cutoff, step = 1 / 64)        # relative encoders
surface.bind(launchpad, 'Top1', app.transport.toggle)        # buttons trigger actions
```

Layouts store bindings too, and the designer edits them (a widget's *control*
field, and *Transport controls* on the surface). Launchpad side buttons become
controls with `side_buttons = False`.

### Sending to other software

Outputs send widget events to a DAW, a synth or an OSC app, and with
`feedback` what comes back updates the widgets:

```python
from pyxelwidgets import Changed, Pressed, Released, Source
from pyxelwidgets.devices.midi_port import MidiPort
from pyxelwidgets.devices.mackie import MackieControl
from pyxelwidgets.message import Command, ControlChange, NoteOff, NoteOn

synth = MidiPort()
synth.connect_virtual('PyxelWidgets')                  # a port the DAW can pick
surface.map(kick, synth, NoteOn(36, Source('velocity'), channel = 10), on = Pressed)
surface.map(kick, synth, NoteOff(36, channel = 10), on = Released)
surface.map(pads, synth, NoteOn(Source('cell', offset = 36)), on = Pressed)   # a note per pad
surface.map(volume, synth, ControlChange(7), on = Changed, feedback = True)

mackie = MackieControl()                               # or HUI(); OSC/REAPER in devices.osc
mackie.connect_virtual('PyxelWidgets MCU')
surface.map(play, mackie, Command('Play'), on = Pressed, feedback = True)   # its LED follows the DAW
surface.map(clock, mackie, Command('Timecode', Source('text')), feedback = True)
```

A field is a constant or a `Source` from the event: `velocity`, `value`,
`pressure` (pad aftertouch), `state`, `x`, `y`, `cell`, `note`, `delta`...
0.0-1.0 values cover the field's range (`min`/`max` narrow it), whole numbers
take an `offset`. Names and OSC addresses take placeholders: `'Mute {x+1}'`,
`'/track/{x+1}/volume'`. Widgets with `interactive = False` only show what the
DAW sends back.

Layouts store outputs and mappings, and the designer edits them: add an output
under *Outputs*, then *Add message* on a widget (it opens the messages and
links window). Mackie Control and HUI
commands (and REAPER's OSC addresses) are picked from a list, with one-per-pad
variants such as `Mute {x+1}`. In Try mode the event log shows
what would be sent; when the output is connected it is sent. See `examples/MidiDrums`
(made in the designer) and `examples/DAWControl`.

#### Plug-in parameters (Mackie Control)

A widget can control a plug-in parameter by name, through the DAW's Mackie
Control plug-in mode. Mackie Control has no way to ask the DAW for names, so
PyxelWidgets presses the DAW's buttons and reads its display: the Bank buttons
for track names, *Plug-in* for the selected track's plug-ins, a V-Pot press
to open one, and the Bank buttons again to page through its parameters.

```python
from pyxelwidgets.message import PluginParameter

mackie.scan_tracks()                          # ['Drums', 'Bass', ...]: 7 characters at most
mackie.scan_plugins('Bass')                   # ['ReaEQ', 'ReaComp']
mackie.scan_parameters('Bass', 'ReaComp')     # ['Thresh', 'Ratio', ...]
surface.map(knob, mackie, PluginParameter('Bass', 'ReaComp', 'Ratio'), on = Changed, feedback = True)
```

A turn makes the DAW show that plug-in's page, then turns its V-Pot by the
widget's steps (`delta`). With feedback the widget follows the V-Pot's LED
ring. In the designer, pick *PluginParameter* as a message to a connected
Mackie Control output, then press *Scan* next to track, plug-in and parameter
and pick from the lists (or type the names).

Tried with Logic Pro (as a Logic Control surface): scanning a track's plug-ins
takes half a second, a plug-in's parameters about 1.3 seconds per page of 8
(Logic shows "Page 2/12" over the names for a moment), and the first turn on
another page about 2 seconds. Names are Logic's 6 character abbreviations
(`Ratio`, `OutLev`, `SCQBan (3)`).

Tried with Cubase 15 (Studio → Studio Setup → Remote Devices → Mackie Control,
MIDI input and output "PyxelWidgets MCU"): 20 tracks scan in about 2 seconds, a
track's plug-ins in 3.5 (Cubase shows one insert slot at a time, so all 16 are
looked at), a plug-in's parameters about 0.4 seconds per page of 8. Cubase
shortens track names to 6 characters ("Audio 01" is `Audi01`) and cuts
parameter names to 7, so many repeat (`SideCha (12)`). It sends a parameter's
position when its page is shown but not after a turn, so a widget's feedback
only follows on page changes. Selecting another track in Cubase (touching its
fader does) makes its plug-in view show that track's plug-in; PyxelWidgets
reads the track and plug-in names on Cubase's display, ignores what belongs to
the other track, and goes back to the right one on the next change (selecting
that track again).

Track names have to differ within those 6 or 7 characters: tracks and plug-ins
are found again by name when they move.

Other DAWs need to show the selected track's
plug-ins on the strips after *Plug-in*, open one when its V-Pot is pressed, and
page with the Bank or cursor buttons; the buttons can be set (`plugin_button`,
`channel_button`, `next_page`, `previous_page`). REAPER's own Mackie Control
support has no plug-in mode (its CSI or Klinke extensions do), but its OSC
reaches every parameter (below). Only one plug-in is shown at a time, so
widgets on different plug-ins make the DAW switch back and forth.

#### Track volume, pan, mute, solo and record by name

`TrackParameter(track, parameter, value)` reaches a track by its scanned name,
wherever it is: `parameter` is `Volume`, `Pan`, `Mute`, `Solo` or `Record`.
A `Command('Fader 1', ...)` moves whichever track is on the first strip at the
moment (after a plug-in parameter on track 19, Cubase shows tracks 13-20);
a TrackParameter first shows its track (checked by name), then moves its fader,
turns its V-Pot (Pan) or switches its button (only when its light says it's
the other way). Mackie Control and REAPER both take it:

```python
from pyxelwidgets.message import TrackParameter

surface.map(fader, mackie, TrackParameter('Audi19', 'Volume'), on = Changed, feedback = True)
surface.map(knob, mackie, TrackParameter('Audi19', 'Pan', Source('delta')), on = Changed)
surface.map(button, reaper, TrackParameter('Bass', 'Mute', Source('state')), on = Toggled, feedback = True)
```

Values: Volume 0-1; Pan is V-Pot steps for Mackie Control and 0-1 for REAPER;
Mute, Solo and Record are on above 0.5. Feedback comes back as 0-1 (a pan's
from the V-Pot ring's 11 lights, so in steps of 0.1). With
Mackie Control the DAW's strips show the track's bank afterwards (and its Pan
view), so widgets on plug-ins and on tracks make it switch back and forth;
feedback from Mackie Control comes while the track is on the strips. In the
designer, pick *TrackParameter*, *Scan* the tracks and pick one.

#### Plug-in parameters (REAPER)

REAPER's OSC sends a device the names of its tracks, plug-ins and parameters,
so the `REAPER` output scans them directly, with full names, and sets a
parameter to the widget's position (`value`, 0-1) instead of turning it:

```python
from pyxelwidgets.devices.osc import REAPER

reaper = REAPER()                              # sends to port 8000, listens on 9000
reaper.connect()
reaper.scan_tracks()                           # ['Drums', 'Bass', ..., 'MASTER']
reaper.scan_plugins('Bass')                    # ['3-Band EQ', 'Volume/Pan Smoother']
reaper.scan_parameters('Bass', '3-Band EQ')    # ['Low (dB)', 'Frequency (Hz)', 'Mid (dB)', ...]
surface.map(knob, reaper, PluginParameter('Bass', '3-Band EQ', 'Mid (dB)', Source('value')),
            on = Changed, feedback = True)
```

**Name every track, each differently.** REAPER's OSC addresses tracks and
plug-ins by their place, so before setting a parameter PyxelWidgets checks
the names at that place and scans again when tracks or plug-ins were moved.
An unnamed track is called "Track 4" by its place, so it can't be followed;
the output's warning lists unnamed and repeated track names.

In REAPER: Preferences → Control/OSC/web → Add → OSC (Open Sound Control),
pattern config *Default*, mode *Configure device IP + local port*, device IP
127.0.0.1 (not 0.0.0.0: that's where REAPER sends to), device port 9000, local listen port 8000. In the designer it works
like Mackie Control: a *REAPER (OSC)* output, *PluginParameter*, *Scan*.

Tried with REAPER 7.79: 20 tracks scan in about 3 seconds (the first scan has
REAPER send everything once), a track's plug-ins in 0.2 seconds, 30
parameters in 0.6 seconds; setting one is immediate. Setting a parameter
selects its track in the OSC device, so OSC addresses without a track number
(`/track/volume`) follow it. REAPER sends parameter changes back only for
tracks in the device's bank (the first 8, unless moved with
`/device/track/bank/+`) and the first 16 parameters of a plug-in, so feedback
works there.

### Keyboard and mouse

Your computer's keyboard and mouse are an output too, for macro boards and
automation (`pip install "pyxelwidgets[desktop]"`):

```python
from pyxelwidgets.devices.desktop import Desktop
from pyxelwidgets.message import Hotkey, Key, MouseClick, MouseMove, Scroll, TypeText

desktop = Desktop()
desktop.connect()
surface.map(save, desktop, Hotkey('cmd+s'), on = Pressed)                 # or 'ctrl+s'
surface.map(talk, desktop, Key('f13', Source('value')), on = Changed)     # held while on
surface.map(snippet, desktop, TypeText('Thanks, talk soon!'), on = Pressed)
surface.map(pad, desktop, MouseMove(Source('value_x'), Source('value_y')), on = Changed)
surface.map(knob, desktop, Scroll(0, Source('delta')), on = Changed)
surface.map(click, desktop, MouseClick('left'), on = Pressed)
```

- **Keys:** joined with `+` (`ctrl`, `shift`, `alt`, `cmd`, `enter`, `f1`-`f20`,
  arrows, `media_play_pause`, `media_volume_up`... or single characters).
  `'f{x+1}'` gives each column its own key.
- **Designer:** the keys field has a *Record* button: press the combination.
  The output isn't connected by itself there; press *Connect* when the keys
  and clicks should happen for real.
- **macOS:** allow the app running it (Terminal, your editor) under System
  Settings > Privacy & Security > Accessibility.

See `examples/MacroBoard`.

### Widgets changing widgets

Links change a widget's options when another widget emits an event, so a
layout can rearrange itself without code:

```python
from pyxelwidgets import Changed, Link, Pressed, Source, Toggled

surface.link(show, panel, 'visible', Source('value'), on = Changed)          # a switch shows a group
surface.link(up, keys, 'octave', 1, on = Pressed, change = Link.Change.Add, maximum = 8)
surface.link(scale, keys, 'scale', on = Pressed, change = Link.Change.Toggle)  # the next scale
surface.link(tabs, pages, 'page', Source('cell'), on = Toggled)               # a page per cell
surface.link(wheel, keys, 'keyboard_color', Source('value'), on = Changed)    # dims a color
```

Any constructor option can be linked, as can `x`, `y`, `width` and `height`.
A change is `Set` (default), `Add` (numbers, or moving through choices) or
`Toggle` (on/off, or the next choice). The value is a constant or a `Source`
from the event. 0.0-1.0 values cover `minimum` to `maximum`: numbers, colors
(black to the option's color by default), choices and text. Whole numbers
take an `offset`, and `Add` stays within `minimum`/`maximum`. Code can do the
same with `widget.configure(octave = 3, active_color = Colors.Red)`.

A link can also call an action. The transport has play, stop, toggle and
rewind, plus `tempo` (a fader sets the bpm, say from 60 to 180) and
`tempo_add`. Widgets have their own: a Sequencer's or Tracker's `advance`,
`play` a step, `start` and `stop`; a ClipLauncher's `launch_scene`; a Pages'
`next` and `previous`.

```python
surface.link(play, app.transport.toggle, on = Pressed)
surface.link(pads, sequencer.play, value = Source('cell'), on = Pressed)   # jump to a step
```

Sequencers and Trackers show and edit a `page` (and a Tracker the rows from
`bar`), apart from the `step` playing; with `follow` the view moves to the
step as it plays. Link buttons to `page`/`bar` to scroll through a long
track. With `clock = Clock.Off` nothing plays them but links (say, a
button's `advance`) or code.

A value can also be a condition: an event value compared with a constant
chooses between two values, which you set (true/false for on/off options):

```python
from pyxelwidgets import Condition

# 16 sequencers in one place, a 4x4 ButtonGroup shows the one of its chosen cell
for n, sequencer in enumerate(sequencers):
    surface.link(tabs, sequencer, 'visible', Condition(Source('cell'), '==', n), on = Toggled)
surface.link(tabs, pad, 'active_color', Condition(Source('x'), '<', 4, Colors.Red, Colors.Blue), on = Toggled)
```

In the designer, pick *condition…* as the value. When a Switch ButtonGroup
changes its cell, the cell turned off is reported first, so the new choice
always comes last.

A link to the debug log writes a text filled in from the event (`'pad {x}
at {velocity}'`, `{all}` for every value, the default): in the designer it
shows in Events (filter *Only debug*); when the layout runs it's printed
(`ui.debug = ...` to send it elsewhere).

In the designer, *Add link* on a widget picks the event, the target widget (or
the Transport, or the Debug log), its option or action and how it changes. Values changed by links are kept while you edit
the layout. See `examples/Links`, a MIDI keyboard made in the designer.

### Threads

Controller input and `app.transport` subscribers (e.g. a `Sequencer`) run on their own
threads and take `app.lock` while touching widgets, so they never interleave
with rendering. Hold the same lock when you change widgets from a thread of
your own, such as a MIDI input callback:

```python
with app.lock:
    surface['Volume'].value = 0.5
```

[docs/threads.md](docs/threads.md) says what runs where. See
[examples](examples) for multi-page layouts, DAW control and a performance
layout.

## Documentation

- [Getting started](docs/getting-started.md): your first controller in the designer, no code
- [Snippets](docs/snippets.md): the designer's ready-made pieces
- [Writing a widget](docs/writing-a-widget.md) and [writing a driver](docs/writing-a-driver.md)
- [Threads](docs/threads.md)
- [API reference](docs/api.md), generated from the docstrings (`python docs/build_api.py`)

Widgets and devices of your own work in layouts and the designer once they
are registered (`@parser.register`; `pyxelwidgets-designer layout.json --import mywidgets.py`).

## Supported Devices  

| Brand      | Family     | Model      | Generation | Support    | Protocol   | Grid       | Color      | Control    |
|------------|------------|------------|------------|------------|------------|------------|------------|------------|
| Virtual    | -          | -          | -          | Full       | tkinter    | NxN        | RGB b 8    | ----       |
| Web grid   | -          | -          | -          | Full       | WebSocket  | NxN        | RGB b 8    | ----       |
| Ableton    | -          | Push       | 2          | Full       | MIDI       | 8x8        | RGB P 128  | B--E       |
| Arturia    | MiniLab    | mkII       | 2          | Untested   | MIDI       | 8x2        | RGB P 8    | ---E       |
|            |            | 3          | 3          | Untested   | MIDI       | 8x2        | RGB b 7    | BFKE       |
| Akai       | APC        | Mini       | 1          | Full       | MIDI       | 8x8        | RG  P 3    | BF--       |
|            |            | 40         | 2          | Full       | MIDI       | 8x5        | RGB P 128  | BFKE       |
| Novation   | LaunchCtl  | Base       | 1          | Full       | MIDI       | 8x1        | RG  P 16   | B-K-       |
|            |            | XL         | 1          | Full       | MIDI       | 8x2        | RG  P 16   | BFK-       |
|            | Launchkey  | Base       | 1          | Full       | MIDI       | 8x2        | RG  P 16   | BFK-       |
|            |            | Base       | 2          | Full       | MIDI       | 8x2        | RGB P 128  | BFK-       |
|            |            | Base       | 3          | Full       | MIDI       | 8x2        | RGB P 128  | B-K-       |
|            | Launchpad  | Base       | 1          | Full       | MIDI       | 9x9        | RG  P 16   | ----       |
|            |            | S          | 1          | Full       | MIDI       | 9x9        | RG  P 16   | ----       |
|            |            | Mini       | 1          | Full       | MIDI       | 9x9        | RG  P 16   | ----       |
|            |            | Mini       | 2          | Full       | MIDI       | 9x9        | RG  P 16   | ----       |
|            |            | Base       | 2          | Full       | MIDI       | 9x9        | RGB b 6    | ----       |
|            |            | Pro        | 1          | Full       | MIDI       | 10x10      | RGB b 6    | ----       |
|            |            | X          | 3          | Full       | MIDI       | 9x9        | RGB b 7    | ----       |
|            |            | Mini       | 3          | Full       | MIDI       | 9x9        | RGB b 7    | ----       |
|            |            | Pro        | 3          | Full       | MIDI       | 10x11      | RGB b 7    | ----       |
| Presonus   | -          | ATOM       | 1          | Full       | MIDI       | 4x4        | RGB b 7    | B--E       |

Color: P = Palette, b = bits  
Control: Extra controls. Button, Fader, Knob, Encoder  
