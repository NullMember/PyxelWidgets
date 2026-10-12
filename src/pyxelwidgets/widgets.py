import pyxelwidgets.animation
import pyxelwidgets.buffer
import pyxelwidgets.events
import pyxelwidgets.font
import pyxelwidgets.color
import pyxelwidgets.rectangle
import numpy
import enum
import time
import typing

# A note value such as '1/16', '1/8.' or 'bar': how often a Transport plays a widget
# (see pyxelwidgets.transport). Widgets only store it.
Rate = typing.NewType('Rate', str)

class Propagation(enum.Enum):
    """
    What happens to a press after a widget handles it, when widgets overlap.

    Stop: widgets underneath don't receive it (default).
    Pass: it continues to the widget underneath (default for display-only widgets).
    """
    Stop = enum.auto()
    Pass = enum.auto()

class Widget(pyxelwidgets.events.Emitter):
    """
    Base class for all widgets: a rectangle of pads with its own frame buffer.

    A widget works on its own: feed it input with ``press``/``release``/...,
    call ``render()`` and read ``buffer``. Subscribe to its events with ``on``.
    Subclasses override ``draw`` and the ``handle_*`` input hooks.
    """
    # Per class counters for default names (Button_0, Fader_0, ...)
    _counts = {}

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 name: str | None = None,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.White,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Black,
                 visible: bool = True,
                 propagation: Propagation = Propagation.Stop):
        """
        Parameters
        ----------
        x, y: int
            Position in the parent Group, from left to right and bottom to top.
        width, height: int
            Size in pads, should be >= 1.
        name: str, optional
            Label used to find the widget in a Group. Defaults to ``<ClassName>_<n>``.
        active_color: Color = Colors.White, optional
            Color of active pads.
        inactive_color: Color = Colors.Black, optional
            Color of inactive pads.
        visible: bool = True, optional
            Hidden widgets are neither drawn nor receive input in a Group.
        propagation: Propagation = Propagation.Stop, optional
            Whether a press continues to overlapped widgets underneath.
        """
        self.name = name if name is not None else self._default_name()
        self.rect = pyxelwidgets.rectangle.Rectangle2D(x, y, width, height)
        self.active_color = active_color
        self.inactive_color = inactive_color
        self.propagation = propagation
        self._visible = visible
        self.updated = True
        self.buffer = pyxelwidgets.buffer.new(self.rect.w, self.rect.h, self.inactive_color)
        self._animation = None
        self.cell_animations = {}
        # The drawing before animations, while animated
        self._static = None
        self._resize(self.rect.w, self.rect.h)

    def _default_name(self) -> str:
        cls = type(self).__name__
        count = Widget._counts.get(cls, 0)
        Widget._counts[cls] = count + 1
        return f'{cls}_{count}'

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if value != self._visible:
            self._visible = value
            # Lets a parent Group notice the change and recompose
            self.updated = True

    @property
    def width(self) -> int:
        return self.rect.w
    
    @width.setter
    def width(self, value: int) -> None:
        if value > 0:
            self._set_size(value, self.rect.h)

    @property
    def height(self) -> int:
        return self.rect.h
    
    @height.setter
    def height(self, value: int) -> None:
        if value > 0:
            self._set_size(self.rect.w, value)

    def _set_size(self, width: int, height: int) -> None:
        # _resize implementations read self.rect, so update it first
        old = self.rect.w, self.rect.h
        self.rect.w, self.rect.h = width, height
        if not self._resize(width, height):
            self.rect.w, self.rect.h = old
            return
        self.buffer = pyxelwidgets.buffer.new(self.rect.w, self.rect.h, self.inactive_color)
        self.updated = True
        self.emit(pyxelwidgets.events.Resized(self, self.rect.w, self.rect.h))

    # Input: public methods emit the event, then call the matching handle_* hook

    def press(self, x: int, y: int, velocity: float = 1.0) -> None:
        """Press the pad at widget coordinates ``x``, ``y``."""
        self.emit(pyxelwidgets.events.Pressed(self, x, y, velocity))
        self.handle_press(x, y, velocity)

    def release(self, x: int, y: int, velocity: float = 0.0) -> None:
        self.emit(pyxelwidgets.events.Released(self, x, y, velocity))
        self.handle_release(x, y, velocity)

    def hold(self, x: int, y: int, velocity: float = 1.0) -> None:
        self.emit(pyxelwidgets.events.Held(self, x, y, velocity))
        self.handle_hold(x, y, velocity)

    def double_press(self, x: int, y: int, velocity: float = 1.0) -> None:
        self.emit(pyxelwidgets.events.DoublePressed(self, x, y, velocity))
        self.handle_double_press(x, y, velocity)

    def tap(self, x: int, y: int, velocity: float = 1.0) -> None:
        """Press and release the pad at ``x``, ``y``."""
        self.press(x, y, velocity)
        self.release(x, y, 0.0)

    def input(self, event: pyxelwidgets.events.PadEvent) -> bool:
        """
        Deliver a device pad event whose ``x``, ``y`` are already widget coordinates.
        Returns True if it should not reach widgets underneath.
        """
        x, y, velocity = event.x, event.y, event.velocity
        if isinstance(event, pyxelwidgets.events.PadPressed):
            self.press(x, y, velocity)
        elif isinstance(event, pyxelwidgets.events.PadReleased):
            self.release(x, y, velocity)
        elif isinstance(event, pyxelwidgets.events.PadHeld):
            self.hold(x, y, velocity)
        elif isinstance(event, pyxelwidgets.events.PadDoublePressed):
            self.double_press(x, y, velocity)
        return self.propagation == Propagation.Stop

    def handle_press(self, x: int, y: int, velocity: float) -> None:
        """Override to react to a press; ``velocity`` is 1.0 on pads without velocity."""

    def handle_release(self, x: int, y: int, velocity: float) -> None:
        """Override to react to a release."""

    def handle_hold(self, x: int, y: int, velocity: float) -> None:
        """Override to react to a pad held longer than the controller's ``held_time``."""

    def handle_double_press(self, x: int, y: int, velocity: float) -> None:
        """Override to react to a double press."""

    # Drawing

    def render(self, time: pyxelwidgets.animation.Time | None = None) -> bool:
        """
        Redraw ``buffer`` if needed, and apply animations at ``time`` (default:
        now, at 120 bpm); returns True if it changed.
        """
        if self._static is not None:
            # Draw on the drawing, not on the animated copy
            self.buffer = self._static
        drawn = self.updated
        if drawn:
            self.updated = False
            self.draw()
        if self._animation is None and not self.cell_animations:
            self._static = None
            return drawn
        self._static = self.buffer
        self.buffer = self._animate(time if time is not None else pyxelwidgets.animation.now())
        return True

    # Animations

    @property
    def animation(self):
        """An Animation of the whole widget (e.g. ``Blink('1/8')``), or None."""
        return self._animation

    @animation.setter
    def animation(self, value) -> None:
        self._animation = value
        self.updated = True

    def animate_cell(self, x: int, y: int, animation) -> None:
        """Animate the cell at widget ``x``, ``y``; None stops animating it."""
        if animation is None:
            self.cell_animations.pop((x, y), None)
        else:
            self.cell_animations[(x, y)] = animation
        self.updated = True

    def _animate(self, time: pyxelwidgets.animation.Time) -> numpy.ndarray:
        frame = self._static.copy()
        for (x, y), animation in list(self.cell_animations.items()):
            if 0 <= x < self.rect.w and 0 <= y < self.rect.h:
                frame[x:x + 1, y:y + 1] = animation.apply(frame[x:x + 1, y:y + 1], time)
            if animation.finished(time):
                del self.cell_animations[(x, y)]
        animation = self._animation
        if animation is not None:
            frame = animation.apply(frame, time)
            if animation.finished(time):
                self._animation = None
                # A fade out ends hidden
                if getattr(animation, 'out', False):
                    self.visible = False
        return frame

    def draw(self) -> None:
        """Override to draw the whole widget into ``self.buffer``. Set ``self.updated`` to keep animating."""

    def _resize(self, width, height) -> bool:
        return True

