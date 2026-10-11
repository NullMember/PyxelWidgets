"""
GUI framework for low resolution devices (e.g. Novation Launchpad, LED keyboards).

Hardware controllers are not imported here so that the core works without
optional dependencies; import them from ``pyxelwidgets.controllers.*``.
"""

__version__ = '0.1.0'

from pyxelwidgets.app import App
from pyxelwidgets.clock import Clock, Target
from pyxelwidgets.controllers import Controller
from pyxelwidgets.enums import Event
from pyxelwidgets.parser import Parser
from pyxelwidgets.pixel import Colors, Pixel
from pyxelwidgets.rectangle import Rectangle2D
from pyxelwidgets.widgets import (Button, ButtonGroup, Fader, Keyboard, Knob,
                                  Sequencer, Sprite, Tracker, Widget, XY)
from pyxelwidgets.window import Manager, Window

__all__ = [
    'App', 'Button', 'ButtonGroup', 'Clock', 'Colors', 'Controller', 'Event', 'Fader',
    'Keyboard', 'Knob', 'Manager', 'Parser', 'Pixel', 'Rectangle2D', 'Sequencer',
    'Sprite', 'Target', 'Tracker', 'Widget', 'Window', 'XY',
]
