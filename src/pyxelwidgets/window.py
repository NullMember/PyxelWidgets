import pyxelwidgets.buffer
import pyxelwidgets.enums
import pyxelwidgets.pixel
import pyxelwidgets.rectangle
import pyxelwidgets.widgets
import pyxelwidgets.controllers
import threading

class Window():
    """
    Composes widgets in the order they were added: later widgets are drawn
    on top, and transparent pixels show the widgets underneath.

    ``lock`` guards widget state. It is shared with the Manager the window
    is added to; hold it when changing widgets from another thread.
    """

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', f'Window_{Window._count}')
        self.rect = pyxelwidgets.rectangle.Rectangle2D(0, 0, width, height)
        self.widgets = {}
        self.buffer = pyxelwidgets.buffer.new(self.rect.w, self.rect.h)
        self.frame_counter = 0
        self.callback = kwargs.get('callback', lambda *_, **__: None)
        self.lock = threading.RLock()
        self._dirty = True
        Window._count += 1

    def add_widget(self, widget: pyxelwidgets.widgets.Widget):
        with self.lock:
            self.widgets[widget.name] = widget
            widget.updated = True
            self._dirty = True

    def add_widgets(self, widgets):
        for widget in widgets:
            self.add_widget(widget)

    def remove_widget(self, name: str):
        with self.lock:
            if name in self.widgets:
                self.widgets.pop(name)
                self._dirty = True

    def force_update(self):
        with self.lock:
            for widget in self.widgets.values():
                widget.updated = True
            self._dirty = True

    def process(self, name, event, data):
        with self.lock:
            if event != pyxelwidgets.enums.Event.Custom:
                x, y, value = data
                b = pyxelwidgets.rectangle.Rectangle2D(x, y)
                if self.rect.collide(b):
                    for widget in list(self.widgets.values()):
                        if widget.rect.collide(b):
                            widget.process(name, event, data)
            else:
                self.callback(name, event, data)

    def set_callback(self, callback) -> None:
        self.callback = callback

    def render(self) -> bool:
        """Redraw changed widgets and recompose; returns True if the buffer changed."""
        with self.lock:
            self.callback(self.name, pyxelwidgets.enums.Event.Frame, self.frame_counter)
            self.frame_counter += 1
            dirty = self._dirty
            for widget in list(self.widgets.values()):
                if widget.updated:
                    widget.update_area(widget.rect)
                    dirty = True
            if dirty:
                self.buffer[:] = 0
                for widget in self.widgets.values():
                    intersect = self.rect.intersect(widget.rect)
                    if intersect is not None:
                        source = widget.buffer[(intersect - widget.rect).slice]
                        pyxelwidgets.buffer.composite(self.buffer[intersect.slice], source)
                self._dirty = False
            return dirty

    def update_area(self, rect: pyxelwidgets.rectangle.Rectangle2D):
        self.render()
        intersect = self.rect.intersect(rect)
        if intersect:
            return intersect, self.buffer[intersect.slice]
        return None, None

    def update(self):
        return self.update_area(self.rect)

class Manager():
    """
    Composes windows (in the order they were added) onto a black background
    and sends the result to controllers.

    ``lock`` is held while processing input and rendering, and is shared with
    every added window and with an App's Clock. Hold it when changing widgets
    from another thread, e.g. a MIDI callback of your own.
    """

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', f'Manager_{Manager._count}')
        self.windows = {}
        self.controllers = {}
        self.rect = pyxelwidgets.rectangle.Rectangle2D(0, 0, width, height)
        self.buffer = pyxelwidgets.buffer.new(self.rect.w, self.rect.h, pyxelwidgets.pixel.Colors.Black)
        self.callback = kwargs.get('callback', lambda *_, **__: None)
        self.lock = threading.RLock()
        self._dirty = True
        Manager._count += 1

    def destroy(self):
        with self.lock:
            controllers = [entry['controller'] for entry in self.controllers.values()]
            self.controllers.clear()
        # Closed outside the lock: closing waits for clock targets that may need it
        for controller in controllers:
            controller.close()

    def add_window(self, window: Window, x: int, y: int, width: int, height: int) -> None:
        with self.lock:
            window.lock = self.lock
            self.windows[window.name] = {}
            self.windows[window.name]['window'] = window
            self.windows[window.name]['rect'] = pyxelwidgets.rectangle.Rectangle2D(x, y, width, height)
            self._dirty = True

    def remove_window(self, name: str):
        with self.lock:
            if name in self.windows:
                self.windows.pop(name)
                self._dirty = True

    def add_controller(self, controller: pyxelwidgets.controllers.Controller, x: int, y: int):
        with self.lock:
            self.controllers[controller.name] = {}
            self.controllers[controller.name]['controller'] = controller
            self.controllers[controller.name]['rect'] = pyxelwidgets.rectangle.Rectangle2D(x, y, controller.rect.w, controller.rect.h)
            controller.set_callback(self.process)
            self._dirty = True

    def remove_controller(self, name):
        with self.lock:
            if name in self.controllers:
                self.controllers.pop(name)

    def force_update(self):
        with self.lock:
            for window in self.windows.values():
                window['window'].force_update()
            self._dirty = True

    def process(self, name, event, data):
        with self.lock:
            if event != pyxelwidgets.enums.Event.Custom:
                for window in list(self.windows.values()):
                    cr = self.controllers[name]['rect']
                    wr = window['rect']
                    if cr.collide(wr):
                        cwr = cr - wr
                        window['window'].process(name, event, (data[0] + cwr.x, data[1] + cwr.y, data[2]))
            else:
                self.callback(name, event, data)

    def set_callback(self, callback) -> None:
        self.callback = callback

    def update(self):
        with self.lock:
            dirty = self._dirty
            for window in list(self.windows.values()):
                # Render every window, even when an earlier one was already dirty
                dirty = window['window'].render() or dirty
            if dirty:
                self.buffer[:] = pyxelwidgets.pixel.Colors.Black
                for window in self.windows.values():
                    content = window['window'].rect + window['rect']
                    intersect = self.rect.intersect(window['rect'])
                    intersect = intersect and intersect.intersect(content)
                    if intersect:
                        source = window['window'].buffer[(intersect - window['rect']).slice]
                        pyxelwidgets.buffer.composite(self.buffer[intersect.slice], source)
                self._dirty = False
            # Always called: controllers diff against what they sent, and
            # some (Virtual) also process their own events here
            for controller in list(self.controllers.values()):
                intersect = self.rect.intersect(controller['rect'])
                if intersect:
                    controller['controller'].update((intersect.origin, self.buffer[intersect.slice]))
