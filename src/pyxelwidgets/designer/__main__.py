import argparse
import importlib
import importlib.util
import pathlib
import signal
import sys
import threading
import webbrowser

import pyxelwidgets.designer

def load_module(name: str) -> None:
    """Import a module by name (from the current directory too) or a .py file by path."""
    path = pathlib.Path(name)
    if path.suffix == '.py':
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)
    else:
        sys.path.insert(0, str(pathlib.Path.cwd()))
        importlib.import_module(name)

SHARED = ('Shared on the network: anyone who has the address below (it carries the key) can edit layouts '
          'and open and save files on this computer as you. Share only on networks you trust.')

def announce(server, stopping: str = 'Ctrl+C to stop') -> None:
    """Print where the designer is, and the shared address when it listens beyond this computer."""
    designer = server.RequestHandlerClass.designer
    print(f'PyxelWidgets designer on {designer.local_url()} ({stopping})', flush = True)
    if designer.fixed():
        print(SHARED)
        for url in designer.network_urls():
            print(f'  Other computers: {url}', flush = True)

def serve_until_stopped(server) -> None:
    """Serve until Ctrl+C or SIGTERM (a service manager), then close the designer's hardware."""
    def stop(number, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.RequestHandlerClass.designer.close()
        server.server_close()

def main(argv = None, prog = 'pyxelwidgets-designer') -> None:
    parser = argparse.ArgumentParser(prog = prog, description = 'Design PyxelWidgets layouts in the browser.')
    parser.add_argument('layout', nargs = '?', help = 'layout file to open and save (created on first save)')
    parser.add_argument('--port', type = int, default = 8765)
    parser.add_argument('--host', default = '127.0.0.1',
                        help = 'address to listen on: 0.0.0.0 shares it with other computers on the network (they need the key '
                               'in the printed address); default 127.0.0.1, this computer only')
    parser.add_argument('--no-browser', action = 'store_true', help = "don't open a browser")
    parser.add_argument('--offline', action = 'store_true', help = "don't connect the layout's devices and outputs (connect them one by one in the browser)")
    parser.add_argument('--import', dest = 'imports', action = 'append', default = [], metavar = 'MODULE',
                        help = 'a module (or .py file) registering widgets or devices of your own with parser.register; repeatable')
    parser.add_argument('--snippets', metavar = 'FOLDER', help = 'where snippets you save go (default ~/.pyxelwidgets/snippets)')
    parser.add_argument('--no-dialogs', action = 'store_true', help = "type file paths in the page instead of the system's file dialogs")
    args = parser.parse_args(argv)
    for module in args.imports:
        load_module(module)
    server = pyxelwidgets.designer.serve(args.layout, args.port, args.host, connect = not args.offline, snippets = args.snippets,
                                         dialogs = not args.no_dialogs)
    announce(server)
    if not args.no_browser:
        threading.Timer(0.3, webbrowser.open, (server.RequestHandlerClass.designer.local_url(),)).start()
    serve_until_stopped(server)

if __name__ == '__main__':
    main()
