import pyxelwidgets.window
import pyxelwidgets.widgets

import json
import importlib

class Parser():
    def __init__(self, file) -> None:
        with open(file, 'r') as f:
            self.json = json.load(f)
        self.windows = []
        self.controllers = []
        self.manager = None
        self.get_manager()
        self.get_controllers()
        self.get_windows()

    def get_manager(self):
        rect = self.json['Manager']['Rect']
        self.manager = pyxelwidgets.window.Manager(rect['width'], rect['height'])

    def get_controllers(self):
        for controller in self.json['Controllers']:
            rect = controller['Rect']
            module = importlib.import_module(f"pyxelwidgets.controllers.{controller['Path']}")
            klass = getattr(module, f"{controller['Class']}")
            args = []
            # Args are dotted paths relative to the class, e.g. "Model.X"
            for arg in controller.get('Args', []):
                prop = klass
                for path in arg.split('.'):
                    prop = getattr(prop, path)
                args.append(prop)
            self.controllers.append(klass(*args))
            self.controllers[-1].init()
            ports = [controller[key] for key in ('Input', 'Output') if key in controller]
            self.controllers[-1].connect(*ports)
            self.manager.add_controller(self.controllers[-1], rect['x'], rect['y'])

    def get_windows(self):
        for window in self.json['Windows']:
            rect = window['Rect']
            self.windows.append(pyxelwidgets.window.Window(rect['width'], rect['height']))
            for widget in window['Widgets']:
                rect = widget['Rect']
                klass = getattr(pyxelwidgets.widgets, widget['Widget'])
                self.windows[-1].add_widget(klass(rect['x'], rect['y'], rect['width'], rect['height']))
            rect = window['Rect']
            self.manager.add_window(self.windows[-1], rect['x'], rect['y'], rect['width'], rect['height'])
