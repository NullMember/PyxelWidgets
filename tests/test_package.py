import os
import subprocess
import sys

import pytest

import pyxelwidgets


def test_public_api():
    for name in pyxelwidgets.__all__:
        assert hasattr(pyxelwidgets, name), name


def test_core_import_has_no_hardware_dependencies():
    code = (
        'import sys, pyxelwidgets\n'
        'loaded = {"rtmidi", "tkinter", "pythonosc"} & set(sys.modules)\n'
        'assert not loaded, loaded\n'
    )
    env = dict(os.environ, PYTHONPATH = os.pathsep.join(sys.path))
    subprocess.run([sys.executable, '-c', code], check = True, env = env)


def test_osc_extra():
    pytest.importorskip('pythonosc')
    from pyxelwidgets.devices.osc import REAPER
    assert issubclass(REAPER, pyxelwidgets.Device)
