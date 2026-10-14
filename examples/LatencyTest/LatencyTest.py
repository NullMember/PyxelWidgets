"""Latency test: press a pad in a running designer and time the MIDI that comes back.

The designer (on this computer or another one, e.g. a Raspberry Pi reached through
an SSH tunnel) gets a test layout whose first output is the one it already has
(e.g. a Bluetooth or network MIDI output), plus a probe Button sending NoteOn 127
on channel 16. This script presses the probe through the designer's API and waits
for that note on a MIDI input of this computer.

    python examples/LatencyTest/LatencyTest.py --url http://127.0.0.1:8766 --port "NullMIDI Bluetooth"
    python examples/LatencyTest/LatencyTest.py --layout light       # only the probe
    python examples/LatencyTest/LatencyTest.py --play               # sequencers send MIDI meanwhile
    python examples/LatencyTest/LatencyTest.py --write heavy.json   # just write the heavy layout

"press → MIDI" counts from sending the HTTP request; "estimated" takes away half
of that request's round trip (the way there), which is what a pad on a device
plugged into that computer would see, give or take its own MIDI input.
The designer's layout is put back at the end.
"""

import argparse
import json
import random
import statistics
import threading
import time
import urllib.request

PROBE = (8, 8)
PROBE_NOTE = 127
PROBE_CHANNEL = 16

def widget(type, name, x, y, width, height, **options):
    entry = {'type': type, 'name': name, 'x': x, 'y': y, 'width': width, 'height': height, 'options': options}
    return entry

def notes(name, channel, on = 'NoteOn', off = 'NoteOff'):
    return [{'widget': name, 'on': on, 'output': 'out',
             'message': {'type': 'NoteOn', 'note': {'source': 'note'}, 'velocity': {'source': 'velocity'}, 'channel': channel}},
            {'widget': name, 'on': off, 'output': 'out',
             'message': {'type': 'NoteOff', 'note': {'source': 'note'}, 'velocity': 0, 'channel': channel}}]

def probe_rules():
    return [{'widget': 'probe', 'on': 'Pressed', 'output': 'out',
             'message': {'type': 'NoteOn', 'note': PROBE_NOTE, 'velocity': 127, 'channel': PROBE_CHANNEL}},
            {'widget': 'probe', 'on': 'Released', 'output': 'out',
             'message': {'type': 'NoteOff', 'note': PROBE_NOTE, 'velocity': 0, 'channel': PROBE_CHANNEL}}]

def layout(output: dict, heavy: bool = True) -> dict:
    """The test layout: an 18x18 surface (four Launchpads' worth) full of playing widgets, or only the probe."""
    output = dict(output, name = 'out')
    probe = widget('Button', 'probe', *PROBE, 1, 1, active_color = '#ffffff')
    if not heavy:
        return {'format': 'pyxelwidgets.layout', 'version': 6, 'surface': {'width': 9, 'height': 9},
                'transport': {'bpm': 120, 'signature': [4, 4]}, 'devices': [], 'outputs': [output],
                'widgets': [probe], 'mappings': probe_rules(), 'links': []}
    widgets = [
        widget('Sequencer', 'seq1', 0, 0, 8, 8, steps = 64, rate = '1/16', gate_random = 0.3),
        dict(widget('Meter', 'meter', 8, 0, 1, 8, falloff = 2.0), animation = {'type': 'Pulse', 'options': {'rate': '1/4'}}),
        widget('Text', 'step_text', 0, 8, 8, 1, text = 'STEP {seq1.step + 1} OF {seq1.steps}'),
        probe,
        widget('Automaton', 'life', 9, 0, 9, 9, rate = '1/16', max_notes = 6),
        widget('Euclidean', 'euclid', 0, 9, 8, 8, rate = '1/16'),
        widget('Fader', 'fader', 8, 9, 1, 8, slew = 0.25),
        widget('Text', 'title', 0, 17, 9, 1, text = 'PYXELWIDGETS HEAVY LAYOUT LATENCY TEST', speed = 12.0),
        widget('Sequencer', 'seq2', 9, 9, 9, 4, rate = '1/8', direction = 'PingPong', swing = 60.0),
        widget('Knob', 'knob', 9, 13, 4, 4),
        widget('XY', 'xy', 13, 13, 4, 4),
        widget('Meter', 'meter2', 17, 13, 1, 4, falloff = 1.0),
        dict(widget('Text', 'tempo', 9, 17, 9, 1, text = 'LIFE {life.rule}', speed = 6.0),
             animation = {'type': 'Blink', 'options': {'rate': '1/8'}}),
    ]
    mappings = (notes('seq1', 1, 'StepPlayed', 'StepEnded') + notes('seq2', 2, 'StepPlayed', 'StepEnded')
                + notes('life', 3) + notes('euclid', 10) + probe_rules()
                + [{'widget': 'fader', 'on': 'Changed', 'output': 'out',
                    'message': {'type': 'ControlChange', 'control': 1, 'value': {'source': 'value'}, 'channel': 4}},
                   {'widget': 'knob', 'on': 'Changed', 'output': 'out',
                    'message': {'type': 'ControlChange', 'control': 2, 'value': {'source': 'value'}, 'channel': 4}}])
    links = [
        {'widget': 'seq1', 'on': 'StepPlayed', 'target': 'meter', 'option': 'value', 'value': '{velocity / 127}'},
        {'widget': 'seq1', 'on': 'StepPlayed', 'target': 'fader', 'option': 'value', 'value': '{(step % 8) / 7}'},
        {'widget': 'life', 'on': 'NoteOn', 'target': 'knob', 'option': 'value', 'value': '{(note % 12) / 11}'},
        {'widget': 'euclid', 'on': 'NoteOn', 'target': 'meter2', 'option': 'value', 'value': '{velocity / 127}'},
        {'widget': 'seq2', 'on': 'StepPlayed', 'target': 'xy', 'option': 'x_color',
         'value': {'choose': ['#00ffff', '#ff00ff', '#ffff00', '#ffffff'], 'by': 'step'}},
    ]
    return {'format': 'pyxelwidgets.layout', 'version': 6, 'surface': {'width': 18, 'height': 18},
            'transport': {'bpm': 140, 'signature': [4, 4]}, 'devices': [], 'outputs': [output],
            'widgets': widgets, 'mappings': mappings, 'links': links}

