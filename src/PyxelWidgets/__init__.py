__all__ = ['Controllers', 'Helpers', 'Utils', 'Widgets']

import PyxelWidgets.Helpers
import PyxelWidgets.Widgets
import PyxelWidgets.Controllers
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

    def addWidget(self, widget: PyxelWidgets.Widgets.Widget):
        self.widgets[widget.name] = widget
    
    def addWidgets(self, widgets):
        for widget in widgets:
            self.widgets[widget.name] = widget
    
    def removeWidget(self, name: str):
        if name in self.widgets:
            self.widgets.pop(name)
    
    def forceUpdate(self):
        self.buffer.fill(PyxelWidgets.Helpers.Colors.Invisible)
        for widget in self.widgets.values():
            widget.updated = True

    def process(self, name, event, data):
        if event != 'custom':
            x, y, value = data
            b = PyxelWidgets.Helpers.Rectangle2D(x, y)
            if self.rect.collide(b):
                for widget in self.widgets.values():
                    if widget.rect.collide(b):
                        widget.process(name, event, data)

    def updateArea(self, rect: PyxelWidgets.Helpers.Rectangle2D):
        intersect = self.rect.intersect(rect)
        if intersect:
            for widget in self.widgets.values():
                if widget.updated:
                    area, buffer = widget.updateArea(intersect)
                    if buffer is not None:
                        try:
                            view = self.buffer[area.slice]
                            view[:] = numpy.where(buffer == False, view, buffer)
                        except BaseException as e:
                            traceback.print_exc()
                            print("Unexpected exception", e)
        return intersect, self.buffer[intersect.slice]

    def update(self):
        for widget in self.widgets.values():
            if widget.updated:
                area, buffer = widget.updateArea(self.rect)
                if buffer is not None:
                    try:
                        view = self.buffer[area.slice]
                        view[:] = numpy.where(buffer == False, view, buffer)
                    except BaseException as e:
                        traceback.print_exc()
                        print("Unexpected exception", e)
        return self.rect, self.buffer[self.rect.slice]

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
    
    def destroy(self):
        for controller in list(self.controllers):
            self.controllers[controller]['controller'].close()
            self.removeController(controller)

    def addWindow(self, window: Window, x: int, y: int, width: int, height: int) -> None:
        self.windows[window.name] = {}
        self.windows[window.name]['window'] = window
        self.windows[window.name]['rect'] = PyxelWidgets.Helpers.Rectangle2D(x, y, width, height)
    
    def removeWindow(self, name: str):
        if name in self.windows:
            self.windows.pop(name)

    def addController(self, controller: PyxelWidgets.Controllers.Controller, x: int, y: int):
        self.controllers[controller.name] = {}
        self.controllers[controller.name]['controller'] = controller
        self.controllers[controller.name]['rect'] = PyxelWidgets.Helpers.Rectangle2D(x, y, controller.rect.w, controller.rect.h)
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
                window['window'].process(name, event, (data[0] + cwr.x, data[1] + cwr.y, data[2]))

    def update(self):
        for window in list(self.windows.values()):
            intersect = self.rect.intersect(window['rect'])
            if intersect:
                rect, buffer = window['window'].updateArea(intersect.origin)
                if rect is not None:
                    update = rect + intersect
                    self.buffer[update.slice] = buffer[rect.slice]
        self.buffer = numpy.where(self.buffer == PyxelWidgets.Helpers.Colors.Invisible, PyxelWidgets.Helpers.Colors.Black, self.buffer)
        for controller in list(self.controllers.values()):
            intersect = self.rect.intersect(controller['rect'])
            if intersect:
                controller['controller'].update((intersect.origin, self.buffer[intersect.slice]))