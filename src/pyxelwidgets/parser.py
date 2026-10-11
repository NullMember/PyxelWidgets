import pyxelwidgets.group
import pyxelwidgets.surface
import pyxelwidgets.widgets

import json
import importlib

class Parser():
    """
    Builds a Surface with controllers and groups of widgets from a JSON layout:

        {"Surface": {"Rect": {"width": 9, "height": 9}},
         "Controllers": [{"Path": "midi.novation.launchpad", "Class": "MK3", "Args": ["Model.X"],
                          "Input": "...", "Output": "...", "Rect": {"x": 0, "y": 0}}],
         "Groups": [{"Rect": {"x": 0, "y": 0, "width": 8, "height": 8},
                     "Widgets": [{"Widget": "Fader", "Rect": {"x": 0, "y": 0, "width": 1, "height": 8}}]}]}
    """
    def __init__(self, file) -> None:
        with open(file, 'r') as f:
            self.json = json.load(f)
        self.groups = []
        self.controllers = []
        self.surface = None
        self.get_surface()
        self.get_controllers()
        self.get_groups()

    def get_surface(self):
        rect = self.json['Surface']['Rect']
        self.surface = pyxelwidgets.surface.Surface(rect['width'], rect['height'])

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
            self.surface.add_controller(self.controllers[-1], rect['x'], rect['y'])

    def get_groups(self):
        for group in self.json['Groups']:
            rect = group['Rect']
            self.groups.append(pyxelwidgets.group.Group(rect['x'], rect['y'], rect['width'], rect['height']))
            for widget in group['Widgets']:
                rect = widget['Rect']
                klass = getattr(pyxelwidgets.widgets, widget['Widget'])
                self.groups[-1].add(klass(rect['x'], rect['y'], rect['width'], rect['height']))
            self.surface.add(self.groups[-1])
