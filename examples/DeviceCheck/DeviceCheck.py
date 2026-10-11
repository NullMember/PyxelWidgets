"""
Checks a hardware device: shows a test pattern and prints every pad and control
event. Pressed pads light up white while held.

    python DeviceCheck.py                    # lists the device classes
    python DeviceCheck.py LaunchpadMiniMK3   # finds the device by its port name
    python DeviceCheck.py LaunchpadMiniMK3 "LPMiniMK3 MIDI" "LPMiniMK3 MIDI"   # explicit ports

Expected on a 9x9 Launchpad: bottom left pad red, top right round button blue,
a rainbow over the 8x8 pads, and pressing a pad prints its x, y from (0, 0) at
the bottom left.
"""

import sys
import time

import pyxelwidgets.devices.akai
import pyxelwidgets.devices.ableton
import pyxelwidgets.devices.novation
import pyxelwidgets.devices.presonus
from pyxelwidgets import buffer
from pyxelwidgets.color import Color, Colors
from pyxelwidgets.devices.midi import MIDI
from pyxelwidgets.events import ControlEvent, PadEvent, PadPressed, PadReleased

DEVICES = {cls.__name__: cls for module in (pyxelwidgets.devices.novation, pyxelwidgets.devices.akai,
                                            pyxelwidgets.devices.ableton, pyxelwidgets.devices.presonus)
           for cls in vars(module).values() if isinstance(cls, type) and issubclass(cls, MIDI) and cls.__module__.startswith(module.__name__)}

def pattern(width, height):
    frame = buffer.new(width, height, Colors.Black)
    for x in range(min(width, 8)):
        for y in range(min(height, 8)):
            hue = (x + y) / 14
            frame[x, y] = Color(255 * max(0, 1 - abs(hue * 3 - 0.5) * 2), 255 * max(0, 1 - abs(hue * 3 - 1.5) * 2),
                                255 * max(0, 1 - abs(hue * 3 - 2.5) * 2))
    frame[0, 0] = Colors.Red
    frame[width - 1, height - 1] = Colors.Blue
    return frame

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in DEVICES:
        print('Devices:', ', '.join(sorted(DEVICES)))
        print('MIDI ports:', MIDI.available_ports())
        return
    cls = DEVICES[sys.argv[1]]
    if len(sys.argv) >= 4:
        device = cls()
        device.connect(sys.argv[2], sys.argv[3])
    else:
        try:
            device = cls.find()
        except LookupError as error:
            print(error)
            print('MIDI ports:', MIDI.available_ports())
            return
    print(f'Connected {cls.__name__} ({device.width}x{device.height}); Ctrl+C to quit')
    base = pattern(device.width, device.height)
    frame = base.copy()

    def on_pad(event):
        print(f'{type(event).__name__:16} x={event.x} y={event.y} velocity={event.velocity:.2f}')
        if isinstance(event, PadPressed):
            frame[event.x, event.y] = Colors.White
        elif isinstance(event, PadReleased):
            frame[event.x, event.y] = base[event.x, event.y]

    device.on(PadEvent, on_pad)
    device.on(ControlEvent, lambda event: print(event))
    try:
        while True:
            device.show(frame)
            time.sleep(1 / 60)
    except KeyboardInterrupt:
        pass
    finally:
        device.close()

if __name__ == '__main__':
    main()
