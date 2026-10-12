# Writing a driver

A driver is one class per hardware model. It turns the device's input into
pad and control events, and frames into whatever lights its LEDs. It knows
nothing about widgets: a device works with a surface, or on its own.

This guide writes a driver for a made-up "PadBox 16". It has 4x4 velocity
pads lit in 8 colors, two buttons, an encoder and a fader.

## The whole driver

```python
"""A driver for the (made up) PadBox 16: 4x4 velocity pads, two buttons, an encoder and a fader."""

from pyxelwidgets import parser
from pyxelwidgets.devices import Control, Palette
from pyxelwidgets.devices.midi import MIDI
from pyxelwidgets.events import ControlChanged, ControlPressed, ControlReleased, ControlTurned

# The LED colors the pads have, by the velocity that lights them
COLORS = [(0, 0, 0), (255, 0, 0), (255, 128, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255), (255, 0, 255), (255, 255, 255)]

# Pads send notes 36-51 on channel 10, left to right from the bottom row
FIRST_NOTE = 36
BUTTONS = {20: 'Shift', 21: 'Play'}
ENCODER, FADER = 22, 7


@parser.register
class PadBox(MIDI):
    """PadBox 16: 4x4 pads lit in 8 colors, Shift and Play buttons, an encoder and a fader."""

    vendor = 'Example'
    model = 'PadBox 16'
    ports = ('PadBox',)
    grid = (4, 4)
    color_model = Palette(COLORS)
    controls = (Control('Shift', 'button'), Control('Play', 'button'),
                Control('Encoder', 'relative'), Control('Volume', 'absolute'))

    def on_connect(self) -> None:
        # Host mode: the pads stop lighting themselves
        self.send_sysex([0x7D, 0x01, 0x01])

    def on_disconnect(self) -> None:
        self.send_sysex([0x7D, 0x01, 0x00])

    def send_pixel(self, x: int, y: int, value) -> None:
        # value: an index into COLORS, from the color model
        self.send_note_on(FIRST_NOTE + x + y * 4, value)

    def decode(self, midi: list) -> None:
        status, data = midi[0] & 0xF0, midi[1:]
        if status in (0x80, 0x90) and FIRST_NOTE <= data[0] < FIRST_NOTE + 16:
            cell = data[0] - FIRST_NOTE
            # A note on with velocity 0 is a release too
            velocity = data[1] / 127 if status == 0x90 else 0.0
            self.set_button(cell % 4, cell // 4, velocity)
        elif status == 0xB0 and data[0] in BUTTONS:
            event = ControlPressed if data[1] else ControlReleased
            self.emit(event(self, BUTTONS[data[0]], data[1] / 127))
        elif status == 0xB0 and data[0] == ENCODER:
            # 1-63 clockwise, 65-127 counter-clockwise
            self.emit(ControlTurned(self, 'Encoder', data[1] if data[1] < 64 else data[1] - 128))
        elif status == 0xB0 and data[0] == FADER:
            self.emit(ControlChanged(self, 'Volume', data[1] / 127))
```

## Step by step

### Describing the hardware

Class attributes describe the model. `describe()` turns them into data,
which is what the designer reads:

| Attribute | Meaning |
|---|---|
| `vendor`, `model` | names shown to people |
| `ports` | parts of its MIDI port names, to find it (`PadBox.find()`) |
| `grid` | `(width, height)` of the pad grid; `(0, 0)` is the bottom-left pad |
| `color_model` | how RGBA frames become LED values (below) |
| `controls` | `Control(name, kind)` for everything besides the grid: `button`, `absolute` (knobs, faders), `relative` (encoders), `touch` |

### Colors

`show(frame)` keeps what the device shows and sends only the pads that
changed: it converts their colors with `color_model` and calls `send_pixel`
(or `send_pixels` with all of them at once, to batch).

