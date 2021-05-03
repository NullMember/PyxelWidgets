class WindowManager():
    def __init__(self):
        self._windows = {}
        self._renderer = {}
        self._controllers = []

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

    def addController(self, controller, x: int, y: int, width: int, height: int):
        self._controllers.append({'object': controller, 'x': x, 'y': y, 'width': width, 'height': height})
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
            self._renderer[window]['object'].setCallback(lambda pixels: self.update(window, pixels))
            self._renderer[window]['object'].run()
    
    def removeWindowFromRenderer(self, window: str):
        if window in self._renderer.keys():
            self._renderer[window]['object'].stop()
            self._renderer[window]['object'].setCallback(lambda *_, **__: None)
            self._renderer.pop(window)
    
    def runAll(self):
        for window in self._renderer.values():
            window['object'].run()
    
    def stopAll(self):
        for window in self._renderer.values():
            window['object'].stop()

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

    def update(self, name, pixels):
        if name in self._renderer.keys():
            window = self._renderer[name]
            x = window['x']
            y = window['y']
            wx = window['object'].x
            wy = window['object'].y
            width = window['width']
            height = window['height']
            for controller in self._controllers:
                controller['object'].updateAreaByArea(controller['x'] + wx, controller['y'] + wy, x, y, width, height, pixels)