import pyxelwidgets.buffer
import pyxelwidgets.color
import pyxelwidgets.events
import pyxelwidgets.rectangle
import pyxelwidgets.widgets
import copy
import dataclasses
import enum

class Group(pyxelwidgets.widgets.Widget):
    """
    A widget made of widgets. Children are positioned relative to the group and
    drawn in the order they were added: later children are on top, and
    transparent pixels show the children underneath. Groups can be nested.

    Input goes to the topmost visible child under the press; if that child's
    ``propagation`` is ``Pass`` it continues to the next child underneath.
    A group itself passes presses on its empty area through by default.

    Children never know their group: it notices changes by rendering them.
    """

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 background: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.Invisible,
                 propagation: pyxelwidgets.widgets.Propagation = pyxelwidgets.widgets.Propagation.Pass,
                 **kwargs):
        """
        background: Color = Colors.Invisible, optional
            The empty area's color (Invisible: the widgets underneath show).
        """
        self._children = []
        self._dirty = True
        super().__init__(x, y, width, height, inactive_color = background, propagation = propagation, **kwargs)

    @property
    def background(self) -> pyxelwidgets.color.Color:
        """The color of the area no child covers (the group's ``inactive_color``)."""
        return self.inactive_color

    @background.setter
    def background(self, value: pyxelwidgets.color.Color) -> None:
        self.inactive_color = value
        self.updated = True

    @property
    def children(self) -> tuple:
        """Children from bottom to top."""
        return tuple(self._children)

    def add(self, widget: pyxelwidgets.widgets.Widget) -> pyxelwidgets.widgets.Widget:
        """Add ``widget`` on top of the existing children and return it."""
        if self.find(widget.name) is not None:
            raise ValueError(f'{self.name} already has a widget named {widget.name!r}')
        self._children.append(widget)
        self._dirty = True
        return widget

    def extend(self, widgets) -> None:
        for widget in widgets:
            self.add(widget)

    def remove(self, widget) -> None:
        """Remove a child, given the widget or its name."""
        if isinstance(widget, str):
            widget = self[widget]
        self._children.remove(widget)
        self._dirty = True

    def clear(self) -> None:
        self._children.clear()
        self._dirty = True

    def find(self, name: str):
        """The child named ``name``, or None."""
        for child in self._children:
            if child.name == name:
                return child
        return None

    def __getitem__(self, name: str):
        child = self.find(name)
        if child is None:
            raise KeyError(name)
        return child

    def __contains__(self, widget) -> bool:
        return widget in self._children or (isinstance(widget, str) and self.find(widget) is not None)

    def __iter__(self):
        return iter(tuple(self._children))

    def __len__(self) -> int:
        return len(self._children)

    def input(self, event: pyxelwidgets.events.PadEvent) -> bool:
        x, y = event.x, event.y
        for child in reversed(self._children):
            if child.visible and child.rect.x <= x < child.rect.r and child.rect.y <= y < child.rect.t:
                if child.input(dataclasses.replace(event, x = x - child.rect.x, y = y - child.rect.y)):
                    return True
        return self.propagation == pyxelwidgets.widgets.Propagation.Stop

    def render(self, time = None) -> bool:
        changed = self._dirty
        # Render every child, even after one already changed
        for child in self._children:
            changed = child.render(time) or changed
        if changed:
            self._dirty = False
            self.updated = True
        return super().render(time)

    def draw(self) -> None:
        self.buffer[:] = self.inactive_color
        for child in self._children:
            if not child.visible:
                continue
            intersect = self.rect.origin.intersect(child.rect)
            if intersect is not None:
                source = child.buffer[(intersect - child.rect).slice]
                pyxelwidgets.buffer.composite(self.buffer[intersect.slice], source)

    def _resize(self, width, height) -> bool:
        self._dirty = True
        return True

