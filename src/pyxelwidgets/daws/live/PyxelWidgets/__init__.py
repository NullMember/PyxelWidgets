# PyxelWidgets DAW protocol for Ableton Live (made by `pyxelwidgets daw install live`).
#
# PyxelWidgets' DAW output (a virtual MIDI port "PyxelWidgets DAW") talks to this
# remote script: transport, track selection, the mixer of 8 tracks at a time,
# the selected device's parameters as 8 macros, clips and scenes, and names back.
# In Live: Settings > Link, Tempo & MIDI > a Control Surface slot "PyxelWidgets"
# with input and output "PyxelWidgets DAW" (start PyxelWidgets first).
from __future__ import absolute_import

import Live
from _Framework.ControlSurface import ControlSurface

P = __PROTOCOL__

NOTES = dict((note, name) for name, note in P['buttons'].items())
CONTROLS = dict((number, name) for name, number in P['faders'].items())
STRIPS = 8


def create_instance(c_instance):
    return PyxelWidgets(c_instance)


def _set(parameter, value):
    """A Live parameter set from 0.0-1.0."""
    if parameter is not None and parameter.is_enabled:
        parameter.value = parameter.min + value * (parameter.max - parameter.min)


def _get(parameter):
    if parameter is None or parameter.max == parameter.min:
        return 0.0
    return (parameter.value - parameter.min) / (parameter.max - parameter.min)


