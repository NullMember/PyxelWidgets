# PyxelWidgets  
GUI Framework for low resolution devices (e.g. Novation Launchpad, LED Keyboards)  
This project is part of my master's thesis. Because of time constraints, this project is still in alpha phase.

## Supported Devices  

| Brand      | Family     | Model      | Generation | Support    | Protocol   | Grid       | Color      | Control    |
|------------|------------|------------|------------|------------|------------|------------|------------|------------|
| Virtual    | -          | -          | -          | Full       | tkinter    | NxN        | RGB b 8    | ----       |
| Ableton    | -          | Push       | 2          | Full       | MIDI       | 8x8        | RGB P 128  | B--E       |
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
