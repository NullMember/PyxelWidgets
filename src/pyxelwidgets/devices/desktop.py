"""
This computer's keyboard and mouse as an output, for macro boards and
automation: widgets press keys and shortcuts, type text, move and click the
mouse, and scroll::

    desktop = Desktop()
    desktop.connect()
    surface.map(save, desktop, Hotkey('ctrl+s'), on = Pressed)
    surface.map(talk, desktop, Key('f13', Source('value')), on = Changed)     # held while pressed
    surface.map(pad, desktop, MouseMove(Source('value_x'), Source('value_y')), on = Changed)
    surface.map(knob, desktop, Scroll(0, Source('delta')), on = Changed)

Needs pynput (``pip install "pyxelwidgets[desktop]"``). On macOS, allow the
app that runs it (Terminal, your editor) under System Settings > Privacy &
Security > Accessibility; without that the keys and clicks go nowhere.
"""

import platform
import queue
import threading
import traceback

import pyxelwidgets.devices
import pyxelwidgets.message

__all__ = ['Desktop']

class Desktop(pyxelwidgets.devices.Device):
    """
    The keyboard and mouse of this computer: sends Hotkey, Key, TypeText,
    MouseMove, MouseButton, MouseClick and Scroll. Actions run in order on a
    thread of their own; keys and buttons still held are let go on disconnect.
    """

    model = 'Keyboard and mouse'
    vendor = 'This computer'
    messages: tuple = ('Hotkey', 'Key', 'TypeText', 'MouseMove', 'MouseButton', 'MouseClick', 'Scroll')
    #: Key names for editors (single characters work too)
    keys: tuple = tuple(sorted(pyxelwidgets.message.KEY_NAMES))
    #: The designer connects it only when asked: trying pads would press keys in the browser
    auto_connect = False
    #: Nothing comes back from it (no feedback)
    receives = False

    def __init__(self, *, type_delay: float = 0.0, backend = None, **kwargs):
        """
        type_delay: float = 0.0, optional
            Seconds between typed characters, for programs that miss fast typing.
        backend: optional
            Does the pressing (default: pynput); tests pass a recorder.
        """
        super().__init__(**kwargs)
        self.type_delay = type_delay
        self.backend = backend
        #: Why actions may go nowhere (e.g. no macOS Accessibility permission), or None
        self.warning = None
        self._held_keys = []
        self._held_buttons = set()
        self._actions = None
        self._thread = None

    @classmethod
    def describe(cls) -> dict:
        info = super().describe()
        info['messages'] = list(cls.messages)
        info['keys'] = list(cls.keys)
        info['receives'] = cls.receives
        return info

    def connect(self) -> None:
        if self.backend is None:
            self.backend = _Pynput()
        super().connect()
        self.warning = _permission_warning()
        self._actions = queue.Queue()
        self._thread = threading.Thread(target = self._run, args = (self._actions,), name = f'{self.name}_actions', daemon = True)
        self._thread.start()

    def disconnect(self) -> None:
        actions, self._actions = self._actions, None
        if actions is not None:
            # Let go of what's held, then stop
            actions.put(None)
            if self._thread is not threading.current_thread():
                self._thread.join(timeout = 2.0)
        super().disconnect()

    def send(self, message) -> None:
        """Queue a message's action; returns at once."""
        if self._actions is not None:
            self._actions.put(message)

    def _run(self, actions: queue.Queue) -> None:
        while True:
            message = actions.get()
            if message is None:
                self._let_go()
                return
            try:
                self.perform(message)
            except Exception:
                traceback.print_exc()

    def perform(self, message) -> None:
        """Do what ``message`` says, now (``send`` queues it instead)."""
        backend = self.backend
        if isinstance(message, pyxelwidgets.message.Hotkey):
            keys = pyxelwidgets.message.parse_keys(message.keys)
            for key in keys:
                backend.press(key)
            for key in reversed(keys):
                backend.release(key)
        elif isinstance(message, pyxelwidgets.message.Key):
            keys = pyxelwidgets.message.parse_keys(message.keys)
            if _on(message.state):
                for key in keys:
                    if key not in self._held_keys:
                        backend.press(key)
                        self._held_keys.append(key)
            else:
                for key in reversed(keys):
                    if key in self._held_keys:
                        backend.release(key)
                        self._held_keys.remove(key)
        elif isinstance(message, pyxelwidgets.message.TypeText):
            backend.type(message.text, self.type_delay)
        elif isinstance(message, pyxelwidgets.message.MouseMove):
            if message.relative:
                backend.move_by(round(float(message.x)), -round(float(message.y)))
            else:
                width, height = backend.screen()
                x = min(1.0, max(0.0, float(message.x))) * (width - 1)
                y = (1.0 - min(1.0, max(0.0, float(message.y)))) * (height - 1)
                backend.move_to(round(x), round(y))
        elif isinstance(message, pyxelwidgets.message.MouseButton):
            if _on(message.state):
                if message.button not in self._held_buttons:
                    backend.button(message.button, True)
                    self._held_buttons.add(message.button)
            elif message.button in self._held_buttons:
                backend.button(message.button, False)
                self._held_buttons.discard(message.button)
        elif isinstance(message, pyxelwidgets.message.MouseClick):
            backend.click(message.button, int(message.count))
        elif isinstance(message, pyxelwidgets.message.Scroll):
            backend.scroll(round(float(message.dx)), round(float(message.dy)))

    def _let_go(self) -> None:
        for key in reversed(self._held_keys):
            self.backend.release(key)
        for button in self._held_buttons:
            self.backend.button(button, False)
        self._held_keys, self._held_buttons = [], set()

