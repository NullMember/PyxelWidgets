from ..Button import Button
from ...Helpers import *
import numpy

class ButtonGroup():

    _count = 0

    def __init__(self, x: int, y: int, width: int, height: int, **kwargs):
        self.name = kwargs.get('name', f'ButtonGroup_{ButtonGroup._count}')
        if 'name' in kwargs.keys():
            del kwargs['name']
        self.rect = Rectangle2D(x, y, width, height)
        self.buttons = numpy.array([[Button(self.rect.x + _x, self.rect.y + _y, 1, 1, \
                                    name = f'{self.name}_{_x}_{_y}', **kwargs) \
                                    for _y in range(height)] for _x in range(width)])
        ButtonGroup._count += 1
    
    @property
    def widgets(self):
        return self.buttons.flatten()