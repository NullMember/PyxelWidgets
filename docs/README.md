# PyxelWidgets documentation

- [Writing a widget](writing-a-widget.md): a die you press to roll, from its options to the designer.
- [Writing a driver](writing-a-driver.md): a MIDI pad controller, its colors, controls and tests.
- [Threads](threads.md): what runs where, and the one lock.
- [API reference](api.md): every module, class and function, from the docstrings.

## How the pieces fit

Every piece works without the bigger ones: a widget without a surface, a
device without an App, a transport without widgets. Modules only import the
layers below them:

```
app, parser, designer       glue: run a surface, read layout files, edit them
surface                     maps a widget tree onto devices; bindings, mappings, links
group                       containers: Group, Pages
widgets | devices.* | transport | binding | mapping
link                        widgets changing widgets
buffer, animation
color, rectangle, events, font, rate, message
```

- **Widgets** draw into their own buffer and emit events (`Pressed`,
  `Changed`, `NoteOn`...). Coordinates start at the bottom-left pad.
- **Devices** turn hardware input into pad and control events, and frames
  into LED messages. A device can also be a browser (`WebGrid`) or a window
  (`Virtual`).
- **The surface** places devices on one big grid, sends their pads to the
  topmost widget underneath, and renders. It also connects controls to
  widgets (bindings), widgets to other software (mappings) and widgets to
  each other (links).
- **The transport** keeps musical time and plays Sequencers, Trackers and
  ClipLaunchers; widgets can also have a clock of their own.
- **Layouts** are JSON files describing all of that. The designer edits them,
  and `parser.load` builds them.

The API reference is generated: run `python docs/build_api.py` after
changing docstrings.
