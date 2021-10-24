__all__ = ['Controller', 'Helpers', 'Util', 'Widgets']

import PyxelWidgets.Helpers
import PyxelWidgets.Widgets
import PyxelWidgets.Controller
import traceback
import numpy

class Window():

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', f'Window_{Window._count}')
        self.rect = PyxelWidgets.Helpers.Rectangle2D(0, 0, width, height)
        self.widgets = {}
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), PyxelWidgets.Helpers.Pixel)
        self.buffer.fill(PyxelWidgets.Helpers.Colors.Invisible)
        self._callback = lambda *_, **__: None
        Window._count += 1

    @property
    def x(self) -> int:
        return self.rect.x
    
    @x.setter
    def x(self, value: int) -> None:
        self.rect.x = min(self.rect.w, max(0, value))
        self.buffer[self.rect.l:self.rect.r, self.rect.b:self.rect.t].fill(PyxelWidgets.Helpers.Colors.Invisible)
        self.forceUpdate()

    @property
    def y(self) -> int:
        return self.rect.y
    
    @y.setter
    def y(self, value: int) -> None:
        self.rect.y = min(self.rect.h, max(0, value))
        self.buffer[self.rect.l:self.rect.r, self.rect.b:self.rect.t].fill(PyxelWidgets.Helpers.Colors.Invisible)
        self.forceUpdate()

    def addWidget(self, widget: PyxelWidgets.Widgets.Widget):
        self.widgets[widget.name] = widget
    
    def addWidgets(self, widgets):
        for widget in widgets:
            self.widgets[widget.name] = widget
    
    def forceUpdate(self):
        for widget in self.widgets.values():
            widget.updated = True

    def process(self, name, event, data):
        if event != 'custom':
            x, y, value = data
            for widget in self.widgets.values():
                b = PyxelWidgets.Helpers.Rectangle2D(x, y)
                w = widget.rect - self.rect
                if b.collide(w):
                    if event == 'pressed':
                        widget.pressed(b.x - w.x, b.y - w.y, value)
                    elif event == 'released':
                        widget.released(b.x - w.x, b.y - w.y, value)
                    elif event == 'held':
                        widget.held(b.x - w.x, b.y - w.y, value)

    def update(self):
        for widget in self.widgets.values():
            if widget.updated:
                buffer = widget.updateArea(self.rect.x, self.rect.y, self.rect.w, self.rect.h)
                if buffer is not None:
                    try:
                        copy = PyxelWidgets.Helpers.Rectangle2D(widget.rect.x, widget.rect.y, buffer.shape[0], buffer.shape[1])
                        view = self.buffer[copy.l:copy.r, copy.b:copy.t]
                        view[:] = numpy.where(buffer == False, view, buffer)
                    except Exception as e:
                        traceback.print_exc()
                        print("Unexpected exception", e)
        return self.buffer

class Manager():

    _count = 0

    def __init__(self, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', f'Manager_{Window._count}')
        self.windows = {}
        self.controllers = {}
        self.rect = PyxelWidgets.Helpers.Rectangle2D(0, 0, width, height)
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), PyxelWidgets.Helpers.Pixel)
        self.buffer.fill(PyxelWidgets.Helpers.Colors.Invisible)
        Manager._count += 1

    def addWindow(self, window: Window, x: int, y: int, width: int, height: int) -> None:
        self.windows[window.name] = {}
        self.windows[window.name]['window'] = window
        self.windows[window.name]['rect'] = PyxelWidgets.Helpers.Rectangle2D(x, y, width, height)
    
    def removeWindow(self, name: str):
        if name in self.windows:
            self.windows.pop(name)

    def addController(self, controller: PyxelWidgets.Controller.Controller, x: int, y: int):
        self.controllers[controller.name] = {}
        self.controllers[controller.name]['controller'] = controller
        self.controllers[controller.name]['rect'] = PyxelWidgets.Helpers.Rectangle2D(x, y, controller.rect.w, controller.rect.h)
        controller.connect()
        controller.setCallback(self.process)
    
    def removeController(self, name):
        if name in self.controllers:
            self.controllers.pop(name)
    
    def forceUpdate(self):
        for window in list(self.windows.values()):
            window.forceUpdate()

    def process(self, name, event, data):
        for window in list(self.windows.values()):
            cr = self.controllers[name]['rect']
            wr = window['rect']
            if cr.collide(wr):
                cwr = cr - wr
                window['window'].process(event, (data[0] + cwr.x, data[1] + cwr.y, data[2]))

    def update(self):
        for window in list(self.windows.values()):
            wr = window['rect']
            intersect = self.rect.intersect(wr)
            if intersect:
                buffer = window['window'].update()
                update = intersect - self.rect
                self.buffer[update.l:update.r, update.b:update.t] = buffer[:wr.w, :wr.h]
        for controller in list(self.controllers.values()):
            intersect = self.rect.intersect(controller['rect'])
            if intersect:
                controller['controller'].update(self.buffer[intersect.l:intersect.r, intersect.b:intersect.t])