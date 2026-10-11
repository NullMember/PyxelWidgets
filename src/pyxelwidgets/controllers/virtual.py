import signal
import threading
import tkinter
import pyxelwidgets.controllers
import pyxelwidgets.color
import pyxelwidgets.rectangle

class Virtual(pyxelwidgets.controllers.Controller):
    def __init__(self, columns = 8, rows = 8, **kwargs):
        super().__init__(width = columns, height = rows, **kwargs)
        self.gui = GUI(columns, rows, self.process, on_close = self.close)

    def send_pixel(self, x: int, y: int, pixel: pyxelwidgets.color.Color):
        r, g, b = pixel.argb
        self.gui.draw_button(x, y, f"#{r:02x}{g:02x}{b:02x}")
    
    def process(self, x, y, value):
        # Clicks in the canvas margin map outside the grid
        if 0 <= x < self.rect.w and 0 <= y < self.rect.h:
            self.set_button(x, y, value)
    
    def close(self):
        if not self.gui.destroyed:
            self.gui.destroy_everything()
        super().close()
    
    def update_area(self, rect: pyxelwidgets.rectangle.Rectangle2D, pixel: pyxelwidgets.color.Color):
        super().update_area(rect, pixel)
        self._process_events()
    
    def update(self, data: tuple):
        super().update(data)
        self._process_events()

    def _process_events(self):
        # Closing the window inside gui.update() closes this controller
        if not self.gui.destroyed:
            self.gui.update()

class GUI(tkinter.Tk):
    def __init__(self, columns, rows, callback, on_close = None) -> None:
        super().__init__()
        # Tk (seen with Tk 9 on macOS) replaces the SIGINT handler at C level,
        # so Ctrl+C exits immediately without cleanup; reinstall Python's handler
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, signal.getsignal(signal.SIGINT))
        self.title("PyxelWidgets Virtual Grid Controller")
        self.protocol("WM_DELETE_WINDOW", on_close or self.destroy_everything)

        self.button_column = columns
        self.button_row = rows
        self.button_width = 80
        self.button_height = 80
        self.button_gap = 10

        self.canvas_width = (self.button_width * self.button_column) + (self.button_gap * self.button_column)
        self.canvas_height = (self.button_height * self.button_row) + (self.button_gap * self.button_row)

        self.canvas = tkinter.Canvas(self, width = self.canvas_width, height = self.canvas_height)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress>", self.button_callback)
        self.canvas.bind("<ButtonRelease>", self.button_callback)

        self.buttons = {}
        for x in range(self.button_column):
            for y in range(self.button_row):
                self.buttons[x, y] = self.create_button(x, y)
        
        self.callback = callback
        self.destroyed = False

    def button_callback(self, event: tkinter.Event):
        column = int(event.x // (self.button_width + self.button_gap))
        row = (self.button_row - 1) - int(event.y // (self.button_height + self.button_gap))
        if event.type == tkinter.EventType.ButtonPress:
            self.callback(column, row, 1.0)
        elif event.type == tkinter.EventType.ButtonRelease:
            self.callback(column, row, 0.0)

    def draw_button(self, column, row, color):
        if (column, row) in self.buttons:
            self.canvas.itemconfigure(self.buttons[column, row], fill = color)

    def create_button(self, column, row):
        row = (self.button_row - 1) - row
        
        x_start = round((self.button_width * column) + (self.button_gap * column) + (self.button_gap / 2))
        y_start = round((self.button_height * row) + (self.button_gap * row) + (self.button_gap / 2))
        x_end = x_start + self.button_width
        y_end = y_start + self.button_height

        return self.canvas.create_rectangle(x_start, y_start, x_end, y_end, fill = "#000000", outline = "")

    def destroy_everything(self):
        self.destroy()
        self.destroyed = True