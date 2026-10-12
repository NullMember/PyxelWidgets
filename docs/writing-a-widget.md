# Writing a widget

A widget is a rectangle of pads with its own frame buffer. It knows nothing
about devices, surfaces or the transport: it takes presses, draws itself and
emits events. That keeps it usable alone, in tests and in any layout.

This guide builds a die you press to roll, then makes it available in layout
files and in the designer.

## The whole widget

```python
import dataclasses
import random

from pyxelwidgets import Color, Colors, Fade, parser
from pyxelwidgets.events import WidgetEvent
from pyxelwidgets.widgets import Widget


@dataclasses.dataclass(frozen = True)
class Rolled(WidgetEvent):
    """The die landed on ``value``."""
    value: int


# The dots of each face on a 3x3 grid, from the bottom-left
FACES = {
    1: [(1, 1)],
    2: [(0, 2), (2, 0)],
    3: [(0, 2), (1, 1), (2, 0)],
    4: [(0, 0), (0, 2), (2, 0), (2, 2)],
    5: [(0, 0), (0, 2), (1, 1), (2, 0), (2, 2)],
    6: [(0, 0), (0, 1), (0, 2), (2, 0), (2, 1), (2, 2)],
}


@parser.register
class Dice(Widget):
    """A die: press it to roll. Emits Rolled."""

    emits = (Rolled,)
    actions = {'roll': None}

    def __init__(self, x: int = 0, y: int = 0, width: int = 3, height: int = 3, *,
                 value: int = 1,
                 active_color: Color = Colors.White,
                 inactive_color: Color = Color(60, 0, 0),
                 **kwargs):
        """
        value: int = 1, optional
            The face shown, 1 to 6.
        """
        self.value = value
        super().__init__(x, y, width, height, active_color = active_color, inactive_color = inactive_color, **kwargs)

    def roll(self) -> None:
        """Land on a random face, fading it in."""
        self.value = random.randint(1, 6)
        self.updated = True
        self.animation = Fade(0.2)
        self.emit(Rolled(self, self.value))

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        self.roll()

    def draw(self) -> None:
        self.buffer[:] = self.inactive_color
        w, h = self.rect.w, self.rect.h
        for dx, dy in FACES.get(self.value, []):
            # Spread the 3x3 positions over the widget's size
            self.buffer[round(dx * (w - 1) / 2), round(dy * (h - 1) / 2)] = self.active_color

    def save_state(self) -> dict:
        return {'value': self.value}

    def load_state(self, state: dict) -> None:
        if 'value' in state:
            self.value = state['value']
            self.updated = True
```

## Step by step

### Options

The constructor is the widget's contract with layouts and the designer:

- **Position and size first** (`x, y, width, height`), then `*`, then options:
  keyword-only, with type annotations and defaults. A typo then raises a
  `TypeError` instead of being ignored.
- **Pass everything else on** with `**kwargs`, so the base options
  (`name`, `visible`, `propagation`...) keep working. Set your attributes
  *before* `super().__init__`, which calls `_resize`.
- **The annotations decide how the designer edits an option**: `int`,
  `float`, `bool`, `str`, `Color` (a color picker), an `Enum` (a list),
  `Rate` or `Rate | float` (a note value, or seconds too), `Frames`
  (Sprite frames). Anything else stays out of layouts.
- **Docstrings:** the class docstring's first paragraph is the description
  the designer shows. Option descriptions go in the constructor docstring,
  in the `name: type = default, optional` style the API reference picks up.

`parser.option_schema(Dice)` shows what layouts and the designer see.

### Input

Override the `handle_*` hooks; the public methods (`press`, `release`,
`hold`, `double_press`, `pressure`) emit the event first and then call
them:

| Hook | Called for |
|---|---|
| `handle_press(x, y, velocity)` | a pad pressed (velocity 1.0 on pads without velocity) |
| `handle_release(x, y, velocity)` | a pad released |
| `handle_hold(x, y, velocity)` | a pad held longer than the device's `held_time` |
| `handle_double_press(x, y, velocity)` | a quick second press |
| `handle_pressure(x, y, pressure)` | aftertouch of a held pad |

Coordinates are the widget's own, with `(0, 0)` at the bottom-left.

`propagation` decides whether a press also reaches the widgets underneath:
`Propagation.Stop` (the default) or `Propagation.Pass` for display-only
widgets (Text, Sprite and Meter pass by default).

A widget with one value (a fader, a knob...) can extend `ValueWidget`
instead. It has `value` (0.0-1.0, or a tuple), `interactive`, and
`set_value(value)`, which emits `Changed` as input should.

### Drawing

- **`draw()`:** fills `self.buffer`, a `(width, height, 4)` RGBA numpy array.
  Index it `[x, y]`; assigning a `Color` works. `Colors.Invisible` lets the
  widgets underneath show through.
- **When it runs:** only when `self.updated` is True. Set it whenever what
  you show changes; nothing redraws otherwise.
- **Animations:** don't code blinking or fading yourself. Set
  `self.animation` (`Blink`, `Pulse`, `Fade`) or `animate_cell(x, y, ...)`;
  `render()` applies them on top of your drawing.
- **Time-based display:** override `render(time)`. Set `updated` when the
  frame should change, then call `super().render(time)`. Text (scrolling)
  and Meter (falling bars) do this.
- **Resizing:** `_resize(width, height)` is called with the new size before
  drawing. Recompute size-dependent data there and return True, or False
  to refuse the size.

### Events

Events are frozen dataclasses subclassing `WidgetEvent` (its first field is
the widget). Name them in the past tense. Listing them in `emits` makes
`events()` return them, so:

- the designer offers them for messages and links;
- every `int`, `float`, `bool` or `str` field becomes a value messages and
  links can use (`value` here, as `{"source": "value"}`).

```python
die.on(Rolled, lambda e: print('rolled', e.value))
```

### Actions, state, feedback

- **`actions`:** methods links may call, by name, each with `None` (no
  argument) or `'int'` (a number from the link). The designer lists them
  under *Actions*: here a button can roll the die.
- **`save_state()` / `load_state()`:** whatever input changed (not options).
  The designer uses them to keep widgets as they were while you edit the
  layout. `load_state` must not emit events.
- **`receive(values)`:** shows what another program sends back through a
  mapping with `feedback` (`value`, `state`, `x`/`y`, `text`...), again
  without emitting events. The base class handles blinking (`flash`).
- **`configure(**options)`:** changes options after construction; links use
  it. It sets the attribute of the same name and redraws. Options stored
  differently override `_configure(name, value)`; options that change the
  layout of the widget go in `reshaping` so `_resize` runs again.

## Using it

On its own, or on a surface like any widget:

```python
die = Dice()
die.on(Rolled, print)
die.press(1, 1)
die.render()                     # die.buffer holds the face

surface.add(Dice(0, 0, 3, 3, name = 'die'))
```

In layout files and the designer, `@parser.register` makes it known by its
class name. Import the module before loading a layout:

```python
import dice                      # registers Dice
ui = parser.load('layout.json')  # may contain {"type": "Dice", ...}
```

and start the designer with it:

```sh
pyxelwidgets-designer layout.json --import dice.py
```

It appears in the palette with its options, events and actions.

## Checklist

- [ ] Keyword-only options with types and defaults; `**kwargs` passed on.
- [ ] `self.updated = True` whenever the drawing changes.
- [ ] Events in `emits`; frozen dataclasses with simple field types.
- [ ] `save_state`/`load_state` for what input changes.
- [ ] No imports of devices, the surface or the transport: a widget works alone.
- [ ] A test that presses it and checks `buffer` and the events.