# Pads pressed after loading so the sequencers and the Euclidean rows have something to play
SEEDS = ([(x, y) for x in range(8) for y in range(8) if (x * 3 + y * 5) % 4 == 0]
         + [(x, y) for x in range(9, 18) for y in range(9, 13) if (x + y) % 3 == 0]
         + [(4, 9), (2, 10), (6, 11), (4, 12), (7, 13), (2, 14), (5, 15), (3, 16)])

class Designer:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip('/')

    def call(self, method: str, path: str, body = None) -> dict:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.url + path, data = data, method = method,
                                         headers = {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout = 30) as response:
            return json.loads(response.read() or b'{}')

    def press(self, x: int, y: int, velocity: float) -> None:
        self.call('POST', '/api/input', {'x': x, 'y': y, 'velocity': velocity})

class Poller(threading.Thread):
    """Asks for frames like an open designer page does (Edit/Try mode), timing each answer."""

    def __init__(self, designer: Designer, fps: float) -> None:
        super().__init__(daemon = True)
        self.designer, self.period, self.times, self.stopping = designer, 1 / fps, [], False

    def run(self) -> None:
        since = 0
        while not self.stopping:
            start = time.perf_counter()
            try:
                frame = self.designer.call('GET', f'/api/frame?since={since}')
                since = max((event['id'] for event in frame.get('events', [])), default = since)
            except OSError:
                pass
            took = time.perf_counter() - start
            self.times.append(took)
            time.sleep(max(0.0, self.period - took))

def summary(name: str, values: list) -> str:
    if not values:
        return f'{name:>22}: no samples'
    values = sorted(value * 1000 for value in values)
    pick = lambda q: values[min(len(values) - 1, int(q * len(values)))]
    return (f'{name:>22}: median {statistics.median(values):6.1f}  p90 {pick(0.9):6.1f}  p99 {pick(0.99):6.1f}'
            f'  min {values[0]:6.1f}  max {values[-1]:6.1f} ms  (n={len(values)})')

