"""
Records how the pre-phase-3 MIDI drivers behave, as a golden reference for the
rewritten devices: connect/disconnect messages, output for a set of frames,
and decoding of every note/CC message. Run once against the old code:

    PYTHONPATH=src python tests/golden/record.py
"""

import json
import pathlib
import random

import numpy
import rtmidi.midiutil

from pyxelwidgets import buffer
from pyxelwidgets.color import Color, Colors
from pyxelwidgets.controllers import Controller
from pyxelwidgets.controllers.midi.ableton import Push2
from pyxelwidgets.controllers.midi.akai import apc, apc40
from pyxelwidgets.controllers.midi.novation import launch_control, launchkey, launchpad
from pyxelwidgets.controllers.midi.presonus import ATOM

from frames import frames

DRIVERS = {
    'LaunchpadMK1': lambda: launchpad.MK1(),
    'LaunchpadMK2': lambda: launchpad.MK2(),
    'LaunchpadX': lambda: launchpad.MK3(launchpad.MK3.Model.X),
    'LaunchpadMiniMK3': lambda: launchpad.MK3(launchpad.MK3.Model.Mini),
    'LaunchpadProMK3': lambda: launchpad.MK3(launchpad.MK3.Model.Pro),
    'LaunchpadPro': lambda: launchpad.Pro(),
    'LaunchkeyMK1': lambda: launchkey.MK1(),
    'LaunchkeyMK2': lambda: launchkey.MK2(),
    'LaunchkeyMK3': lambda: launchkey.MK3(),
    'LaunchControl': lambda: launch_control.MK1(),
    'LaunchControlXL': lambda: launch_control.XL(),
    'APCMini': lambda: apc.Mini(),
    'APC40MK2': lambda: apc40.MK2(),
    'Push2': lambda: Push2(),
    'ATOM': lambda: ATOM(),
}


class Port:
    def __init__(self, log):
        self.log = log

    def send_message(self, message):
        self.log.append([int(b) for b in message])

    def ignore_types(self, **_):
        pass

    def set_callback(self, _):
        pass

    def close_port(self):
        pass


def record_output(make):
    sent = []
    original = (rtmidi.midiutil.open_midiinput, rtmidi.midiutil.open_midioutput)
    rtmidi.midiutil.open_midiinput = lambda port, **_: (Port([]), port)
    rtmidi.midiutil.open_midioutput = lambda port, **_: (Port(sent), port)
    try:
        driver = make()
        driver.connect('in', 'out')
        result = {'connect': list(sent), 'frames': []}
        for frame in frames(driver.rect.w, driver.rect.h):
            sent.clear()
            driver.update((driver.rect.origin, frame))
            result['frames'].append(list(sent))
        sent.clear()
        driver.disconnect()
        result['disconnect'] = list(sent)
    finally:
        rtmidi.midiutil.open_midiinput, rtmidi.midiutil.open_midioutput = original
    return result


def record_input(make, setup = None):
    driver = make()
    if setup:
        setup(driver)
    seen = []
    driver.set_button = lambda x, y, value: seen.append(['pad', int(x), int(y), round(float(value), 6)])
    driver.set_custom = lambda action, name, value: seen.append(['control', name, action.name, round(float(value), 6)])
    decoded = {}
    for status in [0x80, 0x90, 0xB0]:
        for channel in range(16):
            for data1 in range(128):
                for data2 in (0, 1, 63, 64, 65, 127):
                    message = [status | channel, data1, data2]
                    seen.clear()
                    try:
                        driver.process_midi((list(message), 0.0), None)
                    except Exception as error:
                        seen.append(['error', type(error).__name__])
                    if seen:
                        decoded[' '.join(f'{b:02X}' for b in message)] = list(seen)
    return decoded


def main():
    golden = {}
    for name, make in DRIVERS.items():
        golden[name] = {'output': record_output(make), 'input': record_input(make)}
    golden['LaunchControlXL']['input_factory_template'] = record_input(
        DRIVERS['LaunchControlXL'], lambda d: setattr(d, 'current_template', launch_control.XL.Templates.Factory_7))
    path = pathlib.Path(__file__).with_name('devices.json')
    path.write_text(json.dumps(golden, separators = (',', ':')))
    for name, data in golden.items():
        errors = sum(1 for events in data['input'].values() if events[0][0] == 'error')
        print(f"{name:18} connect={len(data['output']['connect']):3} frames={sum(map(len, data['output']['frames'])):5} "
              f"decoded={len(data['input']):5} errors={errors}")


if __name__ == '__main__':
    main()
