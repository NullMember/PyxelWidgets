"""The PyxelWidgets DAW protocol: the DAW output, and the DAW scripts run against stand-ins of their DAWs."""

import shutil
import subprocess
import sys
import types

import pytest

from pyxelwidgets import daws
from pyxelwidgets.devices.daw import BUTTONS, DAW, FADERS, text_sysex
from pyxelwidgets.events import MessageReceived
from pyxelwidgets.message import Command, NoteOn


class Port:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(list(message))

    def close_port(self):
        pass


def output():
    daw = DAW()
    daw._midi_output = Port()
    daw.connected = True
    received = []
    daw.on(MessageReceived, lambda event: received.append(event.message))
    return daw, received


def test_commands_go_out_as_notes_and_controls_and_come_back():
    daw, received = output()
    daw.send(Command('Play'))
    daw.send(Command('Play', 0.0))
    daw.send(Command('Volume 3', 0.5))
    daw.send(Command('Nope'))
    daw.send(NoteOn(60, 100, channel = 2))      # plain MIDI passes through
    assert daw._midi_output.messages == [[0x9F, BUTTONS['Play'], 127], [0x9F, BUTTONS['Play'], 0], [0xBF, FADERS['Volume 3'], 64], [0x91, 60, 100]]
    daw.decode([0x9F, BUTTONS['Mute 2'], 127])
    daw.decode([0xBF, FADERS['Macro 1'], 127])
    daw.decode([0xF0, *text_sysex('Track Name 1', 'Drums'), 0xF7])
    daw.decode([0xF0, *text_sysex('DAW', 'REAPER'), 0xF7])
    assert received == [Command('Mute 2', 1.0), Command('Macro 1', 1.0), Command('Track Name 1', 'Drums'), Command('DAW', 'REAPER')]
    assert daw.status_text == 'talking to REAPER'
    daw.on_connect()
    assert daw._midi_output.messages[-1] == [0xF0, 0x7D, 0x50, 0x57, 0x7F, 0xF7]
    assert {command['kind'] for command in DAW.describe()['commands']} == {'button', 'fader', 'display'}


def test_scripts_carry_the_protocol(tmp_path):
    for name in daws.DAWS:
        written = daws.install(name, tmp_path / name)
        text = written[0].read_text()
        assert '__PROTOCOL__' not in text and "Macro Page Right" in text
    assert (tmp_path / 'cubase' / 'pyxelwidgets' / 'daw' / 'pyxelwidgets_daw.js').exists()
    assert (tmp_path / 'live' / 'PyxelWidgets' / '__init__.py').exists()
    with pytest.raises(ValueError):
        daws.files('logic')


# Ableton Live: the remote script with Live's API stood in for

class Parameter:
    def __init__(self, name, value = 0.0, low = 0.0, high = 1.0):
        self.name, self.value, self.min, self.max, self.is_enabled = name, value, low, high, True

    def __str__(self):
        return f'{self.value:.2f}'


class Track:
    def __init__(self, name):
        self.name, self.mute, self.solo, self.arm, self.can_be_armed = name, False, False, False, True
        self.mixer_device = types.SimpleNamespace(volume = Parameter('Volume', 0.85), panning = Parameter('Pan', 0.0, -1.0, 1.0),
                                                  sends = [Parameter('A'), Parameter('B')])
        self.devices = [types.SimpleNamespace(name = 'EQ Eight', parameters = [Parameter('Device On', 1.0)] + [Parameter(f'P{i}') for i in range(12)])]
        self.view = types.SimpleNamespace(selected_device = self.devices[0])
        self.clip_slots = []

    def stop_all_clips(self):
        pass


class Song:
    def __init__(self):
        self.visible_tracks = [Track(name) for name in ('Drums', 'Bass', 'Keys')]
        self.master_track = Track('Master')
        self.is_playing = self.record_mode = self.loop = self.metronome = self.session_automation_record = False
        self.scenes = []
        self.view = types.SimpleNamespace(selected_track = self.visible_tracks[0], selected_scene = None, select_device = lambda device: None)
        self.can_undo = self.can_redo = False

    def continue_playing(self):
        self.is_playing = True

    def stop_playing(self):
        self.is_playing = False


