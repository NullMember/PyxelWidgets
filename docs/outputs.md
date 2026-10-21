# Outputs: sending to other software

Outputs are where widgets' messages go: a DAW, a synth, an OSC app, another
computer, or your own keyboard and mouse. With *feedback*, what comes back
updates the widgets, so a DAW can light the pads.

| Output | For | Tried with |
|--------|-----|------------|
| MIDI port | any MIDI software, a virtual port or an existing one | macOS, Android (USB and Bluetooth ports) |
| DAW (PyxelWidgets script) | the same commands in every DAW: transport, mixer, macros, clips, names | REAPER 7.82; Ableton Live and Cubase not yet |
| Mackie Control | a DAW's mixer, transport, plug-ins and tracks by name | REAPER, Logic Pro, Cubase 15 |
| HUI | Pro Tools (mixer, transport, plug-ins by name) | Pro Tools |
| OSC, REAPER | OSC apps; REAPER's tracks and plug-ins by name | REAPER 7 |
| Network MIDI | another computer over the network (RTP-MIDI) | macOS, an Android phone |
| Bluetooth MIDI | a computer connecting to the grid (BLE MIDI) | macOS with a Raspberry Pi and an Android phone |
| Keyboard and mouse | shortcuts, typing, the pointer (macro boards) | not yet |

## A DAW, the same way everywhere

Controller makers ship a script per DAW so their controller works the same in
each. PyxelWidgets does too: the **DAW** output speaks one set of commands
(`Play`, `Record`, `Loop`, `Track Left`, `Bank Right`, `Volume 1`-`8`,
`Mute 1`-`8`, `Macro 1`-`8`, `Launch 1`-`8`...; the full list is in
`pyxelwidgets.devices.daw`) and a small script inside the DAW carries them out
and sends back lights, values and names (`Track Name 1`, `Selected Name`,
`Device Name`, `Macro Name 1`, `Macro Value 1`). A layout made this way works
with every DAW that has the script:

```sh
pyxelwidgets daw list                 # the DAWs with a script, and where it goes
pyxelwidgets daw install reaper       # writes it there and says how to turn it on
```

| DAW | Script | Turn it on | Status |
|-----|--------|------------|--------|
| REAPER | Lua (`Scripts/PyxelWidgets`) | enable the "PyxelWidgets DAW" MIDI input and output, run the script (or make it a startup action) | tried (REAPER 7.82: every command) |
| Ableton Live | remote script (`User Library/Remote Scripts`) | a Control Surface slot "PyxelWidgets" with that port as input and output | not tried yet |
| Cubase, Nuendo | MIDI Remote (`MIDI Remote/Driver Scripts/Local`) | MIDI Remote Manager > Reload Scripts: it finds the port by name | not tried yet |
| Logic, Pro Tools | none: no way to add scripts | use the Mackie Control or HUI output | |

Macros are the selected track's first plug-in (REAPER), its selected device
(Live) or its quick controls (Cubase), 8 at a time (`Macro Page Left`/`Right`).
Clip and scene commands only do something in Live. Start PyxelWidgets before
the DAW, or reload the script, so the DAW sees the port. In the designer: add a
*DAW (PyxelWidgets script)* output with the virtual port `PyxelWidgets DAW`;
its commands are in the message editor's pickers like Mackie's.

## Messages

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

A device's knob, fader or button sends messages directly too:
`surface.map(surface.control(xl, 'Knob_0'), synth, ControlChange(74), on = ControlChanged)`
(no feedback: there's no widget to show it).

Layouts store outputs and mappings, and the designer edits them: add an output
under *Outputs*, then *Add message* on a widget, or on a device for one of its
controls (it opens the messages and links window). Mackie Control and HUI
commands (and REAPER's OSC addresses) are picked from a list, with one-per-pad
variants such as `Mute {x+1}`. In Try mode the event log shows
what would be sent; when the output is connected it is sent. See `examples/MidiDrums`
(made in the designer) and `examples/DAWControl`.

## Plug-in parameters (Mackie Control)

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

## HUI (Pro Tools)

`HUI` speaks the protocol Pro Tools uses for control surfaces (REAPER and Logic
know it too): the strips' faders (touched for you, since Pro Tools ignores
untouched faders), mutes, solos, the transport, the jog wheel, the DSP knobs,
and feedback for the lights, faders, rings, meters, timecode and displays.
Plug-in parameters are reached by name like Mackie Control's (`scan_tracks`,
`scan_plugins`, `scan_parameters`, `PluginParameter`):

```python
from pyxelwidgets.devices.mackie import HUI

hui = HUI()
hui.connect_virtual('PyxelWidgets HUI')
surface.map(play, hui, Command('Play'), on = Pressed, feedback = True)
```

