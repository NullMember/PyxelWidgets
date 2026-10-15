"""
Devices notice being unplugged and plugged back in. A subprocess with virtual
MIDI ports plays the device (not on Windows: rtmidi has no virtual ports there).
"""

import platform
import subprocess
import sys
import time

import pytest

rtmidi = pytest.importorskip('rtmidi')
if platform.system() == 'Windows':
    pytest.skip('needs virtual MIDI ports', allow_module_level = True)
if platform.system() == 'Linux' and not __import__('os').path.exists('/dev/snd/seq'):
    pytest.skip('needs the ALSA sequencer (/dev/snd/seq)', allow_module_level = True)

from pyxelwidgets import DeviceDisconnected, DeviceReconnected, Surface  # noqa: E402
from pyxelwidgets.devices.midi import MIDI  # noqa: E402

NAME = 'PyxelWidgets Hotplug'


class Plugged:
    """A process with virtual ports named NAME, as long as it's plugged in."""

    def __init__(self):
        self.process = None

    def plug(self):
        code = ('import rtmidi, sys, time\n'
                f'i = rtmidi.MidiIn(); i.open_virtual_port({NAME!r})\n'
                f'o = rtmidi.MidiOut(); o.open_virtual_port({NAME!r})\n'
                'print("ready", flush = True); sys.stdin.read()\n')
        self.process = subprocess.Popen([sys.executable, '-c', code], stdin = subprocess.PIPE, stdout = subprocess.PIPE, text = True)
        assert self.process.stdout.readline().strip() == 'ready'
        wait_for(lambda: NAME in MIDI.available_ports()[0])

    def unplug(self):
        self.process.stdin.close()
        self.process.wait(5)
        wait_for(lambda: NAME not in MIDI.available_ports()[0])


def wait_for(condition, timeout = 5.0):
    end = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < end, 'timed out'
        time.sleep(0.05)


class Device(MIDI):
    ports = (NAME,)
    connects = 0

    def on_connect(self):
        self.connects += 1


@pytest.fixture
def plugged():
    plugged = Plugged()
    yield plugged
    if plugged.process is not None and plugged.process.poll() is None:
        plugged.unplug()


def test_unplug_and_plug_back(plugged):
    plugged.plug()
    device = Device()
    device.connect()
    events = []
    device.on(DeviceDisconnected, events.append)
    device.on(DeviceReconnected, events.append)
    assert device.connected and device.connects == 1 and not device.check()
    plugged.unplug()
    assert device.check() and not device.connected and device.lost
    assert not device.check()
    plugged.plug()
    assert device.check() and device.connected and not device.lost and device.connects == 2
    assert [type(event) for event in events] == [DeviceDisconnected, DeviceReconnected]
    device.close()


def test_connects_when_plugged_in_later(plugged):
    device = Device()
    device.connect()
    assert not device.connected and device.lost
    surface = Surface(1, 1)
    surface.add_device(device)
    assert surface.check_devices() == []
    plugged.plug()
    assert surface.check_devices() == [device] and device.connected


def test_disconnected_on_purpose_stays_disconnected(plugged):
    plugged.plug()
    device = Device()
    device.connect()
    device.disconnect()
    assert not device.lost and not device.check() and not device.connected


SCENARIO = """
import subprocess, sys, threading, time
from pyxelwidgets.devices.midi import MIDI

class Device(MIDI):
    ports = (%r,)

# Like the designer: a device opened on the main thread, which then only serves web pages;
# checks run on a thread of their own and must see the device plugged in
plug = "import rtmidi, sys; i = rtmidi.MidiIn(); i.open_virtual_port(%r); o = rtmidi.MidiOut(); o.open_virtual_port(%r); print('ready', flush = True); sys.stdin.read()"
device = Device()
device.connect()
assert device.lost                     # not plugged in yet
process = subprocess.Popen([sys.executable, '-c', plug], stdin = subprocess.PIPE, stdout = subprocess.PIPE, text = True)
process.stdout.readline()

def watch(result):
    end = time.monotonic() + 5
    while time.monotonic() < end and not device.check():
        time.sleep(0.2)
    result.append(device.connected)
result = []
thread = threading.Thread(target = watch, args = (result,))
thread.start()
thread.join()
process.stdin.close()
process.wait()
print('noticed' if result[0] else 'missed')
"""


def test_checks_from_another_thread():
    """CoreMIDI only tells one thread about ports appearing; the designer checks on another one."""
    code = SCENARIO % (NAME, NAME, NAME)
    out = subprocess.run([sys.executable, '-c', code], capture_output = True, text = True, timeout = 30,
                         env = {**__import__('os').environ, 'PYTHONPATH': __import__('os').pathsep.join(sys.path)})
    assert out.stdout.strip() == 'noticed', out.stdout + out.stderr
