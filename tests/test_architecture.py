"""
Every module may only load the modules of its own and lower layers, so each
small piece stays usable without the bigger ones:

    app, parser, codegen              glue, may use anything
    surface                           maps a widget tree onto controllers
    group                             container widget
    widgets | devices.* | transport | binding | mapping   never import each other
    link                              uses mapping, message and expression
    buffer
    color, rectangle, events, font, rate, message, expression    no internal dependencies
    animation                         uses color and rate
"""

import os
import subprocess
import sys

import pytest

BASE = {'color', 'rectangle', 'events'}

ALLOWED = {
    'color': set(),
    'rectangle': set(),
    'events': set(),
    'transport': {'events', 'rate'},
    'binding': {'events'},
    'message': set(),
    'expression': set(),
    'mapping': {'events', 'message'},
    'link': {'events', 'color', 'expression', 'mapping', 'message'},
    'buffer': {'color'},
    'font': set(),
    'rate': set(),
    'animation': {'color', 'rate'},
    'widgets': BASE | {'buffer', 'font', 'animation', 'rate'},
    'devices': BASE | {'buffer', 'devices.colors', 'devices.input'},
    'devices.virtual': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input'},
    'devices.midi': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'devices.te_virtual_midi'},
    'devices.novation': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'devices.midi', 'devices.te_virtual_midi',
                                'devices.novation.launchpad', 'devices.novation.launchkey', 'devices.novation.launch_control'},
    'devices.midi_clock': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'devices.midi', 'devices.te_virtual_midi'},
    'devices.midi_port': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'devices.midi', 'devices.te_virtual_midi', 'message'},
    'devices.mackie': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'devices.midi', 'devices.te_virtual_midi', 'devices.midi_port', 'devices.plugins', 'message'},
    'devices.osc': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'devices.plugins', 'message'},
    'devices.plugins': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input'},
    'devices.rtp_midi': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'message'},
    'devices.ble_midi': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'message'},
    'devices.web': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input'},
    'devices.desktop': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'message'},
    'devices.akai': BASE | {'buffer', 'devices', 'devices.colors', 'devices.input', 'devices.midi', 'devices.te_virtual_midi'},
    'group': BASE | {'buffer', 'widgets', 'font', 'animation', 'rate'},
    'surface': BASE | {'binding', 'mapping', 'link', 'message', 'expression', 'buffer', 'widgets', 'group', 'font', 'animation', 'rate'},
    'app': BASE | {'binding', 'mapping', 'link', 'message', 'expression', 'buffer', 'transport', 'widgets', 'group', 'surface', 'font', 'animation', 'rate'},
    'parser': BASE | {'binding', 'mapping', 'link', 'message', 'expression', 'buffer', 'transport', 'widgets', 'group', 'surface', 'font', 'animation', 'rate'},
    'codegen': BASE | {'binding', 'mapping', 'link', 'message', 'expression', 'buffer', 'transport', 'widgets', 'group', 'surface', 'font', 'animation', 'rate',
                       'app', 'parser'},
}


def loaded_by(module):
    code = (
        'import sys, importlib\n'
        f'importlib.import_module("pyxelwidgets.{module}")\n'
        'print("\\n".join(m for m in sys.modules if m.startswith("pyxelwidgets.")))\n'
    )
    env = dict(os.environ, PYTHONPATH = os.pathsep.join(sys.path))
    out = subprocess.run([sys.executable, '-c', code], capture_output = True, text = True, check = True, env = env).stdout
    return {name.removeprefix('pyxelwidgets.') for name in out.split()} - {module}


@pytest.mark.parametrize('module', sorted(ALLOWED))
def test_module_only_loads_lower_layers(module):
    extra = loaded_by(module) - ALLOWED[module]
    assert not extra, f'{module} loads {sorted(extra)}'
