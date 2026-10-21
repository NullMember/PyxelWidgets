# Rig: making music on a Launchpad Mini MK3 and a MiniLab 3

A layout for producing without touching the computer: the controllers keep
time, play instruments in your DAW (one MIDI channel each) and drive the DAW
itself. Open it in the designer or play it:

```sh
pyxelwidgets run examples/Rig/layout.json
```

## Set up once

1. **The DAW script** (transport, mixer, macros): `pyxelwidgets daw install reaper`
   (or `live`, `cubase`) and turn it on as it says. It talks to the virtual port
   **PyxelWidgets DAW**. Logic and Pro Tools have no scripts: change the `daw`
   output to Mackie Control or HUI.
2. **Instruments:** in the DAW, tracks listening to the port **PyxelWidgets Rig**
   on these channels:

   | Channel | Part | Played by |
   |---------|------|-----------|
   | 10 | drums (notes 36-51, a drum rack's pads) | Drums mode, MiniLab finger drums |
   | 2 | bass | Bass mode |
   | 3 | lead | Lead mode |
   | 4 | keys | MiniLab keys (with pitch, mod and sustain), Keys mode |
   | 5 | chords | Chords mode |
   | 6 | arpeggio | Arp mode, from the MiniLab keys |

3. **Clock:** the DAW follows the controllers: set it to sync to MIDI clock
   from **PyxelWidgets Rig** (REAPER: Project Settings > *Synchronize to MIDI
   clock* and the port enabled; Live: the port's *Sync* input switch).
4. On the MiniLab 3 pick its **DAW** program.

## Launchpad

The **top row** picks the mode: Drums, Bass, Lead, Keys, Chords, Arp, Mixer,
Macros. The **right column** is the transport and the DAW: play/stop
(the controllers' transport), stop (and back to the start), record, loop,
metronome (lit by the DAW), undo, tap tempo, capture.

- **Drums:** 8 drum tracks. Top half: the selected track's 32 steps. Below:
  hold steps and press velocity (4 levels), chance (50% / always) or ratchet
  (1 / 2 hits); length 8/16/32, rate 1/32, 1/16, 1/16T, 1/8, clear; the track
  select row; the mute row.
- **Bass, Lead:** piano rolls in the key; bottom row: 16/32 steps, octave
  down/up, page back/forward, clear. Drums, bass and lead are the **patterns**
  (MiniLab, Shift + Rec).
- **Keys:** a keyboard in the key, octave down/up; bottom rows set **the key**
  for everything: scale (minor, major, dorian, phrygian, mixolydian, minor
  pentatonic, harmonic minor, blues) and root (C-B, the last pad sharpens).
- **Chords:** chords of the key's degrees (columns) in different kinds (rows); octave down/up.
- **Arp:** the arpeggiator's pads (or the MiniLab keys) in the key; mode (up,
  down, up-down, random, as played), latch (or the sustain pedal), octaves
  1-4, rate 1/8, 1/16, 1/16T, 1/32.
- **Mixer:** the DAW's 8 tracks: volume, solo, mute, select (lit by the DAW).
- **Macros:** the selected device's 8 parameters in the DAW; bottom row:
  track left/right, device left/right, parameter page left/right, device on,
  automation write.

## MiniLab 3

- **Knobs:** the DAW's 8 macros (they go on from where the DAW has them).
- **Faders:** the selected drum track's swing, gate and humanize; the DAW's
  selected track's volume.
- **Keys** play channel 4 (pitch bend, mod wheel, sustain), or the
  arpeggiator in Arp mode.
- **Encoder:** tempo (Shift: 10 bpm steps); click shows where the widgets are,
  Shift + click goes back to the start.
- **Pads**, Shift + Loop / Stop / Rec (lit while on): drum track select and
  mutes; 16 finger drums; patterns (bank A recalls 1-8, bank B stores).
- Shift + Play plays, Shift + Tap taps the tempo. The screen says what moved.
