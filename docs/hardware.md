# Hardware

PyxelWidgets has drivers for these grid controllers. **Only the Launchpad Mini
MK3 has been tried on hardware.** The other drivers follow their makers'
programmer's manuals, and most send exactly what the 2022 drivers sent
(checked by the test suite against recordings). Some are new and have never
been tried. If you own one, please try it and tell us what works: the
designer's *Check this device* (in a connected device's panel) walks you
through it and makes a report to attach to an
[issue](https://github.com/NullMember/PyxelWidgets/issues).

## Grid controllers

| Device | Layout type | Grid | Colors | Other controls | Status |
|--------|-------------|------|--------|----------------|--------|
| Novation Launchpad Mini MK3 | `novation.LaunchpadMiniMK3` | 9x9 (8x8 + side buttons) | RGB | side buttons | **Tested** |
| Novation Launchpad X | `novation.LaunchpadX` | 9x9 | RGB | side buttons, pressure | Untested |
| Novation Launchpad Pro MK3 | `novation.LaunchpadProMK3` | 10x10 | RGB | side buttons, pressure | Untested |
| Novation Launchpad Pro | `novation.LaunchpadPro` | 10x10 | RGB | side buttons, pressure | Untested |
| Novation Launchpad MK2 | `novation.LaunchpadMK2` | 9x9 | RGB | side buttons | Untested |
| Novation Launchpad, Launchpad S, Launchpad Mini (MK1, MK2) | `novation.LaunchpadMK1` | 9x9 | red/green | side buttons | Untested |
| Novation Launchkey MK3 | `novation.LaunchkeyMK3` | 8x2 | RGB | knobs, buttons | Untested |
| Novation Launchkey MK2 | `novation.LaunchkeyMK2` | 8x2 | RGB | knobs, faders, buttons | Untested |
| Novation Launchkey (MK1) | `novation.LaunchkeyMK1` | 9x2 | red/green | knobs, faders, buttons | Untested |
| Novation Launch Control XL | `novation.LaunchControlXL` | 8x5 | red/green | knobs, faders, buttons | Untested |
| Novation Launch Control | `novation.LaunchControl` | 8x16 | red/green | knobs, buttons | Untested |
| Akai APC Mini | `akai.APCMini` | 8x8 | red/green/yellow | faders, buttons | Untested |
| Akai APC40 MK2 | `akai.APC40MK2` | 8x5 | RGB | knobs, faders, buttons, encoders | Untested |
| Ableton Push 2 | `ableton.Push2` | 8x8 | RGB | buttons, encoders, pressure | Untested |
| Arturia MiniLab mkII | `arturia.MiniLabMK2` | 8x2 | 8 colors | encoders | Untested, new |
| Arturia MiniLab 3 | `arturia.MiniLab3` | 8x2 | RGB | knobs, faders, buttons, encoders, screen | Untested, new |
| PreSonus ATOM | `presonus.ATOM` | 4x4 | RGB | buttons, encoders | Untested |

"Untested" drivers send what the 2022 drivers did, except where a fix was
needed (Launchpad MK2, X and Mini MK3 grid origin, Launch Control XL and APC
Mini fader range, APC note-off, Push 2 note-off). "New" ones were written in
2026 from the makers' documentation and other software's scripts.

Known questions for owners:

- **Launchpad MK2 and Pro:** the color SysEx uses command `03`; it may need to
  be `0B` on these models. The MK2's top row LEDs may be 104-111 rather than
  91-98.
- **APC40 MK2:** the Cue and Tempo knobs are read as centred on 64; that may
  be wrong.
- **Pressure** (Launchpad X, Pro, Pro MK3, Push 2): decoded from the manuals.
- **Arturia MiniLab mkII:** the encoder clicks aren't read yet. Disconnecting
  leaves the controller's settings changed (pick a memory on it to restore).
- **Arturia MiniLab 3:** the port name is a guess (`Minilab3 MIDI`). Pads send
  their notes only in its DAW program.

## Without hardware

| Device | Layout type | What it is |
|--------|-------------|------------|
| Web Grid | `web.WebGrid` | Pads in any browser on the network: a phone, a tablet. Multi-touch, pen pressure, fullscreen, and *Add to Home Screen* on phones. **Tested** (macOS, Android). |
| Virtual | `virtual.Virtual` | A window on the computer (Tk). |

## Outputs

[Outputs](outputs.md) lists what each output has been tried with. Other
pieces still waiting for someone to try them:

- the keyboard and mouse output;
- the desktop apps on Windows and Linux (built by CI, not yet tried);
- Bluetooth MIDI on a Linux computer connecting to devices (Linux as the
  device, on a Raspberry Pi, is tested);
- network MIDI joined by hand from macOS's Audio MIDI Setup (the session is
  found there, and joining was tested from code);
- HUI beyond the strips, transport and DSP section (other zones, timecode).

## Adding a device

[Writing a driver](writing-a-driver.md) shows a new MIDI pad controller from
scratch: its ports, grid, colors, controls and tests. `examples/DeviceCheck`
lights a test pattern and prints every event, to check a device from a
terminal.
