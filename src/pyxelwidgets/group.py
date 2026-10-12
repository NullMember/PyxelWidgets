import pyxelwidgets.buffer
import pyxelwidgets.color
import pyxelwidgets.events
import pyxelwidgets.rectangle
import pyxelwidgets.widgets
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
        self._children = []
        self._dirty = True
        super().__init__(x, y, width, height, inactive_color = background, propagation = propagation, **kwargs)

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

class Pages(Group):
    """
    A group whose children are pages: only the current ``page`` is shown and
    gets input. An optional ``selector`` strip along one side has a cell per
    page; pressing one switches to that page. Emits PageChanged.

    Pages usually fill ``content``, the area besides the selector.
    """

    emits = (pyxelwidgets.events.PageChanged,)

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
