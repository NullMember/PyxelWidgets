"""
Starts the designer's server inside the Android app (MainActivity calls start).
Layouts, snippets and the share key live in the app's folder; MIDI goes through
Android's MIDI service (pyxelwidgets.devices.android_midi).
"""

import os
import pathlib
import threading

_server = None
_lock = threading.Lock()

def start(folder: str) -> str:
    """Start the designer once (the activity can be made again); returns the page's address."""
    global _server
    with _lock:
        if _server is None:
            # Path.home() (snippets, the share key) and relative layout paths: the app's folder
            os.environ['HOME'] = folder
            os.chdir(folder)
            from java import jclass
            print('MIDI devices:\n' + str(jclass('io.github.nullmember.pyxelwidgets.MidiBridge').describe()), flush = True)
            import pyxelwidgets.designer.window
            layout = pathlib.Path(folder) / 'layout.json'
            # No system file dialogs here: Open and Save As ask for a path in the page
            _server = pyxelwidgets.designer.window._server(str(layout), None, connect = True, dialogs = False)
            threading.Thread(target = _server.serve_forever, name = 'designer server', daemon = True).start()
            # Bluetooth MIDI devices connected before connect again (and when they come back in range)
            import pyxelwidgets.devices.bluetooth
            pyxelwidgets.devices.bluetooth.manager().keep_connected()
            print(f'Designer on {_server.RequestHandlerClass.designer.local_url()}, layouts in {folder}, '
                  f'network addresses {pyxelwidgets.designer.network_addresses()}', flush = True)
    return _server.RequestHandlerClass.designer.local_url()

def stop() -> None:
    """Close the designer (the notification's Quit): devices get their goodbye messages."""
    global _server
    with _lock:
        if _server is None:
            return
        server, _server = _server, None
        designer = server.RequestHandlerClass.designer
        server.shutdown()
        designer.close()
        server.server_close()
        import pyxelwidgets.devices.bluetooth
        pyxelwidgets.devices.bluetooth.manager().close()
