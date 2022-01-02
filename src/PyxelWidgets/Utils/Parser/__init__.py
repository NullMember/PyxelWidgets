import PyxelWidgets

import json
import importlib

class Parser():
    def __init__(self, file) -> None:
        with open(file, 'r') as f:
            self.json = json.load(f)
        self.windows = []
        self.controllers = []
        self.manager = None
        self.getManager()
        self.getControllers()
        self.getWindows()
    
    def getManager(self):
        rect = self.json['Manager']['Rect']
        self.manager = PyxelWidgets.Manager(rect['width'], rect['height'])
    
    def getControllers(self):
        for controller in self.json['Controllers']:
            rect = controller['Rect']
            module = importlib.import_module(f"PyxelWidgets.Controllers.{controller['Path']}")
            klass = getattr(module, f"{controller['Class']}")
            args = []
            prop = klass
            for arg in controller['Args']:
                for path in arg.split('.'):
                    prop = getattr(prop, path)
                args.append(prop)
            self.controllers.append(klass(*args))
            self.controllers[-1].init()
            self.controllers[-1].connect(controller['Input'], controller['Output'])
            self.manager.addController(self.controllers[-1], rect['x'], rect['y'])
    
    def getWindows(self):
        for window in self.json['Windows']:
            rect = window['Rect']
            self.windows.append(PyxelWidgets.Window(rect['width'], rect['height']))
            for widget in window['Widgets']:
                rect = widget['Rect']
                module = importlib.import_module(f"PyxelWidgets.Widgets.{widget['Widget']}")
                klass = getattr(module, f"{widget['Widget']}")
                self.windows[-1].addWidget(klass(rect['x'], rect['y'], rect['width'], rect['height']))
            rect = window['Rect']
            self.manager.addWindow(self.windows[-1], rect['x'], rect['y'], rect['width'], rect['height'])