In Pro Tools: Setup > Peripherals > MIDI Controllers, type *HUI*, receive from
and send to the PyxelWidgets port. Pro Tools shows a track's insert slots 1 to
8 to HUI (9 and 10 can't be reached), and a plug-in's parameters a page at a
time (up to 4 switches and 4 knobs), so scanning a plug-in takes about 2
seconds a page.

## Track volume, pan, mute, solo and record by name

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

## Plug-in parameters (REAPER)

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

## Network MIDI

Network MIDI (RTP-MIDI, Apple's network MIDI) sends MIDI to another computer
over Wi-Fi or Ethernet, e.g. from a Raspberry Pi or a phone running the grid.
The session announces itself, so the other computer finds it by name (Bonjour:
the `network` extra, the system's `dns-sd` or `avahi-publish-service`, or
Android's own).

```python
from pyxelwidgets.devices.rtp_midi import RtpMidi

network = RtpMidi(session = 'Pi grid')            # or connect = 'macbook.local' to invite it
network.connect()
surface.map(kick, network, NoteOn(36), on = Pressed)
```

- **macOS:** Audio MIDI Setup > Window > Show MIDI Studio > Network. The
  session shows under *Directory*; select it and press *Connect*. The Mac's own
  session (under *My Sessions*) must be enabled: it's the port your DAW sees.
- **Windows:** rtpMIDI (Tobias Erichsen), the same way. **Linux:** rtpmidid.
- With `connect`, the grid invites the computer itself, and again whenever it
  comes back (on macOS, set "Who may connect to me" to *Anyone*).

In the designer, add a *Network MIDI* output. Its row shows who joined.

## Bluetooth MIDI

There are two ways round.

**Bluetooth MIDI devices** (a BLE MIDI keyboard or controller, or a computer
advertising MIDI) connect from the designer's *Bluetooth* button under
Devices: *Scan*, then *Connect*. Once connected, a device's ports are listed
with the other MIDI ports, so devices, outputs and *Sync to a DAW* use them by
name. Connected devices are remembered, and connect again when they come back
in range or when the program starts. This works on macOS, Windows and Linux
(the `bluetooth` extra) and in the Android app. In code:

```python
from pyxelwidgets.devices import bluetooth

devices = bluetooth.manager()
found = devices.scan()                            # [{'address': ..., 'name': ..., 'rssi': ...}]
name = devices.connect(found[0]['address'])      # then MidiPort().connect(name, name), say
```

Some devices encrypt their MIDI and stay silent until they're paired. The
Android app shows whether each device is paired, with a *Pair* button: press
it and accept the request. On macOS and Windows, accept the system's pairing
request when it shows.

**The grid as a Bluetooth MIDI device** (`BleMidi`): a Raspberry Pi (Linux
with BlueZ) or an Android phone advertises itself, and a computer connects to
it.

```python
from pyxelwidgets.devices.ble_midi import BleMidi

bluetooth = BleMidi()                             # Linux (BlueZ) and the Android app
bluetooth.connect()
surface.map(kick, bluetooth, NoteOn(36), on = Pressed)
```

- **macOS:** Audio MIDI Setup > MIDI Studio > the Bluetooth button >
  *Connect*.
- **Raspberry Pi:** the user needs the `bluetooth` group
  (`sudo usermod -aG bluetooth $USER`). Raspberry Pi OS's own MIDI plugin
  drops a Mac after 30 seconds: start bluetoothd with `-P midi`
  (`sudo systemctl edit bluetooth`). The output's warning says so while the
  plugin runs. A Pi Zero's Bluetooth shares its radio with 2.4 GHz Wi-Fi, so
  timing is steadier with the Wi-Fi idle or off.
- **Android:** the phone advertises under its own Bluetooth name.
- `secure = True` asks the computer to pair first.

## Following a DAW's clock

The transport can follow a DAW's MIDI clock: its tempo, start, stop and
position. Sequencers, Trackers and the other timed widgets then play with the
DAW. In the designer it's *Sync to a DAW* on the Surface panel (select empty
space to see it). In a layout it's `transport.sync`:

| Setting | The clock comes in through |
|---------|----------------------------|
| `{"virtual": "PyxelWidgets Clock"}` | a virtual port the DAW sends to (macOS, Linux) |
| `{"input": "IAC Driver Bus 1"}` | an existing MIDI input port, including a connected Bluetooth device |
| `{"output": "Bluetooth"}` | one of the layout's outputs the DAW connects to: network MIDI, Bluetooth MIDI or a MIDI port |

In the DAW, turn on MIDI clock (and song position) output to that port:

- **REAPER:** Preferences > MIDI Devices > the port's output > *Send clock/SPP*.
- **Ableton Live:** the port's *Sync* switch under MIDI outputs.
- **Logic:** MIDI Sync settings > Clock to the port.

The tempo is measured from the clock, and shown in the designer while it
follows. In code:

```python
from pyxelwidgets import App
from pyxelwidgets.devices.midi_clock import ClockFollower, MidiClockInput, MidiClockOutput

app = App(surface, sync = True)                  # the transport follows a clock
clock = MidiClockInput(app.transport)
clock.connect_virtual('PyxelWidgets Clock')      # or ClockFollower(app.transport, bluetooth)
# Or send the transport's clock: MidiClockOutput(app.transport).connect(out_port = 'IAC Driver Bus 1')
```

See `examples/ClockSync`.

### Sending the clock

The other way round, the controllers keep time and the DAW follows: the
transport's clock, start, stop and position go out through some of the
layout's MIDI outputs while it plays (`"transport": {"clock": ["midi"]}`; in
the designer *Send MIDI clock* on the Surface panel). Set the DAW to follow
that port (REAPER: *Synchronize to MIDI clock* in the Project Settings and the
port's input enabled; Ableton Live: the port's *Sync* switch under MIDI
inputs; Logic: MIDI Sync > Listen to MIDI Clock). In code:
`app.clocks.append(ClockSender(app.transport, output))`.

## Keyboard and mouse

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
