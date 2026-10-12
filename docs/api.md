# PyxelWidgets API reference

Generated from the docstrings by `docs/build_api.py`; see the [guides](README.md) for how the pieces fit.

- Basics
  - [`pyxelwidgets.color`](#pyxelwidgetscolor)
  - [`pyxelwidgets.rectangle`](#pyxelwidgetsrectangle)
  - [`pyxelwidgets.rate`](#pyxelwidgetsrate)
  - [`pyxelwidgets.events`](#pyxelwidgetsevents)
  - [`pyxelwidgets.font`](#pyxelwidgetsfont)
  - [`pyxelwidgets.buffer`](#pyxelwidgetsbuffer)
  - [`pyxelwidgets.animation`](#pyxelwidgetsanimation)
  - [`pyxelwidgets.message`](#pyxelwidgetsmessage)
- Widgets
  - [`pyxelwidgets.widgets`](#pyxelwidgetswidgets)
  - [`pyxelwidgets.group`](#pyxelwidgetsgroup)
- Time, controls and outputs
  - [`pyxelwidgets.transport`](#pyxelwidgetstransport)
  - [`pyxelwidgets.binding`](#pyxelwidgetsbinding)
  - [`pyxelwidgets.mapping`](#pyxelwidgetsmapping)
  - [`pyxelwidgets.link`](#pyxelwidgetslink)
- Putting it together
  - [`pyxelwidgets.surface`](#pyxelwidgetssurface)
  - [`pyxelwidgets.app`](#pyxelwidgetsapp)
  - [`pyxelwidgets.parser`](#pyxelwidgetsparser)
  - [`pyxelwidgets.codegen`](#pyxelwidgetscodegen)
- Devices
  - [`pyxelwidgets.devices`](#pyxelwidgetsdevices)
  - [`pyxelwidgets.devices.colors`](#pyxelwidgetsdevicescolors)
  - [`pyxelwidgets.devices.input`](#pyxelwidgetsdevicesinput)
  - [`pyxelwidgets.devices.midi`](#pyxelwidgetsdevicesmidi)
  - [`pyxelwidgets.devices.novation`](#pyxelwidgetsdevicesnovation)
  - [`pyxelwidgets.devices.akai`](#pyxelwidgetsdevicesakai)
  - [`pyxelwidgets.devices.ableton`](#pyxelwidgetsdevicesableton)
  - [`pyxelwidgets.devices.presonus`](#pyxelwidgetsdevicespresonus)
  - [`pyxelwidgets.devices.virtual`](#pyxelwidgetsdevicesvirtual)
  - [`pyxelwidgets.devices.web`](#pyxelwidgetsdevicesweb)
  - [`pyxelwidgets.devices.midi_clock`](#pyxelwidgetsdevicesmidi_clock)
  - [`pyxelwidgets.devices.midi_port`](#pyxelwidgetsdevicesmidi_port)
  - [`pyxelwidgets.devices.mackie`](#pyxelwidgetsdevicesmackie)
  - [`pyxelwidgets.devices.osc`](#pyxelwidgetsdevicesosc)
  - [`pyxelwidgets.devices.desktop`](#pyxelwidgetsdevicesdesktop)
- Designer
  - [`pyxelwidgets.designer`](#pyxelwidgetsdesigner)

# Basics

## `pyxelwidgets.color`

### `Color`

```python
Color(r: int = 0, g: int = 0, b: int = 0, a: float = 1.0)
```

Immutable RGBA color. `r`, `g` and `b` are 0-255, `a` is 0.0-1.0
(stored in 1/255 steps so a color survives a round trip through a buffer).
Out-of-range values are clamped. Operations return new colors.

- **`replace(**channels)`**: Copy with some channels changed, e.g. `Colors.Red.replace(a = 0.5)` 
- classmethod **`from_value(value: int)`**: Create a Color from a packed 32-bit 0xAARRGGBB value 
- classmethod **`from_array(rgba)`**: Create a Color from a frame buffer cell 
- **`value`**: Packed 32-bit 0xAARRGGBB value 
- **`rgba`**: Raw (red, green, blue, alpha) tuple, alpha scaled to 0-255 
- **`rgb`**: Raw (red, green, blue) tuple 
- **`frgb`**: Raw float (red, green, blue) tuple 
- **`argb`**: Alpha blended (red, green, blue) tuple 
- **`fargb`**: Alpha blended float (red, green, blue) tuple 
- **`grgb`**: Alpha blended and gamma corrected (red, green, blue) tuple 
- **`fgrgb`**: Alpha blended and gamma corrected float (red, green, blue) tuple 
- **`h`**: Hue value calculated from alpha blended rgb 
- **`s`**: Saturation value calculated from alpha blended rgb 
- **`l`**: Luminance value calculated from alpha blended rgb 
- **`mono`**: Linear monophonic color calculated from alpha blended rgb 
- **`gmono`**: Linear monophonic color calculated from alpha blended rgb then applied gamma correction 
- **`find_in_palette(palette)`**: Find in palette using alpha blended rgb value 
- **`minimum(other)`**: Channel-wise minimum of two colors (darken blend) 
- **`maximum(other)`**: Channel-wise maximum of two colors (lighten blend) 

### `Colors`

## `pyxelwidgets.rectangle`

### `Position2D`

```python
Position2D(x: int = 0, y: int = 0)
```

- **`set(x: int, y: int)`**
- **`get()`**

### `Dimension2D`

```python
Dimension2D(w: int = 1, h: int = 1)
```

- **`area`**
- **`set(w: int, h: int)`**
- **`get()`**

### `Rectangle2D` (Position2D, Dimension2D)

```python
Rectangle2D(x: int = 0, y: int = 0, w: int = 1, h: int = 1, position: Position2D = None, dimension: Dimension2D = None)
```

- **`l`**
- **`r`**
- **`b`**
- **`t`**
- **`slice`**
- **`columns`**
- **`rows`**
- **`origin`**
- **`set(x: int, y: int, w: int, h: int)`**
- **`get()`**
- **`copy()`**
- **`intersect(rect)`**
- **`collide(rect)`**

## `pyxelwidgets.rate`

Musical lengths: note values such as `'1/16'`, dotted `'1/8.'`, triplet
`'1/8T'`, whole notes `'1'` or `'2'`, and `'beat'` or `'bar'` of a
time signature. Used by the transport, widgets' `rate` and animations.

### `parse_rate(rate, signature: tuple = (4, 4))`

Length of `rate` in whole notes, e.g. `'1/8.'` → 3/16. Raises ValueError.

### `parse_signature(signature)`

A time signature as (beats per bar, beat note value), e.g. `[6, 8]` → (6, 8). Raises ValueError.

### `quarter_notes(rate, signature: tuple = (4, 4))`

Length of `rate` in quarter notes (beats at x/4), e.g. `'1/8'` → 0.5.

## `pyxelwidgets.events`

Typed events and the :class:`Emitter` mixin that delivers them.

Handlers subscribe to an event class and receive the event object:

    fader.on(Changed, lambda e: print(e.widget.name, e.value))

    @button.on(Pressed)
    def pressed(e):
        ...

Subscribing to a base class (e.g. `Event` or `WidgetEvent`) receives every
subclass too. Handlers run in the order they were added.

### `Emitter`

Mixin giving any object `on`, `off` and `emit`. Needs no `__init__` call.

- **`on(event_type: type, handler: typing.Callable = None)`**: Call `handler(event)` for every emitted `event_type`; usable as a decorator.
- **`off(event_type: type, handler: typing.Callable)`**: Remove a handler added with `on`.
- **`emit(event: Event)`**

### `Event`

```python
Event()
```

Base class of all events.

### `WidgetEvent` (Event)

```python
WidgetEvent(widget: typing.Any)
```

WidgetEvent(widget: 'typing.Any')

### `Pressed` (WidgetEvent)

```python
Pressed(widget: typing.Any, x: int, y: int, velocity: float)
```

A pad on the widget was pressed; `x`, `y` are widget coordinates.

### `Released` (WidgetEvent)

```python
Released(widget: typing.Any, x: int, y: int, velocity: float)
```

Released(widget: 'typing.Any', x: 'int', y: 'int', velocity: 'float')

### `Held` (WidgetEvent)

```python
Held(widget: typing.Any, x: int, y: int, velocity: float)
```

A pad has been held longer than the controller's `held_time`.

### `DoublePressed` (WidgetEvent)

```python
DoublePressed(widget: typing.Any, x: int, y: int, velocity: float)
```

DoublePressed(widget: 'typing.Any', x: 'int', y: 'int', velocity: 'float')

### `Pressure` (WidgetEvent)

```python
Pressure(widget: typing.Any, x: int, y: int, pressure: float)
```

The pressure (aftertouch) of a held pad changed, from 0.0 to 1.0.

### `Changed` (WidgetEvent)

```python
Changed(widget: typing.Any, value: typing.Any)
```

Input changed the widget's value: a float, or a tuple for multi-axis widgets (XY).

### `Resized` (WidgetEvent)

```python
Resized(widget: typing.Any, width: int, height: int)
```

Resized(widget: 'typing.Any', width: 'int', height: 'int')

### `Toggled` (WidgetEvent)

```python
Toggled(widget: typing.Any, x: int, y: int, state: bool)
```

A cell of a ButtonGroup changed state.

### `NoteOn` (WidgetEvent)

```python
NoteOn(widget: typing.Any, note: int, velocity: float)
```

NoteOn(widget: 'typing.Any', note: 'int', velocity: 'float')

### `NoteOff` (WidgetEvent)

```python
NoteOff(widget: typing.Any, note: int, velocity: float)
```

NoteOff(widget: 'typing.Any', note: 'int', velocity: 'float')

### `StepPlayed` (WidgetEvent)

```python
StepPlayed(widget: typing.Any, step: int, active: bool, gate: float = 1.0)
```

The Sequencer playhead moved to `step`; `active` if that step is on.
`gate` is how long an active step sounds, in steps (StepEnded follows).

### `StepEnded` (WidgetEvent)

```python
StepEnded(widget: typing.Any, step: int)
```

The gate of an active Sequencer `step` ended: send a NoteOff on it.

### `PageChanged` (WidgetEvent)

```python
PageChanged(widget: typing.Any, page: int)
```

PageChanged(widget: 'typing.Any', page: 'int')

### `RowPlayed` (WidgetEvent)

```python
RowPlayed(widget: typing.Any, row: int, columns: tuple)
```

The Tracker playhead moved to `row`; `columns` lists the active cells in it.

### `ClipQueued` (WidgetEvent)

```python
ClipQueued(widget: typing.Any, x: int, y: int, launch: bool)
```

A ClipLauncher clip waits for its clock to start (`launch`) or stop.

### `ClipStarted` (WidgetEvent)

```python
ClipStarted(widget: typing.Any, x: int, y: int)
```

A ClipLauncher clip started playing.

### `ClipStopped` (WidgetEvent)

```python
ClipStopped(widget: typing.Any, x: int, y: int)
```

A ClipLauncher clip stopped.

### `PadEvent` (Event)

```python
PadEvent(device: typing.Any, x: int, y: int, velocity: float)
```

Input from a grid pad of a device; `x`, `y` are grid coordinates.

### `PadPressed` (PadEvent)

```python
PadPressed(device: typing.Any, x: int, y: int, velocity: float)
```

PadPressed(device: 'typing.Any', x: 'int', y: 'int', velocity: 'float')

### `PadReleased` (PadEvent)

```python
PadReleased(device: typing.Any, x: int, y: int, velocity: float)
```

PadReleased(device: 'typing.Any', x: 'int', y: 'int', velocity: 'float')

### `PadHeld` (PadEvent)

```python
PadHeld(device: typing.Any, x: int, y: int, velocity: float)
```

The pad has been held longer than the device's `held_time`.

### `PadDoublePressed` (PadEvent)

```python
PadDoublePressed(device: typing.Any, x: int, y: int, velocity: float)
```

Emitted right after PadPressed when the previous press was within `double_press_time`.

### `PadPressure` (PadEvent)

```python
PadPressure(device: typing.Any, x: int, y: int, velocity: float)
```

The pressure (aftertouch) of a held pad changed; `velocity` is the pressure from 0.0 to 1.0.

### `ControlEvent` (Event)

```python
ControlEvent(device: typing.Any, control: str)
```

Input from a named non-grid control of a device (button, knob, fader, encoder, touch strip).

### `ControlPressed` (ControlEvent)

```python
ControlPressed(device: typing.Any, control: str, velocity: float)
```

A button was pressed (or a touch-sensitive control touched).

### `ControlReleased` (ControlEvent)

```python
ControlReleased(device: typing.Any, control: str, velocity: float)
```

ControlReleased(device: 'typing.Any', control: 'str', velocity: 'float')

### `ControlChanged` (ControlEvent)

```python
ControlChanged(device: typing.Any, control: str, value: float)
```

An absolute control (knob, fader) moved to `value` from 0.0 to 1.0.

### `ControlTurned` (ControlEvent)

```python
ControlTurned(device: typing.Any, control: str, delta: int)
```

A relative control (endless encoder) turned by `delta` steps; negative is counter-clockwise.

### `MessageReceived` (Event)

```python
MessageReceived(device: typing.Any, message: typing.Any)
```

An output (MIDI port, OSC, Mackie Control, ...) received `message` (see `pyxelwidgets.message`).

### `DeviceDisconnected` (Event)

```python
DeviceDisconnected(device: typing.Any)
```

A device's ports went away (it was unplugged); it reconnects when they're back.

### `DeviceReconnected` (Event)

```python
DeviceReconnected(device: typing.Any)
```

An unplugged device is back and connected again.

### `Frame` (Event)

```python
Frame(surface: typing.Any, frame: int)
```

Emitted by a Surface before rendering each frame.

### `TransportEvent` (Event)

```python
TransportEvent(transport: typing.Any)
```

TransportEvent(transport: 'typing.Any')

### `TransportStarted` (TransportEvent)

```python
TransportStarted(transport: typing.Any, tick: int)
```

Playback started at `tick`.

### `TransportStopped` (TransportEvent)

```python
TransportStopped(transport: typing.Any, tick: int)
```

Playback stopped at `tick`.

### `TransportLocated` (TransportEvent)

```python
TransportLocated(transport: typing.Any, tick: int)
```

The position was moved to `tick`.

### `TempoChanged` (TransportEvent)

```python
TempoChanged(transport: typing.Any, bpm: float)
```

TempoChanged(transport: 'typing.Any', bpm: 'float')

## `pyxelwidgets.font`

A 3x5 pixel font for grids: digits, letters (upper case; lower case is shown
upper case) and common symbols. Most glyphs are 3 pixels wide, M, N and W are
wider, and some punctuation is narrower.

    text_bitmap('120 BPM')   # bool array (width, 5): x left to right, y bottom to top

### `glyph(char: str)`

The bitmap of one character: bool array (width, 5).

### `text_bitmap(text: str)`

`text` as a bool array (width, 5); x from the left, y from the bottom.

### `text_width(text: str)`

## `pyxelwidgets.buffer`

Frame buffers are `uint8` arrays of shape `(width, height, 4)` holding
straight (non-premultiplied) RGBA, indexed as `buffer[x, y]`.
Any :class:`~pyxelwidgets.color.Color` can be assigned to a buffer cell or slice.

### `new(width: int, height: int, color: Color = None)`

Create a buffer filled with `color` (transparent by default).

### `to_buffer(data)`

Convert an RGBA array, or a 2-d array/list of Colors, to a buffer.

### `composite(dst: ndarray, src: ndarray)`

Draw `src` over `dst` in place using alpha ("over") blending.

## `pyxelwidgets.animation`

Animations change how a widget (or one of its cells) looks over time without
the widget redrawing:

    clip.animation = Blink('1/8')                 # the whole widget
    launcher.animate_cell(2, 3, Pulse('1/2'))     # one cell
    page.animation = Fade(0.3)                    # fades in once, then is removed

Rates and durations are note values (`'1/8'`, `'bar'`), which follow a
transport's position while it plays and its tempo while it doesn't, or seconds
(a number). A Surface supplies the time (`surface.transport`); without one,
note values run at 120 bpm.

### `Time`

```python
Time(seconds: float, beats: float, signature: tuple = (4, 4))
```

When a frame is drawn: wall clock `seconds` and musical `beats` (quarter notes).

### `Animation`

```python
Animation(rate: rate.Rate | float = '1/4')
```

Base class: `apply(cells, time)` returns the animated copy of RGBA
`cells`. `finished(time)` ends one-shot animations.

- **`phase(time: Time)`**: Position within the current period, 0.0 to 1.0; aligned to the beat for note values.
- **`elapsed(time: Time)`**: Periods since the animation was first applied.
- **`apply(cells: ndarray, time: Time)`**
- **`finished(time: Time)`**

### `Blink` (Animation)

```python
Blink(rate: rate.Rate | float = '1/4', *, duty: float = 0.5, off_color: Color | None = None)
```

On for `duty` of each period, off (transparent, or `off_color`) for the rest.

- **`apply(cells, time)`**

### `Pulse` (Animation)

```python
Pulse(rate: rate.Rate | float = '1/2', *, minimum: float = 0.2)
```

Brightness breathes between `minimum` and full once per period.

- **`apply(cells, time)`**

### `Fade` (Animation)

```python
Fade(duration: rate.Rate | float = 0.3, *, out: bool = False)
```

Fades in (or out with `out = True`) once over `duration`. A widget
drops a finished fade; after fading out it is hidden.

- **`amount(time: Time)`**
- **`apply(cells, time)`**
- **`finished(time)`**

### `now(transport = None)`

The current Time: from `transport` (anything with bpm, beats, playing, signature) if given.

## `pyxelwidgets.message`

Messages for other software (a DAW, a synth, an OSC app): MIDI messages, OSC
messages and control surface commands (Mackie Control, HUI). A message is a
template: each field is a constant or a `Source` taken from a widget event:

    NoteOn(note = 36, velocity = Source('velocity'))            # the press velocity
    NoteOn(note = Source('cell', offset = 36))                   # one note per cell
    ControlChange(control = 7, value = Source('value'))          # a fader, 0-127
    OscMessage('/track/{x+1}/mute', Source('state'))             # one track per column
    Command('Play')                                              # Mackie/HUI

`resolve(sources)` fills the fields from an event's values (see
`pyxelwidgets.mapping`); `match(message)` does the reverse for a message
received from the other software, returning the values it carries (e.g.
`{'value': 0.5}`) or None when it is a different message.

Values: `velocity`, `value`, `pressure`, `state`... are 0.0-1.0 and are
scaled to a field's range (`min`/`max` narrow it); `x`, `y`, `cell`,
`note`, `step`, `delta`... are whole numbers, moved by `offset`.

### `Source`

```python
Source(name: str, min: float | None = None, max: float | None = None, offset: int = 0)
```

A field value taken from the event: `name` is one of its values. A 0.0-1.0
value covers `min` to `max` (default: the field's whole range); a whole
number has `offset` added.

- **`integer`**
- **`get(sources: dict, low = None, high = None)`**: This source's value for a field ranging `low`-`high` (None: unbounded).
- **`recover(value, low = None, high = None)`**: The event value that gives the field `value` (the reverse of `get`).

### `Message`

Base of message templates; a template with constants only is a concrete message.

- **`resolve(sources: dict)`**: The concrete message for an event's `sources`.
- **`match(message: Message)`**: The values `message` carries if it is this message (constants equal), else None.
- **`sources`**

### `MidiMessage` (Message)

A MIDI channel message; `channel` is 1-16.

- **`to_midi()`**
- **`from_midi(midi: list)`**: The message for raw MIDI bytes (channel messages only), or None.

### `NoteOn` (MidiMessage)

```python
NoteOn(note: Any = 60, velocity: Any = Source(name='velocity', min=None, max=None, offset=0), channel: Any = 1)
```

NoteOn(note: Any = 60, velocity: Any = Source(name='velocity', min=None, max=None, offset=0), channel: Any = 1)

- **`to_midi()`**

### `NoteOff` (MidiMessage)

```python
NoteOff(note: Any = 60, velocity: Any = 0, channel: Any = 1)
```

NoteOff(note: Any = 60, velocity: Any = 0, channel: Any = 1)

- **`to_midi()`**

### `ControlChange` (MidiMessage)

```python
ControlChange(control: Any = 1, value: Any = Source(name='value', min=None, max=None, offset=0), channel: Any = 1)
```

ControlChange(control: Any = 1, value: Any = Source(name='value', min=None, max=None, offset=0), channel: Any = 1)

- **`to_midi()`**

### `ProgramChange` (MidiMessage)

```python
ProgramChange(program: Any = 0, channel: Any = 1)
```

ProgramChange(program: Any = 0, channel: Any = 1)

- **`to_midi()`**

### `PitchBend` (MidiMessage)

```python
PitchBend(value: Any = Source(name='value', min=None, max=None, offset=0), channel: Any = 1)
```

`value` is 0-16383; 8192 is the centre.

- **`to_midi()`**

### `PolyPressure` (MidiMessage)

```python
PolyPressure(note: Any = 60, pressure: Any = Source(name='pressure', min=None, max=None, offset=0), channel: Any = 1)
```

PolyPressure(note: Any = 60, pressure: Any = Source(name='pressure', min=None, max=None, offset=0), channel: Any = 1)

- **`to_midi()`**

### `ChannelPressure` (MidiMessage)

```python
ChannelPressure(pressure: Any = Source(name='pressure', min=None, max=None, offset=0), channel: Any = 1)
```

ChannelPressure(pressure: Any = Source(name='pressure', min=None, max=None, offset=0), channel: Any = 1)

- **`to_midi()`**

### `OscMessage` (Message)

```python
OscMessage(address: str = '/', *args)
```

An OSC message. `address` may hold `{source}` or `{source+1}`
placeholders; each of `args` is a constant (number or string) or a Source
(0.0-1.0 values are sent as they are unless `min`/`max` are given).

- **`resolve(sources: dict)`**
- **`match(message)`**
- **`sources`**

### `Command` (Message)

```python
Command(name: str = 'Play', value: Any = 1.0, flash: bool = False)
```

A control surface command (Mackie Control, HUI): a button such as
`'Play'` or `'Mute {x+1}'`, a fader (`'Fader 1'`, value 0.0-1.0), a
V-Pot (`'V-Pot 1'`, value in steps, negative turns left) or, received,
a display (`'Timecode'`, value a string). Buttons are pressed while
`value` > 0. Received LEDs set `flash` when blinking.

- **`resolve(sources: dict)`**
- **`match(message)`**
- **`sources`**

### `PluginParameter` (Message)

```python
PluginParameter(track: str = '', plugin: str = '', parameter: str = '', value: Any = Source(name='delta', min=None, max=None, offset=0))
```

A plug-in parameter, through a control surface's plug-in mode (Mackie
Control): `track`, `plugin` and `parameter` are names as the
surface scanned them from the DAW (`scan_tracks`, `scan_plugins`,
`scan_parameters`). `value` is V-Pot steps (a knob's or fader's
`delta`); received, it is the parameter's position 0.0-1.0.

### `Hotkey` (Message)

```python
Hotkey(keys: str = 'ctrl+c')
```

Press `keys` together, then let go: `'ctrl+c'`, `'cmd+shift+4'`, `'f{x+1}'` (one per column).

- **`resolve(sources: dict)`**
- **`sources`**

### `Key` (Message)

```python
Key(keys: str = 'shift', state: Any = Source(name='value', min=None, max=None, offset=0))
```

Hold `keys` down while `state` is above 0, let go at 0 (e.g. push to talk, a held Shift).

- **`resolve(sources: dict)`**
- **`sources`**

### `TypeText` (Message)

```python
TypeText(text: str = 'Hello')
```

Type `text` (placeholders such as `{x+1}` take a value from the event).

- **`resolve(sources: dict)`**
- **`sources`**

### `MouseMove` (Message)

```python
MouseMove(x: Any = Source(name='value_x', min=None, max=None, offset=0), y: Any = Source(name='value_y', min=None, max=None, offset=0), relative: bool = False)
```

Move the pointer: to `x`, `y` on the main screen (0.0-1.0 from the
bottom-left, e.g. an XY's `value_x`/`value_y`), or with `relative`
by `x`, `y` pixels (positive y is up).

### `MouseButton` (Message)

```python
MouseButton(button: str = 'left', state: Any = Source(name='value', min=None, max=None, offset=0))
```

Hold a mouse `button` (left, right, middle) down while `state` is above 0, let go at 0 (dragging).

### `MouseClick` (Message)

```python
MouseClick(button: str = 'left', count: Any = 1)
```

Click a mouse `button` (left, right, middle) `count` times (2: a double click).

### `Scroll` (Message)

```python
Scroll(dx: Any = 0, dy: Any = Source(name='delta', min=None, max=None, offset=0))
```

Scroll by `dx`, `dy` steps (positive dy is up), e.g. a knob's `delta`.

### `parse_keys(keys: str)`

`'ctrl+shift+s'` → `('ctrl', 'shift', 's')`; raises ValueError for unknown keys.

# Widgets

## `pyxelwidgets.widgets`

### `Propagation` (Enum)

What happens to a press after a widget handles it, when widgets overlap.

Stop: widgets underneath don't receive it (default).
Pass: it continues to the widget underneath (default for display-only widgets).

Members: `Stop`, `Pass`.

### `Widget` (Emitter)

```python
Widget(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, name: str | None = None, active_color: Color = Colors.White, inactive_color: Color = Colors.Black, visible: bool = True, propagation: Propagation = Propagation.Stop)
```

Base class for all widgets: a rectangle of pads with its own frame buffer.

A widget works on its own: feed it input with `press`/`release`/...,
call `render()` and read `buffer`. Subscribe to its events with `on`.
Subclasses override `draw` and the `handle_*` input hooks.

**Parameters**

- `x, y: int`: Position in the parent Group, from left to right and bottom to top.
- `width, height: int`: Size in pads, should be >= 1.
- `name: str, optional`: Label used to find the widget in a Group. Defaults to `<ClassName>_<n>`.
- `active_color: Color = Colors.White, optional`: Color of active pads.
- `inactive_color: Color = Colors.Black, optional`: Color of inactive pads.
- `visible: bool = True, optional`: Hidden widgets are neither drawn nor receive input in a Group.
- `propagation: Propagation = Propagation.Stop, optional`: Whether a press continues to overlapped widgets underneath.

- classmethod **`events()`**: Every event class the widget emits, its base classes' included.
- **`visible`** (settable)
- **`x`** (settable)
- **`y`** (settable)
- **`width`** (settable)
- **`height`** (settable)
- **`configure(**options)`**: Change options after construction, given as the constructor takes them (`fader.configure(active_color = Colors.Red, visible = False)`), plus `x`, `y`, `width` and `height`; the widget redraws. Changes are kept in `configured`. Raises AttributeError for unknown options.
- **`press(x: int, y: int, velocity: float = 1.0)`**: Press the pad at widget coordinates `x`, `y`.
- **`release(x: int, y: int, velocity: float = 0.0)`**
- **`hold(x: int, y: int, velocity: float = 1.0)`**
- **`double_press(x: int, y: int, velocity: float = 1.0)`**
- **`pressure(x: int, y: int, pressure: float)`**: The pressure (aftertouch) of the held pad at `x`, `y` changed.
- **`tap(x: int, y: int, velocity: float = 1.0)`**: Press and release the pad at `x`, `y`.
- **`input(event: PadEvent)`**: Deliver a device pad event whose `x`, `y` are already widget coordinates. Returns True if it should not reach widgets underneath.
- **`handle_press(x: int, y: int, velocity: float)`**: Override to react to a press; `velocity` is 1.0 on pads without velocity.
- **`handle_release(x: int, y: int, velocity: float)`**: Override to react to a release.
- **`handle_hold(x: int, y: int, velocity: float)`**: Override to react to a pad held longer than the controller's `held_time`.
- **`handle_double_press(x: int, y: int, velocity: float)`**: Override to react to a double press.
- **`handle_pressure(x: int, y: int, pressure: float)`**: Override to react to pad pressure (aftertouch) on pads that report it.
- **`render(time: animation.Time | None = None)`**: Redraw `buffer` if needed, and apply animations at `time` (default: now, at 120 bpm); returns True if it changed.
- **`save_state()`**: What input changed in the widget (its value, pressed cells, steps...), to restore on another instance with `load_state`, e.g. after rebuilding a layout. Options aren't included.
- **`load_state(state: dict)`**: Restore `save_state` data without emitting events; parts that don't fit are skipped.
- **`receive(values: dict)`**: Show state sent from elsewhere (e.g. a DAW, through a Mapping) without emitting events. `values` are what the message carried: `value`, `state`, `velocity`, `x`/`y`/`cell`, `text`, `flash`... Subclasses override it; a blinking state (`flash`) blinks the widget.
- **`animation`** (settable): An Animation of the whole widget (e.g. `Blink('1/8')`), or None.
- **`animate_cell(x: int, y: int, animation)`**: Animate the cell at widget `x`, `y`; None stops animating it.
- **`draw()`**: Override to draw the whole widget into `self.buffer`. Set `self.updated` to keep animating.

### `ValueWidget` (Widget)

```python
ValueWidget(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, value = 0.0, interactive: bool = True, **kwargs)
```

A widget with a single value set by input: a float from 0.0 to 1.0 by default.
Input emits `Changed`; setting `value` from code doesn't.

- `value: optional`: Initial value.
- `interactive: bool = True, optional`: If False, input doesn't change the value (`Changed` is still emitted), e.g. for widgets that only mirror state sent back from a DAW.

- **`value`** (settable)
- **`save_state()`**
- **`load_state(state: dict)`**
- **`receive(values: dict)`**: Take `value` (or `value_x`/`value_y`, or another 0.0-1.0 state) without emitting `Changed`.
- **`set_value(value)`**: Set the value as input would: respects `interactive` and emits `Changed`.

### `Button` (ValueWidget)

```python
Button(x: int, y: int, width: int, height: int, *, mode: Button.Mode = Button.Mode.Button, **kwargs)
```

A pad area acting as one button: momentary (Button), toggle (Switch) or toggle on hold (Mixed).

- **`handle_press(x: int, y: int, value: float)`**
- **`handle_release(x: int, y: int, value: float)`**
- **`handle_hold(x: int, y: int, value: float)`**
- **`receive(values: dict)`**
- **`save_state()`**
- **`load_state(state: dict)`**
- **`draw()`**

#### `Mode` (Enum)

An enum.

Members: `Button`, `Switch`, `Mixed`.

### `ButtonGroup` (Widget)

```python
ButtonGroup(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, mode: ButtonGroup.Mode = ButtonGroup.Mode.Switch, **kwargs)
```

A grid of buttons: one selected at a time (Switch), toggles (Multi) or momentary (Button); emits Toggled.

- **`handle_press(x: int, y: int, value: float)`**
- **`handle_release(x: int, y: int, value: float)`**
- **`save_state()`**
- **`load_state(state: dict)`**
- **`receive(values: dict)`**: Turn the cell at `x`, `y` (or `cell`) on or off without emitting Toggled.
- **`draw()`**

#### `Mode` (Enum)

An enum.

Members: `Button`, `Switch`, `Multi`.

### `Fader` (ValueWidget)

```python
Fader(x: int, y: int, width: int, height: int, *, direction: Fader.Direction = Fader.Direction.Vertical, grid: Fader.Grid = Fader.Grid.Simple, type: Fader.Type = Fader.Type.Wrap, mode: Fader.Mode = Fader.Mode.Multi, resolution: int = 4, **kwargs)
```

A fader along a row or column (or across the whole area with Matrix grid), drawn in several styles.

**Description**

Fader class implements Widget class

**Parameters**

- `name: str`: Unique widget name, used to find widgets registered on window.
- `x: int`: x axis where widget will be placed on window, from left to right. x value should be positive
- `y: int`: y axis where widget will be placed on window, from bottom to top. y value should be positive.
- `width: int`: Widget width, should >= 1
- `height: int`: Widget height, should >= 1

**Optional Parameters**

- `callback: function`: If widget value is changed this function will be called. Should accept 3 parameters, (widget) name, event and value
- `active_color: [r: int, g: int, b: int] = [255, 255, 255]`: If widget value is non-zero, this color will be used.
- `inactive_color: [r: int, g: int, b: int] = [0, 0, 0]`: If widget value is zero, this color will be used.
- `value: int = 0.0`: Default value of widget.
- `direction: Fader.Direction = Fader.Direction.Vertical`: Can be Fader.Direction.Vertical or Fader.Direction.Horizontal. This will affect how widget rendered and value is calculated. Vertical faders from bottom to top, horizontal faders from left to right.
- `grid: Fader.Grid = Fader.Grid.Simple`: Can be Fader.Grid.Simple or Fader.Grid.Matrix. Simple faders will use only one axis. Matrix faders will use both x and y axis.
- `type: Fader.Type = Fader.Type.Wrap`: Single: Only corresponding pad will active. BoostCut: Corresponding pads from middle active. Wrap: Corresponding pads from bottom active. Spread: Corresponding pads from middle active symmetrically.

- **`handle_press(x: int, y: int, value: float)`**
- **`handle_hold(x: int, y: int, value: float)`**
- **`handle_release(x: int, y: int, value: float)`**
- **`draw()`**

#### `Direction` (Enum)

**Description**

Vertical faders are bottom to top,
Horizontal faders are left to right.

**Enums**

Vertical

Horizontal

Members: `Vertical`, `Horizontal`.

#### `Grid` (Enum)

**Description**

Determines how multi-width vertical faders
or multi-height horizontal faders will work

**Enums**

Simple

Matrix

Members: `Simple`, `Matrix`.

#### `Type` (Enum)

An enum.

Members: `Single`, `BoostCut`, `Wrap`, `Spread`, `Collapse`.

#### `Mode` (Enum)

An enum.

Members: `Simple`, `Multi`, `Magnitude`, `Sensitive`, `Relative`.

### `Keyboard` (Widget)

```python
Keyboard(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, octave: int = 0, fold: int = 4, type: Keyboard.Type = Keyboard.Type.Diatonic, scale: Keyboard.Scale = Keyboard.Scale.Major, root: Keyboard.Root = Keyboard.Root.C, root_color: Color = Colors.Fuchsia, keyboard_color: Color = Colors.Aqua, non_scale_color: Color = Colors.Yellow, active_color: Color = Colors.Green, **kwargs)
```

A playable note layout (piano, chromatic or in-scale) emitting NoteOn and NoteOff.

- **`octave`** (settable)
- **`fold`** (settable)
- **`type`** (settable)
- **`scale`** (settable)
- **`root`** (settable)
- **`root_color`** (settable)
- **`keyboard_color`** (settable)
- **`non_scale_color`** (settable)
- **`handle_press(x: int, y: int, value: float)`**
- **`handle_release(x: int, y: int, value: float)`**
- **`draw()`**

#### `Type` (Enum)

An enum.

Members: `Keyboard`, `ChromaticVertical`, `ChromaticHorizontal`, `Diatonic`, `DiatonicVertical`, `DiatonicHorizontal`.

#### `Scale` (Enum)

An enum.

Members: `Major`, `Minor`, `Dorian`, `Mixolydian`, `Lydian`, `Phrygian`, `Locrian`, `Diminished`, `WholeHalf`, `WholeTone`, `MinorBlues`, `MinorPentatonic`, `MajorPentatonic`, `MinorHarmonic`, `MinorMelodic`.

#### `Root` (Enum)

An enum.

Members: `C`, `CS`, `D`, `DS`, `E`, `F`, `FS`, `G`, `GS`, `A`, `AS`, `B`.

### `Knob` (ValueWidget)

```python
Knob(x: int, y: int, width: int, height: int, *, coefficient: float = 0.05, type: Knob.Type = Knob.Type.Wrap, **kwargs)
```

A value shown around the border of the area; holding a pad turns it continuously.

- **`handle_press(x: int, y: int, value: float)`**
- **`handle_release(x: int, y: int, value: float)`**
- **`tick()`**
- **`draw()`**

#### `Type` (Enum)

An enum.

Members: `Single`, `BoostCut`, `Wrap`, `Spread`, `Collapse`.

### `Clock` (Enum)

What plays a timed widget (Sequencer, Tracker, ClipLauncher) every `rate`.

Transport: the transport, at its tempo, only while it plays (default).
Own: a clock of its own at the widget's `bpm`, running whether the transport plays or not.
Off: nothing; only `play`/`advance` calls (e.g. from links) play it.

Members: `Transport`, `Own`, `Off`.

### `Timed`

```python
Timed(*args, clock: Clock = Clock.Transport, bpm: float = 120.0, running: bool = True, **kwargs)
```

Mixin for widgets a clock plays every `rate`. Widgets don't know about
clocks: glue (`App.attach`, `Parser.attach`, `Parser.start_clocks`) calls `tick`
from the transport or from a clock of the widget's own.

- `clock: Clock = Clock.Transport, optional`: What plays it every `rate`: the transport, its own clock at `bpm`, or nothing (links only).
- `bpm: float = 120.0, optional`: The tempo of its own clock (`clock = Clock.Own`).
- `running: bool = True, optional`: Played by its clock; False pauses it (`start`/`stop`/`toggle`).

- **`tick(count: int)`**: Called by its clock with the number of `rate` lengths since it started: while `running`, the transport places it at `count`, its own clock moves it one on (so it resumes where it paused).
- **`silence()`**: End what's sounding (a Sequencer's gate); glue calls it when the clock stops.
- **`start()`**
- **`stop()`**
- **`toggle()`**

### `Sequencer` (Timed, Widget)

```python
Sequencer(x: int, y: int, width: int, height: int, *, steps: int | None = None, rate: rate.Rate = '1/16', step: int = 0, page: int = 0, follow: bool = True, swing: float = 50.0, gate: float = 0.5, gate_random: float = 0.0, current_color: Color = Colors.Lime, current_active_color: Color = Colors.Red, **kwargs)
```

Step sequencer. Each step plays when `play(step)` or `advance()` is
called; its `clock` (the transport, one of its own, or none) does every
`rate`, with `swing`. Emits StepPlayed, and StepEnded when an active
step's `gate` ends. Steps beyond one screen are on pages: `page` is the
one shown and edited.

- `step: int = 0, optional`: The current (playing) step.
- `page: int = 0, optional`: The page shown and edited.
- `follow: bool = True, optional`: Show the page of the playing step when it plays.
- `swing: float = 50.0, optional`: Where every second step starts, in percent of a pair of steps: 50 is straight, 66 a triplet feel, 75 the most. Needs a clock (calls of `play`/`advance` aren't delayed).
- `gate: float = 0.5, optional`: How long an active step sounds, in steps (up to 1): StepEnded then. Without a clock it ends when the next step plays.
- `gate_random: float = 0.0, optional`: Each hit's gate is longer or shorter by up to this many steps, at random.

- **`pages`**
- **`page`** (settable)
- **`step`** (settable): The current step; setting it moves there without playing it.
- **`steps`** (settable)
- **`current`** (settable)
- **`play(step: int)`**: Move to `step` (wrapped to `steps`) and emit StepPlayed; a sounding step ends first.
- **`silence()`**: End the sounding step's gate now (StepEnded), e.g. when the clock stops.
- **`tick(count: int)`**: Called by its clock `divisions` times a step: plays steps (every second one late by `swing`) and ends gates. `count` counts divisions.
- **`advance()`**: Play the next step.
- **`handle_press(x: int, y: int, value: float)`**
- **`save_state()`**
- **`load_state(state: dict)`**
- **`reset()`**: Clear every step.
- **`draw()`**

### `Sprite` (Widget)

```python
Sprite(x: int, y: int, width: int, height: int, *, frames: widgets.Frames | None = None, rate: rate.Rate | float | None = None, propagation: Propagation = Propagation.Pass, **kwargs)
```

Shows a picture, or animates through `frames` changing every `rate`
(a note value, or seconds). Display-only: presses pass through by default.

- **`render(time: animation.Time | None = None)`**
- **`draw()`**

### `Tracker` (Timed, Widget)

```python
Tracker(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, bars: int = 64, pages: int = 1, rate: rate.Rate = '1/16', step: int = 0, page: int = 0, bar: int = 0, follow: bool = True, current_color: Color = Colors.Aqua, current_active_color: Color = Colors.Fuchsia, **kwargs)
```

A scrolling step grid where rows are steps and columns are tracks. Rows
play when `play(row)` or `advance()` is called; its `clock` does
every `rate`. Emits RowPlayed. The rows shown and edited start at
`bar` (top) on `page`.

- `step: int = 0, optional`: The current (playing) row over all pages: `page * bars + bar`.
- `page: int = 0, optional`: The page shown and edited.
- `bar: int = 0, optional`: The first row shown, at the top.
- `follow: bool = True, optional`: Scroll to the playing row when it plays.

- **`step`** (settable): The current row over all pages: `current_page * bars + current_bar`; setting it moves there without playing it.
- **`page`** (settable): The page shown and edited.
- **`bar`** (settable): The first row shown (at the top), from 0 to `bars - height`.
- **`current_top`**
- **`current_bottom`**
- **`handle_press(x: int, y: int, value: float)`**
- **`play(step: int)`**: Move to `step` (wrapping through rows, then pages) and emit RowPlayed with the row's active columns.
- **`advance()`**: Play the next row.
- **`scroll(step: int)`**: Move to `step` without playing it; with `follow` the view keeps the row in the middle.
- **`save_state()`**
- **`load_state(state: dict)`**
- **`draw()`**

### `DrumPads` (Widget)

```python
DrumPads(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, note: int = 36, bank: int = 0, velocity: bool = True, active_color: Color = Colors.Orange, inactive_color: Color = Color(64, 32, 0), **kwargs)
```

Drum pads: one note per pad, `note` at the bottom-left, then left to
right and up (4x4 from 36 is the General MIDI kit), moved by `bank`
times the pads. Emits NoteOn/NoteOff; pads light while held (brighter for
harder hits) and for notes received, e.g. a DAW playing the pattern back.

- `note: int = 36, optional`: The note of the bottom-left pad.
- `bank: int = 0, optional`: Moves every pad's note by this many times the number of pads (e.g. linked to bank buttons).
- `velocity: bool = True, optional`: Light pads by how hard they're hit (and pressed); else fully.

- **`note_at(x: int, y: int)`**: The note of the pad at `x`, `y`, or None if it is beyond 127.
- **`handle_press(x: int, y: int, velocity: float)`**
- **`handle_release(x: int, y: int, velocity: float)`**
- **`handle_pressure(x: int, y: int, pressure: float)`**
- **`receive(values: dict)`**: Light the pad of a received `note` (or `x`/`y`, `cell`) by its velocity or value.
- **`draw()`**

### `Meter` (ValueWidget)

```python
Meter(x: int, y: int, width: int, height: int, *, direction: Meter.Direction = Meter.Direction.Vertical, warning: float = 0.6, danger: float = 0.85, hold: float = 1.0, falloff: float = 0.0, active_color: Color = Colors.Lime, warning_color: Color = Colors.Yellow, danger_color: Color = Colors.Red, interactive: bool = False, propagation: Propagation = Propagation.Pass, clock: Callable[[], float] = time.monotonic, **kwargs)
```

A level meter: the value lights a bar from the bottom (or the left), in
`active_color` up to `warning`, `warning_color` up to `danger` and
`danger_color` above. The highest level stays lit for `hold` seconds.
Display only: values come from links, mappings (a DAW's meters) or code.

- `warning, danger: float, optional`: Levels (0.0-1.0) where the bar turns `warning_color` and `danger_color`.
- `hold: float = 1.0, optional`: Seconds the peak stays lit; 0 doesn't show it.
- `falloff: float = 0.0, optional`: How fast the bar falls, in full heights per second; 0 falls at once (e.g. meters a DAW already smooths).

- **`level`**: The level shown: the value, or above it while falling.
- **`peak`**
- **`render(time = None)`**
- **`draw()`**

#### `Direction` (Enum)

An enum.

Members: `Vertical`, `Horizontal`.

### `ClipLauncher` (Timed, Widget)

```python
ClipLauncher(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, rate: rate.Rate = 'bar', filled: bool = True, blink_rate: rate.Rate | float = '1/8', active_color: Color = Colors.Lime, inactive_color: Color = Color(0, 72, 72), empty_color: Color = Colors.Black, **kwargs)
```

A grid of clips, columns are tracks and rows scenes (scene 0 at the top).
Pressing a clip queues it (blinking) and it starts on the next `rate`
from its clock, a bar by default, stopping the track's playing clip;
pressing a playing clip queues it to stop (pulsing). Without a clock
(`clock = Clock.Off`) clips start and stop at once. Emits ClipQueued,
ClipStarted and ClipStopped.

- `rate: Rate = 'bar', optional`: When queued clips start and stop: every `rate` of its clock.
- `filled: bool = True, optional`: Every slot starts with a clip; False starts empty (clips come from a DAW).
- `blink_rate: Rate | float = '1/8', optional`: How fast queued clips blink.
- `active_color, inactive_color, empty_color: Color, optional`: Playing clips, stopped clips and empty slots.

- **`playing(track: int)`**: The row of the clip playing in `track`, or None.
- **`handle_press(x: int, y: int, velocity: float)`**
- **`queue(x: int, y: int, launch: bool)`**: Start (`launch`) or stop the clip at `x`, `y` on the next `rate`, or at once without a clock.
- **`launch_scene(scene: int)`**: Queue the clips of `scene` (a row, 0 at the top); tracks without one stop.
- **`stop_track(track: int)`**: Queue the clip playing in `track` (a column) to stop.
- **`stop_all()`**
- **`play(count: int | None = None)`**: Start and stop the queued clips (called every `rate` by its clock).
- **`advance()`**: Start and stop the queued clips now.
- **`receive(values: dict)`**: Show a clip's state from elsewhere (a DAW): at `x`/`y` (or `cell`), playing if the value is above 0, else stopped; `flash` shows it queued.
- **`save_state()`**
- **`load_state(state: dict)`**
- **`draw()`**

### `XY` (ValueWidget)

```python
XY(x: int, y: int, width: int, height: int, *, x_color: Color = Colors.Aqua, y_color: Color = Colors.Fuchsia, value: tuple = (0.0, 0.0), **kwargs)
```

A two dimensional value (x, y) set by pressing anywhere in the area.

- **`handle_press(x: int, y: int, value: float)`**
- **`handle_hold(x: int, y: int, value: float)`**
- **`handle_release(x: int, y: int, value: float)`**
- **`draw()`**

#### `Direction` (Enum)

An enum.

Members: `Vertical`, `Horizontal`.

### `Text` (Widget)

```python
Text(x: int, y: int, width: int, height: int, *, text: str = '', align: Text.Align = Text.Align.Left, scroll: Text.Scroll = Text.Scroll.Auto, speed: float = 8.0, inactive_color: Color = Colors.Invisible, propagation: Propagation = Propagation.Pass, clock: Callable[[], float] = time.monotonic, **kwargs)
```

Text in a 3x5 pixel font (`pyxelwidgets.font`), e.g. a tempo or a track
name, vertically centered. Text that doesn't fit scrolls (`scroll`) at
`speed` columns per second. Display only: presses pass through.

- **`text`** (settable)
- **`save_state()`**
- **`load_state(state: dict)`**
- **`receive(values: dict)`**: Show received `text` (e.g. a DAW's track name or timecode).
- **`scrolling`**
- **`render(time = None)`**
- **`draw()`**

#### `Align` (Enum)

An enum.

Members: `Left`, `Center`, `Right`.

#### `Scroll` (Enum)

An enum.

Members: `Auto`, `Always`, `Off`.

## `pyxelwidgets.group`

### `Group` (Widget)

```python
Group(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, background: Color = Colors.Invisible, propagation: Propagation = Propagation.Pass, **kwargs)
```

A widget made of widgets. Children are positioned relative to the group and
drawn in the order they were added: later children are on top, and
transparent pixels show the children underneath. Groups can be nested.

Input goes to the topmost visible child under the press; if that child's
`propagation` is `Pass` it continues to the next child underneath.
A group itself passes presses on its empty area through by default.

Children never know their group: it notices changes by rendering them.

- **`background`** (settable): The color of the area no child covers (the group's `inactive_color`).
- **`children`**: Children from bottom to top.
- **`add(widget: Widget)`**: Add `widget` on top of the existing children and return it.
- **`extend(widgets)`**
- **`remove(widget)`**: Remove a child, given the widget or its name.
- **`clear()`**
- **`find(name: str)`**: The child named `name`, or None.
- **`input(event: PadEvent)`**
- **`render(time = None)`**
- **`draw()`**

### `Pages` (Group)

```python
Pages(x: int = 0, y: int = 0, width: int = 1, height: int = 1, *, page: int = 0, selector: Pages.Selector = Pages.Selector.Top, current_color: Color = Colors.White, selector_color: Color = Color(48, 48, 48), propagation: Propagation = Propagation.Stop, **kwargs)
```

A group whose children are pages: only the current `page` is shown and
gets input. An optional `selector` strip along one side has a cell per
page; pressing one switches to that page. Emits PageChanged.

Pages usually fill `content`, the area besides the selector.

- **`pages`**
- **`page`** (settable)
- **`save_state()`**
- **`load_state(state: dict)`**
- **`current`**: The widget of the current page, or None without pages.
- **`next()`**
- **`previous()`**
- **`content`**: The area for pages, relative to this widget: everything but the selector.
- **`add(widget: Widget)`**
- **`remove(widget)`**
- **`input(event: PadEvent)`**
- **`draw()`**

#### `Selector` (Enum)

An enum.

Members: `Off`, `Top`, `Bottom`, `Left`, `Right`.

# Time, controls and outputs

## `pyxelwidgets.transport`

Musical time. A Transport keeps the tempo, time signature, play state and
position, and calls subscribers at musical rates:

    transport = Transport(120)
    transport.every('1/16', sequencer.play)   # called with the 16th note count
    transport.play()

Rates are note values: `'1/4'`, `'1/16'`, dotted `'1/8.'`, triplet
`'1/8T'`, whole notes `'1'` or `'2'`, and `'beat'` or `'bar'` from
the time signature.

The internal timer calls subscribers in order from one thread, which runs only
while playing. To follow an external clock instead (e.g. a DAW's MIDI clock),
create the Transport with `sync = True` and forward the MIDI realtime
messages: Timing Clock → `pulse()`, Start → `locate(0)` and `play()`,
Continue → `play()`, Stop → `stop()`, Song Position → `locate(sixteenths / 4)`.

### `Transport` (Emitter)

```python
Transport(bpm: float = 120.0, *, signature: tuple = (4, 4), ppq: int = 96, sync: bool = False, lock = None)
```

Tempo, time signature, play/stop and the position, counted in `tick`
(`ppq` ticks per quarter note: 96, so a 16th note's swing can move in
24ths of it). Emits TransportStarted, TransportStopped,
TransportLocated and TempoChanged.

`lock` (e.g. a Surface's lock) is held while calling subscribers and
handlers; it must be reentrant so they may control the transport.

- **`bpm`** (settable)
- **`signature`** (settable): Time signature as (beats per bar, beat note value), e.g. (6, 8).
- **`ppq`**
- **`sync`**: Following an external clock through `pulse()` instead of the internal timer.
- **`playing`**
- **`tick`**: The next tick to play.
- **`beats`**: Position in quarter notes.
- **`bar`**: Bar of the position, counted from 0.
- **`beat`**: Beat within the bar, counted from 0, in the signature's beat note value.
- **`ticks(rate)`**: Length of `rate` in ticks, e.g. `'1/16'` → 24 at 96 ppq.
- **`play()`**: Play from the current position; the first tick plays right away (with `sync`, on the next `pulse()`).
- **`stop()`**: Stop at the current position; `play()` continues from there.
- **`toggle()`**
- **`locate(beats: float = 0)`**: Move to `beats` quarter notes from the start; while playing, that position plays next.
- **`close()`**: Stop and wait for the timer thread to finish.
- **`every(rate, callback: Callable | None = None, *, offset = 0, divisions: int = 1)`**: Call `callback(count)` every `rate` while playing, where `count` is the number of `rate` lengths since the start (e.g. the 16th note number), so the callback follows `locate` too. `offset` (a rate, e.g. `'1/32'`) delays the calls. With `divisions` the callback is called that many times per `rate` (as often as ticks allow; counts in between may be skipped), counting divisions: a Sequencer times swing and gates with them. Returns a Subscription; usable as a decorator, which returns the function.
- **`cancel(subscription)`**: Remove a Subscription, or every subscription of a callback.
- **`subscriptions`**
- **`pulse()`**: One MIDI Timing Clock (24 per quarter note): advances while playing. The tempo is measured once a beat, averaged over up to 4 beats.

### `Subscription`

```python
Subscription(transport, rate, callback: Callable, offset, divisions: int = 1)
```

A callback made every `rate` by a Transport; `cancel()` removes it.

- **`cancel()`**

### `parse_rate(rate, signature: tuple = (4, 4))`

Length of `rate` in whole notes, e.g. `'1/8.'` → 3/16. Raises ValueError.

### `parse_signature(signature)`

A time signature as (beats per bar, beat note value), e.g. `[6, 8]` → (6, 8). Raises ValueError.

## `pyxelwidgets.binding`

Bindings connect a device's named controls (knobs, faders, encoders, buttons)
to widgets or actions:

    surface.bind(device, 'Knob1', volume)                        # glides to the knob
    surface.bind(device, 'Knob2', pan, takeover = Takeover.Pickup)
    surface.bind(device, 'Encoder1', cutoff, step = 1 / 64)      # relative
    surface.bind(device, 'XFader', xy, axis = 0)                 # one axis of an XY
    surface.bind(device, 'Play', transport.toggle)               # an action

Knobs and faders (ControlChanged) set the widget's value; `takeover` decides
what happens when they disagree with it. Encoders (ControlTurned) add
`delta * step`. Buttons (ControlPressed/Released) press and release the
widget, e.g. a Button. An action (any callable) is called with no arguments on
press, the value for knobs and faders, and the delta for encoders.

A Binding also works without a Surface: `Binding(device, 'Knob1', fader)`;
call `update()` regularly (e.g. every frame) so gliding progresses.

### `Binding`

```python
Binding(source, control: str, target, *, device = None, takeover: Takeover = Takeover.Glide, glide_time: float = 0.3, step: float = 0.015625, axis: int | None = None, clock: Callable[[], float] = time.monotonic)
```

Connects `control` events from `source` (a device, or a Surface with
`device` naming which device) to `target`: a widget with a 0.0-1.0
`value` (or a tuple, with `axis`), or a callable.

`glide_time` is how long a glide across the whole range takes, in seconds.

- **`close()`**: Stop following the control.
- **`is_action`**
- **`get()`**
- **`set(value: float)`**
- **`update()`**: Move a glide along; call it regularly (a Surface does every frame).

### `Takeover` (Enum)

What an absolute control does when its position differs from the widget's value.

Members: `Glide`, `Pickup`, `Jump`.

## `pyxelwidgets.mapping`

Mappings send a widget's events to an output (a MIDI port, OSC, Mackie
Control, ...) as messages, and with `feedback` show what the other side
sends back on the widget:

    from pyxelwidgets.message import NoteOn, NoteOff, ControlChange, Command, Source

    Mapping(kick, synth, NoteOn(36), on = Pressed)                 # velocity from the press
    Mapping(kick, synth, NoteOff(36), on = Released)
    Mapping(volume, synth, ControlChange(7), on = Changed, feedback = True)
    Mapping(play, mackie, Command('Play'), on = Pressed, feedback = True)   # LED follows the DAW
    Mapping(clock, mackie, Command('Timecode', Source('text')), feedback = True)

The message's Sources come from the event (see `sources`): its fields
(`velocity`, `value`, `x`, `state`, `note`...) plus `cell` (the
pad's number in the widget, left to right from the bottom row), `delta` (a
value change in 1/127 steps) and `value_x`/`value_y` for two-axis values.

Feedback calls `widget.receive(values)` with what the received message
carries; widgets show it without emitting events, so nothing is sent back.
`surface.map(...)` creates mappings holding the surface's lock.

### `Mapping`

```python
Mapping(widget, output, message, *, on: type | None = None, feedback: bool = False, lock = None)
```

Sends `message` resolved from each `on` event of `widget` to
`output` (anything with `send(message)`); with `feedback`, messages
the output receives that match `message` update the widget. Without
`on` it only receives. `lock` is held while updating the widget.

- **`close()`**

### `sources(event, widget = None, last_value = None)`

The values a message can take from `event`.

### `available(event_type: type)`

Names of the values events of `event_type` give a message.

## `pyxelwidgets.link`

Links let a widget change another widget's options when it emits an event,
the way mappings send messages:

    Link(show, panel, 'visible', Source('value'), on = Changed)            # a switch shows a group
    Link(up, keys, 'octave', 1, on = Pressed, change = Link.Change.Add, maximum = 4)
    Link(tabs, pages, 'page', Source('cell'), on = Toggled)               # a ButtonGroup picks the page
    Link(level, pad, 'active_color', Source('value'), on = Changed)       # a fader dims a color
    Link(mode, fader, 'mode', on = Pressed, change = Link.Change.Toggle)  # next Fader.Mode

Without an option the target is an action, called on each event, with the
value as its argument if there is one:

    Link(play, transport.toggle, on = Pressed)
    Link(step, sequencer.advance, on = Pressed)
    Link(pads, sequencer.play, value = Source('cell'), on = Pressed)     # jump to a step

The value is a constant or a `Source` from the event (see
`pyxelwidgets.mapping.sources`), turned into what the option holds:

- 0.0-1.0 values (`value`, `velocity`...) cover `minimum` to `maximum`:
  numbers (default 0-1, 0-127 for whole numbers), colors (default black to the
  option's color when linked), enum members (default all of them) and text;
  for on/off options anything above 0 is on.
- Whole numbers (`x`, `cell`, `step`, `delta`...) have the source's
  `offset` added; for enums they are a member's index.

`Change.Add` adds the value to numbers (or moves that many enum members);
a source is added as the event has it (`delta` steps, or 0.0-1.0).
`Change.Toggle` flips on/off options and steps enums to the next member.
Numbers end up clamped to `minimum`/`maximum` when given; a reversed
range (`minimum = 8, maximum = 7`) turns a 0.0-1.0 value around.

The value can also be a `Condition`: an event value compared with a
constant chooses between two values:

    # Sequencer n shows only while cell n is chosen (16 links, one per sequencer)
    Link(tabs, sequencers[n], 'visible', Condition(Source('cell'), '==', n), on = Toggled)
    Link(tabs, pad, 'active_color', Condition(Source('x'), '<', 4, Colors.Red, Colors.Blue), on = Toggled)

An action's value is a number: 0.0-1.0 sources cover `minimum` to
`maximum` (whole numbers if both are), whole number sources add `offset`.
A text value is filled in from the event: `'pad {x},{y} at {velocity}'`;
`{all}` is every value (`x=1 y=0 velocity=0.5`):

    Link(pads, print, value = 'pressed {cell}', on = Pressed)

Options change through `target.configure`, which doesn't emit events, so
links don't trigger each other in loops (Pages emits PageChanged for a new
page; a link doesn't run again while it is running).

### `Link`

```python
Link(widget, target, option: str | None = None, value = None, *, on: type, change: Link.Change = Link.Change.Set, minimum = None, maximum = None)
```

On each `on` event of `widget`, changes `option` of `target` to
`value` (`Change.Set`), by `value` (`Change.Add`) or to the next
state (`Change.Toggle`, which takes no value). Without `option`,
`target` is called (with `value` if given). See the module docs.

- **`close()`**
- **`argument(sources: dict)`**: An action's argument from the event's `sources`.
- **`apply(current, sources: dict)`**: The option's new value, from `current` and the event's `sources`.

#### `Change` (Enum)

An enum.

Members: `Set`, `Add`, `Toggle`.

### `Condition`

```python
Condition(source: Source, op: str = '==', to: Any = 0, then: Any = True, otherwise: Any = False)
```

A link value chosen by a comparison: `then` if the event's `source`
(whole numbers with their offset, 0.0-1.0 values as they are) compared
with `op` (==, !=, <, <=, >, >=) to `to` is true, else `otherwise`.

- **`test(sources: dict)`**
- **`choose(sources: dict)`**

# Putting it together

## `pyxelwidgets.surface`

### `Surface` (Emitter)

```python
Surface(width: int, height: int, *, name: str | None = None)
```

Maps a tree of widgets onto devices: routes pad input to the topmost widget
under each press, and shows the composed frame on the devices on `update()`.

Widgets live in `root`, a Group covering the whole surface; `add`,
`remove` and `find` are shortcuts for it. Devices are placed at an
offset, so several devices can form one larger surface.

Emits `Frame` before rendering each frame, and re-emits every device's
control events (ControlPressed, ControlChanged, ...). `bind` connects a
device's controls to widgets or actions, `map` sends widget events to
other software and `link` lets widgets change each other's options.

`lock` is held while processing input and rendering. Hold it when changing
widgets from another thread, e.g. a MIDI callback of your own.

- **`add(widget: pyxelwidgets.widgets.Widget)`**
- **`remove(widget)`**
- **`find(name: str)`**
- **`add_device(device: pyxelwidgets.devices.Device, x: int = 0, y: int = 0)`**: Place `device` with its bottom left pad at surface `x`, `y`.
- **`remove_device(device)`**: Remove a device, given the device or its name.
- **`bind(device, control: str, target, **kwargs)`**: Connect `device`'s `control` (e.g. `'Knob1'`) to a widget or an action; see `pyxelwidgets.binding` for the options. Glides move every frame.
- **`unbind(binding: pyxelwidgets.binding.Binding)`**
- **`map(widget, output, message, *, on: type | None = None, feedback: bool = False)`**: Send `message` to `output` on each `on` event of `widget`; with `feedback` matching messages from the output update the widget. See `pyxelwidgets.mapping`.
- **`unmap(mapping: pyxelwidgets.mapping.Mapping)`**
- **`link(widget, target, option: str | None = None, value = None, *, on: type, **kwargs)`**: Change `option` of `target` on each `on` event of `widget`; see `pyxelwidgets.link` for `value`, `change`, `minimum` and `maximum`.
- **`unlink(link: pyxelwidgets.link.Link)`**
- **`check_devices(devices = None)`**: Let `devices` (default: the surface's devices and its mappings' outputs) notice being unplugged and plugged back in, with their `check()` (MIDI devices have one). Ports are listed once, outside the lock; each check holds it. Returns the devices whose connection changed. App calls this about once a second.
- **`force_update()`**: Resend every pixel on the next update, e.g. after a device reconnected.
- **`update()`**: Render changed widgets and send changed pixels to every device.
- **`close()`**: Close all devices, and the outputs of the mappings.

## `pyxelwidgets.app`

### `App`

```python
App(surface: Surface, fps: float = 60.0, *, bpm: float = 120, signature: tuple = (4, 4), sync: bool = False, check_interval: float | None = 1.0)
```

Runs a Surface: renders at a fixed frame rate, owns a Transport whose
subscribers run under the Surface's lock, and closes everything on exit.

Input from devices and transport subscribers are handled immediately on
their own threads; the shared lock keeps them from interleaving with
rendering. The transport doesn't play until `app.transport.play()`, or
with `sync = True` it follows an external clock (see
`pyxelwidgets.devices.midi_clock`).

Every `check_interval` seconds devices notice being unplugged and
reconnect when they're back (`Surface.check_devices`); None doesn't.

- **`lock`**: Hold this when changing widgets from a thread the App doesn't manage.
- **`attach(widget)`**: Play `widget` (a Sequencer, Tracker or ClipLauncher) on its clock: the app's transport (`clock = Clock.Transport`) or a clock of its own following its `bpm` (`Clock.Own`, closed with the App). Returns the Subscription, or None for `Clock.Off`.
- **`step()`**: Render one frame; use this to drive the App from your own loop.
- **`run()`**: Run until stop(), Ctrl+C, or a device closes (e.g. the Virtual window); then close().
- **`stop()`**: Make run() return after the current frame; safe to call from any thread.
- **`close()`**

## `pyxelwidgets.parser`

Layout files: a JSON description of a Surface, the devices it is shown on and
its widgets, as written by the designer (`python -m pyxelwidgets.designer`).

    {
      "format": "pyxelwidgets.layout", "version": 6,
      "surface": {"width": 9, "height": 9},
      "transport": {"bpm": 120, "signature": [4, 4]},
      "devices": [{"type": "novation.LaunchpadMiniMK3", "x": 0, "y": 0, "options": {}}],
      "bindings": [
        {"device": 0, "control": "Top1", "widget": "volume", "options": {"takeover": "Pickup"}},
        {"device": 0, "control": "Top8", "action": "transport.toggle"}
      ],
      "outputs": [{"name": "daw", "type": "mackie.MackieControl", "virtual": "PyxelWidgets", "options": {}}],
      "mappings": [
        {"widget": "volume", "on": "Changed", "output": "daw", "feedback": true,
         "message": {"type": "Command", "name": "Fader 1", "value": {"source": "value"}}}
      ],
      "links": [
        {"widget": "show", "on": "Changed", "target": "page", "option": "visible", "value": {"source": "value"}},
        {"widget": "up", "on": "Pressed", "target": "keys", "option": "octave", "change": "Add", "value": 1, "max": 4}
      ],
      "widgets": [
        {"type": "Fader", "name": "volume", "x": 0, "y": 0, "width": 1, "height": 8,
         "options": {"active_color": "#00ffff", "mode": "Magnitude"},
         "animation": {"type": "Pulse", "options": {"rate": "1/2"}}},
        {"type": "Group", "name": "page", "x": 0, "y": 0, "width": 8, "height": 8,
         "options": {"visible": false}, "widgets": [...]}
      ]
    }

Widget options are the widget's constructor arguments: colors as `#rrggbb`
or `#rrggbbaa`, enums by member name (`"Magnitude"` for `Fader.Mode`),
rates as note values (`"1/16"`) or seconds where a widget allows both,
Sprite frames as lists of rows from the top, each a list of colors (`null`
is transparent). A widget's optional `animation` is one of `ANIMATIONS`
with its options. Older versions are upgraded on load.

`transport.sync` makes the transport follow another program's MIDI clock
(a DAW sending MIDI clock to a port): `{"input": "IAC Driver Bus 1"}` or a
virtual port it can send to, `{"virtual": "PyxelWidgets Clock"}`. Its
tempo, start, stop and position (song position) then come from there.

Bindings connect a device's named controls (by the device's index in
`devices`) to a widget, with Binding options (`takeover`, `glide_time`,
`step`, `axis`), or to an action (see `ACTIONS`).
Device inputs/outputs are optional port names; without them devices are found
by their port names.

Outputs send widget events to other software: MIDI ports, OSC, Mackie
Control, HUI (`devices` modules, with `input`/`output` port names or a
`virtual` port name). Mappings send a widget's `on` event to an output as
`message` (a class of `pyxelwidgets.message` with its fields, each a
constant or `{"source": "velocity", "min": 0, "max": 127, "offset": 0}`);
with `feedback` what the output receives updates the widget.

Links change a `target` widget's `option` (one of its options, or `x`,
`y`, `width`, `height`) on a widget's `on` event: `change` is
`Set` (default), `Add` or `Toggle`; `value` is a constant encoded like
the option, or `{"source": "value", "offset": 0}`; optional `min`/`max`
are the range a 0.0-1.0 source covers and clamp numbers (see
`pyxelwidgets.link`). A value can be a condition choosing between two:
`{"if": {"source": "cell"}, "op": "==", "to": 3, "then": true, "else": false}`
(`then`/`else` encoded like the option; true/false by default for on/off options). Instead of an option a link can call an `action`:
one of the target widget's `actions` (`advance`, `play` with a step
`value`, `next`...) or, without a target, a transport action
(`ACTIONS`: `transport.play`..., or `VALUE_ACTIONS` taking a
number: `transport.tempo`, `transport.tempo_add`), or `debug`, which
writes its `value`, a text filled in from the event (`"pad {x}"`,
`{all}`: every value; the default), to `Parser.debug`.

Load a layout and attach behaviour by widget name:

    ui = pyxelwidgets.parser.load('layout.json')
    ui['volume'].on(Changed, lambda e: print(e.value))
    app = ui.app()              # Sequencers and Trackers follow app.transport
    app.transport.play()
    app.run()

### `LayoutError` (ValueError)

A layout that doesn't describe a valid surface; the message names where.

### `register(cls: type)`

Make a widget or device class of your own usable in layouts and in the
designer (start it with `--import your_module`): widgets by their class
name, devices and outputs as `"your_module.YourClass"`. Returns `cls`,
so it works as a class decorator.

### `device_type(cls: type)`

A device class's `type` in layouts: `"novation.LaunchpadX"` for the package's, `"module.Class"` for others.

### `registered_devices()`

Device and output classes added with `register`, by type.

### `widget_types()`

Widget classes usable in layouts, by name (registered ones included).

### `color_to_text(color: Color)`

### `text_to_color(text: str)`

### `frames_to_json(frames)`

Sprite frames (RGBA buffers) as layout JSON: rows from the top, colors as text, None if transparent.

### `json_to_frames(frames)`

Layout JSON frames to RGBA buffers (see `frames_to_json`); rows may differ in length.

### `option_schema(cls)`

Layout options of a widget or device class: name, kind, default and enum choices.

### `linkable(cls)`

Options of a widget class a link can change: its position and size, then its options (not Sprite frames).

### `schema()`

Widget types with their options (kind, default, enum choices), for building editors.

### `message_schema()`

Mapping message types with their fields: name, default (encoded) and range (whole numbers) or kind.

### `message_to_json(message: Message)`

A mapping message as layout JSON.

### `message_from_json(data, where: str = 'message')`

A mapping message from layout JSON; raises LayoutError naming the field.

### `device_class(device: dict, where: str = 'device')`

The class of a layout `device` entry, e.g. `"novation.LaunchpadMiniMK3"` (or a registered one).

### `build_output(entry: dict, where: str = 'output')`

Create a layout `outputs` entry and connect it: to its ports, a `virtual` port, or (OSC) its address.

### `build_device(device: dict, where: str = 'device')`

Create a layout `device` entry and connect it to its ports (or the ports found by name).

### `Parser`

```python
Parser(layout, *, devices: bool = True)
```

Builds a Surface from a layout (a path, JSON text or a dict). `surface`,
`devices` and `widgets` (every widget by name, groups included) are
available after construction; `ui['name']` finds a widget.

With `devices = False` the devices aren't created (no ports are opened),
e.g. to validate or preview a layout.

- **`get_surface()`**
- **`get_devices()`**
- **`get_widgets()`**
- **`sync_settings()`**: The layout's `transport.sync`: `{"input": port}` or `{"virtual": port}`, the MIDI port a DAW's clock comes in through; None if the transport keeps its own time.
- **`sync_input(transport)`**: A MidiClockInput driving `transport` (created with `sync = True`) from the `sync` port, connected; None without sync.
- **`transport_settings()`**: Keyword arguments for a Transport (or App) from the layout's `transport` (bpm and signature).
- **`timed(clock: Clock)`**: The widgets (Sequencers, Trackers...) played by `clock`.
- **`attach(transport)`**: Subscribe the widgets the transport plays (`clock = Clock.Transport`) to `transport` at their `rate`; a Sequencer's sounding step ends when it stops. Returns the Subscriptions.
- **`start_clocks(*, lock = None)`**: Start a clock (a Transport, holding `lock`) for each widget with a clock of its own (`clock = Clock.Own`), following its `bpm`; returns them, to `close()` when done (`close_clocks`).
- **`close_clocks()`**
- **`app(fps: float = 60.0)`**: An App running the surface, with the widgets following its transport, and their own clocks started. With `transport.sync` the transport follows the DAW's MIDI clock (`ui.clock_input`, closed with the App).
- **`output_settings()`**: The layout's `outputs` entries, checked: unique names and known types.
- **`mapping_settings()`**: The layout's mappings as (widget name, event class or None, output name, message, feedback).
- **`map(outputs: dict)`**: Create the layout's mappings on the surface for `outputs` (by name; missing ones are skipped).
- **`link_settings()`**: The layout's links, checked, as dicts: `widget` and `target` names (target None for transport actions), `on` (event class), `option` or `action`, `value`, `change` (Link.Change), `minimum`, `maximum`.
- **`link(transport = None, *, widgets: bool = True)`**: Create the layout's links on the surface: links to widgets (with `widgets`) and, given a `transport`, transport actions. Returns the Links.
- **`binding_settings()`**: The layout's bindings as (device index, control, widget or None, action or None, Binding options).
- **`bind(devices: list, transport = None, *, widgets: bool = True)`**: Create the layout's bindings on the surface: widget bindings (with `widgets`) and, given a `transport`, action bindings. `devices` are in layout order; a missing one (None) is skipped. Returns the Bindings.

### `upgrade(layout: dict)`

`layout` converted to the current version (a copy if it changes); raises LayoutError if it isn't a layout.

### `load(layout, **kwargs)`

Build a Surface from a layout file (or JSON text, or a dict).

## `pyxelwidgets.codegen`

Python code for a layout, as the designer's Python tab shows it: a program
loading the layout file (`loader`), or one building the same surface in
code without it (`standalone`), to start from when a layout outgrows the
designer.

    print(pyxelwidgets.codegen.standalone(json.load(open('layout.json'))))

### `loader(layout: dict, file: str = 'layout.json', *, handlers: bool = False)`

A program loading `file` (holding `layout`) and running it; `handlers` prints each widget's main event.

### `standalone(layout: dict, *, handlers: bool = False, run: bool = True)`

A program building `layout` in code: the surface, devices, widgets,
outputs, mappings, bindings and links, then running it (without `run`
it stops before creating the App's loop). Raises LayoutError for an
invalid layout.

# Devices

## `pyxelwidgets.devices`

Devices: grids of pads with LEDs, plus named controls (buttons, knobs, faders,
encoders). A device works on its own: subscribe to its pad and control events
with `on` and show frames on it with `show`. A Surface connects devices to
widgets.

Concrete devices live in submodules (`pyxelwidgets.devices.novation`,
`.akai`, `.ableton`, `.presonus`, `.virtual`); importing this package
doesn't load MIDI or GUI libraries.

### `Control`

```python
Control(name: str, kind: str)
```

A named non-grid control, for `describe()`. `kind` is one of:
`button` (ControlPressed/Released), `absolute` (ControlChanged, 0.0-1.0),
`relative` (ControlTurned) or `touch` (ControlPressed/Released).

### `Device` (Emitter)

```python
Device(*, name: str | None = None, width: int | None = None, height: int | None = None, held_time: float = 1.0, double_press_time: float = 0.15)
```

Base class of all devices. Subclasses set the class attributes describing the
hardware and implement `send_pixel` (or `send_pixels` to batch).

Input: call `set_button(x, y, velocity)` for grid pads (velocity 0 releases)
and `emit` control events; the base turns pads into PadPressed, PadReleased,
PadDoublePressed and PadHeld events.

- **`width`**
- **`height`**
- classmethod **`describe()`**: The device's layout and capabilities as plain data (e.g. for a design tool).
- **`connect()`**
- **`disconnect()`**
- **`close()`**
- **`set_button(x: int, y: int, velocity: float)`**: Report a grid pad: `velocity` 0.0-1.0, where 0 is a release.
- **`set_pressure(x: int, y: int, pressure: float)`**: Report the pressure (polyphonic aftertouch) of a held grid pad, 0.0-1.0.
- **`set_channel_pressure(pressure: float)`**: Report one pressure (channel aftertouch) for every held grid pad.
- **`poll_input()`**: Emit PadHeld for pads held long enough. `show` calls this every frame.
- **`start_input_timer(interval: float = 0.01)`**: Poll for held pads on a background thread, for devices used without `show`.
- **`stop_input_timer()`**
- **`show(frame: ndarray, x: int = 0, y: int = 0)`**: Show an RGBA `frame` with its bottom left at grid `x`, `y`; only changed pixels are sent.
- **`fill(color)`**: Show one color on the whole grid.
- **`invalidate()`**: Forget what the device shows, so the next `show` sends every pixel.
- **`send_pixels(pixels: list)`**: Send `(x, y, value)` triples, values from `color_model`. Override to batch.
- **`send_pixel(x: int, y: int, value)`**

### `ColorModel`

Base class: `convert` maps `(n, 4)` uint8 RGBA cells to `n` device values.

- **`convert(rgba: ndarray)`**
- **`describe()`**

### `Levels` (ColorModel)

```python
Levels(values, gamma: bool = True)
```

Brightness mapped onto `values` (darkest first): the luminance range is
split into `len(values)` equal steps. `gamma` uses `Color.gmono`
instead of `Color.mono`.

- **`convert(rgba: ndarray)`**
- **`describe()`**

### `Palette` (ColorModel)

```python
Palette(table)
```

Index of the nearest `table` entry to the alpha blended color, like `Color.find_in_palette`.

- **`convert(rgba: ndarray)`**
- **`describe()`**

### `PassThrough` (ColorModel)

Values are `Color` objects, for devices that do their own conversion (e.g. on screen).

- **`convert(rgba: ndarray)`**

### `RGB` (ColorModel)

```python
RGB(bits: int = 8, gamma: bool = True)
```

Alpha blended, optionally gamma corrected (r, g, b) tuples with `bits` per channel.

- **`convert(rgba: ndarray)`**
- **`describe()`**

## `pyxelwidgets.devices.colors`

Color models: how a device turns RGBA frame buffer cells into the values its
LEDs understand. Each model converts many cells at once and gives the same
result as the matching per-color conversion on `Color`.

### `blend(rgba: ndarray)`

Alpha blended (r, g, b) ints for `(n, 4)` cells, like `Color.argb`.

### `ColorModel`

Base class: `convert` maps `(n, 4)` uint8 RGBA cells to `n` device values.

- **`convert(rgba: ndarray)`**
- **`describe()`**

### `PassThrough` (ColorModel)

Values are `Color` objects, for devices that do their own conversion (e.g. on screen).

- **`convert(rgba: ndarray)`**

### `RGB` (ColorModel)

```python
RGB(bits: int = 8, gamma: bool = True)
```

Alpha blended, optionally gamma corrected (r, g, b) tuples with `bits` per channel.

- **`convert(rgba: ndarray)`**
- **`describe()`**

### `Palette` (ColorModel)

```python
Palette(table)
```

Index of the nearest `table` entry to the alpha blended color, like `Color.find_in_palette`.

- **`convert(rgba: ndarray)`**
- **`describe()`**

### `Levels` (ColorModel)

```python
Levels(values, gamma: bool = True)
```

Brightness mapped onto `values` (darkest first): the luminance range is
split into `len(values)` equal steps. `gamma` uses `Color.gmono`
instead of `Color.mono`.

- **`convert(rgba: ndarray)`**
- **`describe()`**

## `pyxelwidgets.devices.input`

### `PadInput`

```python
PadInput(held_time: float = 1.0, double_press_time: float = 0.15, clock = time.monotonic)
```

Turns raw pad presses and releases into pad events: PadPressed (followed by
PadDoublePressed for a quick second press), PadReleased, and PadHeld once a
pad stays down for `held_time`. Holds are found by `poll()`, so no
thread is started per press; call it regularly (Device.show does).

Methods return `(event_class, x, y, velocity)` tuples; the caller emits them.

- **`press(x: int, y: int, velocity: float)`**
- **`release(x: int, y: int, velocity: float = 0.0)`**
- **`poll()`**: PadHeld for every pad that just passed `held_time`.
- **`pressed`**: Pads currently down.

## `pyxelwidgets.devices.midi`

### `InvalidMIDIPortException` (Exception)

```python
InvalidMIDIPortException(*args: object)
```

### `MIDI` (Device)

```python
MIDI(**kwargs)
```

A device talking MIDI through rtmidi (or teVirtualMIDI for virtual ports on
Windows). Subclasses implement `decode` for input, `send_pixel(s)` for
output, and `on_connect` / `on_disconnect` for mode switching messages.

Without a grid (the default 1x1 with no output) it's a plain MIDI port pair:
use `send_*` and override `process_midi` or `decode`.

`check()` notices the device being unplugged and plugged back in.

- **`available_ports()`**: Names of the (input, output) MIDI ports.
- classmethod **`find_ports()`**: The first (input, output) port names containing one of `cls.ports`, in pattern order.
- classmethod **`find(**kwargs)`**: Create the device and connect it to the ports matching `cls.ports`.
- **`connect(in_port: str | None = None, out_port: str | None = None)`**: Open the given ports (names or indexes); with neither, find them from `ports`.
- **`connect_virtual(port: str)`**: Create virtual input and output ports named `port` for other software to connect to.
- **`check(ports: tuple | None = None)`**: Notice the device being unplugged or plugged back in; call it now and then (App and the designer do, about once a second). A device whose port is gone closes its ports, sets `lost` and emits DeviceDisconnected; once its ports are back it reconnects, emits DeviceReconnected and resends everything it shows. Returns True if the connection changed. `ports` are `available_ports()` if known. Virtual ports are left alone.
- **`disconnect()`**
- **`on_connect()`**: Override to put the device in the mode the driver expects.
- **`on_disconnect()`**: Override to return the device to its standalone mode.
- **`process_midi(message, _)`**: rtmidi callback: `message` is `(bytes, delta_time)`.
- **`decode(midi: list)`**: Override to turn an incoming message into `set_button` calls and control events.
- **`send_sysex(message)`**
- **`send_note_off(note, velocity = 0, channel = 0)`**
- **`send_note_on(note, velocity, channel = 0)`**
- **`send_aftertouch(note, velocity, channel = 0)`**
- **`send_control_change(control, value, channel = 0)`**
- **`send_program_change(program, channel = 0)`**
- **`send_channel_aftertouch(velocity, channel = 0)`**
- **`send_pitch_bend(bend, channel = 0)`**
- **`send_message(message: list)`**

## `pyxelwidgets.devices.novation`

Novation Launchpads, Launchkeys and Launch Controls.

### `LaunchControl` (MIDI)

```python
LaunchControl(**kwargs)
```

Launch Control (first generation). The grid is LED x template: `x` is the
LED, `y` the template (0-15) it is set in.

- **`reset(template: LaunchControl.Templates)`**
- **`select_template(template: LaunchControl.Templates)`**
- **`send_pixel(x: int, y: int, value)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`decode(midi: list)`**

#### `Controls` (Enum)

An enum.

Members: `Knob_1`, `Knob_2`, `Knob_3`, `Knob_4`, `Knob_5`, `Knob_6`, `Knob_7`, `Knob_8`, `Knob_9`, `Knob_10`, `Knob_11`, `Knob_12`, `Knob_13`, `Knob_14`, `Knob_15`, `Knob_16`, `Up`, `Down`, `Left`, `Right`, `User`, `Factory`.

#### `Templates` (Enum)

An enum.

Members: `User_0`, `User_1`, `User_2`, `User_3`, `User_4`, `User_5`, `User_6`, `User_7`, `Factory_0`, `Factory_1`, `Factory_2`, `Factory_3`, `Factory_4`, `Factory_5`, `Factory_6`, `Factory_7`.

### `LaunchControlXL` (MIDI)

```python
LaunchControlXL(**kwargs)
```

Launch Control XL: 8x2 buttons as a 8x5 grid (rows 2-4 are the knob LEDs,
output only), knobs, faders and buttons. Input works in factory template 8
(`Templates.Factory_7`), which connecting selects.

- **`reset(template: LaunchControlXL.Templates)`**
- **`select_template(template: LaunchControlXL.Templates)`**
- **`send_pixel(x: int, y: int, value)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`decode(midi: list)`**

#### `Controls` (Enum)

An enum.

Members: `Knob_0`, `Knob_1`, `Knob_2`, `Knob_3`, `Knob_4`, `Knob_5`, `Knob_6`, `Knob_7`, `Knob_8`, `Knob_9`, `Knob_10`, `Knob_11`, `Knob_12`, `Knob_13`, `Knob_14`, `Knob_15`, `Knob_16`, `Knob_17`, `Knob_18`, `Knob_19`, `Knob_20`, `Knob_21`, `Knob_22`, `Knob_23`, `Fader_0`, `Fader_1`, `Fader_2`, `Fader_3`, `Fader_4`, `Fader_5`, `Fader_6`, `Fader_7`, `Up`, `Down`, `Left`, `Right`.

#### `Buttons` (Enum)

An enum.

Members: `Device`, `Mute`, `Solo`, `RecordArm`.

#### `Templates` (Enum)

An enum.

Members: `User_0`, `User_1`, `User_2`, `User_3`, `User_4`, `User_5`, `User_6`, `User_7`, `Factory_0`, `Factory_1`, `Factory_2`, `Factory_3`, `Factory_4`, `Factory_5`, `Factory_6`, `Factory_7`.

### `LaunchkeyMK1` (_Launchkey)

Launchkey (first generation): red/green pads, knobs, faders and buttons.

- **`set_mode(mode: LaunchkeyMK1.Mode)`**
- **`enable_in_control(control: LaunchkeyMK1.InControl)`**
- **`disable_in_control(control: LaunchkeyMK1.InControl)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`decode(midi: list)`**

#### `Mode` (Enum)

An enum.

Members: `Basic`, `Extended`.

#### `InControl` (Enum)

An enum.

Members: `Pots`, `Slider`, `Pads`.

#### `Controls` (Enum)

An enum.

Members: `Track_L`, `Track_R`, `Rewind`, `Forward`, `Stop`, `Play`, `Loop`, `Record`, `Fader_0`, `Fader_1`, `Fader_2`, `Fader_3`, `Fader_4`, `Fader_5`, `Fader_6`, `Fader_7`, `Fader_8`, `Button_0`, `Button_1`, `Button_2`, `Button_3`, `Button_4`, `Button_5`, `Button_6`, `Button_7`, `Button_8`, `Knob_0`, `Knob_1`, `Knob_2`, `Knob_3`, `Knob_4`, `Knob_5`, `Knob_6`, `Knob_7`.

### `LaunchkeyMK2` (_Launchkey)

Launchkey MK2: RGB (palette) pads.

- **`set_mode(mode: LaunchkeyMK2.Mode)`**
- **`enable_in_control(control: LaunchkeyMK2.InControl)`**
- **`disable_in_control(control: LaunchkeyMK2.InControl)`**
- **`on_connect()`**
- **`on_disconnect()`**

#### `Mode` (Enum)

An enum.

Members: `Basic`, `Extended`.

#### `InControl` (Enum)

An enum.

Members: `pots`, `slider`, `pads`.

### `LaunchkeyMK3` (_Launchkey)

Launchkey MK3: RGB (palette) pads in DAW mode.

- **`set_mode(mode: LaunchkeyMK3.Mode)`**
- **`set_layout(layout: LaunchkeyMK3.Layout)`**
- **`on_connect()`**
- **`on_disconnect()`**

#### `Mode` (Enum)

An enum.

Members: `Other`, `DAW`.

#### `Layout` (Enum)

An enum.

Members: `Drum`, `Session`, `Custom`, `Drum2`, `Toggle`, `ProgramChange`.

### `LaunchpadMK1` (Launchpad)

Launchpad, Launchpad S, Launchpad Mini (MK1 and MK2): red/green LEDs, 9x9 with side buttons.

- **`set_layout(layout: LaunchpadMK1.Layout)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`decode(midi: list)`**

#### `Layout` (Enum)

An enum.

Members: `Reset`, `XY`, `Drum`.

### `LaunchpadMK2` (_ProgrammerLayout)

Launchpad MK2: RGB, 9x9 with the top row and right column.

- **`set_layout(layout: LaunchpadMK2.Layout)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`decode(midi: list)`**

#### `Layout` (Enum)

An enum.

Members: `Session`, `User1`, `User2`, `Reserved`, `Volume`, `Pan`.

### `LaunchpadMiniMK3` (_MK3)

Launchpad Mini MK3: RGB, 9x9 with the top row and right column.

- **`set_layout(layout: LaunchpadMiniMK3.Layout)`**

#### `Layout` (Enum)

An enum.

Members: `Session`, `Custom1`, `Custom2`, `Custom3`, `Fader`, `Programmer`.

### `LaunchpadPro` (_ProgrammerLayout)

Launchpad Pro (first generation): RGB, 10x10 with side buttons on all four sides.

- **`set_layout(layout: LaunchpadPro.Layout)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`decode(midi: list)`**

#### `Layout` (Enum)

An enum.

Members: `Note`, `Drum`, `Fader`, `Programmer`.

### `LaunchpadProMK3` (_MK3)

Launchpad Pro MK3: RGB, 10x10 with side buttons on all four sides.

- **`set_layout(layout: LaunchpadProMK3.Layout, page: int = 0)`**
- **`set_mode(mode: _MK3.Mode)`**

#### `Layout` (Enum)

An enum.

Members: `Session`, `Fader`, `Chord`, `CustomLayout`, `NoteDrum`, `ScaleSettings`, `SequencerSettings`, `SequencerSteps`, `SequencerVelocity`, `SequencerPatternSettings`, `SequencerProbability`, `SequencerMutation`, `SequencerMicroStep`, `SequencerProjects`, `SequencerPatterns`, `SequencerTempo`, `SequencerSwing`, `Programmer`, `Settings`, `CustomLayoutSettings`.

### `LaunchpadX` (_MK3)

Launchpad X: RGB, 9x9 with the top row and right column.

- **`set_layout(layout: LaunchpadX.Layout)`**

#### `Layout` (Enum)

An enum.

Members: `Session`, `Note`, `Custom1`, `Custom2`, `Custom3`, `Custom4`, `Fader`, `Programmer`.

## `pyxelwidgets.devices.akai`

Akai Professional APC controllers.

### `APCMini` (MIDI)

APC Mini: 8x8 pads lit green, red or yellow, extra buttons and faders.

Thanks to TomasHubelbauer for his amazing documentation:
    https://github.com/TomasHubelbauer/akai-apc-mini

- **`send_color(x: int, y: int, color: APCMini.Colors)`**
- **`send_pixel(x: int, y: int, value)`**
- **`decode(midi: list)`**

#### `Colors` (Enum)

An enum.

Members: `Off`, `Green`, `GreenBlink`, `Red`, `RedBlink`, `Yellow`, `YellowBlink`.

#### `Notes` (Enum)

An enum.

Members: `Button_1`, `Button_2`, `Button_3`, `Button_4`, `Button_5`, `Button_6`, `Button_7`, `Button_8`, `Button_9`, `Button_10`, `Button_11`, `Button_12`, `Button_13`, `Button_14`, `Button_15`, `Button_16`, `Button_17`.

#### `Controls` (Enum)

An enum.

Members: `Fader_1`, `Fader_2`, `Fader_3`, `Fader_4`, `Fader_5`, `Fader_6`, `Fader_7`, `Fader_8`, `Fader_9`.

### `APC40MK2` (MIDI)

```python
APC40MK2(**kwargs)
```

APC40 MK2: 8x5 RGB pads, knobs, faders and buttons, in Ableton Live mode.

- **`change_mode(mode: APC40MK2.Modes)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`send_pixel(x: int, y: int, value)`**
- **`decode(midi: list)`**

#### `Modes` (Enum)

An enum.

Members: `Generic`, `Ableton`, `Alternative`.

#### `Controls` (Enum)

An enum.

Members: `Fader_0`, `Fader_1`, `Fader_2`, `Fader_3`, `Fader_4`, `Fader_5`, `Fader_6`, `Fader_7`, `Fader_8`, `CrossFader`, `DeviceKnob_0`, `DeviceKnob_1`, `DeviceKnob_2`, `DeviceKnob_3`, `DeviceKnob_4`, `DeviceKnob_5`, `DeviceKnob_6`, `DeviceKnob_7`, `SceneKnob_0`, `SceneKnob_1`, `SceneKnob_2`, `SceneKnob_3`, `SceneKnob_4`, `SceneKnob_5`, `SceneKnob_6`, `SceneKnob_7`, `Cue`, `Tempo`.

#### `Buttons` (Enum)

An enum.

Members: `Select_0`, `Select_1`, `Select_2`, `Select_3`, `Select_4`, `Select_5`, `Select_6`, `Select_7`, `Solo_0`, `Solo_1`, `Solo_2`, `Solo_3`, `Solo_4`, `Solo_5`, `Solo_6`, `Solo_7`, `Record_0`, `Record_1`, `Record_2`, `Record_3`, `Record_4`, `Record_5`, `Record_6`, `Record_7`, `Beat_0`, `Beat_1`, `Beat_2`, `Beat_3`, `Beat_4`, `Beat_5`, `Beat_6`, `Beat_7`, `Beat_8`, `Stop_0`, `Stop_1`, `Stop_2`, `Stop_3`, `Stop_4`, `Stop_5`, `Stop_6`, `Stop_7`, `Stop_8`, `Scene_0`, `Scene_1`, `Scene_2`, `Scene_3`, `Scene_4`, `Pan`, `Sends`, `User`, `Metronome`, `Tap`, `Nudge_N`, `Nudge_P`, `Play`, `Record`, `Session`, `Control_0`, `Control_1`, `Control_2`, `Control_3`, `Control_4`, `Control_5`, `Control_6`, `Control_7`, `Shift`, `Bank`, `Up`, `Down`, `Right`, `Left`.

## `pyxelwidgets.devices.ableton`

Ableton Push.

### `Push2` (MIDI)

Push 2: 8x8 RGB pads, encoders (relative, touch sensitive) and buttons, in dual MIDI mode.

- **`send_command(command: Push2.Commands, *args)`**
- **`set_midi_mode(mode: Push2.Mode)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`send_pixel(x: int, y: int, value)`**
- **`decode(midi: list)`**

#### `Mode` (Enum)

An enum.

Members: `Live`, `User`, `Dual`.

#### `Commands` (Enum)

An enum.

Members: `SetLEDColorPaletteEntry`, `GetLEDColorPaletteEntry`, `ReapplyColorPalette`, `SetLEDBrightness`, `GetLEDBrightness`, `SetDisplayBrightness`, `GetDisplayBrightness`, `SetMIDIMode`, `SetLEDPWMFrequencyCorrection`, `SamplePedalData`, `SetLEDWhiteBalance`, `GetLEDWhiteBalance`, `SetTouchStripConfiguration`, `GetTouchStripConfiguration`, `SetTouchStripLEDs`, `RequestStatistics`, `SetPadParameters`, `Read400gPadValuesFromFlash`, `SetAftertouchMode`, `GetAftertouchMode`, `SetPadVelocityCurveEntry`, `GetPadVelocityCurveEntry`, `SetTemporary400gPadValues`, `FlashLEDWhiteBalance`, `SelectPadSettings`, `GetSelectedPadSettings`, `ConfigurePedal`, `SetPedalCurveLimits`, `SetPedalCurveEntries`.

#### `Controls` (Enum)

An enum.

Members: `Play`, `Record`, `Automate`, `FixedLength`, `New`, `Duplicate`, `Quantize`, `DoubleLoop`, `Convert`, `Undo`, `Delete`, `TapTempo`, `Metronome`, `Setup`, `User`, `AddDevice`, `AddTrack`, `Device`, `Browse`, `Mix`, `Clip`, `Master`, `Up`, `Down`, `Left`, `Right`, `Repeat`, `Accent`, `Scale`, `Layout`, `Note`, `Session`, `OctaveUp`, `OctaveDown`, `PageLeft`, `PageRight`, `Shift`, `Select`, `Encoder1`, `Encoder2`, `Encoder3`, `Encoder4`, `Encoder5`, `Encoder6`, `Encoder7`, `Encoder8`, `Encoder9`, `Encoder10`, `Encoder11`, `Button01`, `Button02`, `Button03`, `Button04`, `Button05`, `Button06`, `Button07`, `Button08`, `Button11`, `Button12`, `Button13`, `Button14`, `Button15`, `Button16`, `Button17`, `Button18`, `Bar4`, `Bar4t`, `Bar8`, `Bar8t`, `Bar16`, `Bar16t`, `Bar32`, `Bar32t`.

#### `Notes` (Enum)

An enum.

Members: `Encoder1Touch`, `Encoder2Touch`, `Encoder3Touch`, `Encoder4Touch`, `Encoder5Touch`, `Encoder6Touch`, `Encoder7Touch`, `Encoder8Touch`, `Encoder9Touch`, `Encoder10Touch`, `Encoder11Touch`, `PitchBendTouch`.

## `pyxelwidgets.devices.presonus`

Presonus controllers.

### `ATOM` (MIDI)

ATOM: 4x4 RGB pads, encoders and buttons, in native control mode.

- **`set_native_control(state: ATOM.NativeControl)`**
- **`on_connect()`**
- **`on_disconnect()`**
- **`send_pixel(x: int, y: int, value)`**
- **`decode(midi: list)`**

#### `Controls` (Enum)

An enum.

Members: `Encoder_0`, `Encoder_1`, `Encoder_2`, `Encoder_3`, `NoteRepeat`, `FullLevel`, `Bank`, `Preset`, `Show`, `Nudge`, `Editor`, `Shift`, `SetLoop`, `Setup`, `Up`, `Down`, `Left`, `Right`, `Select`, `Zoom`, `Click`, `Record`, `Play`, `Stop`.

#### `NativeControl` (Enum)

An enum.

Members: `Enable`, `Disable`.

## `pyxelwidgets.devices.virtual`

An on-screen grid (tkinter window) for trying layouts without hardware.

### `Virtual` (Device)

```python
Virtual(columns: int = 8, rows: int = 8, **kwargs)
```

A window showing a `columns` x `rows` grid; clicking a pad presses it.
Tk needs the thread that created the window: create it and call `show`
(or run the App) from the main thread. Closing the window closes the device.

- **`send_pixel(x: int, y: int, value)`**
- **`process(x, y, value)`**
- **`close()`**
- **`show(frame: ndarray, x: int = 0, y: int = 0)`**

## `pyxelwidgets.devices.web`

A grid in a web browser, e.g. on a tablet or a phone:

    grid = WebGrid(columns = 8, rows = 8, port = 8800)
    grid.connect()
    print('Open', grid.url)           # on any device on the same network
    surface.add_device(grid)

Every browser that opens the page shows the grid and plays it: several
fingers at once, sliding across pads, or the mouse. The corner button goes
fullscreen; "Add to Home Screen" makes it an app that opens fullscreen.
Standard library only: a small HTTP server that talks WebSocket to the page.

### `WebGrid` (Device)

```python
WebGrid(*, columns: int = 8, rows: int = 8, port: int = 8800, host: str = '0.0.0.0', title: str = 'PyxelWidgets', **kwargs)
```

A `columns` x `rows` grid shown in web browsers, served on `port`
(`url` after `connect`). Pads are pressed by touch or mouse; pen
pressure is the velocity, otherwise it is 1.0.

- `columns, rows: int = 8, optional`: The grid's size.
- `port: int = 8800, optional`: The HTTP port browsers open (0: any free one, see `url`).
- `host: str = '0.0.0.0', optional`: The address to listen on; '127.0.0.1' for this computer only.
- `title: str = 'PyxelWidgets', optional`: The page title.

- **`url`**: The page's address for other devices on the network, while connected.
- **`connect()`**
- **`disconnect()`**
- **`send_pixels(pixels: list)`**

## `pyxelwidgets.devices.midi_clock`

MIDI clock: follow another program's clock (e.g. a DAW) or send one.

    transport = Transport(sync = True)            # or App(surface, sync = True)
    clock = MidiClockInput(transport)
    clock.connect_virtual('PyxelWidgets Clock')    # or clock.connect('IAC Driver Bus 1')

    clock = MidiClockOutput(app.transport)
    clock.connect(out_port = 'IAC Driver Bus 1')

Any object with the Transport's `pulse`, `play`, `stop` and `locate`
(input) or `every`, `on`, `tick` and `ppq` (output) works; devices don't
import the transport.

### `MidiClockInput` (MIDI)

```python
MidiClockInput(transport, **kwargs)
```

Drives a `Transport(sync = True)` from incoming MIDI clock, start, continue, stop and song position.

- **`decode(midi: list)`**

### `MidiClockOutput` (MIDI)

```python
MidiClockOutput(transport, **kwargs)
```

Sends a Transport's tempo and position as MIDI clock (24 per quarter note) with start, continue, stop and song position.

- **`close()`**

## `pyxelwidgets.devices.midi_port`

A plain MIDI port pair to send widget messages to other software (a DAW, a
synth) and receive what it sends back:

    port = MidiPort()
    port.connect_virtual('PyxelWidgets')          # a port the DAW can pick
    port.connect(out_port = 'IAC Driver Bus 1')    # or an existing port

    surface.map(kick, port, NoteOn(36), on = Pressed)

See `pyxelwidgets.mapping` and `pyxelwidgets.message`.

### `MidiPort` (MIDI)

Sends MidiMessages with `send`; received channel messages are emitted as MessageReceived.

- classmethod **`describe()`**
- **`send(message: MidiMessage)`**
- **`decode(midi: list)`**

## `pyxelwidgets.devices.mackie`

DAW control surface protocols over MIDI: Mackie Control (also Logic Control)
and HUI. Widgets send and receive `Command`s by name (see `commands`):

    mackie = MackieControl()
    mackie.connect_virtual('PyxelWidgets MCU')   # pick it in the DAW (REAPER: Preferences >
                                                # Control/OSC/web > Add > Mackie Control Universal)
    surface.map(play, mackie, Command('Play'), on = Pressed, feedback = True)
    surface.map(play, mackie, Command('Play', 0.0), on = Released)
    surface.map(volume, mackie, Command('Fader 1', Source('value')), on = Changed, feedback = True)
    surface.map(pan, mackie, Command('V-Pot 1', Source('delta')), on = Changed, feedback = True)
    surface.map(clock, mackie, Command('Timecode', Source('text')), feedback = True)

Buttons are pressed while the value is above 0; received LEDs come back as 1.0
or 0.0 (`flash` when blinking). Faders are 0.0-1.0. V-Pots and the jog wheel
send steps (negative turns left) and receive their LED ring position 0.0-1.0.
Received displays (`Timecode`, `Name 1`, `Display`...) carry text and
meters (`Meter 1`) 0.0-1.0.

Mackie Control also reaches plug-in parameters through the DAW's plug-in
mode, by name: `scan_tracks()`, `scan_plugins(track)` and
`scan_parameters(track, plugin)` press its buttons and read its display,
and `PluginParameter` messages turn a parameter's V-Pot:

    mackie.scan_tracks()                       # ['Drums', 'Bass', ...] (7 characters at most)
    mackie.scan_plugins('Bass')                # ['ReaEQ', 'ReaComp']
    mackie.scan_parameters('Bass', 'ReaComp')  # ['Thresh', 'Ratio', ...]
    surface.map(knob, mackie, PluginParameter('Bass', 'ReaComp', 'Ratio'), on = Changed, feedback = True)

### `MackieControl` (_ControlSurface)

```python
MackieControl(*, mode: MackieControl.Mode = MackieControl.Mode.MackieControl, plugin_button: str = 'Plug-in', channel_button: str = 'Pan', next_page: str = 'Bank Right', previous_page: str = 'Bank Left', **kwargs)
```

Mackie Control Universal (or Logic Control, or an extender, by `mode`):
8 channel strips, transport and function buttons, the jog wheel, and
feedback for LEDs, faders, V-Pot rings, meters, the timecode and
assignment displays and the 2x56 character LCD (`Name 1`-`8`,
`Value 1`-`8` for the strips' top and bottom lines, `Display` for
both). Answers the Logic Control connection handshake.

- `plugin_button: str = 'Plug-in', optional`: The button showing the selected track's plug-ins on the strips (a V-Pot press opens one's parameters).
- `channel_button: str = 'Pan', optional`: The button going back to the tracks on the strips.
- `next_page: str = 'Bank Right', optional`: The button showing a plug-in's next 8 parameters.
- `previous_page: str = 'Bank Left', optional`: The button showing a plug-in's previous 8 parameters.

- **`header`**
- **`send(message)`**
- **`decode(midi: list)`**
- **`close()`**
- **`row(line: int = 0)`**: The 8 strips' texts on the display's top (0) or bottom (1) line.
- **`scanned()`**: What the scans found: `tracks`, `plugins` by track and `parameters` by track and plug-in.
- **`scan_tracks()`**: The DAW's track names: banks through the strips from the first, reading the display (a DAW shows at most 7 characters; repeated names get " (2)"). Blocks for a while; don't call it from a MIDI or widget event handler.
- **`scan_plugins(track: str)`**: The plug-ins on `track` (a name from `scan_tracks`), as the DAW's plug-in mode shows them.
- **`scan_parameters(track: str, plugin: str)`**: The parameters of `plugin` on `track`: opens it and pages through its parameters, 8 at a time.

#### `Mode` (Enum)

The model it presents itself as (its SysEx device ID).

Members: `MackieControl`, `MackieControlExtender`, `LogicControl`, `LogicControlExtender`.

### `HUI` (_ControlSurface)

```python
HUI(**kwargs)
```

HUI (Pro Tools, REAPER, Logic): 8 channel strips, transport and edit
switches, the jog wheel, and feedback for LEDs, faders, V-Pot rings,
meters, the timecode, the strips' 4 character names (`Name 1`-`8`)
and the main display (`Display`). Answers the host's pings.

- **`send(message)`**
- **`decode(midi: list)`**

## `pyxelwidgets.devices.osc`

OSC over UDP (needs the `osc` extra: `pip install "pyxelwidgets[osc]"`):

    reaper = REAPER()                 # REAPER's defaults: sends to port 8000, listens on 9000
    reaper.connect()
    surface.map(play, reaper, OscMessage('/play', 1.0), on = Pressed, feedback = True)
    surface.map(volume, reaper, OscMessage('/track/{x+1}/volume', Source('value')), on = Changed, feedback = True)

Received messages are emitted as MessageReceived with an OscMessage.

### `OSC` (Device)

```python
OSC(*, host: str = '127.0.0.1', send_port: int = 8000, receive_port: int | None = 9000, **kwargs)
```

Sends OscMessages to `host`:`send_port` with `send` and listens on
`receive_port` (None: doesn't listen). `addresses` are suggestions for
editors.

- classmethod **`describe()`**
- **`connect()`**
- **`disconnect()`**
- **`send(message: OscMessage)`**

### `REAPER` (OSC)

REAPER's default OSC pattern (Default.ReaperOSC): tracks are `{x+1}`-style placeholders for `@`.

## `pyxelwidgets.devices.desktop`

This computer's keyboard and mouse as an output, for macro boards and
automation: widgets press keys and shortcuts, type text, move and click the
mouse, and scroll:

    desktop = Desktop()
    desktop.connect()
    surface.map(save, desktop, Hotkey('ctrl+s'), on = Pressed)
    surface.map(talk, desktop, Key('f13', Source('value')), on = Changed)     # held while pressed
    surface.map(pad, desktop, MouseMove(Source('value_x'), Source('value_y')), on = Changed)
    surface.map(knob, desktop, Scroll(0, Source('delta')), on = Changed)

Needs pynput (`pip install "pyxelwidgets[desktop]"`). On macOS, allow the
app that runs it (Terminal, your editor) under System Settings > Privacy &
Security > Accessibility; without that the keys and clicks go nowhere.

### `Desktop` (Device)

```python
Desktop(*, type_delay: float = 0.0, backend = None, **kwargs)
```

The keyboard and mouse of this computer: sends Hotkey, Key, TypeText,
MouseMove, MouseButton, MouseClick and Scroll. Actions run in order on a
thread of their own; keys and buttons still held are let go on disconnect.

- `type_delay: float = 0.0, optional`: Seconds between typed characters, for programs that miss fast typing.
- `backend: optional`: Does the pressing (default: pynput); tests pass a recorder.

- classmethod **`describe()`**
- **`connect()`**
- **`disconnect()`**
- **`send(message)`**: Queue a message's action; returns at once.
- **`perform(message)`**: Do what `message` says, now (`send` queues it instead).

# Designer

## `pyxelwidgets.designer`

A web based designer for layouts:

    python -m pyxelwidgets.designer layout.json

opens a browser where widgets are placed on the surface, configured, and tried
out on a live preview rendered by the real widgets. The layout is saved as JSON
for `pyxelwidgets.parser.load`.

### `Preview`

```python
Preview(layout: dict | None = None, *, connect: bool = False)
```

A layout built without hardware, with a preview device, an event log and a
transport to play it. The layout's devices and outputs can be connected
one by one (`set_connected`), or all as they're added (`connect`):
devices mirror the preview and their pads work the widgets, outputs send
what the widgets' mappings send.

`connect`: connect the layout's devices and outputs as they are added (unless disconnected).

- **`load(layout: dict)`**: Rebuild from `layout` (upgraded to the current version); raises LayoutError and keeps the previous layout if it is invalid. Widgets keep what input changed (values, steps...) unless their options changed it.
- **`set_hidden(names)`**: Hide widgets (by name) in the preview only, e.g. to see what's underneath; the layout is unchanged.
- **`set_connected(kind: str, index: int, connected: bool)`**: Connect or disconnect layout `devices[index]` or `outputs[index]` (`kind`); returns the status.
- **`set_hardware(enabled: bool)`**: Connect (or close) every device and output of the layout, and the ones added later.
- **`hardware_status()`**
- **`scan(index: int, what: str, track: str | None = None, plugin: str | None = None)`**: Scan the DAW through connected output `index` (Mackie Control): `what` is `tracks`, `plugins` (of `track`), `parameters` (of `plugin` on `track`) or `known` (what earlier scans found). Returns the names found and everything scanned so far. Takes seconds: the DAW is driven.
- **`close()`**
- **`frame(since: int = 0)`**: Render; pixels are `#rrggbb` rows from the top, plus events after `since`.
- **`input(x: int, y: int, velocity: float)`**: Press (`velocity` > 0) or release the surface pad at `x`, `y`.
- **`play()`**: Play the layout's transport from the start so Sequencers and Trackers play (not while a DAW plays it).
- **`bpm`**: The tempo: the layout's, or one a link set.
- **`set_tempo(bpm: float)`**: Change the tempo (from a link) until the layout's tempo changes.
- **`synced`**: Following a DAW's clock: the DAW plays and stops the transport.
- **`playing`**
- **`stop()`**

### `Designer`

```python
Designer(path: str | None = None, *, connect: bool = True)
```

The designer's state: the preview and the file it saves to.

- **`close()`**: Stop the transport and close connected hardware.
- **`save(layout: dict, path: str | None = None)`**: Save to the layout file, or to `path`, which becomes the layout file (Save As).
- **`open(path: str)`**: Open the layout file at `path`; it becomes the layout file.
- **`new(template: str | None = None, layout: dict | None = None)`**: Start a layout: empty, from one of `templates()`, or `layout` (imported); it has no file until saved.

### `new_layout(width: int = 9, height: int = 9)`

### `catalog()`

Everything the designer UI offers: widget and binding options, devices, outputs, messages, links and named colors.