| Model | Values your `send_pixel` gets |
|---|---|
| `RGB(bits = 8, gamma = True)` | `(r, g, b)` with `bits` per channel |
| `Palette(table)` | the index of the nearest `(r, g, b)` in `table` |
| `Levels(values)` | one of `values` (darkest first) by brightness: single-color or red/green LEDs |
| `PassThrough()` | the `Color` itself, for devices converting on their own (on screen) |

Transparent and half-transparent pixels arrive already blended over black.

### Input

- **Pads:** call `set_button(x, y, velocity)`, where velocity 0 means a
  release. The base class turns that into `PadPressed`/`PadReleased`, and
  detects holds (`PadHeld`) and double presses from timestamps.
- **Pressure:** `set_pressure(x, y, pressure)` for held pads with
  aftertouch, or `set_channel_pressure(pressure)` for all of them.
- **Controls:** emit `ControlPressed`/`ControlReleased` (velocity),
  `ControlChanged` (an absolute value, 0.0-1.0) or `ControlTurned` (relative
  steps, negative is counter-clockwise), named like your `controls`.

Input arrives on rtmidi's thread; that's fine, see [Threads](threads.md).

### MIDI

Subclassing `pyxelwidgets.devices.midi.MIDI` gives you:

- **Opening:** `connect(in_port, out_port)` opens ports by name (or finds
  them from `ports`), `PadBox.find()` creates and connects one, and
  `connect_virtual(name)` makes ports other software connects to.
- **Mode switching:** `on_connect()` / `on_disconnect()` are your hooks for
  the messages that put the device in the mode you drive (host mode, a
  programmer layout) and back.
- **Decoding:** `decode(midi)` gets each incoming message as a list of bytes.
- **Sending:** `send_note_on`, `send_control_change`, `send_sysex` (without
  F0/F7), `send_message` and friends.
- **Hot-plugging:** `check()` notices the device being unplugged and plugged
  back in. App and the designer call it for you.

A device that isn't MIDI (a network or USB device, a screen) subclasses
`pyxelwidgets.devices.Device` directly and does its own I/O. See
`devices/web.py` (WebSocket) and `devices/virtual.py` (Tk).

### Layouts and the designer

`@parser.register` makes it usable in layouts as `"padbox.PadBox"` (its
module and class). Import the module before loading a layout, and start the
designer with `--import padbox.py`. It is then in the device list, with its
size, controls (for bindings) and options. Options are constructor keyword
arguments with types, like widget options.

Drivers in the package itself live in `src/pyxelwidgets/devices/`, one module
per vendor, listed in `__all__`. Add the module to `DEVICE_MODULES` in
`pyxelwidgets/designer/__init__.py`.

## Testing without the hardware

Feed `decode` the bytes the device would send, and catch what `show` sends
with a stand-in output:

```python
class Recorder:
    """Stands in for the MIDI output: keeps what's sent."""
    def __init__(self):
        self.sent = []
    def send_message(self, message):
        self.sent.append(list(message))

box = PadBox()
box._midi_output = Recorder()
box.connected = True
box.on(Event, print)

box.decode([0x99, 41, 100])          # pad 5 pressed: PadPressed(x = 1, y = 1, velocity ≈ 0.79)
box.decode([0xB0, 22, 125])          # ControlTurned('Encoder', delta = -3)

frame = buffer.new(4, 4, Colors.Black)
frame[1, 1] = Colors.Red
box.show(frame)                      # box._midi_output.sent: [0x90, 41, 1] among the others
```

Presses and releases are emitted at once; `PadHeld` comes from
`poll_input()`, which `show` calls every frame. On real hardware, `python examples/DeviceCheck/DeviceCheck.py` shows
a test pattern and prints every event. The package's own drivers are
checked against recorded MIDI in `tests/golden/`. A driver no one can test
must keep its recorded behaviour.

## Checklist

- [ ] `(0, 0)` is the bottom-left pad; `describe()` shows the right size and controls.
- [ ] Velocity 0 note-ons are releases.
- [ ] `on_disconnect` returns the device to its standalone mode.
- [ ] No imports of widgets or the surface: a device works alone.
- [ ] A decode/show test like the one above.
