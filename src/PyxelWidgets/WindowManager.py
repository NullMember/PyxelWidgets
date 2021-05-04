import time
from threading import Thread

class WindowManager():
    def __init__(self, **kwargs):
        self._windows = {}
        self._renderer = {}
        self._controllers = []
        self._width = kwargs.get('width', 500)
        self._height = kwargs.get('height', 500)
        self._pixels = [[[0, 0, 0] for y in range(self._height)] for x in range(self._width)]
        self._frameTarget = kwargs.get('frameTarget', 60)
        self._run = False
        self._updateRunner = None

    def addWindow(self, window) -> None:
        self._windows[window.name] = window
    
    def addWindows(self, windows: list) -> None:
        for window in windows:
            self.addWindow(window)
    
    def getWindow(self, window: str):
        return self._windows[window]
    
    def getWindowNames(self):
        return list(self._windows.keys())

    def getWindows(self):
        return list(self._windows.values())

    def addController(self, controller, x: int, y: int):
        self._controllers.append({'object': controller, 'x': x, 'y': y, 'width': controller.width, 'height': controller.height})
        controller.init()
        controller.setCallback(lambda _x, _y, _value: self.process(x, y, _x, _y, _value))
    
    def removeControllers(self):
        for controller in self._controllers:
            controller['object'].deinit()
        self._controllers.clear()

    def addWidget(self, window: str, widget):
        if window in self._windows.keys():
            self._windows[window].addWidget(widget)
    
    def addWidgets(self, window: str, widgets: list):
        if window in self._windows.keys():
            self._windows[window].addWidgets(widgets)

    def removeWindow(self, name: str) -> None:
        if name in self.names:
            del self._windows[name]
    
    def addWindowToRenderer(self, window: str, x: int, y: int, width: int, height: int):
        if window in self._windows.keys():
            self._renderer[window] = {'object': self._windows[window], 'x': x, 'y': y, 'width': width, 'height': height}
            self._renderer[window]['object'].setCallback(lambda x, y, width, height, pixels: self.updateBuffer(window, x, y, width, height, pixels))
    
    def removeWindowFromRenderer(self, window: str):
        if window in self._renderer.keys():
            self._renderer[window]['object'].setCallback(lambda *_, **__: None)
            self._renderer.pop(window)
    
    def run(self):
        self._run = True
        self._updateRunner = Thread(None, self.runner)
        self._updateRunner.start()
    
    def stop(self):
        self._run = False

    def runner(self):
        while self._run:
            currentTime = time.time()
            self.update()
            elapsedTime = time.time() - currentTime
            sleepDuration = ((1.0 / self._frameTarget) - elapsedTime)
            time.sleep(sleepDuration if sleepDuration >= 0 else 0)

    def getRenderWindows(self):
        return list(self._renderer.values())

    def getRenderWindowNames(self):
        return list(self._renderer.keys())
    
    def forceUpdate(self):
        for window in self._windows.values():
            window.forceUpdate()
    
    def isCollide(self, x: int, y: int, entry: dict):
        if x >= entry['x'] and \
           x < entry['x'] + entry['width'] and \
           y >= entry['y'] and \
           y < entry['y'] + entry['height']:
            return True
        else:
            return False

    def process(self, cx, cy, x, y, value):
        for window in self._renderer.values():
            if self.isCollide(cx + x, cy + y, window):
                window['object'].setButton(x + cx - window['x'], y + cy - window['y'], value)

    def updateBuffer(self, name, x, y, width, height, pixels):
        if name in self._renderer.keys():
            window = self._renderer[name]
            wx = window['x']
            wy = window['y']
            ww = window['width']
            wh = window['height']
            if x >= 0 and x < ww and y >= 0 and y < wh:
                for _x in range(width):
                    for _y in range(height):
                        self._pixels[_x + x + wx][_y + y + wy] = pixels[_x][_y]

    def update(self):
        try:
            for window in self._renderer.values():
                window['object'].update()
        except:
            pass
        for controller in self._controllers:
            ctl = controller['object']
            cx = controller['x']
            cy = controller['y']
            cw = controller['width']
            ch = controller['height']
            ctl.updateAreaByArea(cx, cy, 0, 0, cw, ch, self._pixels)