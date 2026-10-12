import argparse
import importlib
import importlib.util
import pathlib
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

def main() -> None:
    parser = argparse.ArgumentParser(prog = 'python -m pyxelwidgets.designer', description = 'Design PyxelWidgets layouts in the browser.')
    parser.add_argument('layout', nargs = '?', help = 'layout file to open and save (created on first save)')
    parser.add_argument('--port', type = int, default = 8765)
    parser.add_argument('--no-browser', action = 'store_true', help = "don't open a browser")
    parser.add_argument('--offline', action = 'store_true', help = "don't connect the layout's devices and outputs (connect them one by one in the browser)")
    parser.add_argument('--import', dest = 'imports', action = 'append', default = [], metavar = 'MODULE',
                        help = 'a module (or .py file) registering widgets or devices of your own with parser.register; repeatable')
    args = parser.parse_args()
    for module in args.imports:
        load_module(module)
    server = pyxelwidgets.designer.serve(args.layout, args.port, connect = not args.offline)
    url = f'http://{server.server_address[0]}:{server.server_address[1]}/'
    print(f'PyxelWidgets designer on {url} (Ctrl+C to stop)')
    if not args.no_browser:
        threading.Timer(0.3, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.RequestHandlerClass.designer.close()
        server.server_close()

if __name__ == '__main__':
    main()
