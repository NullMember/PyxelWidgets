"""The pyxelwidgets command: pyxelwidgets run layout.json."""

import json
import signal
import subprocess
import sys
import time

import pytest

from pyxelwidgets.parser import FORMAT, VERSION


def write_layout(path, **extra):
    path.write_text(json.dumps({'format': FORMAT, 'version': VERSION, 'surface': {'width': 4, 'height': 4},
                                'widgets': [{'type': 'Fader', 'name': 'level', 'x': 0, 'y': 0, 'width': 1, 'height': 4}], **extra}))
    return path


@pytest.mark.skipif(sys.platform == 'win32', reason = 'Windows has no SIGTERM to catch (TerminateProcess ends it at once)')
def test_run_plays_until_terminated(tmp_path):
    path = write_layout(tmp_path / 'layout.json')
    process = subprocess.Popen([sys.executable, '-m', 'pyxelwidgets', 'run', str(path), '--play'],
                               stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)
    try:
        time.sleep(1.5)
        assert process.poll() is None
        process.send_signal(signal.SIGTERM)
        out, err = process.communicate(timeout = 10)
    finally:
        process.kill()
    assert process.returncode == 0, err
    assert out.startswith(f'Playing {path}: 1 widgets on a 4x4 surface')
    assert 'No devices in the layout' in out and 'Ctrl+C to stop' in out


@pytest.mark.parametrize('content, message', [(None, 'No layout file'), ('{"surface": {}}', 'not a pyxelwidgets.layout')])
def test_run_reports_bad_layouts(tmp_path, content, message):
    path = tmp_path / 'layout.json'
    if content is not None:
        path.write_text(content)
    result = subprocess.run([sys.executable, '-m', 'pyxelwidgets', 'run', str(path)], capture_output = True, text = True, timeout = 30)
    assert result.returncode == 2 and message in result.stderr


def test_designer_command_passes_its_arguments():
    result = subprocess.run([sys.executable, '-m', 'pyxelwidgets', 'designer', '--help'], capture_output = True, text = True, timeout = 30)
    assert result.returncode == 0 and 'pyxelwidgets designer' in result.stdout and '--offline' in result.stdout