class PyxelWidgets(ControlSurface):

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._bank = 0        # the first strip's track
        self._page = 0        # the macros' page of 8 parameters
        self._sent = {}       # what the other side has: name -> value

    # Input: our channel's notes and controls come to receive_midi

    def build_midi_map(self, midi_map_handle):
        ControlSurface.build_midi_map(self, midi_map_handle)
        handle = self._c_instance.handle()
        for note in NOTES:
            Live.MidiMap.forward_midi_note(handle, midi_map_handle, P['channel'], note)
        for number in CONTROLS:
            Live.MidiMap.forward_midi_cc(handle, midi_map_handle, P['channel'], number)

    def receive_midi(self, midi_bytes):
        status = midi_bytes[0]
        if status == 0xF0:
            if list(midi_bytes[1:5]) == P['sysex'] + [P['refresh']]:
                self._sent = {}
            return
        if status == 0x90 | P['channel'] and midi_bytes[2] > 0 and midi_bytes[1] in NOTES:
            self._button(NOTES[midi_bytes[1]])
        elif status == 0xB0 | P['channel'] and midi_bytes[1] in CONTROLS:
            self._fader(CONTROLS[midi_bytes[1]], midi_bytes[2] / 127.0)

    # Tracks and devices

    def _tracks(self):
        return list(self.song().visible_tracks)

    def _strip(self, n):
        tracks = self._tracks()
        index = self._bank + n - 1
        return tracks[index] if 0 <= index < len(tracks) else None

    def _selected(self):
        return self.song().view.selected_track

    def _device(self):
        track = self._selected()
        return track.view.selected_device if track is not None else None

    def _macro(self, n):
        device = self._device()
        if device is None:
            return None
        # Parameter 0 is the device's on/off
        index = 1 + self._page * 8 + n - 1
        return device.parameters[index] if index < len(device.parameters) else None

    def _select(self, track):
        if track is not None:
            self.song().view.selected_track = track

    @staticmethod
    def _toggle(track, attribute):
        if track is not None and (attribute != 'arm' or track.can_be_armed):
            setattr(track, attribute, not getattr(track, attribute))

    def _scene(self):
        scenes = list(self.song().scenes)
        selected = self.song().view.selected_scene
        return scenes.index(selected) if selected in scenes else 0

    # Commands

    def _button(self, name):
        song = self.song()
        tracks = self._tracks()
        selected = self._selected()
        if name == 'Play':
            song.continue_playing() if not song.is_playing else None
        elif name == 'Stop':
            song.stop_playing()
        elif name == 'Record':
            song.record_mode = not song.record_mode
        elif name == 'Loop':
            song.loop = not song.loop
        elif name == 'Metronome':
            song.metronome = not song.metronome
        elif name == 'Rewind':
            song.current_song_time = 0.0
        elif name == 'Forward':
            song.jump_by(song.signature_numerator)
        elif name == 'Undo' and song.can_undo:
            song.undo()
        elif name == 'Redo' and song.can_redo:
            song.redo()
        elif name == 'Tap Tempo':
            song.tap_tempo()
        elif name == 'Automation':
            song.session_automation_record = not song.session_automation_record
        elif name == 'Capture':
            song.capture_midi()
        elif name in ('Track Left', 'Track Right') and selected in tracks:
            index = tracks.index(selected) + (-1 if name == 'Track Left' else 1)
            if 0 <= index < len(tracks):
                self._select(tracks[index])
        elif name == 'Bank Left':
            self._bank = max(0, self._bank - STRIPS)
        elif name == 'Bank Right' and self._bank + STRIPS < len(tracks):
            self._bank += STRIPS
        elif name in ('Device Left', 'Device Right') and selected is not None:
            devices = list(selected.devices)
            device = self._device()
            if devices:
                index = devices.index(device) if device in devices else 0
                index = max(0, min(len(devices) - 1, index + (-1 if name == 'Device Left' else 1)))
                song.view.select_device(devices[index])
                self._page = 0
        elif name == 'Macro Page Left':
            self._page = max(0, self._page - 1)
        elif name == 'Macro Page Right':
            device = self._device()
            if device is not None and 1 + (self._page + 1) * 8 < len(device.parameters):
                self._page += 1
        elif name in ('Scene Up', 'Scene Down'):
            scenes = list(song.scenes)
            index = max(0, min(len(scenes) - 1, self._scene() + (-1 if name == 'Scene Up' else 1)))
            song.view.selected_scene = scenes[index]
        elif name == 'Scene Launch':
            song.view.selected_scene.fire()
        elif name == 'Stop All Clips':
            song.stop_all_clips()
        elif name == 'Device On':
            device = self._device()
            if device is not None and device.parameters:
                _set(device.parameters[0], 0.0 if _get(device.parameters[0]) > 0.5 else 1.0)
        elif name in ('Selected Mute', 'Selected Solo', 'Selected Arm'):
            self._toggle(selected, name.split()[1].lower())
        else:
            kind, _, number = name.rpartition(' ')
            track = self._strip(int(number)) if number.isdigit() else None
            if track is None:
                return
            if kind == 'Select':
                self._select(track)
            elif kind in ('Mute', 'Solo', 'Arm'):
                self._toggle(track, kind.lower())
            elif kind == 'Launch':
                slots = list(track.clip_slots)
                if self._scene() < len(slots):
                    slots[self._scene()].fire()
            elif kind == 'Stop':
                track.stop_all_clips()

    def _fader(self, name, value):
        song = self.song()
        selected = self._selected()
        if name == 'Master Volume':
            return _set(song.master_track.mixer_device.volume, value)
        if name.startswith('Selected ') and selected is not None:
            mixer = selected.mixer_device
            target = {'Selected Volume': mixer.volume, 'Selected Pan': mixer.panning,
                      'Selected Send A': mixer.sends[0] if len(mixer.sends) > 0 else None,
                      'Selected Send B': mixer.sends[1] if len(mixer.sends) > 1 else None}.get(name)
            return _set(target, value)
        kind, _, number = name.rpartition(' ')
        if not number.isdigit():
            return
        if kind == 'Macro':
            return _set(self._macro(int(number)), value)
        track = self._strip(int(number))
        if track is None:
            return
        mixer = track.mixer_device
        target = {'Volume': mixer.volume, 'Pan': mixer.panning,
                  'Send A': mixer.sends[0] if len(mixer.sends) > 0 else None,
                  'Send B': mixer.sends[1] if len(mixer.sends) > 1 else None}.get(kind)
        _set(target, value)

    # What the other side shows: lights, values and names

    def _state(self):
        song = self.song()
        now = {'Play': song.is_playing, 'Record': song.record_mode, 'Loop': song.loop, 'Metronome': song.metronome,
               'Automation': song.session_automation_record, 'DAW': 'Ableton Live'}
        selected = self._selected()
        for n in range(1, STRIPS + 1):
            track = self._strip(n)
            now['Track Name %d' % n] = track.name if track is not None else ''
            now['Select %d' % n] = track is not None and track == selected
            now['Mute %d' % n] = track is not None and track.mute
            now['Solo %d' % n] = track is not None and track.solo
            now['Arm %d' % n] = track is not None and track.can_be_armed and track.arm
            mixer = track.mixer_device if track is not None else None
            now['Volume %d' % n] = _get(mixer.volume) if mixer else 0.0
            now['Pan %d' % n] = _get(mixer.panning) if mixer else 0.0
            now['Send A %d' % n] = _get(mixer.sends[0]) if mixer and len(mixer.sends) > 0 else 0.0
            now['Send B %d' % n] = _get(mixer.sends[1]) if mixer and len(mixer.sends) > 1 else 0.0
        now['Selected Name'] = selected.name if selected is not None else ''
        if selected is not None:
            now['Selected Mute'] = selected.mute
            now['Selected Solo'] = selected.solo
            now['Selected Arm'] = selected.can_be_armed and selected.arm
            now['Selected Volume'] = _get(selected.mixer_device.volume)
            now['Selected Pan'] = _get(selected.mixer_device.panning)
        now['Master Volume'] = _get(song.master_track.mixer_device.volume)
        device = self._device()
        now['Device Name'] = device.name if device is not None else ''
        now['Device On'] = device is not None and bool(device.parameters) and _get(device.parameters[0]) > 0.5
        for n in range(1, 9):
            parameter = self._macro(n)
            now['Macro Name %d' % n] = parameter.name if parameter is not None else ''
            now['Macro Value %d' % n] = str(parameter) if parameter is not None else ''
            now['Macro %d' % n] = _get(parameter)
        return now

    def _text(self, name, value):
        field, index = P['texts'][name]
        text = [ord(c) if 32 <= ord(c) < 127 else 63 for c in value[:32]]
        self._send_midi(tuple([0xF0] + P['sysex'] + [field, index] + text + [0xF7]))

    def update_display(self):
        ControlSurface.update_display(self)
        for name, value in self._state().items():
            if name in P['texts']:
                value = value if isinstance(value, str) else str(value)
                if self._sent.get(name) != value:
                    self._text(name, value)
                    self._sent[name] = value
            elif name in P['buttons']:
                velocity = 127 if value else 0
                if self._sent.get(name) != velocity:
                    self._send_midi((0x90 | P['channel'], P['buttons'][name], velocity))
                    self._sent[name] = velocity
            elif name in P['faders']:
                number = int(round(value * 127))
                if self._sent.get(name) != number:
                    self._send_midi((0xB0 | P['channel'], P['faders'][name], number))
                    self._sent[name] = number
