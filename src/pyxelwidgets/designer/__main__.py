import argparse
import threading
import webbrowser

import pyxelwidgets.designer

def main() -> None:
    parser = argparse.ArgumentParser(prog = 'python -m pyxelwidgets.designer', description = 'Design PyxelWidgets layouts in the browser.')
    parser.add_argument('layout', nargs = '?', help = 'layout file to open and save (created on first save)')
    parser.add_argument('--port', type = int, default = 8765)
    parser.add_argument('--no-browser', action = 'store_true', help = "don't open a browser")
    args = parser.parse_args()
    server = pyxelwidgets.designer.serve(args.layout, args.port)
    url = f'http://{server.server_address[0]}:{server.server_address[1]}/'
    print(f'PyxelWidgets designer on {url} (Ctrl+C to stop)')
    if not args.no_browser:
        threading.Timer(0.3, webbrowser.open, (url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.RequestHandlerClass.designer.preview.stop()
        server.server_close()

if __name__ == '__main__':
    main()
