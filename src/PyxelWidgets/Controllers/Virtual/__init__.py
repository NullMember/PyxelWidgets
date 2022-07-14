import tkinter
import PyxelWidgets.Controllers
import PyxelWidgets.Utils.Pixel
import PyxelWidgets.Utils.Rectangle

class Virtual(PyxelWidgets.Controllers.Controller):
    def __init__(self, columns = 8, rows = 8, **kwargs):
        super().__init__(width = columns, height = rows, **kwargs)
        self.gui = GUI(columns, rows, self.process)

    def sendPixel(self, x: int, y: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        self.gui.draw_button(x, y, f"#{pixel.r:02x}{pixel.g:02x}{pixel.b:02x}")
    
    def process(self, x, y, value):
        self.setButton(x, y, value)
    
    def close(self):
        if not self.gui.destroyed:
            self.gui.destroy_everything()
        super().close()
    
    def updateOne(self, x: int, y: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        super().updateOne(x, y, pixel)
        self.gui.update()
    
    def updateRow(self, y: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        super().updateRow(y, pixel)
        self.gui.update()
    
    def updateColumn(self, x: int, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        super().updateColumn(x, pixel)
        self.gui.update()
    
    def updateArea(self, rect: PyxelWidgets.Utils.Rectangle.Rectangle2D, pixel: PyxelWidgets.Utils.Pixel.Pixel):
        super().updateArea(rect, pixel)
        self.gui.update()
    
    def update(self, data: tuple):
        super().update(data)
        self.gui.update()

class GUI(tkinter.Tk):
    def __init__(self, columns, rows, callback) -> None:
        super().__init__()
        self.title("PyxelWidgets Virtual Grid Controller")
        self.protocol("WM_DELETE_WINDOW", self.destroy_everything)

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

        for x in range(self.button_column):
            for y in range(self.button_row):
                self.draw_button(x, y, "#000000")
        
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
        if column < 0 or column > self.button_column or row < 0 or row > self.button_row:
            return
        
        row = (self.button_row - 1) - row
        
        x_start = round((self.button_width * column) + (self.button_gap * column) + (self.button_gap / 2))
        y_start = round((self.button_height * row) + (self.button_gap * row) + (self.button_gap / 2))
        x_end = x_start + self.button_width
        y_end = y_start + self.button_height

        self.canvas.create_rectangle(x_start, y_start, x_end, y_end, fill = color, outline = "")

    def destroy_everything(self):
        self.destroy()
        self.destroyed = True