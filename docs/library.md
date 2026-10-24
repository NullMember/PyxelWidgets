# The Python library

Everything the designer makes is plain Python underneath: a surface of widgets, the devices showing it, a transport keeping time. This guide shows the pieces in code. Layout files from the designer load with `parser.load` (see the README), and the designer's *Python* tab writes the code for a layout. Sending to other software is in the [outputs guide](outputs.md).

## Layout files

A layout made in the designer loads with `parser.load`; widgets are found by
name, and `ui.app()` makes an App with the layout's devices, outputs, links and
clocks:

```python
from pyxelwidgets import Changed, parser

ui = parser.load('layout.json')
ui['volume'].on(Changed, lambda event: print(event.value))
app = ui.app()          # Sequencers and Trackers follow app.transport
app.transport.play()
app.run()
```

The designer's *Python* tab writes this for a layout, or a program building
the same surface in code (*Standalone*), to carry on from when a layout
outgrows the designer. Widgets and devices of your own work in layouts and the
designer once registered (`@parser.register`, then `--import my_widgets.py`;
see [writing a widget](writing-a-widget.md)).

## A first surface

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
  or code. With `decay` (seconds) each value is a hit that fades away: link a
  voice's NoteOn velocity to it and it flashes with each note. `MeterBank` is a row of them, one per column, picked by a
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

## Hardware

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

## Musical time

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

The transport can also follow a DAW's MIDI clock, over a port, network MIDI
or Bluetooth, or send its own: see [following a DAW's clock](outputs.md#following-a-daws-clock).

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

## Animations

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

## Knobs, faders and buttons

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

A control can also send messages and start links by itself, without a widget
in between: `surface.control(device, name)` stands in for the widget, with the
control's events (`ControlChanged` for knobs and faders, `ControlTurned` for
encoders, `ControlPressed`/`ControlReleased` for buttons):

```python
from pyxelwidgets import ControlChanged, ControlPressed, ControlTurned, Link, Source
from pyxelwidgets.message import ControlChange

cutoff = surface.control(xl, 'Knob_0')
surface.map(cutoff, synth, ControlChange(74), on = ControlChanged)
surface.link(cutoff, pads, 'active_color', Source('value'), on = ControlChanged)
surface.link(surface.control(push, 'Encoder1'), keys, 'octave', Source('delta'),
             on = ControlTurned, change = Link.Change.Add, minimum = -2, maximum = 8)
surface.link(surface.control(xl, 'Solo'), mixer, 'visible', on = ControlPressed, change = Link.Change.Toggle)
```

In the designer these are on the device's panel: pick the control (or
*Learn* it), then *Add message* or *Add link*.

A controller's keyboard is a control too (kind `keys`, a MiniLab's `Keys`):
`KeyPressed`/`KeyReleased` carry the `note`, so keys can feed an
Arpeggiator, set a root or play a synth on a channel of its own:

```python
from pyxelwidgets import KeyPressed, KeyReleased
from pyxelwidgets.message import NoteOn

keys = surface.control(minilab, 'Keys')
surface.link(keys, arp.add, value = Source('note'), on = KeyPressed)
surface.link(keys, arp.remove, value = Source('note'), on = KeyReleased)
surface.map(keys, synth, NoteOn(Source('note'), Source('velocity'), channel = 4), on = KeyPressed)
```

### Lights, rings and screens

Controls with a light show what they're bound to: a Button's active or
inactive color, another widget's color dimmed by its value, lime for a bound
play/toggle while the transport plays. A held button that nothing lights
shows `surface.held_color` (white). Knobs with an LED ring (APC40 MK2) show
their widget's value. Devices with a screen (MiniLab 3, Launchkey MK3 49/61/88)
show a moved control's widget and value for `surface.value_time` seconds
(1.5), unless a link of that widget writes to the screen (e.g. a tempo
fader writing `Tempo\n{round(60 + value * 120)} bpm`). `Device.describe()`
lists `lights`, `rings` and `screens`; on a MiniLab 3 the "rings" are the
endless knobs' values, so a knob goes on from its widget's value.

Links set a light or a screen's text like a widget's option:

```python
from pyxelwidgets import Changed, Colors, Condition, Source

surface.link(volume, surface.light(apc, 'Button_1'), 'light',
             Condition(Source('value'), '>', 0.9, Colors.Red, Colors.Invisible), on = Changed)
surface.link(volume, surface.screen(minilab), 'text', 'Volume\n{round(value * 100)}%', on = Changed)
```

A light set this way wins over what its control shows; `Colors.Invisible`
gives it back. A screen's text shows while no moved control's value does.
`device.set_control(name, color)`, `set_ring(name, value)` and
`set_screen(name, lines)` drive them directly, without a surface.

## Widgets changing widgets

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

`SKIP` (in a condition or a list, or `skip` in a formula) does nothing for
that event: the option stays as it is and an action isn't called. Keys that
set a bass line's note only while its page shows:

```python
from pyxelwidgets import Expression, KeyPressed, SKIP

surface.link(keys, bass, 'note', Expression('note if pages.page == 3 else skip', {'pages': pages}), on = KeyPressed)
surface.link(tabs, panel, 'visible', Condition(Source('cell'), '<', 4, True, SKIP), on = Toggled)
```

A message with a field that computes `skip` isn't sent
(`NoteOn(36, Expression('velocity * 127 if velocity > 0 else skip'))`), and an
option's formula giving `skip` leaves the option as it is.

Options changed by links emit nothing, so links don't set each other off.
When they should, `emit = True` on a link setting a widget's `value` makes
that widget emit `Changed` as if it had been played: a shortcut button
setting a page selector lets the selector's own links switch the page, name
it on a screen and light its buttons:

```python
surface.link(shortcut, selector, 'value', 1.0, on = Pressed, emit = True)
```

In the designer it's the *send Changed* box of a link setting `value`.

### A key for every widget

A layout's `key` (`{"root": "D", "scale": "Dorian"}`, the Surface panel's
*Key*) is shared by widgets whose `root` and `scale` are the formulas
`{key.root}` and `{key.scale}` (*Make widgets follow it* sets them on every
widget having both). Links change it with the target *Key*: set the scale
from a knob or a list, add semitones to the root, toggle to the next scale.
In code it's a `Key`:

```python
from pyxelwidgets import Key, Root, Scale

key = Key(root = Root.D, scale = Scale.Dorian)
for widget in (chords, arp, lead):
    surface.formula(widget, 'root', Expression('key.root', {'key': key}))
    surface.formula(widget, 'scale', Expression('key.scale', {'key': key}))
surface.link(up, key, 'root', 1, on = Pressed, change = Link.Change.Add)     # a semitone up
```

Widgets can't be named `key` or `transport`: formulas and links use the names.

A link to the debug log writes a text filled in from the event (`'pad {x}
at {velocity}'`, `{all}` for every value, the default): in the designer it
shows in Events (filter *Only debug*); when the layout runs it's printed
(`ui.debug = ...` to send it elsewhere).

In the designer, *Add link* on a widget picks the event, the target widget (or
the Transport, or the Debug log), its option or action and how it changes. Values changed by links are kept while you edit
the layout. See `examples/Links`, a MIDI keyboard made in the designer.

## Threads

Controller input and `app.transport` subscribers (e.g. a `Sequencer`) run on their own
threads and take `app.lock` while touching widgets, so they never interleave
with rendering. Hold the same lock when you change widgets from a thread of
your own, such as a MIDI input callback:

```python
with app.lock:
    surface['Volume'].value = 0.5
```

[Threads](threads.md) says what runs where. See
[examples](../examples) for multi-page layouts, DAW control and a performance
layout.