class ValueWidget(Widget):
    """
    A widget with a single value set by input: a float from 0.0 to 1.0 by default.
    Input emits ``Changed``; setting ``value`` from code doesn't.
    """

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 value = 0.0,
                 interactive: bool = True,
                 **kwargs):
        """
        value: optional
            Initial value.
        interactive: bool = True, optional
            If False, input doesn't change the value (``Changed`` is still emitted),
            e.g. for widgets that only mirror state sent back from a DAW.
        """
        self._value = self._clamp(value)
        self.delta = 0.0
        self.interactive = interactive
        super().__init__(x, y, width, height, **kwargs)

    def _clamp(self, value):
        return round(min(1.0, max(0.0, value)), 6)

    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, value) -> None:
        value = self._clamp(value)
        if value != self._value:
            self.delta = self._delta(self._value, value)
            self._value = value
            self.updated = True

    def _delta(self, old, new):
        return new - old
    
    def set_value(self, value) -> None:
        """Set the value as input would: respects ``interactive`` and emits ``Changed``."""
        value = self._clamp(value)
        if self.interactive:
            self.value = value
        self.emit(pyxelwidgets.events.Changed(self, value))

# Button class
class Button(ValueWidget):
    """A pad area acting as one button: momentary (Button), toggle (Switch) or toggle on hold (Mixed)."""
    class Mode(enum.Enum):
        Button  = enum.auto()
        Switch  = enum.auto()
        Mixed   = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 mode: Mode = Mode.Button,
                 **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.mode = mode
        self.state = False
        self.is_hold = False

    def handle_press(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Button:
            self.set_value(value)
        elif self.mode == Button.Mode.Switch:
            if self.state:
                self.set_value(0.0)
                self.state = False
            else:
                self.set_value(value)
                self.state = True
        elif self.mode == Button.Mode.Mixed:
            if self.is_hold:
                return
            else:
                self.set_value(value)
    
    def handle_release(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Button:
            self.set_value(0.0)
        elif self.mode == Button.Mode.Switch:
            pass
        elif self.mode == Button.Mode.Mixed:
            if self.is_hold:
                return
            else:
                self.set_value(0.0)
    
    def handle_hold(self, x: int, y: int, value: float):
        if self.mode == Button.Mode.Mixed:
            self.is_hold = not self.is_hold

    def draw(self) -> None:
        area = self.rect.origin
        self.buffer[area.slice] = self.active_color * self._value if self._value else self.inactive_color

# ButtonGroup class
class ButtonGroup(Widget):
    """A grid of buttons: one selected at a time (Switch), toggles (Multi) or momentary (Button); emits Toggled."""

    class Mode(enum.Enum):
        Button = enum.auto()
        Switch = enum.auto()
        Multi = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 mode: Mode = Mode.Switch,
                 **kwargs):
        self.state = numpy.ndarray((1, 1), dtype = numpy.bool_)
        super().__init__(x=x, y=y, width=width, height=height, **kwargs)
        self.mode = mode
        self.state.fill(False)
        self._old_button = [-1, -1]
        if self.mode == ButtonGroup.Mode.Switch:
            self.state[0, 0] = True
            self._old_button = [0, 0]

    def handle_press(self, x: int, y: int, value: float):
        before = self.state.copy()
        if self.mode == ButtonGroup.Mode.Button:
            self.state[x, y] = True
        if self.mode == ButtonGroup.Mode.Switch:
            self.state[self._old_button[0], self._old_button[1]] = False
            self._old_button = [x, y]
            self.state[self._old_button[0], self._old_button[1]] = True
        if self.mode == ButtonGroup.Mode.Multi:
            self.state[x, y] = not self.state[x, y]
        self._emit_toggled(before)
    
    def handle_release(self, x: int, y: int, value: float):
        if self.mode == ButtonGroup.Mode.Button:
            before = self.state.copy()
            self.state[x, y] = False
            self._emit_toggled(before)

    def _emit_toggled(self, before) -> None:
        for x, y in numpy.argwhere(before != self.state):
            self.updated = True
            self.emit(pyxelwidgets.events.Toggled(self, int(x), int(y), bool(self.state[x, y])))

    def draw(self) -> None:
        area = self.rect.origin
        self.buffer[area.slice] = numpy.where(self.state[(*area.slice, None)], self.active_color, self.inactive_color)

    def _resize(self, width, height):
        self.state.resize((width, height), refcheck = False)
        return True

# Fader class
class Fader(ValueWidget):
    """A fader along a row or column (or across the whole area with Matrix grid), drawn in several styles."""

    class Direction(enum.Enum):
        """
        Description
        ----
        Vertical faders are bottom to top,
        Horizontal faders are left to right.
        
        Enums
        ----
        Vertical\n
        Horizontal
        """
        Vertical    = enum.auto()
        Horizontal  = enum.auto()

    class Grid(enum.Enum):
        """
        Description
        ----
        Determines how multi-width vertical faders
        or multi-height horizontal faders will work
        
        Enums
        ----
        Simple\n
        Matrix
        """
        Simple      = enum.auto()
        Matrix      = enum.auto()

    class Type(enum.Enum):
        Single      = enum.auto()
        BoostCut    = enum.auto()
        Wrap        = enum.auto()
        Spread      = enum.auto()
        Collapse    = enum.auto()

    class Mode(enum.Enum):
        Simple      = enum.auto()
        Multi       = enum.auto()
        Magnitude   = enum.auto()
        Sensitive   = enum.auto()
        Relative    = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 direction: Direction = Direction.Vertical,
                 grid: Grid = Grid.Simple,
                 type: Type = Type.Wrap,
                 mode: Mode = Mode.Multi,
                 resolution: int = 4,
                 **kwargs):
        """
        Description
        ----
        Fader class implements Widget class

        Parameters
        ----
        name: str
            Unique widget name, used to find widgets registered on window.
        x: int
            x axis where widget will be placed on window, from left to right.
            x value should be positive
        y: int
            y axis where widget will be placed on window, from bottom to top.
            y value should be positive.
        width: int
            Widget width, should >= 1
        height: int
            Widget height, should >= 1
        
        Optional Parameters
        ----
        callback: function
            If widget value is changed this function will be called.  
            Should accept 3 parameters, (widget) name, event and value
        active_color: [r: int, g: int, b: int] = [255, 255, 255]
            If widget value is non-zero, this color will be used.
        inactive_color: [r: int, g: int, b: int] = [0, 0, 0]
            If widget value is zero, this color will be used.
        value: int = 0.0
            Default value of widget.
        direction: Fader.Direction = Fader.Direction.Vertical
            Can be Fader.Direction.Vertical or Fader.Direction.Horizontal.  
            This will affect how widget rendered and value is calculated.  
            Vertical faders from bottom to top, horizontal faders from left to right.
        grid: Fader.Grid = Fader.Grid.Simple
            Can be Fader.Grid.Simple or Fader.Grid.Matrix.  
            Simple faders will use only one axis.  
            Matrix faders will use both x and y axis.
        type: Fader.Type = Fader.Type.Wrap
            Single: Only corresponding pad will active.  
            BoostCut: Corresponding pads from middle active.  
            Wrap: Corresponding pads from bottom active.  
            Spread: Corresponding pads from middle active symmetrically.  
        """
        self.direction = direction
        self.grid = grid
        self.type = type
        self.mode = mode
        self.resolution = resolution
        super().__init__(x, y, width, height, **kwargs)
        self._multi_step = 0
        self._old_button = [-1, -1]
        self._held_button = [-1, -1]

    def handle_press(self, x: int, y: int, value: float):
        if self.mode == Fader.Mode.Simple:
            self.set_value(self._pressed_simple(x, y, value))
        elif self.mode == Fader.Mode.Multi:
            self.set_value(self._pressed_multi(x, y, value))
        elif self.mode == Fader.Mode.Magnitude:
            self.set_value(self._pressed_magnitude(x, y, value))
        elif self.mode == Fader.Mode.Sensitive:
            self.set_value(self._pressed_sensitive(x, y, value))
        elif self.mode == Fader.Mode.Relative:
            self.set_value(self._pressed_relative(x, y, value))
        self.updated = True
    
    def _pressed_simple(self, x, y, value):
        if self.type == Fader.Type.BoostCut:
            if self._min_v[x][y] < 0.5:
                return self._min_v[x][y]
            else:
                return self._max_v[x][y]
        else:
            return self._min_v[x][y]

    def _pressed_multi(self, x, y, value):
        if self.type == Fader.Type.BoostCut:
            if self._min_v[x][y] < 0.5:
                if self._old_button[0] == x and self._old_button[1] == y:
                    self._multi_step = (self._multi_step - 1) % self.resolution
                else:
                    self._old_button = [x, y]
                    self._multi_step = self.resolution - 1
                return self._calc_fader_value(x, y, self._multi_step / self.resolution)
            else:
                if self._old_button[0] == x and self._old_button[1] == y:
                    self._multi_step = (self._multi_step + 1) % self.resolution
                else:
                    self._old_button = [x, y]
                    self._multi_step = 0
                return self._calc_fader_value(x, y, self._multi_step / self.resolution)
        elif self.type == Fader.Type.Collapse:
            if self._old_button[0] == x and self._old_button[1] == y:
                self._multi_step = (self._multi_step - 1) % self.resolution
            else:
                self._old_button = [x, y]
                self._multi_step = self.resolution - 1
            return self._calc_fader_value(x, y, self._multi_step / self.resolution)
        else:
            if self._old_button[0] == x and self._old_button[1] == y:
                self._multi_step = (self._multi_step + 1) % self.resolution
            else:
                self._old_button = [x, y]
                self._multi_step = 0
            return self._calc_fader_value(x, y, self._multi_step / self.resolution)

    def _pressed_magnitude(self, x, y, value):
        return self._calc_fader_value(x, y, self._calc_fader_magnitude(x, y))

    def _pressed_sensitive(self, x, y, value):
        if self.type == Fader.Type.BoostCut:
            if self._min_v[x][y] < 0.5:
                return self._calc_fader_value(x, y, 1.0 - value)
            else:
                return self._calc_fader_value(x, y, value)
        elif self.type == Fader.Type.Collapse:
            return self._calc_fader_value(x, y, 1.0 - value)
        else:
            return self._calc_fader_value(x, y, value)

    def _pressed_relative(self, x, y, value):
        if self._held_button[0] >= 0 and self._held_button[1] >= 0:
            return self._calc_fader_value(self._held_button[0], self._held_button[1], self._calc_fader_magnitude(x, y))
        else:
            self._held_button = [x, y]
            return self._calc_fader_value(x, y, self._calc_fader_magnitude(x, y))

    def handle_hold(self, x: int, y: int, value: float):
        if self.mode != Fader.Mode.Relative:
            if x == 0 and y == 0:
                self.set_value(0.0)
            elif x == self.rect.w - 1 and y == self.rect.h - 1:
                self.set_value(1.0)
            else:
                self.set_value(0.5)
        self.updated = True
    
    def handle_release(self, x: int, y: int, value: float):
        if self._held_button[0] == x and self._held_button[1] == y:
            self._held_button = [-1, -1]

    def draw(self) -> None:
        halfval = self._value / 2.0
        halfvalpluspointfive = halfval + 0.5
        area = self.rect.origin
        for x in area.columns:
            for y in area.rows:
                min_v = self._min_v[x][y]
                max_v = self._max_v[x][y]
                if self.type == Fader.Type.Single:
                    # if current pad lower than last pressed pad
                    if max_v <= self._value:
                        self.buffer[x, y] = self.inactive_color
                    # if current pad higher than last pressed pad
                    elif min_v > self._value:
                        self.buffer[x, y] = self.inactive_color
                    # if current pad is last pressed pad
                    else:
                        coefficient = min(self._calc_pixel_coefficient(self._value - min_v) + self._calc_pixel_step(), 1.0)
                        self.buffer[x, y] = self.active_color * coefficient
                elif self.type == Fader.Type.BoostCut:
                    # if last pressed pad in upper half
                    if self._value > 0.5:
                        # if current pad in lower half
                        if min_v < 0.5:
                            self.buffer[x, y] = self.inactive_color
                        # if current pad in upper half
                        else:
                            # if current pad is lower than last pressed pad
                            if max_v <= self._value:
                                self.buffer[x, y] = self.active_color
                            # if current pad is higher than last pressed pad
                            elif min_v > self._value:
                                self.buffer[x, y] = self.inactive_color
                            # if current pad is last pressed pad
                            else:
                                coefficient = min(self._calc_pixel_coefficient(self._value - min_v) + self._calc_pixel_step(), 1.0)
                                self.buffer[x, y] = self.active_color * coefficient
                    # if last pressed pad in lower half
                    elif self._value < 0.5:
                        # if current pad in upper half
                        if max_v > 0.5:
                            self.buffer[x, y] = self.inactive_color
                        # if current pad in lower half
                        else:
                            # if current pad is higher than last pressed pad
                            if min_v >= self._value:
                                self.buffer[x, y] = self.active_color
                            # if current pad is lower than last pressed pad
                            elif max_v < self._value:
                                self.buffer[x, y] = self.inactive_color
                            # if current pad is last pressed pad
                            else:
                                # reverse brightness to match type
                                coefficient = 1.0 - self._calc_pixel_coefficient(self._value - min_v)
                                self.buffer[x, y] = self.active_color * coefficient
                    # if current value is 0.5
                    else:
                        # lit middle pad(s)
                        if min_v == 0.5 or max_v == 0.5:
                            self.buffer[x, y] = self.active_color
                        # unlit every other pad
                        else:
                            self.buffer[x, y] = self.inactive_color
                elif self.type == Fader.Type.Wrap:
                    # if current pad lower than last pressed pad
                    if max_v <= self._value:
                        self.buffer[x, y] = self.active_color
                    # if current pad higher than last pressed pad
                    elif min_v > self._value:
                        self.buffer[x, y] = self.inactive_color
                    # if current pad is last pressed pad
                    else:
                        coefficient = min(self._calc_pixel_coefficient(self._value - min_v) + self._calc_pixel_step(), 1.0)
                        self.buffer[x, y] = self.active_color * coefficient
                elif self.type == Fader.Type.Spread:
                    # if current pad in upper half
                    if min_v >= 0.5:
                        # if current pad higher than current value
                        if min_v > halfvalpluspointfive:
                            self.buffer[x, y] = self.inactive_color
                        # if current pad lower than current value
                        elif max_v <= halfvalpluspointfive:
                            self.buffer[x, y] = self.active_color
                        # if current value is in current pad's boundary
                        else:
                            coefficient = self._calc_pixel_coefficient(halfvalpluspointfive - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                    # if current pad in lower half
                    elif max_v <= 0.5:
                        # if current pad higher than current value
                        if min_v >= (1.0 - halfvalpluspointfive):
                            self.buffer[x, y] = self.active_color
                        # if current pad lower than current value
                        elif max_v < (1.0 - halfvalpluspointfive):
                            self.buffer[x, y] = self.inactive_color
                        # if current value is in current pad's boundary
                        else:
                            coefficient = 1.0 - self._calc_pixel_coefficient((1.0 - halfvalpluspointfive) - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                elif self.type == Fader.Type.Collapse:
                    # if current pad in upper half
                    if min_v >= 0.5:
                        # if current pad lower than current value
                        if min_v >= (1.0 - halfval):
                            self.buffer[x, y] = self.inactive_color
                        # if current pad higher than current value
                        elif max_v < (1.0 - halfval):
                            self.buffer[x, y] = self.active_color
                        # if current value is in current pad's boundary
                        else:
                            coefficient = self._calc_pixel_coefficient((1.0 - halfval) - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                    # if current pad in lower half
                    elif max_v <= 0.5:
                        # if current pad lower than current value
                        if min_v > halfval:
                            self.buffer[x, y] = self.active_color
                        # if current pad higher than current value
                        elif max_v <= halfval:
                            self.buffer[x, y] = self.inactive_color
                        # if current value is in current pad's boundary
                        else:
                            coefficient = 1.0 - self._calc_pixel_coefficient(halfval - min_v)
                            self.buffer[x, y] = self.active_color * coefficient

    def _resize(self, width, height):
        self._min_v = [[self._calc_fader_value(x, y, 0.0) for y in range(height)] for x in range(width)]
        self._max_v = [[self._calc_fader_value(x, y, 1.0) for y in range(height)] for x in range(width)]
        return True

    """
        For 2-d widgets, where output values are single float,
        we must calculate single float from 2-d area.
        Calculation done from left to right, bottom to top in order
        to get final value for vertical faders. its basically (y * step) + x.
        Vertical matrix faders are left to right, bottom to up in order.
        Horizontal matrix faders are bottom to up, left to right in order.
        Simple faders are bottom to up for vertical, left to right for horizontal.
    """
    def _calc_fader_value(self, x: int, y: int, value: float) -> float:
        """Calculate fader value from pad location"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return round(((y / self.rect.h) + (value / self.rect.h)), 6)
            elif self.direction == Fader.Direction.Horizontal:
                return round(((x / self.rect.w) + (value / self.rect.w)), 6)
        elif self.grid == Fader.Grid.Matrix:
            if self.direction == Fader.Direction.Vertical:
                base = (x / self.rect.area) + (y / self.rect.h)
            elif self.direction == Fader.Direction.Horizontal:
                base = (y / self.rect.area) + (x / self.rect.w)
            return round(base + (value / self.rect.area), 6)
    
    def _calc_fader_magnitude(self, x: int, y: int) -> float:
        """Calculate pad magnitude from pad location"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return self._calc_fader_value(x, y, y / (self.rect.h - 1))
            elif self.direction == Fader.Direction.Horizontal:
                return self._calc_fader_value(x, y, x / (self.rect.w - 1))
        elif self.grid == Fader.Grid.Matrix:
            if self.direction == Fader.Direction.Vertical:
                base = (x / (self.rect.area - 1)) + (y / (self.rect.h - 1))
            elif self.direction == Fader.Direction.Horizontal:
                base = (y / (self.rect.area - 1)) + (x / (self.rect.w - 1))
            return self._calc_fader_value(x, y, base)
    
    def _calc_pixel_coefficient(self, value: float) -> float:
        """Calculate pixel coefficient for different fader options"""
        if self.grid == Fader.Grid.Simple:
            if self.direction == Fader.Direction.Vertical:
                return (value * self.rect.h)
            elif self.direction == Fader.Direction.Horizontal:
                return (value * self.rect.w)
        elif self.grid == Fader.Grid.Matrix:
            return (value * self.rect.area)
    
    def _calc_pixel_step(self):
        if self.mode == Fader.Mode.Simple:
            return 0.5
        elif self.mode == Fader.Mode.Multi:
            return 1.0 / self.resolution
        elif self.mode == Fader.Mode.Magnitude:
            return 1.0 / 256
        elif self.mode == Fader.Mode.Sensitive:
            return 1.0 / 256
        elif self.mode == Fader.Mode.Relative:
            if self.grid == Fader.Grid.Simple:
                if self.direction == Fader.Direction.Vertical:
                    return 1.0/ self.rect.h
                elif self.direction == Fader.Direction.Horizontal:
                    return 1.0 / self.rect.w
            elif self.grid == Fader.Grid.Matrix:
                return 1.0 / self.rect.area

# Keyboard class
class Keyboard(Widget):
    """A playable note layout (piano, chromatic or in-scale) emitting NoteOn and NoteOff."""

    class Type(enum.Enum):
        Keyboard            = 0
        ChromaticVertical   = 1
        ChromaticHorizontal = 2
        Diatonic            = 3
        DiatonicVertical    = 4
        DiatonicHorizontal  = 5

    class Scale(enum.Enum):
        Major           = 0
        Minor           = 1
        Dorian          = 2
        Mixolydian      = 3
        Lydian          = 4
        Phrygian        = 5
        Locrian         = 6
        Diminished      = 7
        WholeHalf       = 8
        WholeTone       = 9
        MinorBlues      = 10
        MinorPentatonic = 11
        MajorPentatonic = 12
        MinorHarmonic   = 13
        MinorMelodic    = 14

    class Root(enum.Enum):
        C   = 0
        CS  = 1
        D   = 2
        DS  = 3
        E   = 4
        F   = 5
        FS  = 6
        G   = 7
        GS  = 8
        A   = 9
        AS  = 10
        B   = 11

    Scales = {
        'Major': [0, 2, 4, 5, 7, 9, 11],
        'Minor': [0, 2, 3, 5, 7, 8, 10],
        'Dorian': [0, 2, 3, 5, 7, 9, 10],
        'Mixolydian': [0, 2, 4, 5, 7, 9, 10],
        'Lydian': [0, 2, 4, 6, 7, 9, 11],
        'Phrygian': [0, 1, 3, 5, 7, 8, 10],
        'Locrian': [0, 1, 3, 5, 6, 8, 10],
        'Diminished': [0, 1, 3, 4, 6, 7, 9, 10],
        'WholeHalf': [0, 2, 3, 5, 6, 8, 9, 11],
        'WholeTone': [0, 2, 4, 6, 8, 10],
        'MinorBlues': [0, 3, 5, 6, 7, 10],
        'MinorPentatonic': [0, 3, 5, 7, 10],
        'MajorPentatonic': [0, 2, 4, 7, 9],
        'MinorHarmonic': [0, 2, 3, 5, 7, 8, 11],
        'MinorMelodic': [0, 2, 3, 5, 7, 9, 11],

        'Keyboard': [0, 2, 4, 5, 7, 9, 11],
        'KeyboardUpper': [-1, 1, 3, -1, 6, 8, 10]
    }

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 octave: int = 0,
                 fold: int = 4,
                 type: Type = Type.Diatonic,
                 scale: Scale = Scale.Major,
                 root: Root = Root.C,
                 root_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Magenta,
                 keyboard_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Cyan,
                 non_scale_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Yellow,
                 active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Green,
                 **kwargs):
        self._octave = octave
        self._fold = fold
        self._type: Keyboard.Type = type
        self._scale: Keyboard.Scale = scale
        self._root: Keyboard.Root = root
        self._root_color: pyxelwidgets.color.Color = root_color
        self._keyboard_color: pyxelwidgets.color.Color = keyboard_color
        self._non_scale_color: pyxelwidgets.color.Color = non_scale_color
        self.buttons = None
        self.notes = None
        self.colors = None
        self.states = None
        super().__init__(x=x, y=y, width=width, height=height, active_color = active_color, **kwargs)

    @property
    def octave(self):
        return self._octave
    
    @octave.setter
    def octave(self, octave: int):
        self._octave = octave
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def fold(self):
        return self._fold
    
    @fold.setter
    def fold(self, fold: int):
        self._fold = fold
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def type(self):
        return self._type
    
    @type.setter
    def type(self, mode: Type):
        self._type = mode
        self._resize(self.width, self.height)
        self.updated = True
    
    @property
    def scale(self):
        return self._scale
    
    @scale.setter
    def scale(self, scale: Scale):
        self._scale = scale
        self._resize(self.width, self.height)
        self.updated = True
    
    @property
    def root(self):
        return self._root
    
    @root.setter
    def root(self, root: Root):
        self._root = root
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def root_color(self):
        return self._root_color
    
    @root_color.setter
    def root_color(self, root_color: pyxelwidgets.color.Color):
        self._root_color = root_color
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def keyboard_color(self):
        return self._keyboard_color
    
    @keyboard_color.setter
    def keyboard_color(self, keyboard_color: pyxelwidgets.color.Color):
        self._keyboard_color = keyboard_color
        self._resize(self.width, self.height)
        self.updated = True

    @property
    def non_scale_color(self):
        return self._non_scale_color
    
    @non_scale_color.setter
    def non_scale_color(self, non_scale_color: pyxelwidgets.color.Color):
        self._non_scale_color = non_scale_color
        self._resize(self.width, self.height)
        self.updated = True

    def handle_press(self, x: int, y: int, value: float):
        note = int(self.notes[x, y])
        if note >= 0:
            for button in self.buttons[note]:
                self.states[button[0], button[1]] = True
            self.updated = True
            self.emit(pyxelwidgets.events.NoteOn(self, note, value))
    
    def handle_release(self, x: int, y: int, value: float):
        note = int(self.notes[x, y])
        if note >= 0:
            for button in self.buttons[note]:
                self.states[button[0], button[1]] = False
            self.updated = True
            self.emit(pyxelwidgets.events.NoteOff(self, note, value))
    
    def draw(self) -> None:
        area = self.rect.origin
        for x in area.columns:
            for y in area.rows:
                note = self.notes[x, y]
                if note >= 0:
                    if self.states[x, y]:
                        self.buffer[x, y] = self.active_color
                    else:
                        self.buffer[x, y] = self.colors[note]
                else:
                    self.buffer[x, y] = self.inactive_color

    def _resize(self, width, height) -> bool:
        self.notes = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.states = numpy.array([[0 for y in range(height)] for x in range(width)])
        self.colors = [pyxelwidgets.color.Colors.Invisible for i in range(128)]
        self.buttons = [[] for i in range(128)]
        self._calc_notes()
        return True

    def _calc_notes(self):
        base = self._root.value + (self._octave * 12)
        scale = Keyboard.Scales[self._scale.name]
        precalc = []
        #precalculate scale values, enough for the largest index any layout below reads
        for i in range((self.rect.w + self.rect.h) * max(len(scale), self._fold)):
            precalc.append(scale[i % len(scale)] + base + ((i // len(scale)) * 12))
        for x in range(self.rect.w):
            for y in range(self.rect.h):
                #calculate notes
                if self._type == Keyboard.Type.Keyboard:
                    base = Keyboard.Root.C.value + (self._octave * 12)
                    length = 7 if 7 < self.rect.w else self.rect.w
                    if y % 2 == 0:
                        scale = Keyboard.Scales['Keyboard']
                    else:
                        scale = Keyboard.Scales['KeyboardUpper']
                    if scale[x % length] == -1:
                        self.notes[x, y] = -1
                    else:
                        self.notes[x, y] = scale[x % length] + base + ((y // 2) * 12) + ((x // length) * 12)
                elif self._type == Keyboard.Type.ChromaticVertical:
                    index = x + (y * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._type == Keyboard.Type.ChromaticHorizontal:
                    index = y + (x * (self._fold - 1))
                    self.notes[x, y] = index + base
                elif self._type == Keyboard.Type.Diatonic:
                    self.notes[x, y] = precalc[x + (y * len(scale))]
                elif self._type == Keyboard.Type.DiatonicVertical:
                    self.notes[x, y] = precalc[x + (y * len(scale)) - (y * (len(scale) - self._fold + 1))]
                elif self._type == Keyboard.Type.DiatonicHorizontal:
                    self.notes[x, y] = precalc[y + (x * len(scale)) - (x * (len(scale) - self._fold + 1))]
                #clear notes 128 or higher
                if self.notes[x, y] > 127:
                    self.notes[x, y] = -1
                #make array from same buttons
                if self.notes[x, y] != -1:
                    self.buttons[self.notes[x, y]].append([x, y])
                #change colors
                if self.notes[x, y] != -1:
                    if (self.notes[x, y] - self._root.value) % 12 == 0:
                        self.colors[self.notes[x, y]] = self._root_color
                    elif (self.notes[x, y] - self._root.value) % 12 in Keyboard.Scales[self._scale.name]:
                        self.colors[self.notes[x, y]] = self._keyboard_color
                    else:
                        self.colors[self.notes[x, y]] = self._non_scale_color

# Knob class
class Knob(ValueWidget):
    """A value shown around the border of the area; holding a pad turns it continuously."""

    class Type(enum.Enum):
        Single      = enum.auto()
        BoostCut    = enum.auto()
        Wrap        = enum.auto()
        Spread      = enum.auto()
        Collapse    = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 coefficient: float = 0.05,
                 type: Type = Type.Wrap,
                 **kwargs):
        super().__init__(x, y, width, height, **kwargs)
        self.coefficient = coefficient
        self.type = type
        self.state = False
        self._held = [-1, -1]

    def handle_press(self, x: int, y: int, value: float):
        if self._held == [-1, -1]:
            if self._calc_knob_index(x, y) != -1:
                self._held = [x, y]
                self.state = True
                self.updated = True
        else:
            held_index = self._calc_knob_index(self._held[0], self._held[1])
            cur_index = self._calc_knob_index(x, y)
            half_perimeter = self.perimeter // 2
            if held_index != -1 and cur_index != -1:
                if (held_index < half_perimeter and cur_index >= half_perimeter) or (cur_index < half_perimeter and held_index >= half_perimeter):
                    self.state = False
                    self.set_value(0.5)
    
    def handle_release(self, x: int, y: int, value: float):
        self._held = [-1, -1]
        self.state = False
    
    def tick(self):
        if self.state:
            index = self._calc_knob_index(self._held[0], self._held[1])
            if index != -1:
                self.set_value(self._value + (self._calc_knob_weight(index) * self.coefficient))

    def draw(self) -> None:
        if self.state:
            # A held knob keeps turning every frame
            self.tick()
            self.updated = True
        halfval = self._value / 2.0
        halfvalpluspointfive = halfval + 0.5
        area = self.rect.origin
        for x in area.columns:
            for y in area.rows:
                index = self.indexes[x][y]
                min_v = self._min_v[index]
                max_v = self._max_v[index]
                if index == -1:
                    self.buffer[x, y] = pyxelwidgets.color.Colors.Invisible
                else:
                    if self.type == Knob.Type.Single:
                        if max_v < self._value:
                            self.buffer[x, y] = self.inactive_color
                        elif min_v > self._value:
                            self.buffer[x, y] = self.inactive_color
                        else:
                            coefficient = self._calc_pixel_coefficient(self._value - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                    elif self.type == Knob.Type.BoostCut:
                        if self._value > 0.5:
                            if min_v < 0.5:
                                self.buffer[x, y] = self.inactive_color
                            else:
                                if max_v <= self._value:
                                    self.buffer[x, y] = self.active_color
                                elif min_v > self._value:
                                    self.buffer[x, y] = self.inactive_color
                                else:
                                    coefficient = self._calc_pixel_coefficient(self._value - min_v)
                                    self.buffer[x, y] = self.active_color * coefficient
                        elif self._value < 0.5:
                            if max_v > 0.5:
                                self.buffer[x, y] = self.inactive_color
                            else:
                                if min_v >= self._value:
                                    self.buffer[x, y] = self.active_color
                                elif max_v < self._value:
                                    self.buffer[x, y] = self.inactive_color
                                else:
                                    coefficient = 1.0 - self._calc_pixel_coefficient(self._value - min_v)
                                    self.buffer[x, y] = self.active_color * coefficient
                        else:
                            if min_v == 0.5 or max_v == 0.5:
                                self.buffer[x, y] = self.active_color
                            else:
                                self.buffer[x, y] = self.inactive_color
                    elif self.type == Knob.Type.Wrap:
                        if max_v <= self._value:
                            self.buffer[x, y] = self.active_color
                        elif min_v > self._value:
                            self.buffer[x, y] = self.inactive_color
                        else:
                            coefficient = self._calc_pixel_coefficient(self._value - min_v)
                            self.buffer[x, y] = self.active_color * coefficient
                    elif self.type == Knob.Type.Spread:
                        if min_v >= 0.5:
                            if min_v > halfvalpluspointfive:
                                self.buffer[x, y] = self.inactive_color
                            elif max_v <= halfvalpluspointfive:
                                self.buffer[x, y] = self.active_color
                            else:
                                coefficient = self._calc_pixel_coefficient(halfvalpluspointfive - min_v)
                                self.buffer[x, y] = self.active_color * coefficient
                        elif max_v <= 0.5:
                            if min_v >= (1.0 - halfvalpluspointfive):
                                self.buffer[x, y] = self.active_color
                            elif max_v < (1.0 - halfvalpluspointfive):
                                self.buffer[x, y] = self.inactive_color
                            else:
                                coefficient = 1.0 - self._calc_pixel_coefficient((1.0 - halfvalpluspointfive) - min_v)
                                self.buffer[x, y] = self.active_color * coefficient
                    elif self.type == Knob.Type.Collapse:
                        if halfval < 0.5:
                            if max_v <= 0.5:
                                if min_v > halfval:
                                    self.buffer[x, y] = self.active_color
                                elif max_v <= halfval:
                                    self.buffer[x, y] = self.inactive_color
                                else:
                                    coefficient = 1.0 - self._calc_pixel_coefficient(halfval - min_v)
                                    self.buffer[x, y] = self.active_color * coefficient
                            elif min_v >= 0.5:
                                if min_v >= (1.0 - halfval):
                                    self.buffer[x, y] = self.inactive_color
                                elif max_v < (1.0 - halfval):
                                    self.buffer[x, y] = self.active_color
                                else:
                                    coefficient = self._calc_pixel_coefficient((1.0 - halfval) - min_v)
                                    self.buffer[x, y] = self.active_color * coefficient
                        else:
                            self.buffer[x, y] = self.inactive_color
    
    def _resize(self, width, height):
        self.perimeter = self._calc_perimeter(width, height)
        self.indexes = [[self._calc_knob_index(x, y) for y in range(height)] for x in range(width)]
        self._min_v = [self._calc_knob_value(index, 0.0) for index in range(self.perimeter)]
        self._max_v = [self._calc_knob_value(index, 1.0) for index in range(self.perimeter)]
        return True

    def _calc_knob_index(self, x: int, y: int) -> float:
        if self.rect.w == 1:
            return y
        elif self.rect.h == 1:
            return x
        halfwidth = int(self.rect.w / 2)
        if y == (self.rect.h - 1):
            return (y + halfwidth + x) - 1
        elif x < halfwidth:
            if y == 0:
                return (halfwidth - x) - 1
            elif x == 0:
                return (y + halfwidth) - 1
        elif x >= halfwidth:
            if y == 0:
                return (self.perimeter - (x - halfwidth)) - 1
            elif x == (self.rect.w - 1):
                return (self.perimeter - (x - halfwidth) - y) - 1
        return -1

    def _calc_knob_value(self, index: int, value: float) -> float:
        if index == -1:
            return 0.0
        return round(((index / self.perimeter) + (value / self.perimeter)), 6)
    
    def _calc_knob_weight(self, index: int) -> float:
        if index == -1:
            return 0.0
        halfperimeter = int(self.perimeter / 2)
        if index < halfperimeter:
            return round(-(0.5 - self._min_v[index]), 6)
        else:
            return round(self._max_v[index] - 0.5, 6)

    def _calc_pixel_coefficient(self, value: float) -> float:
        return value * self.perimeter
    
    def _calc_perimeter(self, width, height) -> float:    
        if width == 1:
            return height
        elif height == 1:
            return width
        return ((width - 1) * 2) + ((height - 1) * 2)

# Sequencer class
class Sequencer(Widget):
    """
    Step sequencer. Each step plays when ``play(step)`` or ``advance()`` is
    called, e.g. every 16th note from a Transport:
    ``transport.every(sequencer.rate, sequencer.play)``. Emits StepPlayed.
    """
    def __init__(self, x: int, y: int, width: int, height: int, *,
                 steps: int | None = None,
                 rate: Rate = '1/16',
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Lime,
                 current_active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Red,
                 **kwargs):
        self.state = numpy.ndarray((1, 1), dtype = numpy.bool_)
        self._steps = steps if steps is not None else width * height
        self._step = 0
        self._page_count = 1
        super().__init__(x, y, width, height, **kwargs)
        self.state.fill(False)
        self.current_page = 0
        self._page = 0
        self.follow = True
        self.active = True
        self.rate = rate
        self.current_color = current_color
        self.current_active_color = current_active_color
    
    @property
    def pages(self) -> int:
        return self._page_count

    @property
    def page(self) -> int:
        return self._page

    @page.setter
    def page(self, value: int) -> None:
        self._page = value % self._page_count
        self.updated = True

    @property
    def step(self) -> int:
        return self._step
    
    @step.setter
    def step(self, value: int) -> None:
        self._step = value % self._steps
        self.updated = True

    @property
    def steps(self) -> int:
        return self._steps

    @steps.setter
    def steps(self, value: int) -> None:
        self._steps = value
        self._page_count = int((self._steps - 1) / self.rect.area) + 1
        self.state = numpy.zeros((self.rect.w, self.rect.h * self._page_count), dtype = numpy.bool_)
        self._step %= self._steps
        self.current_page = self._step // self.rect.area
        self.updated = True

    @property
    def current(self) -> bool:
        return bool(self.state[self._tick_x(), self._tick_y()])
    
    @current.setter
    def current(self, state: bool) -> None:
        self.state[self._tick_x(), self._tick_y()] = state
        self.updated = True

    def play(self, step: int) -> None:
        """Move to ``step`` (wrapped to ``steps``) and emit StepPlayed; does nothing while not ``active``."""
        if not self.active:
            return
        self._step = step % self._steps
        page = self._step // self.rect.area
        if page != self.current_page:
            self.current_page = page
            self.emit(pyxelwidgets.events.PageChanged(self, self.current_page))
        self.emit(pyxelwidgets.events.StepPlayed(self, self._step, bool(self._is_tick_active())))
        self.updated = True

    def advance(self) -> None:
        """Play the next step."""
        self.play(self._step + 1)

    def handle_press(self, x: int, y: int, value: float):
        if self._calc_tick_position(x, y) < self._steps:
            page_y = y + (self.rect.h * self._tick_page())
            self.state[x, page_y] = not self.state[x, page_y]
            self.updated = True

    def reset(self):
        self.state.fill(False)
        self.updated = True

    def draw(self) -> None:
        area = self.rect.origin
        tick_p = self._tick_page()
        tick_x = self._tick_x()
        tick_y = self._tick_y() % self.rect.h
        state_area = area + pyxelwidgets.rectangle.Rectangle2D(0, self.rect.h * tick_p)
        self.buffer[area.slice] = numpy.where(self.state[(*state_area.slice, None)], self.active_color, self.inactive_color)
        if tick_p == self.current_page:
            if numpy.array_equal(self.buffer[tick_x, tick_y], self.active_color):
                self.buffer[tick_x, tick_y] = self.current_active_color
            else:
                self.buffer[tick_x, tick_y] = self.current_color
    
    def _resize(self, width, height):
        self._page_count = int((self._steps - 1) / (width * height)) + 1
        self.state.resize((width, height * self._page_count), refcheck = False)
        self._step %= self._steps
        return True
    
    def _calc_tick_position(self, x, y):
        return (x + (y * self.rect.w)) + (self.rect.area * self._tick_page())
    
    def _tick_page(self):
        return self.current_page if self.follow else self._page

    def _tick_x(self):
        return self._step % self.rect.w
    
    def _tick_y(self):
        return self._step // self.rect.w
    
    def _is_tick_active(self):
        return self.state[self._tick_x()][self._tick_y()]
    
# Sprite class
class Sprite(Widget):
    """Displays frames (optionally animated). Display-only: presses pass through by default."""
    def __init__(self, x: int, y: int, width: int, height: int, *,
                 animate: bool = False,
                 frames = None,
                 target: int = 30,
                 tick: int = 0,
                 propagation: Propagation = Propagation.Pass,
                 **kwargs):
        super().__init__(x=x, y=y, width=width, height=height, propagation = propagation, **kwargs)
        self.animate = animate
        # Sequence of frames, each an RGBA buffer or a 2-d array/list of Colors
        self.target = target
        self.tick = tick
        self.current_frame = 0
        self.next_frame = 0
        if frames is None:
            self.frames = [pyxelwidgets.buffer.new(self.rect.w, self.rect.h)]
        else:
            self.frames = [pyxelwidgets.buffer.to_buffer(frame) for frame in frames]
        self.buffer = self.frames[0]

    def draw(self) -> None:
        self.buffer = self.frames[self.next_frame]
        if self.animate:
            self.tick += 1
            if self.tick == self.target:
                self.tick = 0
                self.current_frame = self.next_frame
                self.next_frame += 1
                if self.next_frame == len(self.frames):
                    self.next_frame = 0
            self.updated = True

# Tracker class
class Tracker(Widget):
    """
    A scrolling step grid where rows are steps and columns are tracks. Rows
    play when ``play(row)`` or ``advance()`` is called, e.g. from a Transport:
    ``transport.every(tracker.rate, tracker.play)``. Emits RowPlayed.
    """

    # class Scroll(enum.Enum):
    #     Continuous = enum.auto()
    #     Page = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 bars: int = 64,
                 pages: int = 1,
                 rate: Rate = '1/16',
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Cyan,
                 current_active_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Magenta,
                 **kwargs):
        self.bars = bars
        self.bars = self.bars if self.bars >= height else height
        self.pages = pages
        self.pages = self.pages if self.pages > 0 else 1
        self.states = numpy.ndarray((1, 1, 1), dtype = numpy.bool_)
        self.current_bar = 0
        self.current_page = 0
        self.rate = rate
        super().__init__(x, y, width, height, **kwargs)
        self.states.fill(False)
        self.current_color = current_color
        self.current_active_color = current_active_color

    @property
    def step(self) -> int:
        """Position over all pages: ``current_page * bars + current_bar``."""
        return self.current_page * self.bars + self.current_bar

    def handle_press(self, x: int, y: int, value: float):
        self.states[self.current_page, x, self.rect.h - 1 - y + self.current_top] = not self.states[self.current_page, x, self.rect.h - 1 - y + self.current_top]
        self.updated = True

    def play(self, step: int) -> None:
        """Move to ``step`` (wrapping through rows, then pages) and emit RowPlayed with the row's active columns."""
        self.scroll(step)
        row = self.states[self.current_page, :, self.current_bar]
        self.emit(pyxelwidgets.events.RowPlayed(self, self.current_bar, tuple(int(i) for i in numpy.flatnonzero(row))))

    def advance(self) -> None:
        """Play the next row."""
        self.play(self.step + 1)

    def scroll(self, step: int) -> None:
        """Move to ``step`` without playing it."""
        self.current_page = (step // self.bars) % self.pages
        self.current_bar = step % self.bars
        half_height = self.height // 2
        # if self.scroll == Tracker.Scroll.Continuous:
        corr = int(not (self.height % 2))
        if self.current_bar < half_height:
            self.current_top = 0
            self.current_bottom = self.current_top + self.height - 1
        elif self.current_bar >= self.bars - half_height:
            self.current_top = self.bars - self.height
            self.current_bottom = self.bars - corr
        else:
            self.current_top = self.current_bar - (half_height - corr)
            self.current_bottom = self.current_bar + half_height
        # elif self.scroll == Tracker.Scroll.Page:
        #     pass
        self.updated = True

    def draw(self) -> None:
        area = self.rect.origin
        self.buffer[area.slice] = numpy.fliplr(numpy.where(self.states[self.current_page, :, self.current_top:(self.current_bottom + 1), None], self.active_color, self.inactive_color))
        self.buffer[:, self.current_bottom - self.current_bar] = numpy.where(self.states[self.current_page, :, self.current_bar, None], self.current_active_color, self.current_color)

    def _resize(self, width, height) -> bool:
        self.states.resize((self.pages, width, self.bars), refcheck = False)
        self.scroll(self.step)
        return True

# XY class
class XY(ValueWidget):
    """A two dimensional value (x, y) set by pressing anywhere in the area."""

    class Direction(enum.Enum):
        Vertical    = enum.auto()
        Horizontal  = enum.auto()

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 x_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Cyan,
                 y_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Magenta,
                 value: tuple = (0.0, 0.0),
                 **kwargs):
        super().__init__(x, y, width, height, value = value, **kwargs)
        self.x_color = x_color
        self.y_color = y_color
        self._held_button = [-1, -1]

    def _clamp(self, value) -> tuple:
        return tuple(round(min(1.0, max(0.0, v)), 6) for v in value)

    def _delta(self, old, new) -> tuple:
        return tuple(n - o for o, n in zip(old, new))

    def handle_press(self, x: int, y: int, value: float):
        if self._held_button[0] >= 0 and self._held_button[1] >= 0:
            self.set_value(self._calc_xy_value_with_magnitude(self._held_button[0], self._held_button[1], x, y))
        else:
            self.set_value(self._calc_xy_value(x, y, value))
    
    def handle_hold(self, x: int, y: int, value: float):
        if self._held_button[0] == -1 and self._held_button[1] == -1:
            self._held_button = [x, y]
            self.set_value(self._calc_xy_value_with_magnitude(x, y, x, y))
    
    def handle_release(self, x: int, y: int, value: float):
        if self._held_button[0] == x and self._held_button[1] == y:
            self._held_button = [-1, -1]

    def draw(self) -> None:
        area = self.rect.origin
        x_point = self._find_x_point()
        y_point = self._find_y_point()
        self.buffer[area.slice] = self.inactive_color
        self.buffer[x_point, area.slice[1]] = self.x_color * self._value[0]
        self.buffer[area.slice[0], y_point] = self.y_color * self._value[1]
        min_v = self._min_v[x_point][y_point]
        coefficient_x = ((self.value[0] - min_v[0]) * self.rect.w) / 2
        coefficient_y = ((self.value[1] - min_v[1]) * self.rect.h) / 2
        color = (self.x_color * coefficient_x) + (self.y_color * coefficient_y)
        self.buffer[x_point, y_point] = color

    def _resize(self, width, height) -> bool:
        self._min_v = [[self._calc_xy_value(x, y, 0.0) for y in range(height)] for x in range(width)]
        self._max_v = [[self._calc_xy_value(x, y, 1.0) for y in range(height)] for x in range(width)]
        return True

    def _find_x_point(self):
        point = (self._value[0] * self.rect.w)
        if point > 0.0:
            point = point - 1 if point % 1.0 == 0.0 else point
        return int(point)
    
    def _find_y_point(self):
        point = (self._value[1] * self.rect.h)
        if point > 0.0:
            point = point - 1 if point % 1.0 == 0.0 else point
        return int(point)

    def _calc_x_value(self, x: int, value: float) -> float:
        return round(((x / self.rect.w) + (value / self.rect.w)), 6)
    
    def _calc_y_value(self, y: int, value: float) -> float:
        return round(((y / self.rect.h) + (value / self.rect.h)), 6)

    def _calc_xy_value(self, x: int, y: int, value: float):
        return [self._calc_x_value(x, value), self._calc_y_value(y, value)]
    
    def _calc_x_magnitude(self, x: int) -> float:
        return self._calc_x_value(x, (x + 1) / self.rect.w)
    
    def _calc_y_magnitude(self, y: int) -> float:
        return self._calc_y_value(y, (y + 1) / self.rect.h)

    def _calc_xy_magnitude(self, x: int, y: int):
        return [self._calc_x_magnitude(x), self._calc_y_magnitude(y)]
    
    def _calc_xy_value_with_magnitude(self, val_x: int, val_y: int, mag_x: int, mag_y: int):
        return [self._calc_x_value(val_x, self._calc_x_magnitude(mag_x)), self._calc_y_value(val_y, self._calc_y_magnitude(mag_y))]

# Text class
class Text(Widget):
    """
    Text in a 3x5 pixel font (``pyxelwidgets.font``), e.g. a tempo or a track
    name, vertically centered. Text that doesn't fit scrolls (``scroll``) at
    ``speed`` columns per second. Display only: presses pass through.
    """

    class Align(enum.Enum):
        Left    = enum.auto()
        Center  = enum.auto()
        Right   = enum.auto()

    class Scroll(enum.Enum):
        #: Scroll only when the text is wider than the widget
        Auto    = enum.auto()
        Always  = enum.auto()
        Off     = enum.auto()

    #: Empty columns between the end of scrolling text and its start
    GAP = 3

    def __init__(self, x: int, y: int, width: int, height: int, *,
                 text: str = '',
                 align: Align = Align.Left,
                 scroll: Scroll = Scroll.Auto,
                 speed: float = 8.0,
                 inactive_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Invisible,
                 propagation: Propagation = Propagation.Pass,
                 clock: typing.Callable[[], float] = time.monotonic,
                 **kwargs):
        self._text = str(text)
        self._bitmap = pyxelwidgets.font.text_bitmap(self._text)
        self.align = align
        self.scroll = scroll
        self.speed = speed
        self.clock = clock
        self._start = clock()
        self._offset = 0
        super().__init__(x, y, width, height, inactive_color = inactive_color, propagation = propagation, **kwargs)

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value) -> None:
        value = str(value)
        if value != self._text:
            self._text = value
            self._bitmap = pyxelwidgets.font.text_bitmap(value)
            # Scrolling starts over
            self._start = self.clock()
            self._offset = 0
            self.updated = True

    @property
    def scrolling(self) -> bool:
        if self.scroll == Text.Scroll.Off or self.speed <= 0 or not self._text:
            return False
        return self.scroll == Text.Scroll.Always or self._bitmap.shape[0] > self.rect.w

    def render(self, time = None) -> bool:
        if self.scrolling:
            period = self._bitmap.shape[0] + Text.GAP
            offset = int((self.clock() - self._start) * self.speed) % period
            if offset != self._offset:
                self._offset = offset
                self.updated = True
        return super().render(time)

    def draw(self) -> None:
        self.buffer[:] = self.inactive_color
        bitmap = self._bitmap
        if self.scrolling:
            # The text followed by a gap, repeated, starting at the scroll offset
            strip = numpy.zeros((bitmap.shape[0] + Text.GAP, bitmap.shape[1]), dtype = bool)
            strip[:bitmap.shape[0]] = bitmap
            columns = strip[(numpy.arange(self.rect.w) + self._offset) % strip.shape[0]]
            left = 0
        else:
            columns = bitmap[:self.rect.w] if self.align != Text.Align.Right else bitmap[max(bitmap.shape[0] - self.rect.w, 0):]
            free = self.rect.w - columns.shape[0]
            left = {Text.Align.Left: 0, Text.Align.Center: free // 2, Text.Align.Right: free}[self.align]
        # Vertically centered; rows that don't fit are cut from the top
        bottom = (self.rect.h - pyxelwidgets.font.HEIGHT) // 2
        for row in range(pyxelwidgets.font.HEIGHT):
            y = bottom + row
            if 0 <= y < self.rect.h:
                lit = columns[:, row]
                xs = numpy.flatnonzero(lit) + left
                self.buffer[xs, y] = self.active_color

