# MiniLab Studio: a MiniLab 3 on its own

A small studio on nothing but a MiniLab 3: finger drums, a euclidean beat, a
snare and a bass sequencer, chords, an arpeggiator, a lead, a generative
voice, effects, mutes, patterns and tempo, on 16 pads. It keeps time and
plays your synths on six MIDI channels. Open it in the designer or play it:

```sh
pyxelwidgets run examples/MiniLabStudio/layout.json
```

## Set up once

1. On the MiniLab 3, pick its **DAW** program.
2. In your DAW (or any synths), tracks listening to the virtual port
   **PyxelWidgets Studio** on these channels:

   | Channel | Voice | Played by |
   |---------|-------|-----------|
   | 10 | drums (kick 36, snare 38, hats 42; pads 36-51) | Drums, Beat, Snare |
   | 2 | bass | Bass |
   | 3 | chords | Chords |
   | 4 | arpeggio | Arp |
   | 1 | lead (pitch, mod, sustain, filter, envelope) | the keys, Lead |
   | 5 | generative | Gen |

3. Optional: let the DAW follow the clock sent on that port, so its tempo
   and position match.

To hear something right away: **Shift + Rec**, then the bottom-left pad
(pattern 1 is a starter groove), then **Shift + Play**.

## The pads: turn the encoder to change page

The screen names each page. Bank A (the Pad button) is the bottom row, bank B the top.

1. **Drums:** 16 finger drums (notes 36-51), velocity-sensitive.
2. **Beat:** euclidean rhythms: bottom row the kick (8 eighths), top row the
   hats (8 sixteenths). Press a pad to set how many hits (press it again for
   none); hold one and press another to rotate.
3. **Snare:** 16 steps (bank A steps 1-8, bank B 9-16), soft hits recorded
   as soft steps.
4. **Bass:** 16 steps. The keys play the bass here, and the line follows the
   last key you played.
5. **Chords:** a column per degree of the key, triads below, sevenths above.
6. **Arp:** hold pads or **keys** (only here) and it arpeggiates them; the
   sustain pedal latches.
7. **Lead:** the key's notes on the pads, two octaves.
8. **Gen:** Conway's Game of Life playing the key; the right column makes new
   cells (top) or clears (bottom). Switch it on in Mutes.
9. **Mutes:** top row turns each voice on or off (kick, hats, snare, bass,
   chords, arp, lead, gen); the meters below light when each voice plays.
10. **FX:** an XY pad for the lead and arp filter (left/right cutoff,
    up/down resonance; springs back when let go), lead attack and release knobs.
11. **Patterns:** top row stores, bottom row recalls the beat, snare, bass,
    mutes and generative cells (8 slots, saved in the layout file).
12. **Tempo:** tap tempo, -/+ 1 bpm (hold to repeat), a light per beat.

## The rest of the MiniLab

- **Knobs:** swing, gate, humanize (random velocity), key, scale (minor,
  major, dorian, phrygian, mixolydian, minor pentatonic, harmonic minor,
  blues), arp mode, arp range, space (reverb send, every channel). The
  screen shows each value; key and scale reach chords, arp, lead and gen.
- **Faders:** drums, bass, chords and arp volume.
- **Keys** play the lead with the pitch and mod strips and the sustain pedal
  (the bass on the Bass page, the arpeggiator on the Arp page).
- **Encoder:** the page; Shift + turn: tempo. Click shows where the widgets
  are, Shift + click goes back to the start.
- **Shift + pads:** Loop = Mutes, Stop = stop and back to the start,
  Play = play/stop, Rec = Patterns, Tap = tap tempo. Loop and Rec stay lit
  while their page shows.
