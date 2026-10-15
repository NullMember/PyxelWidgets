# PyxelWidgets

Build your own instruments and controllers for grid controllers like the
Launchpad, APC, Push and Launchkey, in a visual designer or in Python.
Faders, drum pads, sequencers, keyboards, clip launchers and more, wired to
your DAW, synths, OSC apps or each other.

![The PyxelWidgets designer playing the performance template: clip launcher, drum pads, a beat sequencer and a meter](https://raw.githubusercontent.com/NullMember/PyxelWidgets/main/docs/images/designer.png)

- **Design without code:** drag widgets onto the grid, try them on your
  controller as you edit, connect them to your DAW, save a layout file.
- **Play it anywhere:** `pyxelwidgets run` plays a layout without the
  designer, on a computer or a Raspberry Pi. Apps are available for macOS,
  Windows, Linux and Android.
- **Talk to your music software:** MIDI, Mackie Control and HUI (with
  plug-in parameters by name in Logic, Cubase, REAPER and Pro Tools), OSC,
  network MIDI, Bluetooth MIDI, MIDI clock in and out, and your computer's
  keyboard and mouse.
- **Grow into code:** the designer writes the Python for your layout, and
  every piece (widgets, devices, the transport) works on its own.

## Install

Python 3.10 or newer:

```sh
pip install pyxelwidgets
pyxelwidgets designer my-layout.json
```

The designer opens in your browser. `my-layout.json` is created the first time
you save.

Optional extras add more connections. `"pyxelwidgets[all]"` installs every
extra except `test`.

| Extra | Adds |
|-------|------|
| `osc` | OSC and REAPER outputs |
| `network` | announcing network MIDI sessions (Bonjour) |
| `bluetooth` | Bluetooth MIDI devices, and the computer as one (Linux) |
| `desktop` | keyboard and mouse output (macro boards) |
| `app` | the designer in a window of its own (`pyxelwidgets app`) |

Prefer an app? Download it for macOS, Windows, Linux or Android from the
[releases page](https://github.com/NullMember/PyxelWidgets/releases). The
[apps guide](https://github.com/NullMember/PyxelWidgets/blob/main/docs/apps.md)
has the details.

## Commands

| Command | What it does |
|---------|--------------|
| `pyxelwidgets designer [layout.json]` | The designer, in your browser |
| `pyxelwidgets app [layout.json]` | The designer in its own window (extra `app`) |
| `pyxelwidgets run layout.json` | Plays a layout on its devices and outputs, without the designer |

`pyxelwidgets-designer` is the same as `pyxelwidgets designer`. Useful options:

- `designer --offline`: don't connect devices and outputs on start (connect
  them one by one in the page).
- `designer --host 0.0.0.0`: edit from another computer, a tablet or a phone on
  your network. The *Share* button in the designer does the same while it
  runs.
- `run --play`: start the transport, so sequencers play right away.
- `run --fps 30`: send fewer frames, e.g. on a Raspberry Pi Zero.
- `app --perform --play`: player mode. It opens the layout ready to play,
  without the editing grid.
- `app --headless layout.json`: play without a window, like `run`.
- `--import my_widgets.py`: load widgets or devices of your own (see
  [writing a widget](https://github.com/NullMember/PyxelWidgets/blob/main/docs/writing-a-widget.md)).

`pyxelwidgets <command> --help` lists them all.

## The designer

Start from a template (drum controller, MIDI keyboard, DAW mixer, performance,
macro board) or an empty grid. Then:

- **Add your controller.** *Detect* finds what's plugged in. The grid takes
  its size, and the device shows the layout as you edit and plays it when you
  press its pads.
- **Place widgets** by dragging them from the palette, or pick a
  [snippet](https://github.com/NullMember/PyxelWidgets/blob/main/docs/snippets.md):
  ready-made pieces for 8x8, 8x2, 9x9 and other grids, from a drum machine to
  16 switchable sequencers.
- **Send to your software.** Add an output (a MIDI port, Mackie Control,
  REAPER, network or Bluetooth MIDI, keyboard and mouse), then give widgets
  messages. *Learn* fills a message in from what the DAW sends. Feedback lets
  the DAW light the pads.
- **Wire widgets together** with links: a button switches pages, a fader sets
  the tempo, a knob changes a keyboard's scale. Formulas keep options computed
  from other widgets.
- **Try it** in Try mode: click pads, watch events and messages in the log,
  hover a pad to see what it sends.
- **Play it** in Perform mode, follow a DAW's MIDI clock, or turn a phone or
  tablet into a touch grid.
- **Take the code.** The Python tab shows a program for the layout, either
  one that loads the file or one that builds it all in code.

[Getting started](https://github.com/NullMember/PyxelWidgets/blob/main/docs/getting-started.md)
builds a first controller step by step, and the
[designer guide](https://github.com/NullMember/PyxelWidgets/blob/main/docs/designer.md)
covers the rest.

## In Python

A layout file from the designer, with your own code attached by widget name:

```python
from pyxelwidgets import Changed, parser

ui = parser.load('my-layout.json')
ui['volume'].on(Changed, lambda event: print('volume', event.value))
app = ui.app()
app.transport.play()
app.run()           # until Ctrl+C
```

Or everything in code. This example puts a fader and a button on an on-screen
grid; use `LaunchpadMiniMK3.find()` or another device class for real
hardware:

```python
from pyxelwidgets import App, Button, Changed, Colors, Fader, Surface
from pyxelwidgets.devices.virtual import Virtual

surface = Surface(8, 8)
volume = surface.add(Fader(0, 0, 1, 8, active_color = Colors.Cyan))
record = surface.add(Button(7, 0, 1, 1, active_color = Colors.Red))
volume.on(Changed, lambda event: print('volume', event.value))

grid = Virtual(8, 8)
grid.connect()
surface.add_device(grid)
App(surface).run()
```

The [Python guide](https://github.com/NullMember/PyxelWidgets/blob/main/docs/library.md)
covers widgets, devices, musical time, animations, bindings and links. The
[outputs guide](https://github.com/NullMember/PyxelWidgets/blob/main/docs/outputs.md)
covers sending to other software.

## Hardware

| Maker | Devices |
|-------|---------|
| Novation | Launchpad (MK1, S, Mini MK1/MK2, MK2, Pro, X, Mini MK3, Pro MK3), Launchkey (MK1-3), Launch Control, Launch Control XL |
| Akai | APC Mini, APC40 MK2 |
| Ableton | Push 2 |
| Arturia | MiniLab mkII, MiniLab 3 |
| PreSonus | ATOM |
| No hardware | Web Grid (any browser, multi-touch), Virtual (a window) |

So far only the **Launchpad Mini MK3** has been tried on hardware. The
others follow their makers' documentation and earlier drivers, and need
owners to try them.
[Hardware](https://github.com/NullMember/PyxelWidgets/blob/main/docs/hardware.md)
lists what's been checked. The designer's *Check this device* walks you
through a test and makes a report to send back.

## Documentation

- [Getting started](https://github.com/NullMember/PyxelWidgets/blob/main/docs/getting-started.md): a first controller in the designer, no code
- [The designer](https://github.com/NullMember/PyxelWidgets/blob/main/docs/designer.md): everything it does, and its shortcuts
- [Apps](https://github.com/NullMember/PyxelWidgets/blob/main/docs/apps.md): the desktop apps and the Android app
- [Outputs](https://github.com/NullMember/PyxelWidgets/blob/main/docs/outputs.md): DAWs, Mackie Control, HUI, OSC, network and Bluetooth MIDI, MIDI clock, keyboard and mouse
- [Python guide](https://github.com/NullMember/PyxelWidgets/blob/main/docs/library.md): the library itself
- [Hardware](https://github.com/NullMember/PyxelWidgets/blob/main/docs/hardware.md): supported devices and what's been tested
- [Snippets](https://github.com/NullMember/PyxelWidgets/blob/main/docs/snippets.md), [writing a widget](https://github.com/NullMember/PyxelWidgets/blob/main/docs/writing-a-widget.md), [writing a driver](https://github.com/NullMember/PyxelWidgets/blob/main/docs/writing-a-driver.md), [threads](https://github.com/NullMember/PyxelWidgets/blob/main/docs/threads.md), [API reference](https://github.com/NullMember/PyxelWidgets/blob/main/docs/api.md)
- [Examples](https://github.com/NullMember/PyxelWidgets/tree/main/examples) and the [changelog](https://github.com/NullMember/PyxelWidgets/blob/main/CHANGELOG.md)

## License

MIT. PyxelWidgets started as Malik Enes Şafak's 2022 master's thesis
(tag `thesis-2022`) and was redesigned for 1.0.
