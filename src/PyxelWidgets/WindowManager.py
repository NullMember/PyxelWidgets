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
        self._controllers.append({'controller': controller, 'x': x, 'y': y, 'width': width, 'height': height})
        controller.init()
        controller.setCallback(lambda _x, _y, _value: self.process(x, y, _x, _y, _value))
    
    def removeControllers(self):
        for controller in self._controllers:
            controller['controller'].deinit()
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
            self._renderer[window] = {'window': self._windows[window], 'x': x, 'y': y, 'width': width, 'height': height}
            self._renderer[window]['window'].setCallback(lambda pixels: self.update(window, pixels))
            self._renderer[window]['window'].run()
    
    def removeWindowFromRenderer(self, window: str):
        if window in self._renderer.keys():
            self._renderer[window]['window'].stop()
            self._renderer[window]['window'].setCallback(lambda *_, **__: None)
            self._renderer.pop(window)
    
    def runAll(self):
        for window in self._renderer.values():
            window['window'].run()
    
    def stopAll(self):
        for window in self._renderer.values():
            window['window'].stop()

    def getRenderWindows(self):
        return list(self._renderer.values())

    def getRenderWindowNames(self):
        return list(self._renderer.keys())
    
    def isCollide(self, x: int, y: int, entry: dict):
        if x >= entry['x'] and \
           x < entry['x'] + entry['width'] and \
           y >= entry['y'] and \
           y < entry['y'] + entry['height']:
            print(entry, x, y, True)
            return True
        else:
            print(entry, x, y, False)
            return False

    def process(self, cx, cy, x, y, value):
        for window in self._renderer.values():
            if self.isCollide(x, y, window):
                window['window'].setButton(x + cx - window['x'], y + cy - window['y'], value)

    def update(self, name, pixels):
        if name in self._renderer.keys():
            window = self._renderer[name]
            x = window['x']
            y = window['y']
            width = window['width']
            height = window['height']
            for controller in self._controllers:
                controller['controller'].updateAreaByArea(x + controller['x'], y + controller['y'], x - controller['x'], y - controller['y'], width, height, pixels)