def _on(state) -> bool:
    return isinstance(state, (int, float)) and state > 0

class _Pynput:
    """Keyboard and mouse through pynput (macOS, Windows, Linux with X)."""

    def __init__(self) -> None:
        try:
            from pynput import keyboard, mouse
        except ImportError:
            raise ImportError('the keyboard and mouse output needs pynput: pip install "pyxelwidgets[desktop]"') from None
        self.keyboard = keyboard.Controller()
        self.mouse = mouse.Controller()
        self._keys = keyboard.Key
        self._key_code = keyboard.KeyCode
        self._buttons = mouse.Button

    def _key(self, name: str):
        if len(name) == 1:
            return self._key_code.from_char(name)
        key = getattr(self._keys, name, None)
        if key is None:
            raise ValueError(f'this system has no {name!r} key')
        return key

    def press(self, name: str) -> None:
        self.keyboard.press(self._key(name))

    def release(self, name: str) -> None:
        self.keyboard.release(self._key(name))

    def type(self, text: str, delay: float = 0.0) -> None:
        if not delay:
            self.keyboard.type(text)
            return
        import time
        for character in text:
            self.keyboard.type(character)
            time.sleep(delay)

    def move_to(self, x: int, y: int) -> None:
        self.mouse.position = (x, y)

    def move_by(self, dx: int, dy: int) -> None:
        self.mouse.move(dx, dy)

    def button(self, name: str, down: bool) -> None:
        (self.mouse.press if down else self.mouse.release)(getattr(self._buttons, name))

    def click(self, name: str, count: int) -> None:
        self.mouse.click(getattr(self._buttons, name), count)

    def scroll(self, dx: int, dy: int) -> None:
        self.mouse.scroll(dx, dy)

    def screen(self) -> tuple:
        return _screen_size()

def _screen_size() -> tuple:
    """(width, height) of the main screen in the pointer's coordinates."""
    system = platform.system()
    if system == 'Darwin':
        import Quartz
        bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        return int(bounds.size.width), int(bounds.size.height)
    if system == 'Windows':
        import ctypes
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    from Xlib import display
    screen = display.Display().screen()
    return screen.width_in_pixels, screen.height_in_pixels

def _permission_warning() -> str | None:
    """On macOS, whether this process may send keys and clicks (Accessibility)."""
    if platform.system() != 'Darwin':
        return None
    try:
        import HIServices
        if HIServices.AXIsProcessTrusted():
            return None
    except ImportError:
        return None
    return ('macOS hasn\'t allowed this app to control the computer: add the app running it (Terminal, your editor) '
            'under System Settings > Privacy & Security > Accessibility, then restart it')
