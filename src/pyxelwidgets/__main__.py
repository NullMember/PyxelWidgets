"""
The ``pyxelwidgets`` command: ``pyxelwidgets run layout.json`` plays a layout
without the designer (devices, outputs, links, clocks, hot-plug); stored presets
go back into the layout file. ``pyxelwidgets designer ...`` opens the designer,
``pyxelwidgets app ...`` the designer in a window of its own.
"""

import argparse
import signal
import sys

def run(args) -> int:
    import pyxelwidgets.designer.__main__
    import pyxelwidgets.events
    import pyxelwidgets.parser
    for module in args.imports:
        pyxelwidgets.designer.__main__.load_module(module)
    # Bluetooth MIDI devices connected in the designer connect again; devices using them wait until they have
    import pyxelwidgets.devices.bluetooth
    pyxelwidgets.devices.bluetooth.manager().keep_connected_if_remembered()
    try:
        ui = pyxelwidgets.parser.load(args.layout)
    except FileNotFoundError:
        print(f'No layout file {args.layout}', file = sys.stderr)
        return 2
    except (pyxelwidgets.parser.LayoutError, ValueError) as error:
        print(f'{args.layout}: {error}', file = sys.stderr)
        return 2
    app = ui.app(args.fps)
    say = (lambda text: None) if args.quiet else (lambda text: print(text, flush = True))
    say(f'Playing {args.layout}: {len(ui.widgets)} widgets on a {ui.surface.rect.w}x{ui.surface.rect.h} surface')
    for device in ui.devices:
        name = type(device).__name__
        say(f'  {name}: ' + ('connected' if device.connected else 'waiting until it is plugged in'))
        device.on(pyxelwidgets.events.DeviceDisconnected, lambda event, name = name: say(f'{name} unplugged: waiting for it'))
        device.on(pyxelwidgets.events.DeviceReconnected, lambda event, name = name: say(f'{name} is back'))
    for name, output in ui.outputs.items():
        say(f'  {name} ({type(output).__name__}): ' + ('connected' if output.connected else 'not connected'))
        if getattr(output, 'warning', None):
            say(f'    {output.warning}')
    if not ui.devices:
        say('  No devices in the layout: add one in the designer')
    # Devices find out some things after connecting (e.g. the MiniLab 3's program): say when a warning comes or goes
    warnings = {}
    def check_warnings(event) -> None:
        for device in ui.devices:
            warning = getattr(device, 'warning', None)
            if warning != warnings.get(device.name):
                warnings[device.name] = warning
                say(f'{type(device).__name__}: {warning}' if warning else f'{type(device).__name__}: fine now')
    ui.surface.on(pyxelwidgets.events.Frame, check_warnings)
    if any(getattr(widget, 'save', False) and type(widget).__name__ == 'Presets' for widget in ui.widgets.values()):
        say(f'  Stored presets are saved to {args.layout}')
    if ui.clock_input is not None:
        say('  Following the DAW\'s MIDI clock')
    elif args.play:
        app.transport.play()
    say('Ctrl+C to stop')
    # A service manager (launchd, systemd) stops it with SIGTERM
    signal.signal(signal.SIGTERM, lambda number, frame: app.stop())
    app.run()
    return 0

def main(argv = None) -> None:
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ['designer']:
        import pyxelwidgets.designer.__main__
        return pyxelwidgets.designer.__main__.main(argv[1:], prog = 'pyxelwidgets designer')
    if argv[:1] == ['app']:
        import pyxelwidgets.designer.window
        return pyxelwidgets.designer.window.main(argv[1:], prog = 'pyxelwidgets app')
    parser = argparse.ArgumentParser(prog = 'pyxelwidgets', description = 'Play PyxelWidgets layouts, or design them.')
    commands = parser.add_subparsers(dest = 'command', required = True)
    play = commands.add_parser('run', help = 'play a layout on its devices, without the designer',
                               description = 'Play a layout on its devices and outputs until Ctrl+C. Devices '
                                             'unplugged meanwhile reconnect; stored presets are saved to the layout file.')
    play.add_argument('layout', help = 'layout file (made with the designer)')
    play.add_argument('--fps', type = float, default = 60.0, help = 'frames per second sent to the devices (default 60)')
    play.add_argument('--play', action = 'store_true', help = 'start the transport (unless it follows a DAW)')
    play.add_argument('--quiet', action = 'store_true', help = 'print only errors')
    play.add_argument('--import', dest = 'imports', action = 'append', default = [], metavar = 'MODULE',
                      help = 'a module (or .py file) registering widgets or devices of your own with parser.register; repeatable')
    commands.add_parser('designer', help = 'design layouts in the browser (pyxelwidgets designer --help)', add_help = False)
    commands.add_parser('app', help = 'the designer in a window of its own, or a player (pyxelwidgets app --help)', add_help = False)
    args = parser.parse_args(argv)
    sys.exit(run(args))

if __name__ == '__main__':
    main()
