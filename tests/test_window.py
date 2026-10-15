"""The designer's window (pyxelwidgets.designer.window) without a GUI: its server, bridge and dialogs."""

import pathlib
import socket
import sys
import types

import pytest

import pyxelwidgets.designer.window as window

def test_chosen_normalizes_dialog_answers():
    assert window._chosen(None) is None
    assert window._chosen(()) is None
    assert window._chosen(('/a/b.json',)) == '/a/b.json'
    assert window._chosen('/a/c.json') == '/a/c.json'

def test_server_takes_the_next_free_port():
    taken = socket.socket()
    try:
        taken.bind(('127.0.0.1', window.PORTS.start))
    except OSError:
        pytest.skip(f'port {window.PORTS.start} is in use')
    taken.listen()
    try:
        server = window._server(None, None, connect = False)
        try:
            assert server.server_address[1] != window.PORTS.start
            assert server.server_address[1] in window.PORTS or window.PORTS.stop <= server.server_address[1]
        finally:
            server.RequestHandlerClass.designer.close()
            server.server_close()
        # A port asked for that's taken is an error, not another port
        with pytest.raises(OSError):
            window._server(None, window.PORTS.start, connect = False)
    finally:
        taken.close()

class FakeWindow:
    def __init__(self, answer = None):
        self.confirm_close = False
        self.title = None
        self.answer = answer
        self.dialogs = []

    def set_title(self, title):
        self.title = title

    def create_file_dialog(self, kind, **options):
        self.dialogs.append((kind, options))
        return self.answer

@pytest.fixture
def fake_webview(monkeypatch):
    module = types.SimpleNamespace(FileDialog = types.SimpleNamespace(OPEN = 10, SAVE = 30))
    monkeypatch.setitem(sys.modules, 'webview', module)
    return module

def test_bridge_title_and_closing():
    bridge = window.Bridge()
    bridge._window = FakeWindow()
    bridge.changed(True, '/some/where/drums.json')
    assert bridge._window.title == '• drums.json — PyxelWidgets'
    assert bridge._window.confirm_close
    bridge.changed(False, None)
    assert bridge._window.title == 'Unsaved layout — PyxelWidgets'
    assert not bridge._window.confirm_close

def test_bridge_download_writes_the_chosen_file(tmp_path, fake_webview):
    bridge = window.Bridge()
    target = tmp_path / 'copy.json'
    bridge._window = FakeWindow((str(target),))
    assert bridge.download('layout.json', '{"a": 1}\n')
    assert target.read_text() == '{"a": 1}\n'
    assert bridge._window.dialogs[0][1]['save_filename'] == 'layout.json'
    bridge._window.answer = None
    assert not bridge.download('layout.json', 'x')

def test_bridge_pick_starts_in_the_layout_folder(tmp_path, fake_webview):
    bridge = window.Bridge()
    bridge._window = FakeWindow(str(tmp_path / 'picked.json'))
    assert bridge._pick('open', str(tmp_path / 'missing' / 'old.json')) == str(tmp_path / 'picked.json')
    kind, options = bridge._window.dialogs[-1]
    assert kind == fake_webview.FileDialog.OPEN and options['directory'] == str(tmp_path)
    bridge._pick('save', str(tmp_path / 'old.json'))
    kind, options = bridge._window.dialogs[-1]
    assert kind == fake_webview.FileDialog.SAVE and options['save_filename'] == 'old.json'

def test_icon_is_drawn():
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'packaging'))
    try:
        import icon
    finally:
        sys.path.pop(0)
    image = icon.draw(32)
    assert image.shape == (32, 32, 4)
    assert image[0, 0, 3] == 0 and image[16, 16, 3] == 255
    assert icon.png(image).startswith(b'\x89PNG')
    assert icon.ico((16, 32))[:4] == b'\0\0\1\0'
    assert window.ICON.exists()

def test_headless_plays_like_run(monkeypatch, tmp_path):
    import pyxelwidgets.__main__
    played = []
    monkeypatch.setattr(pyxelwidgets.__main__, 'run', lambda args: played.append(args) or 0)
    with pytest.raises(SystemExit) as stopped:
        window.main(['--headless', str(tmp_path / 'a.json'), '--play', '--fps', '30', '--quiet'])
    assert stopped.value.code == 0
    args = played[0]
    assert (args.layout, args.play, args.fps, args.quiet, args.imports) == (str(tmp_path / 'a.json'), True, 30.0, True, [])

def test_headless_needs_a_layout(capsys):
    with pytest.raises(SystemExit) as stopped:
        window.main(['--headless'])
    assert stopped.value.code == 2
    assert '--headless needs a layout file' in capsys.readouterr().err
