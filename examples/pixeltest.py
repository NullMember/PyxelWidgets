from PyxelWidgets.Controller.MIDI.Launchpad.MK3 import *
from PyxelWidgets.Helper import *
from random import randint
import time

controller = MK3('Input', 'Input', Model.Mini)
controller.connect()
#pixels = [Pixel(randint(63, 255), randint(63, 255), randint(63, 255), randint(63, 255)) for i in range(8)]
pixels = [
    Pixel(0, 0, 0),
    Pixel(0, 0, 0),
    Pixel(255, 0, 0, randint(63, 255)),
    Pixel(255, 255, 0, randint(63, 255)),
    Pixel(0, 255, 0, randint(63, 255)),
    Pixel(0, 255, 255, randint(63, 255)),
    Pixel(0, 0, 255, randint(63, 255)),
    Pixel(255, 0, 255, randint(63, 255)),
    Pixel(255, 255, 255, randint(63, 255)),
    Pixel(randint(63, 255), randint(63, 255), randint(63, 255), randint(63, 255)),
]

for y in range(1, 10):
    for x in range(1, 10):
        if x == 1 and not y == 1:
            controller.updateOne(x, y, [pixels[y].r, pixels[y].g, pixels[y].b])
        elif y == 1 and not x == 1:
            controller.updateOne(x, y, [pixels[x].r, pixels[x].g, pixels[x].b])
        else:
            pixel = pixels[x] + pixels[y]
            controller.updateOne(x, y, [pixel.r, pixel.g, pixel.b])
            print(pixel, end = ';')
    print()

while True:
    try:
        time.sleep(1)
    except:
        controller.disconnect()
        break
