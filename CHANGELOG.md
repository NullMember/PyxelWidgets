# Changelog

## Unreleased

- **Clock out:** the transport's MIDI clock, start/stop and position go out
  through outputs (`transport.clock`, *Send MIDI clock*), so a DAW follows the
  controllers.
- **Keyboards:** a controller's keys are a control (`KeyPressed`/`KeyReleased`
  with the note): MiniLab keys, pitch and mod strips and sustain pedal.
- **Rates follow changes:** a Sequencer's (or other timed widget's) `rate`
  changed by a link or formula now changes when it plays.
- **Fixes:** a Switch Button starting on turns off on the first press;
  TapTempo has a `tap` action (a controller's Tap button).
- **Layout format version 4:** `transport.clock` and keyboard events.

- **Control lights, rings and screens:** buttons with a light on more
  controllers (APC Mini, APC40 MK2, Push 2, ATOM, Launch Control XL) show the
  widget they're bound to and light up while held; the APC40 MK2's knob rings
  show their widget's value; the MiniLab 3's and Launchkey MK3's screens show
  the widget a control moved and its value (or what a link of that widget
  writes there). Links can set a control's light and a screen's text
  (`surface.light`, `surface.screen`).
- **MiniLab 3 tried on hardware:** its Shift + pad buttons are pads 4-8 (lit
  while Shift is held, with velocity), knobs go on from their widget's value,
  the encoder steps evenly both ways, the screen comes back after Shift, and a
  warning says when the DAW program isn't on. `examples/MiniLab3` tries it all.
  Its knobs can be encoders (`relative_knobs`).
- **Layout format version 3:** a link's `target` can be a device's control,
  `{"device": 0, "control": "Play"}`, with the option `light` or `text`.

- **Controls send messages and start links themselves:** a device's knob,
  fader, encoder or button can send messages to outputs and change widgets'
  options without a widget in between (`surface.control(device, name)` in
  code; on the device's panel in the designer).
- **Layout format version 2:** mappings and links can start from
  `"device"`/`"control"` instead of a `"widget"`. Version 1 layouts load as
  they are; files saved by this version need it to open them.

## 1.0.0

The first release since the 2022 thesis version (tag `thesis-2022`): a
redesign from the ground up. Layouts made with pre-release versions of the
designer need their `"version"` set to `1`.

- **Designer:** lay out widgets in the browser or in the app's window, try
  them on a live preview and on connected devices, wire them to each other
  (links, formulas) and to other software (messages), with templates,
  snippets, undo, copy/paste, learning controls and messages, and a Python
  export.
- **Player:** `pyxelwidgets run layout.json` plays a layout without the
  designer; devices reconnect when plugged back in.
- **Apps:** the designer in a window of its own for macOS, Windows and Linux
  (with a player mode and a headless mode), and an Android app (USB,
  Bluetooth and network MIDI, a touch grid, playing in the background).
- **Widgets:** Arpeggiator, Automaton, Button, ButtonGroup, ChordPads,
  ClipLauncher, DrumPads, Euclidean, Fader, Keyboard, Knob, Meter, MeterBank,
  PianoRoll, Sequencer, Sprite, Stepper, TapTempo, Text, Tracker, XY, and the
  Group, Pages and Presets containers.
- **Devices:** Novation Launchpads (MK1, MK2, Pro, X, Mini MK3, Pro MK3),
  Launchkeys, Launch Control and XL, Akai APC Mini and APC40 MK2, Ableton
  Push 2, Arturia MiniLab mkII and 3, PreSonus ATOM, a browser grid (Web
  Grid) and an on-screen grid. Only the Launchpad Mini MK3 has been tried on
  hardware; see the docs' hardware page.
- **Outputs:** MIDI ports, Mackie Control and HUI (with plug-in parameters
  and tracks by name in Logic, Cubase, REAPER and Pro Tools), OSC and
  REAPER, network MIDI (RTP-MIDI), Bluetooth MIDI (both ways), and the
  computer's keyboard and mouse.
- **Time:** a transport with swing, gates, ratchets and probabilities,
  following a DAW's MIDI clock over a port, Bluetooth or the network, or
  sending one.
