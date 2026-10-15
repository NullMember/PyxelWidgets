"""
The designer in a window of its own instead of a browser tab: the system's web
view through pywebview (extra ``app``: WKWebView on macOS, WebView2 on Windows,
Qt or GTK on Linux), with native menus and file dialogs, and a question before
closing with unsaved changes. ``pyxelwidgets app`` and the packaged application
(``packaging/``) start it; player mode (``--perform``, ``--play``) opens the
layout in Perform mode, playing, and ``--headless`` plays it without a window
(``pyxelwidgets run``, for the packaged application). ``--server`` runs only the
designer's server, ``--host 0.0.0.0`` shares it on the network.
"""

import argparse
import os
import pathlib
import sys
import threading
import urllib.parse

import pyxelwidgets.designer
from pyxelwidgets.designer.__main__ import announce, load_module, serve_until_stopped

__all__ = ['main', 'data_folder', 'PORTS']

#: The window's server tries these first: a page's storage (preferences, the clipboard, recent files)
#: belongs to its address, so a port that changes every start would forget them
PORTS = range(8770, 8780)

LAYOUTS = ('Layouts (*.json)', 'All files (*.*)')

#: The window's icon (Linux, Windows; a macOS application has its bundle's), drawn by packaging/icon.py
ICON = pathlib.Path(__file__).parent / 'static' / 'icon.png'

def data_folder() -> pathlib.Path:
    """Where the window keeps its web view's storage."""
    home = pathlib.Path.home()
    if sys.platform == 'darwin':
        base = home / 'Library' / 'Application Support'
    elif sys.platform == 'win32':
        base = pathlib.Path(os.environ.get('APPDATA') or home / 'AppData' / 'Roaming')
    else:
        base = pathlib.Path(os.environ.get('XDG_DATA_HOME') or home / '.local' / 'share')
    return base / 'PyxelWidgets'

def _chosen(result) -> str | None:
    """A file dialog's answer: platforms give a path or a sequence of them, None or empty when cancelled."""
    if isinstance(result, (tuple, list)):
        result = result[0] if result else None
    return str(result) if result else None

class Bridge:
    """What the page calls (``window.pywebview.api``); also the designer's file dialogs."""

    def __init__(self):
        self._window = None

    def changed(self, dirty: bool, file: str | None) -> None:
        """The layout's file and whether it has unsaved changes: the title, and whether closing asks first."""
        name = pathlib.Path(file).name if file else 'Unsaved layout'
        self._window.confirm_close = bool(dirty)
        self._window.set_title(f"{'• ' if dirty else ''}{name} — PyxelWidgets")

    def download(self, name: str, text: str) -> bool:
        """Save ``text`` where the person chooses (the page's Download and device reports)."""
        import webview
        path = _chosen(self._window.create_file_dialog(webview.FileDialog.SAVE, directory = str(pathlib.Path.home() / 'Downloads'),
                                                       save_filename = name, file_types = LAYOUTS))
        if path is None:
            return False
        pathlib.Path(path).write_text(text, encoding = 'utf-8')
        return True

    def _pick(self, mode: str, path: str | None = None) -> str | None:
        """``Designer.pick``: the window's own dialog for Open and Save As."""
        import webview
        start = pathlib.Path(path).expanduser() if path else pathlib.Path.home()
        folder = start if start.is_dir() else start.parent
        while not folder.is_dir() and folder != folder.parent:
            folder = folder.parent
        if mode == 'open':
            return _chosen(self._window.create_file_dialog(webview.FileDialog.OPEN, directory = str(folder), file_types = LAYOUTS))
        name = start.name if not start.is_dir() else 'layout.json'
        return _chosen(self._window.create_file_dialog(webview.FileDialog.SAVE, directory = str(folder), save_filename = name,
                                                       file_types = LAYOUTS))

def _server(layout, port, host = '127.0.0.1', **options):
    """The designer's server on ``port``, else the first free one of ``PORTS``, else any."""
    for candidate in ([port] if port is not None else [*PORTS, 0]):
        try:
            return pyxelwidgets.designer.serve(layout, candidate, host, **options)
        except OSError:
            if port is not None:
                raise
    raise OSError('No free port for the designer')

def _menus(window):
    import webview.menu as menu
    def page(script):
        return lambda: window.evaluate_js(f'window.pyxelwidgets && window.pyxelwidgets.{script}')
    return [
        menu.Menu('File', [
            menu.MenuAction('New…', page('openStart()')),
            menu.MenuAction('Open…', page('showOpen()')),
            menu.MenuSeparator(),
            menu.MenuAction('Save', page('save()')),
            menu.MenuAction('Save As…', page('saveAs()')),
            menu.MenuAction('Save a Copy…', page('download()')),
        ]),
        menu.Menu('Mode', [
            menu.MenuAction('Edit', page("setMode('edit')")),
            menu.MenuAction('Try', page("setMode('try')")),
            menu.MenuAction('Perform', page("setMode('perform')")),
        ]),
        menu.Menu('Transport', [
            menu.MenuAction('Play / Stop', page('togglePlay()')),
        ]),
    ]