class Pages(pyxelwidgets.widgets.Paged, Group):
    """
    A group whose children are pages: only the current ``page`` is shown and
    gets input. An optional ``selector`` strip along one side has a cell per
    page; pressing one switches to that page. Emits PageChanged, and
    PageShown (also when pages are added or removed).

    Pages usually fill ``content``, the area besides the selector.
    """

    emits = (pyxelwidgets.events.PageChanged,)

    actions = {'next': None, 'previous': None, **pyxelwidgets.widgets.Paged.page_actions}

    class Selector(enum.Enum):
        Off     = enum.auto()
        Top     = enum.auto()
        Bottom  = enum.auto()
        Left    = enum.auto()
        Right   = enum.auto()

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 page: int = 0,
                 selector: Selector = Selector.Top,
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.White,
                 selector_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(48, 48, 48),
                 propagation: pyxelwidgets.widgets.Propagation = pyxelwidgets.widgets.Propagation.Stop,
                 **kwargs):
        """
        page: int = 0, optional
            The page shown first, from 0.
        selector: Selector = Selector.Top, optional
            The side of the strip with a cell per page (Off: no strip; ``next``/``previous`` or
            links switch pages).
        current_color, selector_color: Color, optional
            The current page's cell, and the others'.
        """
        self._page = page
        self.selector = selector
        self.current_color = current_color
        self.selector_color = selector_color
        super().__init__(x, y, width, height, propagation = propagation, **kwargs)

    @property
    def pages(self) -> int:
        return len(self._children)

    @property
    def page(self) -> int:
        return self._page

    @page.setter
    def page(self, value: int) -> None:
        """Show page ``value`` (wrapped to the number of pages) and emit PageChanged if it changed."""
        value = value % self.pages if self.pages else 0
        if value != self._page:
            self._page = value
            self._show()
            self.emit(pyxelwidgets.events.PageChanged(self, value))

    def save_state(self) -> dict:
        return {'page': self._page}

    def load_state(self, state: dict) -> None:
        page = state.get('page')
        if isinstance(page, int) and 0 <= page < self.pages and page != self._page:
            # Without PageChanged, like the other widgets
            self._page = page
            self._show()

    @property
    def current(self):
        """The widget of the current page, or None without pages."""
        return self._children[self._page] if self._page < len(self._children) else None

    def next(self) -> None:
        self.page = self._page + 1

    def previous(self) -> None:
        self.page = self._page - 1

    @property
    def content(self) -> pyxelwidgets.rectangle.Rectangle2D:
        """The area for pages, relative to this widget: everything but the selector."""
        w, h = self.rect.w, self.rect.h
        return {
            Pages.Selector.Off: pyxelwidgets.rectangle.Rectangle2D(0, 0, w, h),
            Pages.Selector.Top: pyxelwidgets.rectangle.Rectangle2D(0, 0, w, h - 1),
            Pages.Selector.Bottom: pyxelwidgets.rectangle.Rectangle2D(0, 1, w, h - 1),
            Pages.Selector.Left: pyxelwidgets.rectangle.Rectangle2D(1, 0, w - 1, h),
            Pages.Selector.Right: pyxelwidgets.rectangle.Rectangle2D(0, 0, w - 1, h),
        }[self.selector]

    def add(self, widget: pyxelwidgets.widgets.Widget) -> pyxelwidgets.widgets.Widget:
        super().add(widget)
        self._show()
        return widget

    def remove(self, widget) -> None:
        super().remove(widget)
        self._page = min(self._page, max(self.pages - 1, 0))
        self._show()

    def _show(self) -> None:
        for index, child in enumerate(self._children):
            child.visible = index == self._page
        self._dirty = True
        self._page_shown()

    def _cells(self) -> list:
        """Selector cell positions, one per page that fits: left to right, or top to bottom."""
        w, h = self.rect.w, self.rect.h
        count = self.pages
        if self.selector == Pages.Selector.Top:
            return [(i, h - 1) for i in range(min(count, w))]
        if self.selector == Pages.Selector.Bottom:
            return [(i, 0) for i in range(min(count, w))]
        if self.selector == Pages.Selector.Left:
            return [(0, h - 1 - i) for i in range(min(count, h))]
        if self.selector == Pages.Selector.Right:
            return [(w - 1, h - 1 - i) for i in range(min(count, h))]
        return []

    def input(self, event: pyxelwidgets.events.PadEvent) -> bool:
        cells = self._cells()
        if (event.x, event.y) in cells:
            if isinstance(event, pyxelwidgets.events.PadPressed):
                self.page = cells.index((event.x, event.y))
            return True
        return super().input(event)

    def draw(self) -> None:
        super().draw()
        for index, cell in enumerate(self._cells()):
            self.buffer[cell] = self.current_color if index == self._page else self.selector_color

