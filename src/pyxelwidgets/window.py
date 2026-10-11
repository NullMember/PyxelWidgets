import pyxelwidgets.enums
import pyxelwidgets.pixel
import pyxelwidgets.rectangle
import pyxelwidgets.widgets
import pyxelwidgets.controllers
import numpy

class Window():

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', f'Window_{Window._count}')
        self.rect = pyxelwidgets.rectangle.Rectangle2D(0, 0, width, height)
        self.widgets = {}
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), pyxelwidgets.pixel.Pixel)
        self.buffer.fill(pyxelwidgets.pixel.Colors.Invisible)
        self.frame_counter = 0
        self.callback = kwargs.get('callback', lambda *_, **__: None)
        Window._count += 1

    def add_widget(self, widget: pyxelwidgets.widgets.Widget):
        self.widgets[widget.name] = widget
        widget.updated = True
    
    def add_widgets(self, widgets):
        for widget in widgets:
            self.widgets[widget.name] = widget
            widget.updated = True
    
    def remove_widget(self, name: str):
        if name in self.widgets:
            self.widgets.pop(name)
    
    def force_update(self):
        self.buffer.fill(pyxelwidgets.pixel.Colors.Invisible)
        for widget in list(self.widgets.values()):
            widget.updated = True

    def process(self, name, event, data):
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

    def update_area(self, rect: pyxelwidgets.rectangle.Rectangle2D):
        self.callback(self.name, pyxelwidgets.enums.Event.Frame, self.frame_counter)
        self.frame_counter += 1
        intersect = self.rect.intersect(rect)
        if intersect:
            for widget in list(self.widgets.values()):
                if widget.updated:
                    area, buffer = widget.update_area(intersect)
                    if buffer is not None:
                        view = self.buffer[area.slice]
                        view[:] = buffer
            return intersect, self.buffer[intersect.slice]
        return None, None

    def update(self):
        return self.update_area(self.rect)

class Manager():

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', f'Manager_{Manager._count}')
        self.windows = {}
        self.controllers = {}
        self.rect = pyxelwidgets.rectangle.Rectangle2D(0, 0, width, height)
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), pyxelwidgets.pixel.Pixel)
        self.buffer.fill(pyxelwidgets.pixel.Colors.Invisible)
        self.callback = kwargs.get('callback', lambda *_, **__: None)
        Manager._count += 1
    
    def destroy(self):
        for controller in list(self.controllers):
            self.controllers[controller]['controller'].close()
            self.remove_controller(controller)

    def add_window(self, window: Window, x: int, y: int, width: int, height: int) -> None:
        self.windows[window.name] = {}
        self.windows[window.name]['window'] = window
        self.windows[window.name]['rect'] = pyxelwidgets.rectangle.Rectangle2D(x, y, width, height)
    
    def remove_window(self, name: str):
        if name in self.windows:
            self.windows.pop(name)

    def add_controller(self, controller: pyxelwidgets.controllers.Controller, x: int, y: int):
        self.controllers[controller.name] = {}
        self.controllers[controller.name]['controller'] = controller
        self.controllers[controller.name]['rect'] = pyxelwidgets.rectangle.Rectangle2D(x, y, controller.rect.w, controller.rect.h)
        controller.set_callback(self.process)
    
    def remove_controller(self, name):
        if name in self.controllers:
            self.controllers.pop(name)
    
    def force_update(self):
        for window in list(self.windows.values()):
            window.force_update()

    def process(self, name, event, data):
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
        for window in list(self.windows.values()):
            intersect = self.rect.intersect(window['rect'])
            if intersect:
                rect, buffer = window['window'].update_area(intersect.origin)
                if rect is not None:
                    update = rect + intersect
                    self.buffer[update.slice] = buffer[rect.slice]
        self.buffer = numpy.where(self.buffer == pyxelwidgets.pixel.Colors.Invisible, pyxelwidgets.pixel.Colors.Black, self.buffer)
        for controller in list(self.controllers.values()):
            intersect = self.rect.intersect(controller['rect'])
            if intersect:
                controller['controller'].update((intersect.origin, self.buffer[intersect.slice]))