@pytest.fixture
def live(monkeypatch):
    forwarded = []
    class ControlSurface:
        def __init__(self, c_instance):
            self._c_instance = c_instance
            self.sent = []
        def build_midi_map(self, handle):
            pass
        def update_display(self):
            pass
        def _send_midi(self, message):
            self.sent.append(list(message))
    live_module = types.ModuleType('Live')
    live_module.MidiMap = types.SimpleNamespace(forward_midi_note = lambda *args: forwarded.append(('note', args[2], args[3])),
                                                forward_midi_cc = lambda *args: forwarded.append(('cc', args[2], args[3])))
    framework = types.ModuleType('_Framework')
    surface_module = types.ModuleType('_Framework.ControlSurface')
    surface_module.ControlSurface = ControlSurface
    monkeypatch.setitem(sys.modules, 'Live', live_module)
    monkeypatch.setitem(sys.modules, '_Framework', framework)
    monkeypatch.setitem(sys.modules, '_Framework.ControlSurface', surface_module)
    namespace = {'__name__': 'PyxelWidgets'}
    exec(compile(daws.files('live')['PyxelWidgets/__init__.py'], 'live', 'exec'), namespace)
    song = Song()
    script = namespace['create_instance'](types.SimpleNamespace(handle = lambda: 1))
    script.song = lambda: song
    script.build_midi_map(0)
    return script, song, forwarded


def test_live_script(live):
    script, song, forwarded = live
    assert ('note', 15, BUTTONS['Play']) in forwarded and ('cc', 15, FADERS['Macro 8']) in forwarded
    daw, received = output()
    def answer():
        script.update_display()
        for message in script.sent:
            daw.decode(message)
        script.sent.clear()
        return {message.name: message.value for message in received}
    state = answer()
    assert (state['DAW'], state['Track Name 2'], state['Selected Name'], state['Device Name'], state['Macro Name 1']) == ('Ableton Live', 'Bass', 'Drums', 'EQ Eight', 'P0')
    script.receive_midi((0x9F, BUTTONS['Play'], 127))
    script.receive_midi((0x9F, BUTTONS['Select 2'], 127))
    script.receive_midi((0x9F, BUTTONS['Mute 3'], 127))
    script.receive_midi((0xBF, FADERS['Volume 1'], 127))
    script.receive_midi((0xBF, FADERS['Macro 2'], 64))
    script.receive_midi((0x9F, BUTTONS['Macro Page Right'], 127))
    state = answer()
    assert state['Play'] == 1.0 and state['Selected Name'] == 'Bass' and state['Mute 3'] == 1.0 and state['Volume 1'] == 1.0
    assert song.visible_tracks[1].devices[0].parameters[2].value == pytest.approx(64 / 127)
    assert state['Macro Name 1'] == 'P8'
    before = len(received)
    script.receive_midi((0xF0, 0x7D, 0x50, 0x57, 0x7F, 0xF7))      # refresh: everything again
    answer()
    assert len(received) - before > 100


# Cubase: the MIDI Remote script run in Node against a stand-in API that takes any call

FAKE_API = '''
const calls = []
function fake(path) {
  return new Proxy(function () {}, {
    get(target, key) { if (key === Symbol.toPrimitive) return () => path; return fake(path + '.' + String(key)) },
    set(target, key, value) { calls.push(path + '.' + String(key) + '='); return true },
    apply(target, self, args) { calls.push(path + '()'); return fake(path + '()') },
  })
}
const Module = require('module')
const original = Module.prototype.require
Module.prototype.require = function (name) { return name === 'midiremote_api_v1' ? fake('api') : original.apply(this, arguments) }
require(process.argv[2])
const bindings = calls.filter((call) => call.endsWith('makeValueBinding()')).length
console.log(JSON.stringify({ bindings, titles: calls.filter((call) => call.endsWith('mOnTitleChange=')).length }))
'''


@pytest.mark.skipif(shutil.which('node') is None, reason = 'needs Node')
def test_cubase_script_runs(tmp_path):
    script = daws.install('cubase', tmp_path)[0]
    runner = tmp_path / 'run.js'
    runner.write_text(FAKE_API)
    result = subprocess.run(['node', str(runner), str(script)], capture_output = True, text = True, timeout = 60)
    assert result.returncode == 0, result.stderr
    found = __import__('json').loads(result.stdout.strip().splitlines()[-1])
    # Transport, the selected track, 8 strips x 8, the master and 8 macros; names from the strips, the selection and the macros
    assert found['bindings'] >= 70 and found['titles'] == 17