def main() -> None:
    parser = argparse.ArgumentParser(description = __doc__.split('\n\n')[0])
    parser.add_argument('--url', default = 'http://127.0.0.1:8766', help = 'the designer')
    parser.add_argument('--port', default = 'NullMIDI Bluetooth', help = 'MIDI input on this computer (part of its name)')
    parser.add_argument('--layout', choices = ('heavy', 'light'), default = 'heavy')
    parser.add_argument('--play', action = 'store_true', help = 'play the transport during the test')
    parser.add_argument('--count', type = int, default = 200, help = 'probe presses')
    parser.add_argument('--fps', type = float, default = 30.0, help = 'frames asked for meanwhile (0: none)')
    parser.add_argument('--write', metavar = 'FILE', help = 'write the heavy layout (with a MIDI port output) and stop')
    arguments = parser.parse_args()

    if arguments.write:
        output = {'name': 'out', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets Latency', 'options': {}}
        with open(arguments.write, 'w') as file:
            json.dump(layout(output), file, indent = 2)
        return

    import rtmidi
    midi = rtmidi.MidiIn()
    ports = [index for index, name in enumerate(midi.get_ports()) if arguments.port.lower() in name.lower()]
    if not ports:
        raise SystemExit(f'no MIDI input like {arguments.port!r}: {midi.get_ports()}')
    arrived = {}  # (kind, note) -> time
    signal = threading.Condition()
    traffic = [0]
    steps = []  # arrival of each of seq1's steps (its NoteOns on channel 1)
    def received(event, data = None) -> None:
        message, _ = event
        now = time.perf_counter()
        traffic[0] += 1
        if len(message) == 3 and message[0] == 0x90 and message[2] > 0 and (not steps or now - steps[-1] > 0.03):
            steps.append(now)
        if len(message) == 3 and message[0] & 0x0F == PROBE_CHANNEL - 1 and message[1] == PROBE_NOTE:
            kind = 'on' if message[0] & 0xF0 == 0x90 and message[2] > 0 else 'off'
            with signal:
                arrived[kind] = now
                signal.notify_all()
    midi.set_callback(received)
    midi.open_port(ports[0])

    designer = Designer(arguments.url)
    original = designer.call('GET', '/api/layout')['layout']
    if not original.get('outputs'):
        raise SystemExit('the designer\'s layout has no output to test (add the Bluetooth/network output first)')
    test = layout(original['outputs'][0], arguments.layout == 'heavy')
    poller = None
    try:
        answer = designer.call('PUT', '/api/layout', test)
        if not answer.get('ok', True):
            raise SystemExit(f'layout refused: {answer.get("error")}')
        for _ in range(100):
            status = designer.call('GET', '/api/frame?since=0')['hardware']['outputs'][0]
            if status['connected']:
                break
            time.sleep(0.1)
        print(f'output: {status}')
        if arguments.layout == 'heavy':
            for x, y in SEEDS:
                designer.press(x, y, 1.0)
                designer.press(x, y, 0.0)
        if arguments.play:
            designer.call('POST', '/api/play', {'playing': True})
        if arguments.fps > 0:
            poller = Poller(designer, arguments.fps)
            poller.start()
        time.sleep(1.0)

        total, estimated, round_trips, lost = [], [], [], 0
        for index in range(arguments.count):
            for kind, velocity in (('on', 1.0), ('off', 0.0)):
                with signal:
                    arrived.pop(kind, None)
                start = time.perf_counter()
                designer.press(*PROBE, velocity)
                answered = time.perf_counter()
                with signal:
                    signal.wait_for(lambda: kind in arrived, timeout = 2.0)
                    came = arrived.get(kind)
                if came is None:
                    lost += 1
                    continue
                trip = answered - start
                total.append(came - start)
                round_trips.append(trip)
                estimated.append(max(0.0, came - start - trip / 2))
                # Not in step with the frames, the transport or Bluetooth's connection interval
                time.sleep(random.uniform(0.03, 0.12))
            if (index + 1) % 50 == 0:
                print(f'{index + 1}/{arguments.count}…')

        print(f'\nlayout {arguments.layout}, {"playing" if arguments.play else "stopped"}, '
              f'frames at {arguments.fps:g} fps, {traffic[0]} MIDI messages received')
        print(summary('press → MIDI', total))
        print(summary('HTTP round trip', round_trips))
        print(summary('estimated (– trip/2)', estimated))
        if poller is not None:
            print(summary('frame request', poller.times))
        if arguments.play and len(steps) > 10:
            # seq1 plays on a grid of 1/16 notes: how far each arrival is from it (the median one at 0)
            period = 60 / test['transport']['bpm'] / 4
            phases = [((when - steps[0]) / period) % 1 for when in steps]
            middle = statistics.median((phase + 0.5) % 1 for phase in phases)
            offsets = [abs((((phase + 0.5) % 1) - middle) * period) for phase in phases]
            print(summary('seq1 timing jitter', offsets))
        if lost:
            print(f'{lost} probe messages never arrived')
    finally:
        if poller is not None:
            poller.stopping = True
            poller.join()
        if arguments.play:
            designer.call('POST', '/api/play', {'playing': False})
        designer.call('PUT', '/api/layout', original)
        midi.close_port()

if __name__ == '__main__':
    main()
