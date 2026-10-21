"""Closing a MIDI input while messages keep coming (a DAW's feedback) doesn't hang: it used to deadlock in rtmidi."""

import subprocess
import sys
import textwrap

import pytest

SCRIPT = textwrap.dedent('''
    import threading, time, rtmidi
    from pyxelwidgets.devices.midi_port import MidiPort
    for attempt in range(5):
        port = MidiPort()
        port.connect_virtual('PyxelWidgets close test')
        time.sleep(0.1)
        out = rtmidi.MidiOut()
        out.open_port(out.get_ports().index('PyxelWidgets close test'))
        stop = threading.Event()
        def flood():
            while not stop.is_set():
                out.send_message([0xB0, 1, 64])
        thread = threading.Thread(target = flood, daemon = True)
        thread.start()
        time.sleep(0.05)
        port.close()
        stop.set()
        thread.join()
        out.close_port()
    print('closed')
''')


def test_closing_an_input_flooded_with_messages():
    pytest.importorskip('rtmidi')
    probe = subprocess.run([sys.executable, '-c', 'import rtmidi; m = rtmidi.MidiIn(); m.open_virtual_port("probe"); m.close_port()'],
                           capture_output = True, timeout = 30)
    if probe.returncode != 0:
        pytest.skip('no virtual MIDI ports here')
    try:
        result = subprocess.run([sys.executable, '-c', SCRIPT], capture_output = True, text = True, timeout = 60)
    except subprocess.TimeoutExpired:
        pytest.fail('closing a flooded MIDI input hung')
    assert 'closed' in result.stdout, result.stderr[-2000:]