class Presets(Group):
    """
    A group that remembers what its widgets show (values, steps, pages...) in
    slots, one per cell of its ``selector`` strip: press an empty cell to
    store, a stored one to bring it back, hold one to store over it. Values
    brought back are sent on (Changed), so outputs follow, unless ``send`` is
    off. Emits PresetStored and PresetRecalled. A layout loaded from a file
    keeps what is stored in that file unless ``save`` is off.
    """

    emits = (pyxelwidgets.events.PresetStored, pyxelwidgets.events.PresetRecalled)

    actions = {'recall': 'int', 'store': 'int'}

    def __init__(self, x: int = 0, y: int = 0, width: int = 1, height: int = 1, *,
                 selector: Pages.Selector = Pages.Selector.Top,
                 send: bool = True,
                 save: bool = True,
                 presets: dict | None = None,
                 current_color: pyxelwidgets.color.Color = pyxelwidgets.color.Colors.White,
                 stored_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(0, 64, 96),
                 empty_color: pyxelwidgets.color.Color = pyxelwidgets.color.Color(24, 24, 24),
                 propagation: pyxelwidgets.widgets.Propagation = pyxelwidgets.widgets.Propagation.Stop,
                 **kwargs):
        """
        selector: Pages.Selector = Pages.Selector.Top, optional
            The side of the strip of slots (Off: only the ``store``/``recall`` actions).
        send: bool = True, optional
            Widgets brought back emit Changed with their values.
        save: bool = True, optional
            Keep stored presets in the layout file (``parser.load`` of a file
            writes them there; the designer puts them in the layout it saves).
        presets: dict, optional
            What the slots hold: ``{slot: {widget path: state}}``, as ``presets``
            holds it, or as ``stored()`` gives it for a layout.
        current_color, stored_color, empty_color: Color, optional
            The slot brought back last, slots with something stored, empty ones.
        """
        self.selector = selector
        self.send = send
        self.save = save
        self.current_color = current_color
        self.stored_color = stored_color
        self.empty_color = empty_color
        #: What each slot stored: {slot: {widget path (names): state}}
        self.presets = self._decode(presets)
        #: The slot stored or brought back last, or None
        self.preset = None
        # The slot pressed, until let go (a hold stores instead)
        self._pressed = None
        super().__init__(x, y, width, height, propagation = propagation, **kwargs)

    @property
    def content(self) -> pyxelwidgets.rectangle.Rectangle2D:
        """The area for widgets, relative to this one: everything but the strip."""
        return Pages.content.fget(self)

    def _cells(self) -> list:
        w, h = self.rect.w, self.rect.h
        return {
            Pages.Selector.Top: [(i, h - 1) for i in range(w)],
            Pages.Selector.Bottom: [(i, 0) for i in range(w)],
            Pages.Selector.Left: [(0, h - 1 - i) for i in range(h)],
            Pages.Selector.Right: [(w - 1, h - 1 - i) for i in range(h)],
            Pages.Selector.Off: [],
        }[self.selector]

    def _widgets(self, group = None, path = ()):
        """(path of names, widget) of every widget inside, groups' children included."""
        for child in (group or self).children:
            yield path + (child.name,), child
            if isinstance(child, Group) and not isinstance(child, Presets):
                yield from self._widgets(child, path + (child.name,))

    @staticmethod
    def _decode(presets) -> dict:
        """Presets as ``stored()`` gives them (or as ``presets`` holds them) to ``presets``."""
        decoded = {}
        for slot, stored in (presets or {}).items():
            decoded[int(slot)] = {tuple(path.split('/')) if isinstance(path, str) else tuple(path):
                                  pyxelwidgets.widgets.state_from_json(state) for path, state in stored.items()}
        return decoded

    def stored(self) -> dict:
        """What the slots hold as JSON data, for a layout's ``presets`` option: widget paths as ``'group/name'``."""
        return {str(slot): {'/'.join(path): pyxelwidgets.widgets.state_to_json(state) for path, state in stored.items()}
                for slot, stored in sorted(self.presets.items())}

    def _configure(self, name: str, value) -> None:
        if name == 'presets':
            value = self._decode(value)
        super()._configure(name, value)

    def snapshot(self) -> dict:
        """What the widgets inside show now, by path."""
        return {path: copy.deepcopy(state) for path, widget in self._widgets() if (state := widget.save_state())}

    def store(self, slot: int) -> None:
        """Store what the widgets show in ``slot``."""
        self.presets[int(slot)] = self.snapshot()
        self.preset = int(slot)
        self.updated = True
        self.emit(pyxelwidgets.events.PresetStored(self, int(slot)))

    def recall(self, slot: int) -> None:
        """Bring back what ``slot`` stored (nothing if it's empty)."""
        stored = self.presets.get(int(slot))
        if stored is None:
            return
        widgets = dict(self._widgets())
        for path, state in stored.items():
            widget = widgets.get(path)
            if widget is None:
                continue
            before = getattr(widget, 'value', None)
            widget.load_state(copy.deepcopy(state))
            if self.send and isinstance(widget, pyxelwidgets.widgets.ValueWidget) and widget.value != before:
                widget.emit(pyxelwidgets.events.Changed(widget, widget.value))
        self.preset = int(slot)
        self.updated = True
        self.emit(pyxelwidgets.events.PresetRecalled(self, int(slot)))

    def save_state(self) -> dict:
        return {'presets': copy.deepcopy(self.presets), 'preset': self.preset}

    def load_state(self, state: dict) -> None:
        if isinstance(state.get('presets'), dict):
            self.presets = copy.deepcopy(state['presets'])
            self.preset = state.get('preset')
            self.updated = True

    def input(self, event: pyxelwidgets.events.PadEvent) -> bool:
        cells = self._cells()
        if (event.x, event.y) not in cells:
            return super().input(event)
        slot = cells.index((event.x, event.y))
        if isinstance(event, pyxelwidgets.events.PadPressed):
            self._pressed = slot
        elif isinstance(event, pyxelwidgets.events.PadHeld) and self._pressed == slot:
            self._pressed = None
            self.store(slot)
        elif isinstance(event, pyxelwidgets.events.PadReleased) and self._pressed == slot:
            self._pressed = None
            if slot in self.presets:
                self.recall(slot)
            else:
                self.store(slot)
        return True

    def draw(self) -> None:
        super().draw()
        for slot, cell in enumerate(self._cells()):
            if slot == self.preset:
                color = self.current_color
            elif slot in self.presets:
                color = self.stored_color
            else:
                color = self.empty_color
            self.buffer[cell] = color
