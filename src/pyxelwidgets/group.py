import pyxelwidgets.buffer
import pyxelwidgets.color
import pyxelwidgets.events
import pyxelwidgets.widgets
import dataclasses

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

    def render(self) -> bool:
        changed = self._dirty or self.updated
        # Render every child, even after one already changed
        for child in self._children:
            changed = child.render() or changed
        if not changed:
            return False
        self._dirty = False
        self.updated = False
        self.draw()
        return True

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
