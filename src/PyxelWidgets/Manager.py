import PyxelWidgets.Helpers
import PyxelWidgets.Window
import PyxelWidgets.Controller
import numpy

class Manager():
    def __init__(self, width: int = 32, height: int = 32, **kwargs):
        self.windows = {}
        self.controllers = {}
        self.rect = PyxelWidgets.Helpers.Rectangle2D(0, 0, width, height)
        self.buffer = numpy.ndarray((self.rect.w, self.rect.h), PyxelWidgets.Helpers.Pixel)
        self.buffer.fill(PyxelWidgets.Helpers.Colors.Invisible)

    def addWindow(self, window: PyxelWidgets.Window.Window, x: int, y: int, width: int, height: int) -> None:
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