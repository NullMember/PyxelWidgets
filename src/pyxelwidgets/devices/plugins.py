"""
Shared by the outputs that reach a DAW's tracks and plug-in parameters by
name (``mackie.MackieControl``, ``osc.REAPER``): the names scans found, and a
thread that drives the DAW there, so ``send`` never blocks.

An output mixes in ``PluginParameters`` and provides ``scan_tracks()``,
``scan_plugins(track)``, ``scan_parameters(track, plugin)``,
``_turn(track, plugin, parameter, value)`` (PluginParameter) and
``_set_track(track, parameter, value)`` (TrackParameter).
"""

import threading

__all__ = ['PluginParameters', 'labels']

def labels(names: list) -> list:
    """Names made unique: a repeated one gets " (2)", " (3)"..."""
    counts, found = {}, []
    for name in names:
        counts[name] = counts.get(name, 0) + 1
        found.append(name if counts[name] == 1 else f'{name} ({counts[name]})')
    return found

class PluginParameters:
    """
    Scans by label: ``tracks``, plug-ins as (label, ...) by track, parameters
    as (label, ...) by (track, plugin); what follows the label is where the
    output finds it. ``warning`` says what went wrong reaching a parameter last.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tracks = []
        self._plugins = {}
        self._parameters = {}
        #: What went wrong reaching a plug-in parameter last, if anything
        self.warning = None
        # What the last scan of tracks found wrong (shown while parameters are reached)
        self._scan_warning = None
        self._navigation = threading.RLock()
        # Values waiting for the DAW to get there: (track, plugin, parameter) → value
        self._turns = {}
        self._turns_lock = threading.Lock()
        self._turned = threading.Event()
        self._worker = None
        self._closing = False

    def scanned(self) -> dict:
        """What the scans found: ``tracks``, ``plugins`` by track and ``parameters`` by track and plug-in."""
        with self._navigation:
            return {'tracks': list(self.tracks),
                    'plugins': {track: [entry[0] for entry in plugins] for track, plugins in self._plugins.items()},
                    'parameters': {f'{track}/{plugin}': [entry[0] for entry in parameters]
                                   for (track, plugin), parameters in self._parameters.items()}}

    def close(self) -> None:
        self._closing = True
        self._turned.set()
        super().close()

    def _turn_later(self, message, value, combine = None) -> None:
        """
        Queue ``value`` for ``message``'s parameter (a PluginParameter's or a
        TrackParameter's); ``combine(waiting, value)`` merges it with a value
        still waiting (default: the newest wins).
        """
        if self._closing:
            return
        key = (message.track, getattr(message, 'plugin', None), message.parameter)
        with self._turns_lock:
            if key in self._turns and combine is not None:
                value = combine(self._turns[key], value)
            self._turns[key] = value
            if self._worker is None:
                self._worker = threading.Thread(target = self._work, name = f'{type(self).__name__}Plugins', daemon = True)
                self._worker.start()
        self._turned.set()

    def _work(self) -> None:
        while True:
            self._turned.wait()
            if self._closing:
                return
            with self._turns_lock:
                turns, self._turns = self._turns, {}
                self._turned.clear()
            for (track, plugin, parameter), value in turns.items():
                try:
                    if plugin is None:
                        self._set_track(track, parameter, value)
                    else:
                        self._turn(track, plugin, parameter, value)
                    self.warning = self._scan_warning
                except Exception as error:
                    self.warning = f'{" / ".join(name for name in (track, plugin, parameter) if name)}: {error}'

    def _turn(self, track: str, plugin: str, parameter: str, value) -> None:
        raise NotImplementedError

    def _set_track(self, track: str, parameter: str, value) -> None:
        raise NotImplementedError
