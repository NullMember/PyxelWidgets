__all__ = ['Controller']

import pyxelwidgets.buffer
import pyxelwidgets.enums
import pyxelwidgets.color
import pyxelwidgets.rectangle
import pyxelwidgets.clock
import numpy
import threading
import time

class Controller():

    _count = 0

    def __init__(self, **kwargs):
        self.name = kwargs.get('name', f'Controller_{Controller._count}')
        self.rect = pyxelwidgets.rectangle.Rectangle2D(kwargs.get('x', 0), kwargs.get('y', 0), kwargs.get('width', 1), kwargs.get('height', 1))
        self.held_time = kwargs.get('held_time', 1.0)
        self.double_press_time = kwargs.get('double_press_time', 0.15)
        self.initialized = False
        self.connected = False
        self.terminated = False
        # What the device currently shows; starts transparent so the first frame is sent in full
        self.buffer = pyxelwidgets.buffer.new(self.rect.w, self.rect.h)
        self.buttons = numpy.ndarray((self.rect.w, self.rect.h))
        self.buttons.fill(0.0)
        self.clock = pyxelwidgets.clock.Clock()
        self._press_time = numpy.ndarray((self.rect.w, self.rect.h))
        self._press_time.fill(0.0)
        self._held = numpy.ndarray((self.rect.w, self.rect.h), threading.Timer)
        self.callback = lambda *_, **__ : None
        Controller._count += 1

    def set_callback(self, callback):
        self.callback = callback

    def init(self, clock = False):
        if self.initialized:
            raise Exception(f'{self.name} already initialized')
        if clock:
            self.clock.start()
        self.initialized = True
    
    def close(self):
        if self.connected:
            self.disconnect()
        for timer in self._held.flat:
            if timer is not None:
                timer.cancel()
        self.clock.terminate()
        self.terminated = True

    def connect(self):
        if self.connected:
            self.disconnect()
        self.connected = True

    def disconnect(self):
        self.connected = False
    
    def get_button(self, x: int, y: int) -> float:
        return self.buttons[x, y]

    def set_button(self, x: int, y: int, value: float) -> None:
        self.buttons[x, y] = min(1.0, max(0.0, value))
        self.set_state(x, y, bool(self.buttons[x, y]))
    
    def set_state(self, x: int, y: int, state: bool) -> None:
        if state:
            self.set_pressed(x, y)
        else:
            self.set_released(x, y)
        return
    
    def set_pressed(self, x: int, y: int) -> None:
        current_time = time.time()
        if self._held[x, y] is not None:
            self._held[x, y].cancel()
        self._held[x, y] = threading.Timer(interval = self.held_time, function = self.set_held, args = (x, y))
        self._held[x, y].start()
        self.callback(self.name, pyxelwidgets.enums.Event.Pressed, (x, y, self.buttons[x, y]))
        if self._press_time[x, y] + self.double_press_time > current_time:
            self.callback(self.name, pyxelwidgets.enums.Event.DoublePressed, (x, y, self.buttons[x, y]))
        self._press_time[x, y] = current_time

    def set_released(self, x: int, y: int) -> None:
        # Release can arrive without a press, e.g. pad held while connecting
        if self._held[x, y] is not None:
            self._held[x, y].cancel()
            self._held[x, y] = None
        self.callback(self.name, pyxelwidgets.enums.Event.Released, (x, y, self.buttons[x, y]))
    
    def set_held(self, x: int, y: int) -> None:
        self.callback(self.name, pyxelwidgets.enums.Event.Held, (x, y, self.buttons[x, y]))
    
    def set_custom(self, event, name, data):
        self.callback(self.name, pyxelwidgets.enums.Event.Custom, (name, event, data))

    def send_pixel(self, x: int, y: int, pixel: pyxelwidgets.color.Color):
        raise NotImplementedError("send_pixel method must be implemented")

    def update_one(self, x: int, y: int, pixel: pyxelwidgets.color.Color):
        self.update_area(pyxelwidgets.rectangle.Rectangle2D(x, y, 1, 1), pixel)

    def update_row(self, y: int, pixel: pyxelwidgets.color.Color):
        self.update_area(pyxelwidgets.rectangle.Rectangle2D(0, y, self.rect.w, 1), pixel)

    def update_column(self, x: int, pixel: pyxelwidgets.color.Color):
        self.update_area(pyxelwidgets.rectangle.Rectangle2D(x, 0, 1, self.rect.h), pixel)
    
    def update_area(self, rect: pyxelwidgets.rectangle.Rectangle2D, pixel: pyxelwidgets.color.Color):
        if self.connected:
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                self._send(intersect, pyxelwidgets.buffer.new(intersect.w, intersect.h, pixel))

    def update(self, data: tuple):
        rect, buffer = data
        if rect is not None and self.connected:
            intersect = self.rect.intersect(rect)
            if intersect is not None:
                self._send(intersect, buffer[(intersect - rect).slice])

    def _send(self, rect: pyxelwidgets.rectangle.Rectangle2D, source: numpy.ndarray):
        """Send the pixels of ``source`` (placed at ``rect``) that differ from what the device shows."""
        current = self.buffer[rect.slice]
        changed = numpy.any(source != current, axis = -1)
        for dx, dy in numpy.argwhere(changed):
            x, y = rect.x + int(dx), rect.y + int(dy)
            current[dx, dy] = source[dx, dy]
            self.send_pixel(x, y, pyxelwidgets.color.Color.from_array(source[dx, dy]))
