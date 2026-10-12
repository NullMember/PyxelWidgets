"""
Loads layout.json (made with the designer: ``python -m pyxelwidgets.designer layout.json``)
and attaches behaviour to its widgets by name.
"""

import pathlib

from pyxelwidgets import Changed, Pressed, parser

ui = parser.load(pathlib.Path(__file__).with_name('layout.json'))
app = ui.app()
transport = app.transport

for channel in range(1, 9):
    ui[f'volume{channel}'].on(Changed, lambda e: print(f'{e.widget.name}: {e.value:.2f}'))
    ui[f'mute{channel}'].on(Changed, lambda e: print(f'{e.widget.name}: {"muted" if e.value else "on"}'))

ui['record'].on(Changed, lambda e: print('record', 'on' if e.value else 'off'))

# Play/pause the transport, and stop returns to the start
ui['play'].on(Changed, lambda e: transport.play() if e.value else transport.stop())

@ui['stop'].on(Pressed)
def rewind(e):
    ui['play'].set_value(False)
    transport.locate(0)

transport.every('beat', lambda beat: print(f'bar {transport.bar + 1}, beat {transport.beat + 1}'))

if __name__ == '__main__':
    # Runs until Ctrl+C or the grid window is closed
    app.run()