def main(argv = None, prog = 'pyxelwidgets app') -> None:
    parser = argparse.ArgumentParser(prog = prog, description = 'Design and play PyxelWidgets layouts in a window of their own.')
    parser.add_argument('layout', nargs = '?', help = 'layout file to open and save (created on first save)')
    parser.add_argument('--perform', action = 'store_true', help = 'player mode: open in Perform mode (no editing grid)')
    parser.add_argument('--play', action = 'store_true', help = "start the layout's transport")
    parser.add_argument('--port', type = int, help = f'server port (default: the first free of {PORTS.start}-{PORTS.stop - 1})')
    parser.add_argument('--host', default = '127.0.0.1',
                        help = 'address to listen on: 0.0.0.0 shares the designer with other computers on the network '
                               '(they need the key in the address it shows); default 127.0.0.1, this computer only')
    parser.add_argument('--server', action = 'store_true',
                        help = "the designer's server without a window: open the printed address in a browser")
    parser.add_argument('--offline', action = 'store_true', help = "don't connect the layout's devices and outputs")
    parser.add_argument('--import', dest = 'imports', action = 'append', default = [], metavar = 'MODULE',
                        help = 'a module (or .py file) registering widgets or devices of your own with parser.register; repeatable')
    parser.add_argument('--snippets', metavar = 'FOLDER', help = 'where snippets you save go (default ~/.pyxelwidgets/snippets)')
    parser.add_argument('--debug', action = 'store_true', help = "allow the web view's developer tools")
    headless = parser.add_argument_group('headless', 'Without the window, like pyxelwidgets run: plays the layout on its '
                                         'devices and outputs until stopped (Ctrl+C, SIGTERM)')
    headless.add_argument('--headless', action = 'store_true', help = 'play the layout without a window (needs a layout)')
    headless.add_argument('--fps', type = float, default = 60.0, help = 'frames per second sent to the devices (default 60)')
    headless.add_argument('--quiet', action = 'store_true', help = 'print only errors')
    args = parser.parse_args(argv)
    if args.headless:
        if not args.layout:
            parser.error('--headless needs a layout file')
        import pyxelwidgets.__main__
        sys.exit(pyxelwidgets.__main__.run(args))
    if args.layout:
        args.layout = str(pathlib.Path(args.layout).expanduser().resolve())
    if args.server:
        for module in args.imports:
            load_module(module)
        server = _server(args.layout, args.port, args.host, connect = not args.offline, snippets = args.snippets)
        announce(server)
        if args.play:
            server.RequestHandlerClass.designer.preview.play()
        serve_until_stopped(server)
        return
    try:
        import webview
    except ImportError:
        sys.exit('The window needs pywebview: pip install "pyxelwidgets[app]" (or use pyxelwidgets designer, which opens a browser)')
    for module in args.imports:
        load_module(module)
    server = _server(args.layout, args.port, args.host, connect = not args.offline, snippets = args.snippets)
    designer = server.RequestHandlerClass.designer
    if designer.fixed():
        announce(server, 'close the window to stop')
    query = {key: value for key, value in (('mode', 'perform' if args.perform else None), ('play', '1' if args.play else None)) if value}
    url = designer.local_url() + (f'?{urllib.parse.urlencode(query)}' if query else '')
    threading.Thread(target = server.serve_forever, name = 'designer server', daemon = True).start()
    bridge = Bridge()
    window = webview.create_window('PyxelWidgets', url, js_api = bridge, width = 1440, height = 900, min_size = (800, 500),
                                   text_select = True, background_color = '#121418')
    bridge._window = window
    designer.pick = bridge._pick
    webview.settings['ALLOW_DOWNLOADS'] = True
    storage = data_folder() / 'webview'
    storage.mkdir(parents = True, exist_ok = True)
    try:
        # Windows' web view takes only .ico icons (a PNG threw in .NET and closed the app before anything showed);
        # without one it uses the program's own icon
        icon = None if sys.platform == 'win32' else str(ICON)
        webview.start(private_mode = False, storage_path = str(storage), debug = args.debug, menu = _menus(window), icon = icon,
                      localization = {'global.quitConfirmation': 'The layout has unsaved changes. Close it anyway?',
                                      'global.quit': 'Close'})
    finally:
        server.shutdown()
        designer.close()
        server.server_close()

if __name__ == '__main__':
    main()
