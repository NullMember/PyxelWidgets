"""
End-to-end test of the designer UI in a headless browser. Needs Playwright:

    pip install playwright && python -m playwright install chromium

Skipped when Playwright isn't installed. Set DESIGNER_SHOTS=<dir> to save screenshots.
"""

import json
import os
import pathlib
import threading

import pytest

playwright = pytest.importorskip('playwright.sync_api')

from pyxelwidgets import parser  # noqa: E402
from pyxelwidgets.designer import serve  # noqa: E402
from pyxelwidgets.devices import Device  # noqa: E402

SHOTS = os.environ.get('DESIGNER_SHOTS')


@pytest.fixture
def page(tmp_path):
    server = serve(str(tmp_path / 'layout.json'), port = 0, connect = False, snippets = str(tmp_path / 'snippets'), dialogs = False)
    threading.Thread(target = server.serve_forever, daemon = True).start()
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport = {'width': 1400, 'height': 900})
        errors = []
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_address[1]}/')
        page.wait_for_selector('#palette button')
        page.layout_path = tmp_path / 'layout.json'
        page.designer = server.RequestHandlerClass.designer
        yield page
        assert errors == []
        browser.close()
    server.RequestHandlerClass.designer.close()
    server.shutdown()
    server.server_close()


def shot(page, name):
    if SHOTS:
        pathlib.Path(SHOTS).mkdir(parents = True, exist_ok = True)
        page.screenshot(path = str(pathlib.Path(SHOTS) / f'{name}.png'))


def close_rules(page):
    """Close the messages and links window, which floats over the grid."""
    page.click('#rules-close')
    assert page.is_hidden('#rules')


def pad(page, x, y):
    return page.locator(f'.pad[data-x="{x}"][data-y="{y}"]')


def drag_cells(page, locator, dx, dy):
    box = locator.bounding_box()
    step = page.evaluate("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--pad')) + 4")
    x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx * step, y - dy * step, steps = 8)
    page.mouse.up()


def test_design_try_and_save(page):
    shot(page, '1-empty')
    page.select_option('#device-type', 'novation.LaunchpadMiniMK3')
    page.click('#add-device')
    assert page.locator('.outline.device').count() == 1
    assert 'Launchpad Mini MK3' in page.inner_text('#properties h3')

    page.click('#palette button[data-type="Fader"]')
    page.select_option('#option-mode', 'Magnitude')
    assert page.locator('.outline.widget').count() == 1

    page.click('#palette button[data-type="Button"]')
    button = page.locator('.outline.widget.selected')
    drag_cells(page, button, 8, 8)
    page.wait_for_function("document.querySelector('#properties .quad input').value === '8'")

    # Try the fader: pressing its top pad sets it to 1.0 and lights it
    page.click('#mode-try')
    page.wait_for_function("document.querySelector('.pad[data-x=\"0\"][data-y=\"7\"]').dataset.color !== undefined")
    pad(page, 0, 7).click()
    page.wait_for_selector('#events li:has-text("Changed")')
    page.wait_for_function("document.querySelector('.pad[data-x=\"0\"][data-y=\"7\"]').dataset.color === '#ffffff'")
    assert 'value=1' in page.inner_text('#events')
    shot(page, '2-try')

    # A group with a sequencer inside, played by the transport
    page.click('#mode-edit')
    page.click('#palette button[data-type="Group"]')
    page.fill('#properties .quad label:nth-child(1) input', '2')
    page.press('#properties .quad label:nth-child(1) input', 'Enter')
    page.click('#palette button[data-type="Sequencer"]')
    assert page.locator('#tree ul li').count() >= 1
    assert 'group1' in page.inner_text('#tree') and 'sequencer1' in page.inner_text('#tree')
    page.click('#play')
    page.wait_for_selector('#events li:has-text("StepPlayed")')
    page.wait_for_function("document.querySelector('#position').textContent.startsWith('bar ')")
    page.click('#play')
    shot(page, '3-group')

    # Undo the sequencer, redo it
    page.click('#undo')
    assert 'sequencer1' not in page.inner_text('#tree')
    page.click('#redo')
    assert 'sequencer1' in page.inner_text('#tree')

    page.click('#save')
    page.wait_for_selector('#status.ok')
    saved = json.loads(page.layout_path.read_text())
    ui = parser.load(saved, devices = False)
    assert ui['fader1'].mode.name == 'Magnitude'
    assert (ui['button1'].rect.x, ui['button1'].rect.y) == (8, 8)
    assert ui['sequencer1'] in ui['group1'].children
    assert saved['devices'][0]['type'] == 'novation.LaunchpadMiniMK3'
    # The snippet loads and runs the layout; handlers on request
    page.click('.tabs button[data-tab="python"]')
    page.wait_for_function("document.querySelector('#code').textContent.includes('parser.load')")
    assert 'on(Changed' not in page.inner_text('#code')
    page.check('#code-handlers')
    page.wait_for_function("document.querySelector('#code').textContent.includes(\"ui['fader1'].on(Changed\")")
    # Or the same surface built in code, without the layout file
    page.click('#code-standalone')
    page.wait_for_function("document.querySelector('#code').textContent.includes('fader1.on(Changed')")
    code = page.inner_text('#code')
    assert 'parser.load' not in code and "fader1 = " in code and 'mode = Fader.Mode.Magnitude' in code
    page.click('#code-loader')
    assert 'parser.load' in page.inner_text('#code')
    shot(page, '4-saved')



def test_perform_mode_hides_the_grid(page):
    page.click('#palette button[data-type="Button"]')
    page.click('#mode-perform')
    assert page.locator('body.perform').count() == 1
    assert page.is_visible('#perform-note') and not page.is_visible('#board')
    with page.expect_request(lambda request: '/api/frame' in request.url and 'pixels=0' in request.url):
        pass
    page.keyboard.press('e')
    assert page.locator('body.perform').count() == 0 and page.is_visible('#board')
    with page.expect_request(lambda request: '/api/frame' in request.url and 'pixels=0' not in request.url):
        pass

def test_invalid_edit_shows_error(page):
    page.click('#palette button[data-type="Fader"]')
    page.fill('#widget-name', '')
    page.press('#widget-name', 'Enter')
    page.wait_for_selector('#status.error')


def test_geometry_edits_stay_inside_parent(page):
    page.click('#palette button[data-type="Group"]')
    x = page.locator('#properties .quad label:nth-child(1) input')
    x.fill('2')
    x.press('Enter')
    # A full width group can't move right
    assert x.input_value() == '0'
    width = page.locator('#properties .quad label:nth-child(3) input')
    width.fill('4')
    width.press('Enter')
    x = page.locator('#properties .quad label:nth-child(1) input')
    x.fill('20')
    x.press('Enter')
    assert page.locator('#properties .quad label:nth-child(1) input').input_value() == '5'
    assert 'null' not in page.inner_text('#properties')


def test_bind_controls(page):
    layout = parser.upgrade({'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 9, 'height': 9},
                             'devices': [{'type': 'novation.LaunchControlXL', 'x': 0, 'y': 0, 'options': {}},
                                         {'type': 'novation.LaunchpadMiniMK3', 'x': 0, 'y': 0, 'options': {'side_buttons': False}}],
                             'widgets': [{'type': 'Fader', 'name': 'volume', 'x': 0, 'y': 0, 'width': 1, 'height': 8, 'options': {}}]})
    page.evaluate("layout => fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)})", layout)
    page.reload()
    page.wait_for_selector('#palette button')

    # Transport action on a Launchpad side button
    page.select_option('#action-transport-toggle', '1:Top8')
    # A fader on a Launch Control XL fader, picking up
    page.click('#tree .node:has-text("volume")')
    page.select_option('#widget-control', '0:Fader_0')
    page.select_option('#option-takeover', 'Pickup')
    assert page.locator('#option-glide_time').count() == 0
    page.select_option('#option-takeover', 'Glide')
    assert page.locator('#option-glide_time').count() == 1
    page.select_option('#option-takeover', 'Pickup')
    shot(page, '4-bind')
    # Renaming keeps the binding; removing a device drops its bindings and renumbers the others
    page.fill('#widget-name', 'master')
    page.press('#widget-name', 'Enter')
    page.click('#devices li .name >> nth=0')
    page.click('text=Remove device')
    page.click('#save')
    page.wait_for_selector('#status.ok')
    assert json.loads(page.layout_path.read_text())['bindings'] == [{'device': 0, 'control': 'Top8', 'action': 'transport.toggle'}]
    page.click('#undo')
    page.click('#save')
    page.wait_for_selector('#status.ok')
    saved = json.loads(page.layout_path.read_text())['bindings']
    assert {'device': 0, 'control': 'Fader_0', 'widget': 'master', 'options': {'takeover': 'Pickup'}} in saved
    parser.load(page.layout_path, devices = False)


def saved_layout(page):
    # Clear an earlier "Saved" first, so the wait is for this save
    page.evaluate("document.getElementById('status').className = ''")
    page.click('#save')
    page.wait_for_selector('#status.ok')
    return json.loads(page.layout_path.read_text())


def preview_layout(page):
    """The layout the designer has, without saving (a new layout has no file)."""
    import time
    time.sleep(0.4)          # edits reach the server after a short delay
    return page.designer.preview.layout


def outline(page, name):
    return page.locator(f'.outline.widget[title^="{name} ("]')


def test_paint_sprite_frames(page):
    page.click('#palette button[data-type="Sprite"]')
    cell = lambda top, x: page.locator(f'#sprite-grid .cell[data-top="{top}"][data-x="{x}"]')
    page.click('.swatch[title="Red"]')
    # One stroke over the top row is one undo step
    drag = cell(0, 0).bounding_box(), cell(0, 1).bounding_box()
    page.mouse.move(drag[0]['x'] + 4, drag[0]['y'] + 4)
    page.mouse.down()
    page.mouse.move(drag[1]['x'] + 4, drag[1]['y'] + 4, steps = 4)
    page.mouse.up()
    page.wait_for_function("document.querySelector('.pad[data-x=\"1\"][data-y=\"1\"]').dataset.color === '#ff0000'")
    cell(0, 1).click(button = 'right')
    page.click('#undo')
    assert 'empty' not in cell(0, 1).get_attribute('class')
    # A second frame, played every 1/8
    page.click('.frames button:has-text("+")')
    page.click('.swatch[title="Blue"]')
    cell(1, 1).click()
    page.fill('#option-rate', '1/8')
    page.press('#option-rate', 'Enter')
    shot(page, '5-sprite')
    sprite = saved_layout(page)['widgets'][0]
    assert sprite['options'] == {'frames': [[['#ff0000', '#ff0000'], [None, None]], [[None, None], [None, '#0000ff']]], 'rate': '1/8'}
    assert parser.load(sprite_only(sprite), devices = False)['sprite1'].rate == '1/8'


def sprite_only(widget):
    return {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 9, 'height': 9}, 'widgets': [widget]}


def test_widget_animation(page):
    page.click('#palette button[data-type="Button"]')
    page.select_option('#animation-type', 'Blink')
    page.fill('#animation-rate', '0.5')
    page.press('#animation-rate', 'Enter')
    page.select_option('#option-mode', 'Switch')
    assert saved_layout(page)['widgets'][0]['animation'] == {'type': 'Blink', 'options': {'rate': 0.5}}
    page.select_option('#animation-type', '')
    assert 'animation' not in saved_layout(page)['widgets'][0]


def test_drag_device(page):
    page.fill('#properties .quad label:nth-child(1) input', '18')
    page.press('#properties .quad label:nth-child(1) input', 'Enter')
    page.select_option('#device-type', 'novation.LaunchpadMiniMK3')
    page.click('#add-device')
    drag_cells(page, page.locator('.outline.device .tag'), 12, 3)
    # Kept on the surface: 9 to the right at most, and no room upwards
    page.wait_for_function("document.querySelector('#properties .quad input').value === '9'")
    device = saved_layout(page)['devices'][0]
    assert (device['x'], device['y']) == (9, 0)


def test_select_several(page):
    for x, y in ((0, 0), (2, 0), (4, 4)):
        page.click('#palette button[data-type="Button"]')
        for nth, value in ((1, x), (2, y)):
            field = page.locator(f'#properties .quad label:nth-child({nth}) input')
            field.fill(str(value))
            field.press('Enter')
    # Drag a rectangle from an empty pad over the two bottom buttons
    start, end = pad(page, 3, 1).bounding_box(), pad(page, 0, 0).bounding_box()
    page.mouse.move(start['x'] + start['width'] / 2, start['y'] + start['height'] / 2)
    page.mouse.down()
    page.mouse.move(end['x'] + end['width'] / 2, end['y'] + end['height'] / 2, steps = 6)
    page.mouse.up()
    assert page.inner_text('#properties h3') == '2 widgets'
    outline(page, 'button3').click(modifiers = ['Shift'])
    assert page.inner_text('#properties h3') == '3 widgets'
    assert page.locator('.outline.widget.selected').count() == 3
    # Edited together, moved together (button3 can't go higher than the surface allows)
    page.select_option('#option-mode', 'Switch')
    page.keyboard.press('ArrowUp')
    shot(page, '6-select')
    page.keyboard.press('Control+g')
    layout = saved_layout(page)
    group, = layout['widgets']
    assert group['type'] == 'Group' and (group['x'], group['y'], group['width'], group['height']) == (0, 1, 5, 5)
    assert [(w['name'], w['x'], w['y'], w['options']) for w in group['widgets']] == [
        ('button1', 0, 0, {'mode': 'Switch'}), ('button2', 2, 0, {'mode': 'Switch'}), ('button3', 4, 4, {'mode': 'Switch'})]
    page.click('text=Ungroup')
    assert page.inner_text('#properties h3') == '3 widgets'
    # Shift+click takes one out again
    outline(page, 'button2').click(modifiers = ['Shift'])
    assert page.inner_text('#properties h3') == '2 widgets'
    page.keyboard.press('Delete')
    assert [w['name'] for w in saved_layout(page)['widgets']] == ['button2']


def test_pick_midi_ports(page, monkeypatch):
    from pyxelwidgets.devices.midi import MIDI
    ports = (['Synth In', 'IAC Driver Bus 1'], ['Synth Out', 'PyxelWidgets midi'])
    monkeypatch.setattr(MIDI, 'available_ports', staticmethod(lambda: ports))
    page.click('#palette button[data-type="Button"]')
    page.select_option('#output-type', 'midi_port.MidiPort')
    page.click('#add-output')
    # Found ports to pick, without the layout's own virtual port
    page.wait_for_selector('#output-output-pick option[value="Synth Out"]', state = 'attached')
    assert page.locator('#output-output-pick option').all_inner_texts() == ['None', 'Synth Out', 'Custom…']
    page.select_option('#output-output-pick', 'Synth Out')
    assert saved_layout(page)['outputs'][0]['output'] == 'Synth Out'
    # Custom: a typed name
    page.select_option('#output-input-pick', 'Custom…')
    page.fill('#output-input', 'Some Input')
    page.press('#output-input', 'Enter')
    assert saved_layout(page)['outputs'][0]['input'] == 'Some Input'
    assert page.input_value('#output-input-pick') != ''
    # Scan finds new ones
    ports[0].append('New In')
    page.click('#output-input-scan')
    page.wait_for_selector('#output-input-pick option[value="New In"]', state = 'attached')
    page.select_option('#output-input-pick', 'New In')
    page.select_option('#output-output-pick', 'None')
    output = saved_layout(page)['outputs'][0]
    assert output['input'] == 'New In' and 'output' not in output
    # Devices too
    page.select_option('#device-type', 'novation.LaunchpadMiniMK3')
    page.click('#add-device')
    page.select_option('#device-input-pick', 'Synth In')
    assert saved_layout(page)['devices'][0]['input'] == 'Synth In'
    page.select_option('#device-input-pick', 'Find by name')
    assert 'input' not in saved_layout(page)['devices'][0]


def test_send_messages_to_outputs(page):
    page.click('#palette button[data-type="Button"]')
    assert 'Add an output' in page.inner_text('#properties')
    page.select_option('#output-type', 'midi_port.MidiPort')
    page.click('#add-output')
    assert page.input_value('#output-virtual') == 'PyxelWidgets midi'
    # Back to the button: press sends a note on, release a note off
    page.click('#tree .node:has-text("button1")')
    page.click('text=Add message')
    page.select_option('#mapping-0-on', 'Pressed')
    page.fill('#mapping-0-note >> xpath=following-sibling::input', '36')
    page.press('#mapping-0-note >> xpath=following-sibling::input', 'Enter')
    page.click('text=Add message')
    page.select_option('#mapping-1-on', 'Released')
    page.select_option('#mapping-1-type', 'NoteOff')
    # The second message's note comes from... a constant 36 too
    page.fill('#mapping-1-note >> xpath=following-sibling::input', '36')
    page.press('#mapping-1-note >> xpath=following-sibling::input', 'Enter')
    shot(page, '7-messages')
    close_rules(page)
    # Try it: the event log shows what would be sent
    page.click('#mode-try')
    pad(page, 0, 0).click()
    page.wait_for_selector('#events li:has-text("→ NoteOff")')
    assert 'note=36 velocity=127 channel=1' in page.inner_text('#events')
    page.click('#mode-edit')
    # Renaming the output keeps the messages pointing at it
    page.click('#outputs li .name >> nth=0')
    page.fill('#output-name', 'synth')
    page.press('#output-name', 'Enter')
    layout = saved_layout(page)
    assert layout['outputs'] == [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets midi', 'options': {}}]
    assert layout['mappings'] == [
        {'widget': 'button1', 'on': 'Pressed', 'output': 'synth', 'message': {'type': 'NoteOn', 'note': 36, 'velocity': {'source': 'velocity'}, 'channel': 1}},
        {'widget': 'button1', 'on': 'Released', 'output': 'synth', 'message': {'type': 'NoteOff', 'note': 36, 'velocity': 0, 'channel': 1}}]
    parser.load(layout, devices = False)
    # Removing the output removes its messages
    page.click('text=Remove output')
    assert 'mappings' not in saved_layout(page)


def test_mackie_commands_and_feedback(page):
    page.click('#palette button[data-type="Fader"]')
    page.select_option('#output-type', 'mackie.MackieControl')
    page.click('#add-output')
    page.click('#tree .node:has-text("fader1")')
    page.click('text=Add message')
    assert page.input_value('#mapping-0-name-pick') == 'Fader 1' and page.is_hidden('#mapping-0-name')
    page.select_option('#mapping-0-name-pick', 'Fader 2')
    page.check('#mapping-0-feedback')
    # A source with a narrower range
    page.select_option('#mapping-0-value', 'value')
    mapping = saved_layout(page)['mappings'][0]
    assert mapping == {'widget': 'fader1', 'on': 'Changed', 'output': 'mackie', 'feedback': True,
                       'message': {'type': 'Command', 'name': 'Fader 2', 'value': {'source': 'value'}}}
    page.select_option('#mapping-0-on', '')
    assert 'on' not in saved_layout(page)['mappings'][0]


def drag_from_palette(page, widget_type, x, y):
    page.drag_and_drop(f'#palette button[data-type="{widget_type}"]', f'.pad[data-x="{x}"][data-y="{y}"]', force = True)


def test_drop_widgets_on_the_grid(page):
    # A Button dropped on pad (3, 5)
    drag_from_palette(page, 'Button', 3, 5)
    assert page.inner_text('#properties h3') == 'Button'
    assert page.input_value('#properties .quad label:nth-child(1) input') == '3'
    assert page.input_value('#properties .quad label:nth-child(2) input') == '5'
    # A Group, then a Button dropped inside it goes into it
    drag_from_palette(page, 'Group', 0, 8)
    group_width = page.locator('#properties .quad label:nth-child(3) input')
    group_width.fill('4')
    group_width.press('Enter')
    drag_from_palette(page, 'Button', 1, 7)
    layout = saved_layout(page)
    button, group = layout['widgets']
    assert (button['x'], button['y']) == (3, 5)
    assert [(w['name'], w['x'], w['y']) for w in group['widgets']] == [('button2', 1, 7)]
    # A tall widget near the top is moved down to fit
    drag_from_palette(page, 'Fader', 6, 2)
    fader = saved_layout(page)['widgets'][-1]
    assert (fader['x'], fader['y'], fader['height']) == (6, 0, 8)


class FakeGrid(Device):
    grid = (9, 9)
    opened = []

    def connect(self, *ports):
        super().connect()
        FakeGrid.opened.append(self)

    def send_pixel(self, x, y, color):
        pass


@pytest.fixture
def fake_grid(monkeypatch):
    import sys
    import types
    module = types.ModuleType('pyxelwidgets.devices.browsertest')
    module.FakeGrid = FakeGrid
    monkeypatch.setitem(sys.modules, module.__name__, module)
    FakeGrid.opened = []
    return FakeGrid.opened


def test_connect_devices_from_their_list(page, fake_grid):
    layout = parser.upgrade({'format': 'pyxelwidgets.layout', 'version': 1, 'surface': {'width': 9, 'height': 9},
                             'devices': [{'type': 'browsertest.FakeGrid', 'x': 0, 'y': 0, 'options': {}}],
                             'widgets': [{'type': 'Fader', 'name': 'level', 'x': 0, 'y': 0, 'width': 1, 'height': 8, 'options': {}}]})
    page.evaluate("layout => fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)})", layout)
    page.reload()
    page.wait_for_selector('#devices .connect')
    assert page.inner_text('#devices .connect') == 'Connect' and page.locator('#hardware').count() == 0
    page.click('#devices .connect')
    page.wait_for_selector('#devices .dot.on')
    assert len(fake_grid) == 1 and page.inner_text('#devices .connect') == 'Disconnect'
    page.select_option('#output-type', 'mackie.MackieControl')
    page.click('#add-output')
    shot(page, '8-connect')
    # A pad pressed on the device moves the fader, which keeps its value when the layout changes
    fake_grid[0].set_button(0, 7, 1.0)
    page.click('#palette button[data-type="Button"]')
    page.wait_for_function("document.querySelector('.pad[data-x=\"0\"][data-y=\"7\"]').dataset.color === '#ffffff'")
    page.click('#devices .connect')
    page.wait_for_selector('#devices .dot.idle')
    assert not fake_grid[0].connected


def test_pick_commands(page):
    page.click('#palette button[data-type="Knob"]')
    page.select_option('#output-type', 'mackie.MackieControl')
    page.click('#add-output')
    page.click('#tree .node:has-text("knob1")')
    page.click('text=Add message')
    groups = page.eval_on_selector_all('#mapping-0-name-pick optgroup', 'gs => gs.map(g => g.label)')
    assert groups[:3] == ['Buttons', 'Faders', 'V-Pots and jog wheel (steps)'] and 'Displays (received)' in groups
    # A V-Pot sends the knob's steps
    page.select_option('#mapping-0-name-pick', 'V-Pot 1')
    shot(page, '9-commands')
    message = saved_layout(page)['mappings'][0]['message']
    assert message == {'type': 'Command', 'name': 'V-Pot 1', 'value': {'source': 'delta'}}
    # One V-Pot per pad needs a pad event; a knob turn has none, so it's only received
    page.select_option('#mapping-0-name-pick', 'V-Pot {x+1}')
    assert 'on' not in saved_layout(page)['mappings'][0]
    page.select_option('#mapping-0-on', 'Changed')
    # A display is only received
    page.select_option('#mapping-0-name-pick', 'Name 1')
    mapping = saved_layout(page)['mappings'][0]
    assert 'on' not in mapping and mapping['feedback'] and mapping['message']['value'] == {'source': 'text'}
    # A button takes a constant again; Custom shows the name to type
    page.select_option('#mapping-0-on', 'Pressed')
    page.select_option('#mapping-0-name-pick', 'Play')
    assert saved_layout(page)['mappings'][0]['message'] == {'type': 'Command', 'name': 'Play', 'value': 1}
    page.select_option('#mapping-0-name-pick', '')
    page.fill('#mapping-0-name', 'Solo {y+1}')
    page.press('#mapping-0-name', 'Enter')
    assert saved_layout(page)['mappings'][0]['message']['name'] == 'Solo {y+1}'
    assert page.input_value('#mapping-0-name-pick') == ''


def test_zoom_the_grid(page):
    pad_size = lambda: page.evaluate("document.querySelector('.pad').getBoundingClientRect().width")
    fitted = pad_size()
    page.click('#zoom-in')
    page.click('#zoom-in')
    # It eases there
    assert page.inner_text('#zoom-fit') == '156%'
    page.wait_for_function(f"document.querySelector('.pad').getBoundingClientRect().width > {fitted * 1.55}")
    # Bigger than the window, and widgets still line up with pads
    page.fill('#properties .quad label:nth-child(1) input', '24')
    page.press('#properties .quad label:nth-child(1) input', 'Enter')
    page.click('#palette button[data-type="Button"]')
    assert page.evaluate("document.getElementById('board').offsetWidth > document.getElementById('stage').clientWidth")
    shot(page, '10-zoom')
    outline = page.locator('.outline.widget.selected').bounding_box()
    corner = pad(page, 0, 0).bounding_box()
    # Outlines are 2px outside their pads
    assert abs(outline['x'] + 2 - corner['x']) < 2 and abs(outline['width'] - 4 - corner['width']) < 2
    page.keyboard.press('Control+0')
    assert page.inner_text('#zoom-fit') == 'Fit'
    # Back to fitting: all of it in view
    page.wait_for_function("(b => b.left >= 0 && b.right <= document.getElementById('stage').getBoundingClientRect().right)"
                           "(document.getElementById('board').getBoundingClientRect())")


def drag_layer(page, name, onto, where):
    """Drag a layer onto another one's top or bottom edge, or its middle."""
    target = page.locator(f'#tree .node:has(.name:text-is("{onto}"))')
    box = target.bounding_box()
    y = {'above': 2, 'into': box['height'] / 2, 'below': box['height'] - 2}[where]
    page.drag_and_drop(f'#tree .node:has(.name:text-is("{name}"))', f'#tree .node:has(.name:text-is("{onto}"))',
                       target_position = {'x': box['width'] / 2, 'y': y})


def names(widgets):
    return [w['name'] for w in widgets]


def test_reorder_and_regroup_layers(page):
    for widget_type in ('Button', 'Fader', 'Group'):
        page.click(f'#palette button[data-type="{widget_type}"]')
        page.click('#stage', position = {'x': 5, 'y': 5})
    # Group: 4 wide at x 4, from the bottom
    page.click('#tree .node:has-text("group1")')
    for nth, value in ((3, 4), (1, 4)):
        field = page.locator(f'#properties .quad label:nth-child({nth}) input')
        field.fill(str(value))
        field.press('Enter')
    assert names(saved_layout(page)['widgets']) == ['button1', 'fader1', 'group1']
    # The tree lists the topmost first: dragging button1 above group1 draws it on top
    drag_layer(page, 'button1', 'group1', 'above')
    assert names(saved_layout(page)['widgets']) == ['fader1', 'group1', 'button1']
    drag_layer(page, 'button1', 'fader1', 'below')
    assert names(saved_layout(page)['widgets']) == ['button1', 'fader1', 'group1']
    # Into the group: it keeps its place on the grid where it fits (x 0 -> clamped into the group)
    drag_layer(page, 'fader1', 'group1', 'into')
    layout = saved_layout(page)
    assert names(layout['widgets']) == ['button1', 'group1']
    fader, = layout['widgets'][1]['widgets']
    assert (fader['name'], fader['x'], fader['y'], fader['height']) == ('fader1', 0, 0, 8)
    assert page.inner_text('#properties h3') == 'Fader'
    # And out again, below button1
    drag_layer(page, 'fader1', 'button1', 'below')
    layout = saved_layout(page)
    assert names(layout['widgets']) == ['fader1', 'button1', 'group1'] and layout['widgets'][0]['x'] == 4
    # A group can't go into itself
    page.click('#tree .node:has-text("group1")')
    drag_layer(page, 'group1', 'group1', 'into')
    assert names(saved_layout(page)['widgets']) == ['fader1', 'button1', 'group1']
    page.click('#undo')
    assert names(saved_layout(page)['widgets']) == ['button1', 'group1']


def test_drag_selected_layers_together(page):
    for widget_type in ('Group', 'Button', 'Button'):
        page.click(f'#palette button[data-type="{widget_type}"]')
        page.click('#stage', position = {'x': 5, 'y': 5})
    page.click('#tree .node:has-text("button1")')
    page.click('#tree .node:has-text("button2")', modifiers = ['Shift'])
    drag_layer(page, 'button2', 'group1', 'into')
    layout = saved_layout(page)
    assert names(layout['widgets']) == ['group1'] and names(layout['widgets'][0]['widgets']) == ['button1', 'button2']
    assert page.inner_text('#properties h3') == '2 widgets'
    # Dropped on the empty part of the panel: back on the surface, on top
    tree = page.locator('#tree').bounding_box()
    page.drag_and_drop('#tree .node:has(.name:text-is("button1"))', '#tree', target_position = {'x': 50, 'y': tree['height'] - 4})
    layout = saved_layout(page)
    assert names(layout['widgets']) == ['group1', 'button1', 'button2']


def test_link_widgets(page):
    drag_from_palette(page, 'Keyboard', 0, 0)
    drag_from_palette(page, 'Button', 8, 8)
    page.click('#tree .node:has-text("button1")')
    page.click('text=Add link')
    # A momentary button: on presses, showing or hiding the keyboard
    assert page.input_value('#link-0-on') == 'Pressed' and page.input_value('#link-0-target') == 'keyboard1'
    assert page.input_value('#link-0-option') == 'option:visible' and page.input_value('#link-0-change') == 'Toggle'
    # One octave up each press, up to 2
    page.select_option('#link-0-option', 'option:octave')
    assert page.input_value('#link-0-change') == 'Add'
    page.fill('#link-0-max', '2')
    page.press('#link-0-max', 'Enter')
    close_rules(page)
    # A second button sets the root color from its velocity
    drag_from_palette(page, 'Button', 7, 8)
    page.click('#tree .node:has-text("button2")')
    page.click('text=Add link')
    page.select_option('#link-1-option', 'option:root_color')
    page.select_option('#link-1-value', 'velocity')
    page.wait_for_timeout(800)
    shot(page, '9-links')
    close_rules(page)
    page.click('#mode-try')
    for _ in range(3):
        pad(page, 8, 8).click()
    pad(page, 7, 8).click()
    page.wait_for_function('document.querySelectorAll("#events li").length >= 8')
    keys = page.designer.preview.ui['keyboard1']
    assert keys.octave == 2 and keys.root_color == parser.text_to_color('#ff00ff')
    page.click('#mode-edit')
    layout = saved_layout(page)
    assert layout['links'] == [
        {'widget': 'button1', 'on': 'Pressed', 'target': 'keyboard1', 'option': 'octave', 'change': 'Add', 'value': 1, 'max': 2},
        {'widget': 'button2', 'on': 'Pressed', 'target': 'keyboard1', 'option': 'root_color', 'value': {'source': 'velocity'}}]
    parser.load(layout, devices = False)
    # Renaming the target keeps the links; deleting it removes them
    page.click('#tree .node:has-text("keyboard1")')
    page.fill('#widget-name', 'keys')
    page.press('#widget-name', 'Enter')
    assert {link['target'] for link in saved_layout(page)['links']} == {'keys'}
    page.click('#properties button.danger:has-text("Delete")')
    assert 'links' not in saved_layout(page)


def test_link_transport_and_actions(page):
    drag_from_palette(page, 'Sequencer', 0, 0)
    page.select_option('#option-clock', 'Off')
    drag_from_palette(page, 'Button', 8, 8)
    drag_from_palette(page, 'Button', 7, 8)
    page.click('#tree .node:has-text("button1")')
    page.click('text=Add link')
    page.select_option('#link-0-target', '')
    assert page.input_value('#link-0-option') == 'action:transport.toggle'
    page.click('#tree .node:has-text("button2")')
    page.click('text=Add link')
    page.select_option('#link-1-target', 'sequencer1')
    page.select_option('#link-1-option', 'action:advance')
    page.wait_for_timeout(300)
    shot(page, '11-actions')
    close_rules(page)
    page.click('#mode-try')
    pad(page, 7, 8).click()
    pad(page, 7, 8).click()
    page.wait_for_selector('#events li:has-text("StepPlayed")')
    preview = page.designer.preview
    assert preview.ui['sequencer1'].step == 2 and preview.transport is None
    pad(page, 8, 8).click()
    page.wait_for_function('document.querySelector("#play").textContent.includes("Stop")')
    # Detached from the transport: playing doesn't move it
    page.wait_for_timeout(300)
    assert preview.transport is not None and preview.ui['sequencer1'].step == 2
    page.click('#mode-edit')
    layout = saved_layout(page)
    assert layout['links'] == [{'widget': 'button1', 'on': 'Pressed', 'action': 'transport.toggle'},
                               {'widget': 'button2', 'on': 'Pressed', 'target': 'sequencer1', 'action': 'advance'}]
    # Deleting a widget keeps the transport link
    page.click('#tree .node:has-text("sequencer1")')
    page.click('#properties button.danger:has-text("Delete")')
    assert saved_layout(page)['links'] == [{'widget': 'button1', 'on': 'Pressed', 'action': 'transport.toggle'}]


def performance_layout(page):
    """Load the Performance example layout into the designer."""
    layout = json.loads((pathlib.Path(__file__).parent.parent / 'examples' / 'Performance' / 'layout.json').read_text())
    page.evaluate("async (layout) => { await fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)}); }", layout)
    page.reload()
    page.wait_for_selector('#tree .node')


def node(page, name):
    return page.locator(f'#tree .node:has(.name:text-is("{name}"))')


def test_rename_in_layers(page):
    drag_from_palette(page, 'Button', 0, 0)
    drag_from_palette(page, 'Keyboard', 2, 0)
    node(page, 'button1').click()
    page.click('text=Add link')
    close_rules(page)
    # Double-click the name, type, Enter: links follow
    node(page, 'keyboard1').locator('.name').dblclick()
    page.fill('#tree input.rename', 'keys')
    page.press('#tree input.rename', 'Enter')
    assert node(page, 'keys').count() and not page.locator('#tree input.rename').count()
    assert saved_layout(page)['links'][0]['target'] == 'keys'
    # Escape keeps the name; a taken name is refused
    node(page, 'keys').locator('.name').dblclick()
    page.fill('#tree input.rename', 'other')
    page.press('#tree input.rename', 'Escape')
    assert node(page, 'keys').count()
    node(page, 'keys').click()
    page.keyboard.press('F2')
    page.fill('#tree input.rename', 'button1')
    page.press('#tree input.rename', 'Enter')
    assert node(page, 'keys').count() and page.locator('#status.error').count()
    # Clicking elsewhere keeps what was typed
    node(page, 'button1').locator('.name').dblclick()
    page.fill('#tree input.rename', 'play')
    page.click('#layer-search')
    assert node(page, 'play').count() and saved_layout(page)['links'][0]['widget'] == 'play'


def test_layers_fold_search_hide_and_lock(page):
    for widget_type in ('Group', 'Button', 'Fader'):
        page.click(f'#palette button[data-type="{widget_type}"]')
    page.click('#stage', position = {'x': 5, 'y': 5})
    # Fold the group: its widgets disappear from the list, and come back
    node(page, 'group1').locator('.caret').click()
    assert not node(page, 'button1').count() and 'Group · 2' in node(page, 'group1').inner_text()
    node(page, 'group1').locator('.caret').click()
    assert node(page, 'button1').count()
    # Search keeps the groups leading to a match
    page.fill('#layer-search', 'fad')
    assert node(page, 'fader1').count() and node(page, 'group1').count() and not node(page, 'button1').count()
    page.fill('#layer-search', '')
    # Hidden in the designer: gone from the grid and the preview, still in the layout
    node(page, 'button1').hover()
    node(page, 'button1').locator('.toggle.hidden').click()
    assert page.locator('.outline.widget.hidden-here').count() == 1
    assert page.designer.preview.ui['button1'].visible is False
    assert 'visible' not in json.dumps(saved_layout(page)['widgets'])
    node(page, 'button1').locator('.toggle.hidden').click()
    assert page.designer.preview.ui['button1'].visible is True
    # Locked: can't be grabbed on the grid
    node(page, 'fader1').locator('.toggle.locked').click()
    assert page.locator('.outline.widget.locked').count() == 1


def test_wiring_is_visible(page):
    performance_layout(page)
    node(page, 'drums').click()
    changed_by = page.inner_text('details[data-group="behaviour"] .controlled')
    assert 'bank_down' in changed_by and 'bank_up' in changed_by
    # Drums change the meter; the bank buttons change the drums
    assert page.locator('.outline.widget.affects').count() == 1
    assert page.locator('.outline.widget.affected-by').count() == 2
    page.click('details[data-group="behaviour"] .controlled li:has-text("bank_up")')
    assert page.input_value('#widget-name') == 'bank_up'
    # Every connection in one table; a row selects its widget
    page.click('.tabs button[data-tab="connections"]')
    rows = page.locator('#connections tr.connection')
    assert rows.count() == 15
    rows.filter(has_text = 'beat_toggle').first.click()
    assert page.input_value('#widget-name') == 'beat_toggle'
    # Problems: the devices aren't connected (offline designer)... and an output without ports
    page.click('#outputs li .name >> nth=0')
    page.fill('#output-virtual', '')
    page.press('#output-virtual', 'Enter')
    page.wait_for_selector('#problems:not([hidden])')
    page.click('#problems')
    assert 'has no port' in page.inner_text('#problem-list')


def test_panels_drawer_alt_click_and_shortcuts(page):
    page.click('#palette button[data-type="Button"]')
    page.click('#toggle-left')
    assert 'no-left' in page.get_attribute('body', 'class')
    page.keyboard.press('f')
    assert 'no-right' in page.get_attribute('body', 'class')
    page.keyboard.press('f')                    # back as it was: left hidden, right shown
    classes = page.get_attribute('body', 'class') or ''
    assert 'no-left' in classes and 'no-right' not in classes
    page.click('#toggle-left')
    # Alt + click presses a pad without leaving Edit mode
    page.click('.outline.widget', modifiers = ['Alt'])
    page.wait_for_selector('#events li:has-text("Pressed")')
    assert page.is_visible('#mode-edit.active')
    page.keyboard.press('Shift+?')
    assert page.is_visible('dialog table.keys')
    page.keyboard.press('Escape')
    # Try mode opens the events
    page.click('.tabs button[data-tab="events"]')
    assert page.locator('#drawer.collapsed').count() == 1
    page.click('#mode-try')
    assert page.locator('#drawer.collapsed').count() == 0 and page.is_visible('#events')


def test_copy_paste_and_duplicate_keep_behaviour(page):
    performance_layout(page)
    node(page, 'bank_up').click()
    page.keyboard.press('Control+d')
    assert page.input_value('#widget-name') == 'button1'
    layout = saved_layout(page)
    assert {'widget': 'button1', 'on': 'Pressed', 'target': 'drums', 'option': 'bank', 'change': 'Add', 'value': 1, 'max': 5} in layout['links']
    # Copy drums and the bank buttons, paste: new names, links between the copies stay between them
    node(page, 'drums').click()
    node(page, 'bank_down').click(modifiers = ['ControlOrMeta'])
    page.keyboard.press('Control+c')
    page.keyboard.press('Control+v')
    layout = saved_layout(page)
    names = [widget['name'] for widget in layout['widgets']]
    assert 'drumPads1' in names and 'button2' in names
    assert {'widget': 'button2', 'on': 'Pressed', 'target': 'drumPads1', 'option': 'bank', 'change': 'Add', 'value': -1, 'min': 0} in layout['links']
    assert any(mapping['widget'] == 'drumPads1' and mapping['output'] == 'midi' for mapping in layout['mappings'])
    # Into another layout without that output: names kept, the messages left out
    page.click('#file-menu')
    page.click('#menu-new')
    page.click('#start button[data-template=""]')   # saved by saved_layout: nothing to discard
    page.wait_for_selector('#tree li.hint')
    page.keyboard.press('Control+v')
    assert 'left out' in page.inner_text('#status')
    layout = preview_layout(page)
    assert sorted(widget['name'] for widget in layout['widgets']) == ['bank_down', 'drums']
    assert 'mappings' not in layout and layout['links'][0]['target'] == 'drums'
    # Cut
    node(page, 'drums').click()
    page.keyboard.press('Control+x')
    assert [widget['name'] for widget in preview_layout(page)['widgets']] == ['bank_down']


def test_files_templates_and_detection(page, tmp_path, monkeypatch):
    import pyxelwidgets.designer
    monkeypatch.setattr(pyxelwidgets.designer, 'detect_devices', lambda: [{'type': 'novation.LaunchpadMiniMK3', 'model': 'Launchpad Mini MK3'}])
    # An empty layout opens the start window: an empty layout first, then templates and the devices plugged in
    page.wait_for_selector('#start')
    assert page.get_attribute('#start .choices button >> nth=0', 'data-template') == ''
    shot(page, '15-start')
    page.click('#start-detect')
    page.click('#start button:has-text("Add Launchpad Mini MK3")')
    layout = preview_layout(page)
    assert layout['devices'][0]['type'] == 'novation.LaunchpadMiniMK3' and layout['surface'] == {'width': 9, 'height': 9}
    # Then snippets fitting its grid, the biggest first, and outputs for other software
    page.wait_for_selector('#start .snippet-choices button')
    sizes = page.eval_on_selector_all('#start .snippet-choices small', 'items => items.map(item => item.textContent)')
    assert sizes[0] == '9x9' and all(int(w) <= 9 and int(h) <= 9 for w, h in (size.split('x') for size in sizes))
    page.click('#start button[data-output="mackie.MackieControl"]')
    page.wait_for_selector('#start button[data-output="mackie.MackieControl"][disabled]')
    shot(page, '16-start-device')
    page.click('#start .snippet-choices button >> nth=1')
    page.wait_for_selector('#start', state = 'detached')
    assert saved_layout(page)['widgets']
    # A press elsewhere closes it too
    page.click('#file-menu')
    page.click('#menu-new')
    page.wait_for_selector('#start')
    page.click('#tab-widgets')
    page.wait_for_selector('#start', state = 'detached')
    # File > New opens it again; Escape closes it, a template replaces the layout
    page.click('#file-menu')
    page.click('#menu-new')
    page.wait_for_selector('#start')
    page.keyboard.press('Escape')
    page.wait_for_selector('#start', state = 'detached')
    page.click('#file-menu')
    page.click('#menu-new')
    page.once('dialog', lambda dialog: dialog.accept())
    page.click('#start button[data-template="drums"]')
    page.wait_for_selector('#tree .node:has(.name:text-is("pads"))')
    assert page.inner_text('#file') == 'Unsaved layout'
    # Save asks where; then it's the layout file and in the recent list
    page.evaluate("document.getElementById('status').className = ''")
    page.keyboard.press('Control+s')
    target = tmp_path / 'sets' / 'drums.json'
    page.fill('#ask-path', str(target))
    page.click('#ask-ok')
    page.wait_for_selector('#status.ok')
    assert json.loads(target.read_text())['widgets'][0]['name'] == 'pads'
    assert page.inner_text('#file') == 'drums.json'
    # Open another file by path, then the first one from the recent list
    page.click('#palette button[data-type="Button"]')
    other = tmp_path / 'other.json'
    other.write_text(json.dumps(parser.load(str(target), devices = False).json))
    page.click('#file-menu')
    page.click('#menu-open')
    page.fill('#ask-path', str(other))
    page.click('#ask-ok')
    page.click('dialog #ask-ok')                 # discard the added button
    page.wait_for_function('document.querySelector("#file").textContent === "other.json"')
    page.click('#file-menu')
    page.click(f'.menu button.recent[title="{target}"]')
    page.wait_for_function('document.querySelector("#file").textContent === "drums.json"')


def test_system_file_dialogs(page, tmp_path):
    # The server shows the system's dialog: here a stand-in answering in turn
    answers = [str(tmp_path / 'kept' / 'mine'), None]
    asked = []
    page.designer.pick = lambda mode, path: (asked.append((mode, path)), answers.pop(0))[1]
    page.click('#palette button[data-type="Button"]')
    page.click('#file-menu')
    page.click('#menu-save-as')
    page.wait_for_function('document.querySelector("#file").textContent === "mine.json"')
    assert json.loads((tmp_path / 'kept' / 'mine.json').read_text())['widgets'][0]['type'] == 'Button'
    assert asked[0] == ('save', str(page.layout_path))
    # Cancelled: nothing asked in the page, nothing changes
    page.click('#file-menu')
    page.click('#menu-open')
    page.wait_for_function('() => !document.querySelector("dialog[open]")')
    assert asked[1][0] == 'open' and page.inner_text('#file') == 'mine.json'
    # No dialog (e.g. a browser on another computer): paths are typed in the page
    page.designer.pick = None
    page.click('#file-menu')
    page.click('#menu-open')
    page.wait_for_selector('#ask-path')


def test_keyboard_and_mouse_output(page):
    page.click('#palette button[data-type="Button"]')
    page.select_option('#output-type', 'desktop.Desktop')
    page.click('#add-output')
    assert 'press Connect' in page.inner_text('#properties')
    node(page, 'button1').click()
    page.click('text=Add message')
    # A button sends a shortcut on presses; record one by pressing it
    assert page.input_value('#mapping-0-on') == 'Pressed' and page.input_value('#mapping-0-type') == 'Hotkey'
    page.click('#mapping-0-keys-record')
    page.keyboard.press('Control+Shift+KeyS')
    page.wait_for_function("document.querySelector('#mapping-0-keys').value === 'ctrl+shift+s'")
    # A mouse click, with its button from a list
    page.click('text=Add message')
    page.select_option('#mapping-1-type', 'MouseClick')
    page.select_option('#mapping-1-button', 'right')
    layout = saved_layout(page)
    assert layout['outputs'] == [{'name': 'desktop', 'type': 'desktop.Desktop', 'options': {}}]
    messages = [mapping['message'] for mapping in layout['mappings']]
    assert messages[0] == {'type': 'Hotkey', 'keys': 'ctrl+shift+s'}
    assert messages[1]['type'] == 'MouseClick' and messages[1]['button'] == 'right'
    close_rules(page)
    # Trying it logs what it would do (not connected: nothing is pressed)
    page.click('#mode-try')
    pad(page, 0, 0).click()
    page.wait_for_selector('#events li:has-text("→ Hotkey")')
    assert 'keys=ctrl+shift+s' in page.inner_text('#events')


def test_debug_links(page):
    page.click('#palette button[data-type="Button"]')
    node(page, 'button1').click()
    page.click('text=Add link')
    page.select_option('#link-0-target', label = 'Debug log')
    page.fill('#link-0-value', 'hit {velocity}')
    page.press('#link-0-value', 'Enter')
    assert saved_layout(page)['links'] == [{'widget': 'button1', 'on': 'Pressed', 'action': 'debug', 'value': 'hit {velocity}'}]
    close_rules(page)
    page.click('#mode-try')
    pad(page, 0, 0).click()
    page.wait_for_selector('#events li.debug:has-text("hit 1")')
    # Only debug hides the widget events
    page.select_option('#event-filter', 'debug')
    assert page.locator('#events li').count() == 1 and page.locator('#events li.debug').count() == 1
    page.click('.tabs button[data-tab="connections"]')
    assert 'Debug log' in page.inner_text('#connections')


def test_link_conditions(page):
    drag_from_palette(page, 'ButtonGroup', 0, 8)
    drag_from_palette(page, 'Sequencer', 0, 0)
    node(page, 'buttonGroup1').click()
    page.click('text=Add link')
    page.select_option('#link-0-target', 'sequencer1')
    page.select_option('#link-0-option', 'option:visible')
    page.select_option('#link-0-value', label = 'condition…')
    page.select_option('#link-0-if', 'cell')
    page.fill('#link-0-to', '2')
    page.press('#link-0-to', 'Enter')
    link = saved_layout(page)['links'][0]
    assert link['value'] == {'if': {'source': 'cell'}, 'op': '==', 'to': 2, 'then': True, 'else': False}
    page.select_option('#link-0-op', '!=')
    page.uncheck('#link-0-then')
    page.check('#link-0-else')
    assert saved_layout(page)['links'][0]['value'] == {'if': {'source': 'cell'}, 'op': '!=', 'to': 2, 'then': False, 'else': True}
    # Cell 2 chosen: 2 != 2 is false, so "else": shown; cell 1: hidden
    import time
    close_rules(page)
    page.click('#mode-try')
    pad(page, 2, 8).click()
    time.sleep(0.3)
    assert page.designer.preview.ui['sequencer1'].visible is True
    pad(page, 1, 8).click()
    time.sleep(0.3)
    assert page.designer.preview.ui['sequencer1'].visible is False
    page.click('.tabs button[data-tab="connections"]')
    assert 'cell != 2 ? false : true' in page.inner_text('#connections')


def test_sync_to_a_daw_and_sequencer_feel(page, monkeypatch):
    from pyxelwidgets.devices.midi_clock import MidiClockInput
    monkeypatch.setattr(MidiClockInput, 'connect_virtual', lambda self, name: setattr(self, 'connected', True))
    drag_from_palette(page, 'Sequencer', 0, 0)
    # Swing and gates are Sequencer options
    page.fill('#option-swing', '66')
    page.press('#option-swing', 'Enter')
    # A feel tweak: under More options
    page.click('#properties details.more summary')
    page.fill('#option-gate_random', '0.2')
    page.press('#option-gate_random', 'Enter')
    options = saved_layout(page)['widgets'][0]['options']
    assert options['swing'] == 66 and options['gate_random'] == 0.2
    # Offline (as this designer is): a problem, and Play still plays
    page.keyboard.press('Escape')
    page.click('#stage', position = {'x': 5, 'y': 5})
    page.select_option('#sync-kind', 'virtual')
    page.wait_for_function("document.querySelector('#sync-status').textContent.includes('offline')")
    assert saved_layout(page)['transport']['sync'] == {'virtual': 'PyxelWidgets Clock'}
    assert not page.is_disabled('#play')
    # Connected: the DAW plays it
    page.designer.preview.connect = True
    page.fill('#sync-port', 'My Clock')
    page.press('#sync-port', 'Enter')
    page.wait_for_selector('#play:disabled')
    clock = page.designer.preview.sync['input']
    page.wait_for_function("document.querySelector('#sync-status').textContent.includes('waiting for the DAW')")
    clock.decode([0xFA])
    for _ in range(48):
        clock.decode([0xF8])
    page.wait_for_function("document.querySelector('#sync-status').textContent.includes('Following the DAW')")
    assert 'bar' in page.inner_text('#position')
    shot(page, 'sync')
    clock.decode([0xFC])
    page.select_option('#sync-kind', 'off')
    page.wait_for_selector('#play:enabled')
    assert 'sync' not in saved_layout(page)['transport']


def test_sync_to_an_outputs_clock(page):
    page.select_option('#output-type', 'rtp_midi.RtpMidi')
    page.click('#add-output')
    page.click('#stage', position = {'x': 5, 'y': 5})
    page.select_option('#sync-kind', 'output')
    name = saved_layout(page)['outputs'][0]['name']
    assert saved_layout(page)['transport']['sync'] == {'output': name}
    assert page.input_value('#sync-output') == name
    # Renaming the output keeps it; removing it stops the sync
    page.click('#outputs li')
    page.fill('#output-name', 'phone')
    page.press('#output-name', 'Enter')
    page.wait_for_function("document.querySelector('#outputs').textContent.includes('phone')")
    assert saved_layout(page)['transport']['sync'] == {'output': 'phone'}
    page.click('text=Remove output')
    page.wait_for_function("!document.querySelector('#outputs').textContent.includes('phone')")
    assert 'sync' not in saved_layout(page)['transport']


def test_scan_daw_plugins(page, monkeypatch):
    from pyxelwidgets.devices.mackie import MackieControl
    from test_mackie_plugins import TRACKS, Daw
    monkeypatch.setattr(MackieControl, 'settle', 0.005)
    monkeypatch.setattr(MackieControl, 'timeout', 0.03)
    daws = []
    def connect_virtual(self, name):
        daw = Daw(TRACKS)
        daw.connect(self)
        self.connected = True
        daws.append(daw)
    monkeypatch.setattr(MackieControl, 'connect_virtual', connect_virtual)
    page.click('#palette button[data-type="Fader"]')
    page.select_option('#output-type', 'mackie.MackieControl')
    page.click('#add-output')
    page.click('#tree .node:has-text("fader1")')
    page.click('text=Add message')
    page.select_option('#mapping-0-type', 'PluginParameter')
    # Not connected yet: Scan says so
    page.click('#mapping-0-track-scan')
    page.wait_for_selector('#status.error')
    assert 'Connect the output' in page.inner_text('#status')
    assert not page.is_enabled('#mapping-0-plugin-scan')
    page.click('#outputs .connect')
    page.wait_for_selector('#outputs .dot.on')
    page.click('#tree .node:has-text("fader1")')
    # Scan the tracks, pick one; then its plug-ins, then the parameters
    page.click('#mapping-0-track-scan')
    page.wait_for_selector('#mapping-0-track-pick')
    assert 'Bass (2)' in page.inner_text('#mapping-0-track-pick')
    page.select_option('#mapping-0-track-pick', 'Bass')
    page.click('#mapping-0-plugin-scan')
    page.wait_for_selector('#mapping-0-plugin-pick')
    page.select_option('#mapping-0-plugin-pick', 'ReaComp')
    page.click('#mapping-0-parameter-scan')
    page.wait_for_selector('#mapping-0-parameter-pick')
    page.select_option('#mapping-0-parameter-pick', 'P10')
    page.check('#mapping-0-feedback')
    shot(page, 'plugin-parameter')
    mapping = saved_layout(page)['mappings'][0]
    assert mapping['message'] == {'type': 'PluginParameter', 'track': 'Bass', 'plugin': 'ReaComp', 'parameter': 'P10', 'value': {'source': 'delta'}}
    # Try it: the fader turns the parameter in the DAW
    import time
    close_rules(page)
    page.click('#mode-try')
    rect = page.designer.preview.ui['fader1'].rect
    pad(page, rect.x, rect.y + rect.h - 1).click()
    page.wait_for_selector('#events li:has-text("→ PluginParameter")')
    end = time.monotonic() + 3
    while (2, 1, 9) not in daws[0].values and time.monotonic() < end:
        time.sleep(0.02)
    preview = page.designer.preview
    assert daws[0].values.get((2, 1, 9), 0) > 0, ([e for _, e in preview.events if e['event'] != '← Command'][-8:], preview.outputs[0]['device'].warning)
    # Picking another track forgets nothing: typed names work too
    page.click('#mode-edit')
    page.keyboard.press('m')
    page.select_option('#mapping-0-track-pick', '\u0000')
    page.fill('#mapping-0-track', 'Vocals')
    page.press('#mapping-0-track', 'Enter')
    assert saved_layout(page)['mappings'][0]['message']['track'] == 'Vocals'


def test_scan_reaper_plugins(page, monkeypatch):
    from pyxelwidgets.devices.osc import REAPER
    from test_reaper_plugins import MASTER, TRACKS, Reaper
    monkeypatch.setattr(REAPER, 'settle', 0.001)
    monkeypatch.setattr(REAPER, 'timeout', 0.01)
    daws = []
    def connect(self):
        self.connected = True
        daw = Reaper(TRACKS, MASTER)
        daw.connect(self)
        daws.append(daw)
    monkeypatch.setattr(REAPER, 'connect', connect)
    page.click('#palette button[data-type="Fader"]')
    page.select_option('#output-type', 'osc.REAPER')
    page.click('#add-output')
    page.click('#outputs .connect')
    page.wait_for_selector('#outputs .dot.on')
    page.click('#tree .node:has-text("fader1")')
    page.click('text=Add message')
    page.select_option('#mapping-0-type', 'PluginParameter')
    page.click('#mapping-0-track-scan')
    page.wait_for_selector('#mapping-0-track-pick')
    assert 'MASTER' in page.inner_text('#mapping-0-track-pick')
    page.select_option('#mapping-0-track-pick', 'Bass')
    page.click('#mapping-0-plugin-scan')
    page.wait_for_selector('#mapping-0-plugin-pick')
    page.select_option('#mapping-0-plugin-pick', 'ReaComp')
    page.click('#mapping-0-parameter-scan')
    page.wait_for_selector('#mapping-0-parameter-pick')
    page.select_option('#mapping-0-parameter-pick', 'P2')
    # REAPER takes the parameter's position: the fader's value
    mapping = saved_layout(page)['mappings'][0]
    assert mapping['message'] == {'type': 'PluginParameter', 'track': 'Bass', 'plugin': 'ReaComp', 'parameter': 'P2', 'value': {'source': 'value'}}
    import time
    close_rules(page)
    page.click('#mode-try')
    rect = page.designer.preview.ui['fader1'].rect
    pad(page, rect.x, rect.y + rect.h - 1).click()
    end = time.monotonic() + 3
    fader = page.designer.preview.ui['fader1']
    while daws[0].values.get(('Bass', 2, 2)) != fader.value and time.monotonic() < end:
        time.sleep(0.02)
    assert daws[0].values.get(('Bass', 2, 2)) == pytest.approx(fader.value) and fader.value > 0.5


def test_layers_shift_selects_a_range(page):
    for _ in range(4):
        page.click('#palette button[data-type="Button"]')
    # Layers lists the topmost first: button4, button3, button2, button1
    node(page, 'button4').click()
    node(page, 'button2').click(modifiers = ['Shift'])
    assert page.inner_text('#properties h3') == '3 widgets'
    assert page.locator('#tree .node.selected').count() == 3
    # Ctrl/Cmd + click takes one out, Shift + click goes from the last one clicked
    node(page, 'button3').click(modifiers = ['ControlOrMeta'])
    assert page.locator('#tree .node.selected').count() == 2
    node(page, 'button1').click(modifiers = ['Shift'])
    assert page.locator('#tree .node.selected').count() == 3
    assert page.locator('#tree .node.selected:has-text("button4")').count() == 0


def test_wheel_zooms_the_grid(page):
    page.keyboard.press('Escape')        # the start window
    page.wait_for_selector('#start', state = 'detached')
    pad_size = lambda: page.evaluate("document.querySelector('.pad').getBoundingClientRect().width")
    fitted = pad_size()
    corner = pad(page, 0, 0).bounding_box()
    page.mouse.move(corner['x'] + 5, corner['y'] + 5)
    page.mouse.wheel(0, -400)
    page.wait_for_function(f"document.querySelector('.pad').getBoundingClientRect().width > {fitted * 1.5}")
    page.wait_for_timeout(400)
    # Around the pointer: the pad under it stays under it
    moved = pad(page, 0, 0).bounding_box()
    assert moved['x'] <= corner['x'] + 5 <= moved['x'] + moved['width']
    # The wheel can move the grid instead
    page.click('#wheel-mode')
    assert page.inner_text('#wheel-mode') == 'Wheel scrolls'
    size = pad_size()
    page.mouse.move(corner['x'] + 5, corner['y'] + 5)
    page.mouse.wheel(0, 100)
    page.wait_for_timeout(300)
    assert pad_size() == size and pad(page, 0, 0).bounding_box()['y'] == pytest.approx(moved['y'] - 100, abs = 1)
    # The middle button drags it
    page.mouse.down(button = 'middle')
    page.mouse.move(corner['x'] + 45, corner['y'] + 5, steps = 4)
    page.mouse.up(button = 'middle')
    assert pad(page, 0, 0).bounding_box()['x'] == pytest.approx(moved['x'] + 40, abs = 1)
    # So does dragging the space around it
    stage = page.locator('#stage').bounding_box()
    before = pad(page, 0, 0).bounding_box()
    page.mouse.move(stage['x'] + 5, stage['y'] + 5)
    page.mouse.down()
    page.mouse.move(stage['x'] + 35, stage['y'] + 25, steps = 4)
    page.mouse.up()
    after = pad(page, 0, 0).bounding_box()
    assert after['x'] == pytest.approx(before['x'] + 30, abs = 1) and after['y'] == pytest.approx(before['y'] + 20, abs = 1)
    # A trackpad's two-finger scroll moves it even while the wheel zooms; a pinch (ctrlKey) zooms
    page.click('#wheel-mode')
    assert page.inner_text('#wheel-mode') == 'Wheel zooms'
    page.wait_for_timeout(400)
    page.evaluate("""document.getElementById('stage').dispatchEvent(new WheelEvent('wheel',
        {deltaX: 10, deltaY: 15.5, clientX: 300, clientY: 300, bubbles: true, cancelable: true}))""")
    moved = pad(page, 0, 0).bounding_box()
    assert pad_size() == size and moved['x'] == pytest.approx(after['x'] - 10, abs = 1) and moved['y'] == pytest.approx(after['y'] - 15.5, abs = 1)
    page.wait_for_timeout(400)
    page.evaluate("""document.getElementById('stage').dispatchEvent(new WheelEvent('wheel',
        {deltaY: -20, ctrlKey: true, clientX: 300, clientY: 300, bubbles: true, cancelable: true}))""")
    page.wait_for_function(f"document.querySelector('.pad').getBoundingClientRect().width > {size * 1.1}")


def test_rules_window_pastes_and_edits_several(page):
    page.select_option('#output-type', 'midi_port.MidiPort')
    page.click('#add-output')
    for _ in range(3):
        page.click('#palette button[data-type="Fader"]')
    node(page, 'fader1').click()
    page.click('text=Add message')
    assert page.is_visible('#rules') and page.input_value('#mapping-0-type') == 'ControlChange'
    # Copy it, select the two others and paste: one each
    page.click('#rules-list .rule-row')
    page.keyboard.press('ControlOrMeta+c')
    node(page, 'fader2').click()
    node(page, 'fader3').click(modifiers = ['Shift'])
    page.click('#rules-paste')
    mappings = saved_layout(page)['mappings']
    assert [mapping['widget'] for mapping in mappings] == ['fader1', 'fader2', 'fader3']
    assert page.locator('#rules-list .rule-row').count() == 2 and page.locator('#rules-list .rule-widget').count() == 2
    # fader3 gets its own control number
    page.click('#rules-list .rule-row >> nth=1')
    page.fill('#mapping-2-control >> xpath=following-sibling::input', '8')
    page.press('#mapping-2-control >> xpath=following-sibling::input', 'Enter')
    # Both picked: the control differs, a new channel goes to both
    page.click('#rules-all-rows')
    assert page.locator('#rules-editor .mixed').count() == 1
    page.fill('#mapping-1-channel >> xpath=following-sibling::input', '2')
    page.press('#mapping-1-channel >> xpath=following-sibling::input', 'Enter')
    mappings = saved_layout(page)['mappings']
    assert [(m['message']['control'], m['message']['channel']) for m in mappings] == [(1, 1), (1, 2), (8, 2)]
    # So does another event value
    page.select_option('#mapping-1-value', 'value_x' if False else 'value')
    page.select_option('#mapping-1-on', 'Released')
    assert [m.get('on') for m in saved_layout(page)['mappings']] == ['Changed', 'Released', 'Released']
    parser.load(saved_layout(page), devices = False)
    # Delete with the window's focus deletes the picked ones, not the widgets
    page.click('#rules-list .rule-row >> nth=0')
    page.click('#rules-all-rows')
    page.keyboard.press('Delete')
    layout = saved_layout(page)
    assert [m['widget'] for m in layout['mappings']] == ['fader1'] and len(layout['widgets']) == 3
    # All widgets
    page.click('#rules-all')
    assert page.locator('#rules-list .rule-row').count() == 1
    page.keyboard.press('Escape')
    assert page.is_hidden('#rules')


def test_note_widgets_get_their_note_offs(page):
    page.click('#palette button[data-type="PianoRoll"]')
    page.select_option('#output-type', 'midi_port.MidiPort')
    page.click('#add-output')
    page.click('#tree .node:has-text("pianoRoll1")')
    page.click('text=Add message')
    close_rules(page)
    page.click('#palette button[data-type="Sequencer"]')
    page.click('#tree .node:has-text("sequencer1")')
    page.click('text=Add message')
    close_rules(page)
    mappings = saved_layout(page)['mappings']
    assert [(m['widget'], m['on'], m['message']['type'], m['message']['note'], m['message']['velocity']) for m in mappings] == [
        ('pianoRoll1', 'NoteOn', 'NoteOn', {'source': 'note'}, {'source': 'velocity'}),
        ('pianoRoll1', 'NoteOff', 'NoteOff', {'source': 'note'}, 0),
        ('sequencer1', 'StepPlayed', 'NoteOn', {'source': 'note'}, {'source': 'velocity'}),
        ('sequencer1', 'StepEnded', 'NoteOff', {'source': 'note'}, 0)]
    parser.load(saved_layout(page), devices = False)


def test_snippets(page):
    assert page.is_hidden('#snippets')
    page.click('#tab-snippets')
    assert page.is_hidden('#palette')
    page.click('#snippets button[data-snippet="drum-pads-4x4"]')
    layout = saved_layout(page)
    assert [(w['name'], w['x'], w['y']) for w in layout['widgets']] == [('pads', 0, 0)]
    assert [output['type'] for output in layout['outputs']] == ['midi_port.MidiPort']
    assert [(m['widget'], m['on'], m['output']) for m in layout['mappings']] == [('pads', 'NoteOn', 'midi'), ('pads', 'NoteOff', 'midi')]
    # Dragged: its top-left at the pointer; a taken name changes, the MIDI output is shared
    page.drag_and_drop('#snippets button[data-snippet="drum-pads-4x4"]', '.pad[data-x="5"][data-y="8"]', force = True)
    layout = saved_layout(page)
    assert [(w['name'], w['x'], w['y']) for w in layout['widgets']] == [('pads', 0, 0), ('drumPads1', 5, 5)]
    assert len(layout['outputs']) == 1 and [m['widget'] for m in layout['mappings']] == ['pads', 'pads', 'drumPads1', 'drumPads1']
    # Sizes filter the list
    page.select_option('#snippet-size', '4x4')
    sizes = page.locator('#snippets .size').all_inner_texts()
    assert sizes and set(sizes) == {'4x4'}
    # The selection kept as a snippet of your own
    page.click('#tree .node:has-text("drumPads1")')
    page.click('#save-snippet')
    page.fill('#ask-title', 'Kit')
    page.fill('#ask-doc', 'Pads on channel 10')
    page.click('#ask-ok')
    page.wait_for_selector('#snippets button[data-snippet="user/kit"]')
    saved = json.loads((page.layout_path.parent / 'snippets' / 'kit.json').read_text())
    assert saved['size'] == [4, 4] and saved['widgets'][0]['x'] == 0 and saved['outputs'][0]['name'] == 'midi'
    assert 'My snippets' in page.inner_text('#snippets')
    page.hover('#snippets button[data-snippet="user/kit"]')
    page.click('#snippets button[data-snippet="user/kit"] .delete')
    page.click('#ask-ok')
    page.wait_for_selector('#snippets button[data-snippet="user/kit"]', state = 'detached')
    assert not (page.layout_path.parent / 'snippets' / 'kit.json').exists()


def test_link_value_from_a_list(page):
    drag_from_palette(page, 'Sequencer', 0, 4)
    drag_from_palette(page, 'ButtonGroup', 0, 0)
    page.click('#tree .node:has-text("buttonGroup1")')
    page.click('text=Add link')
    page.select_option('#link-0-target', 'sequencer1')
    page.select_option('#link-0-option', 'option:direction')
    page.select_option('#link-0-change', 'Set')
    page.select_option('#link-0-value', 'list…')
    assert page.input_value('#link-0-by') == 'x'
    page.click('#link-0-choose-add')
    page.select_option('#link-0-choose-0', 'PingPong')
    page.select_option('#link-0-choose-2', 'Random')
    close_rules(page)
    link, = saved_layout(page)['links']
    assert link['value'] == {'choose': ['PingPong', 'Backward', 'Random'], 'by': 'x'}
    page.click('#mode-try')
    pad(page, 2, 0).click()
    page.wait_for_function("document.querySelector('#events').textContent.includes('Toggled')")
    assert page.designer.preview.ui['sequencer1'].direction.name == 'Random'


def test_formulas_in_options_and_links(page):
    drag_from_palette(page, 'PianoRoll', 0, 4)
    drag_from_palette(page, 'Stepper', 0, 0)
    page.click('#tree .node:has-text("stepper1")')
    # ƒ turns the field into a formula of other widgets' options
    page.click('#option-maximum-formula')
    page.fill('#option-maximum', 'pianoRoll1.steps - pianoRoll1.width')
    page.press('#option-maximum', 'Enter')
    page.wait_for_function("document.querySelector('#option-maximum').value === '{pianoRoll1.steps - pianoRoll1.width}'")
    page.click('text=Add link')
    page.select_option('#link-0-target', 'pianoRoll1')
    page.select_option('#link-0-option', 'option:column')
    page.select_option('#link-0-change', 'Set')
    page.select_option('#link-0-value', 'formula…')
    page.fill('#link-0-formula', '{stepper1.number}')
    page.press('#link-0-formula', 'Enter')
    shot(page, 'formulas')
    close_rules(page)
    layout = saved_layout(page)
    stepper = next(widget for widget in layout['widgets'] if widget['name'] == 'stepper1')
    assert stepper['options']['maximum'] == '{pianoRoll1.steps - pianoRoll1.width}'
    assert layout['links'][0]['value'] == '{stepper1.number}' and layout['links'][0].get('change', 'Set') == 'Set'
    ui = page.designer.preview.ui
    assert ui['stepper1'].maximum == ui['pianoRoll1'].steps - ui['pianoRoll1'].width
    # The last pad goes up a step: the roll shows a column further
    page.click('#mode-try')
    for _ in range(2):
        pad(page, ui['stepper1'].width - 1, 0).click()
    page.wait_for_function("document.querySelector('#events').textContent.includes('column=2')")
    assert page.designer.preview.ui['pianoRoll1'].column == 2
    # Back to a constant
    page.click('#mode-edit')
    page.click('#tree .node:has-text("stepper1")')
    page.click('#option-maximum-formula')
    page.wait_for_function("document.querySelector('#option-maximum').type === 'number'")


def test_presets_are_kept_in_the_layout(page):
    layout = {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 4, 'height': 4},
              'widgets': [{'type': 'Presets', 'name': 'snapshots', 'x': 0, 'y': 0, 'width': 4, 'height': 4, 'options': {},
                           'widgets': [{'type': 'Fader', 'name': 'level', 'x': 0, 'y': 0, 'width': 1, 'height': 3,
                                        'options': {'mode': 'Magnitude'}}]}]}
    page.evaluate("layout => fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)})", layout)
    page.reload()
    page.wait_for_selector('#palette button')
    page.click('#mode-try')
    pad(page, 0, 2).click()          # the fader to 1.0
    pad(page, 1, 3).click()          # an empty slot stores
    page.wait_for_selector('#events li:has-text("PresetStored")')
    page.click('#save')
    page.wait_for_selector('#status.ok')
    saved = json.loads(page.layout_path.read_text())
    assert saved['widgets'][0]['options']['presets'] == {'1': {'level': {'value': 1.0}}}
    page.click('#mode-edit')
    page.click('#tree .node:has-text("snapshots")')
    assert '1 stored preset kept' in page.inner_text('#presets-stored')
    # Options are described on hover (from the docstrings)
    assert page.get_attribute('label[for="option-save"]', 'title').startswith('save: Keep stored presets in the layout file')
    page.click('#presets-clear')
    page.evaluate("document.getElementById('status').className = ''")
    page.click('#save')
    page.wait_for_selector('#status.ok')
    assert 'presets' not in json.loads(page.layout_path.read_text())['widgets'][0]['options']
    # Save off (under More options): stored presets stay out of the layout
    page.click('#properties details.more summary')
    page.click('#option-save')
    page.click('#mode-try')
    pad(page, 2, 3).click()
    page.wait_for_function("[...document.querySelectorAll('#events li')].filter(li => li.textContent.includes('PresetStored')).length >= 2")
    page.evaluate("document.getElementById('status').className = ''")
    page.click('#save')
    page.wait_for_selector('#status.ok')
    options = json.loads(page.layout_path.read_text())['widgets'][0]['options']
    assert options == {'save': False}


@pytest.fixture
def fake_hardware(monkeypatch):
    """A Launch Control XL and MIDI port outputs that connect without ports; returns what was opened."""
    from pyxelwidgets.designer import Preview
    from pyxelwidgets.devices import Device
    from pyxelwidgets.devices.midi_port import MidiPort
    from pyxelwidgets.devices.novation import LaunchControlXL

    class Offline:
        def connect(self, *ports):
            Device.connect(self)

        def connect_virtual(self, port):
            Device.connect(self)

        def disconnect(self):
            Device.disconnect(self)

        def send_message(self, message):
            pass

        def send_sysex(self, message):
            pass

        def check(self, ports = None):
            return False

    class FakeXL(Offline, LaunchControlXL):
        pass

    class FakePort(Offline, MidiPort):
        def send(self, message):
            pass

    opened = {'devices': [], 'outputs': []}
    def open_device(spec, index):
        device = FakeXL()
        device.connect()
        opened['devices'].append(device)
        return device, None
    def open_output(spec, index):
        output = FakePort(name = spec['name'])
        output.connect()
        opened['outputs'].append(output)
        return output, None
    monkeypatch.setattr(Preview, '_open', staticmethod(open_device))
    monkeypatch.setattr(Preview, '_open_output', staticmethod(open_output))
    return opened


def test_learn_controls_and_messages(page, fake_hardware):
    from pyxelwidgets.events import ControlChanged, ControlPressed, MessageReceived
    from pyxelwidgets.message import ControlChange
    layout = {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 8, 'height': 8},
              'devices': [{'type': 'novation.LaunchControlXL', 'x': 0, 'y': 0, 'options': {}}],
              'outputs': [{'name': 'daw', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets learn', 'options': {}}],
              'widgets': [{'type': 'Fader', 'name': 'level', 'x': 7, 'y': 0, 'width': 1, 'height': 8, 'options': {}}],
              'mappings': [{'widget': 'level', 'on': 'Changed', 'output': 'daw',
                            'message': {'type': 'ControlChange', 'control': 1, 'value': {'source': 'value'}, 'channel': 1}}]}
    page.evaluate("layout => fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)})", layout)
    page.reload()
    page.wait_for_selector('#devices .connect')
    page.click('#devices .connect')
    page.click('#outputs .connect')
    page.wait_for_selector('#devices .dot.on')
    page.wait_for_selector('#outputs .dot.on')
    xl = fake_hardware['devices'][-1]
    # A control moved while learning binds the widget to it
    page.click('#tree .node:has-text("level")')
    page.click('#widget-control-learn')
    assert 'Move a knob' in page.inner_text('#status') and page.inner_text('#widget-control-learn') == 'Cancel'
    shot(page, '14-learn')
    xl.emit(ControlChanged(xl, 'Fader_3', 0.5))
    page.wait_for_function("document.querySelector('#widget-control').value === '0:Fader_3'")
    assert saved_layout(page)['bindings'] == [{'device': 0, 'control': 'Fader_3', 'widget': 'level'}]
    assert 'ControlChanged' in page.inner_text('#events') and '_device' not in page.inner_text('#events')
    # Escape stops waiting; a transport action learns a button
    page.click('#widget-control-learn')
    page.keyboard.press('Escape')
    assert page.inner_text('#widget-control-learn') == 'Learn'
    page.keyboard.press('Escape')        # nothing selected: the surface's transport controls
    page.click('#action-transport-toggle-learn')
    xl.emit(ControlPressed(xl, 'Solo', 1.0))
    page.wait_for_function("document.querySelector('#action-transport-toggle').value === '0:Solo'")
    # A message from the DAW fills in the message, keeping the fader's value
    page.click('#tree .node:has-text("level")')
    page.click('.rule-summary li >> nth=0')
    page.wait_for_selector('#mapping-0-message-learn')
    page.click('#mapping-0-message-learn')
    port = fake_hardware['outputs'][-1]
    port.emit(MessageReceived(port, ControlChange(control = 7, value = 100, channel = 3)))
    page.wait_for_function("document.querySelector('#status').textContent.includes('Learned')")
    assert saved_layout(page)['mappings'][0]['message'] == {'type': 'ControlChange', 'control': 7, 'value': {'source': 'value'}, 'channel': 3}


def test_messages_and_links_from_device_controls(page, fake_hardware):
    from pyxelwidgets.events import ControlChanged, ControlPressed
    layout = {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 8, 'height': 8},
              'devices': [{'type': 'novation.LaunchControlXL', 'x': 0, 'y': 0, 'options': {}}],
              'outputs': [{'name': 'daw', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets controls', 'options': {}}],
              'widgets': [{'type': 'Fader', 'name': 'level', 'x': 7, 'y': 0, 'width': 1, 'height': 8, 'options': {}}]}
    page.evaluate("layout => fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)})", layout)
    page.reload()
    page.wait_for_selector('#devices .connect')
    page.click('#devices .connect')
    page.wait_for_selector('#devices .dot.on')
    xl = fake_hardware['devices'][-1]
    # The device's panel picks the control new rules start from: learned here
    page.click('#devices li .name >> nth=0')
    page.click('#device-control-learn')
    xl.emit(ControlChanged(xl, 'Fader_3', 0.5))
    page.wait_for_function("document.querySelector('#device-control').value === '0:Fader_3'")
    page.click('#properties button:has-text("Add message")')
    page.wait_for_selector('#mapping-0-control')
    assert page.input_value('#mapping-0-on') == 'ControlChanged' and page.locator('#mapping-0-feedback').count() == 0
    assert page.locator('#mapping-0-on option[value=""]').count() == 0
    assert saved_layout(page)['mappings'] == [{'device': 0, 'control': 'Fader_3', 'on': 'ControlChanged', 'output': 'daw',
                                               'message': {'type': 'ControlChange', 'control': 1, 'value': {'source': 'value'}, 'channel': 1}}]
    # A link from a button: picking it in the card makes it a press toggling the option
    page.click('#properties button:has-text("Add link")')
    page.wait_for_selector('#link-0-control')
    page.select_option('#link-0-control', '0:Solo')
    page.wait_for_function("document.querySelector('#link-0-on').value === 'ControlPressed'")
    shot(page, '15-control-rules')
    assert saved_layout(page)['links'] == [{'device': 0, 'control': 'Solo', 'on': 'ControlPressed', 'target': 'level', 'option': 'visible', 'change': 'Toggle'}]
    xl.emit(ControlPressed(xl, 'Solo', 1.0))
    assert not page.designer.preview.ui['level'].visible
    xl.emit(ControlChanged(xl, 'Fader_3', 1.0))
    page.wait_for_function("document.querySelector('#events').textContent.includes('→ ControlChange')")
    # Listed where they come from, and in Connections
    close_rules(page)
    assert page.locator('#properties .rule-summary li').count() == 2
    page.click('.tabs button[data-tab="connections"]')
    assert 'Solo · 1. Launch Control XL' in page.inner_text('#connections')
    # Deleting the widget keeps the message; removing the device takes both
    page.click('#tree .node:has-text("level")')
    page.keyboard.press('Delete')
    saved = saved_layout(page)
    assert len(saved['mappings']) == 1 and 'links' not in saved
    page.click('#devices li .name >> nth=0')
    page.click('text=Remove device')
    saved = saved_layout(page)
    assert 'mappings' not in saved and saved['devices'] == []


def test_rules_window_lists_widgets_and_devices(page, fake_hardware):
    layout = {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 8, 'height': 8},
              'devices': [{'type': 'novation.LaunchControlXL', 'x': 0, 'y': 0, 'options': {}}],
              'outputs': [{'name': 'daw', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets owners', 'options': {}}],
              'widgets': [{'type': 'Fader', 'name': 'level', 'x': 7, 'y': 0, 'width': 1, 'height': 8, 'options': {}},
                          {'type': 'Group', 'name': 'box', 'x': 0, 'y': 0, 'width': 4, 'height': 4, 'options': {}, 'widgets': [
                              {'type': 'Button', 'name': 'go', 'x': 0, 'y': 0, 'width': 1, 'height': 1, 'options': {}}]}],
              'links': [{'widget': 'go', 'on': 'Pressed', 'target': 'level', 'option': 'visible', 'change': 'Toggle'},
                        {'device': 0, 'control': 'Solo', 'on': 'ControlPressed', 'action': 'transport.toggle'}]}
    page.evaluate("layout => fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)})", layout)
    page.reload()
    page.wait_for_selector('#palette button')
    # The toolbar button opens and closes it
    page.click('#rules-open')
    assert page.is_visible('#rules') and 'active' in page.get_attribute('#rules-open', 'class')
    owners = page.locator('#rules-owners')
    assert owners.locator('.owner').all_inner_texts() == ['level\nFader', 'box\nGroup', 'go\nButton\n1', '1. Launch Control XL\n1']
    # A widget there shows its messages and links (and selects it)
    owners.locator('[data-owner="widget:go"]').click()
    assert page.locator('#rules-list .rule-row').count() == 1 and page.inner_text('#rules-title') == 'go'
    owners.locator('[data-owner="widget:level"]').click(modifiers = ['Shift'])
    assert page.inner_text('#rules-title') == '2 widgets'
    # A device: its controls' rules, and the control new ones start from
    owners.locator('[data-owner="device:0"]').click()
    assert page.locator('#rules-list .rule-row').count() == 1
    assert owners.locator('[data-owner="control:0:Solo"]').count() == 1
    page.select_option('#rules-control', '0:Knob_2')
    page.click('#rules-add-message')
    page.wait_for_selector('#mapping-0-control')
    assert page.input_value('#mapping-0-control') == '0:Knob_2'
    shot(page, '16-rules-owners')
    page.click('#rules-open')
    assert page.is_hidden('#rules')


def test_pad_info_in_try_mode(page):
    layout = {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 8, 'height': 8},
              'outputs': [{'name': 'synth', 'type': 'midi_port.MidiPort', 'virtual': 'PyxelWidgets pads', 'options': {}}],
              'widgets': [{'type': 'Text', 'name': 'label', 'x': 0, 'y': 4, 'width': 8, 'height': 4, 'options': {}},
                          {'type': 'DrumPads', 'name': 'drums', 'x': 0, 'y': 0, 'width': 4, 'height': 4, 'options': {}}],
              'mappings': [{'widget': 'drums', 'on': 'Pressed', 'output': 'synth',
                            'message': {'type': 'NoteOn', 'note': {'source': 'cell', 'offset': 36}, 'velocity': {'source': 'velocity'}, 'channel': 10}}],
              'links': [{'widget': 'drums', 'on': 'Pressed', 'target': 'label', 'option': 'text', 'value': 'pad {x+1}'}]}
    page.evaluate("layout => fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)})", layout)
    page.reload()
    page.wait_for_selector('#palette button')
    def hover(x, y):
        box = pad(page, x, y).bounding_box()
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, steps = 2)
    hover(1, 1)
    assert page.locator('#pad-info:visible').count() == 0      # Edit mode: no info
    page.click('#mode-try')
    hover(1, 1)
    page.wait_for_selector('#pad-info:visible')
    info = page.inner_text('#pad-info')
    assert 'drums DrumPads · pad 1, 1 · cell 5' in info
    assert 'Pressed → synth: NoteOn note 41 · velocity {velocity} · channel 10' in info
    assert 'Pressed → label: set text = pad 2' in info
    shot(page, '13-pad-info')
    hover(6, 6)
    page.wait_for_function("document.querySelector('#pad-info').textContent.includes('label Text')")
    hover(6, 1)
    page.wait_for_function("document.querySelector('#pad-info').textContent.includes('Nothing here')")


def test_device_check(page, fake_hardware):
    from pyxelwidgets.events import ControlChanged
    layout = {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 8, 'height': 5},
              'devices': [{'type': 'novation.LaunchControlXL', 'x': 0, 'y': 0, 'options': {}}], 'widgets': []}
    page.evaluate("layout => fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)})", layout)
    page.reload()
    page.wait_for_selector('#devices .connect')
    page.click('#devices li .name >> nth=0')
    assert page.is_disabled('#device-check')
    page.click('#devices .connect')
    page.wait_for_selector('#devices .dot.on')
    xl = fake_hardware['devices'][-1]
    page.click('#device-check')
    page.wait_for_selector('#check')
    page.click('#check-next')
    # Corners: the device shows the test pattern instead of the widgets
    page.wait_for_selector('#check-corners')
    page.wait_for_timeout(200)
    assert tuple(int(v) for v in xl.buffer[0, 0][:3]) == (255, 0, 0) and tuple(int(v) for v in xl.buffer[7, 4][:3]) == (0, 0, 255)
    page.click('#check-corners button[data-answer="yes"]')
    # Pads: presses are listed and checked against the corners
    page.wait_for_selector('#check-pads')
    xl.set_button(0, 0, 1.0)
    xl.set_button(0, 0, 0.0)
    xl.set_button(6, 4, 1.0)
    page.wait_for_function("document.querySelectorAll('#check-pads li.wrong').length === 1")
    assert page.locator('#check-pads li.ok').count() == 1
    shot(page, '17-check-pads')
    page.click('#check-next')
    page.click('#check-colors button[data-answer="close"]')
    page.fill('#check-note-colors', 'orange looks yellow')
    page.click('#check-next')
    # Controls tick as they arrive
    xl.emit(ControlChanged(xl, 'Fader_0', 0.5))
    xl.process_midi(([0xB8, 77, 64], 0), None)
    page.wait_for_function("document.querySelectorAll('#check-controls li.ok').length >= 1")
    page.click('#check-next')
    page.wait_for_selector('#check-download')
    shot(page, '18-check-report')
    report = page.evaluate("""async () => {
        const module = await import('/check.js');
        return module.buildReport().data;
    }""")
    assert report['format'] == 'pyxelwidgets.device-check' and report['device']['type'] == 'novation.LaunchControlXL'
    assert report['corners'] == {'answer': 'yes'} and report['colors']['note'] == 'orange looks yellow'
    assert report['pads']['pressed'] == [[0, 0], [6, 4]] and not report['pads']['ok']
    assert 'Fader_0' in report['controls']['understood'] and report['midi'][-1][1] == [0xB8, 77, 64]
    page.click('#check-done')
    page.wait_for_selector('#check', state = 'detached')
    assert page.designer.preview.check is None


def test_link_to_device_lights_and_screens(page):
    layout = {'format': 'pyxelwidgets.layout', 'version': 3, 'surface': {'width': 8, 'height': 8},
              'devices': [{'type': 'arturia.MiniLab3', 'x': 0, 'y': 0}, {'type': 'akai.APCMini', 'x': 0, 'y': 0}],
              'widgets': [{'type': 'Fader', 'name': 'cutoff', 'x': 0, 'y': 0, 'width': 1, 'height': 8}]}
    page.evaluate("async (layout) => { await fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)}); }", layout)
    page.reload()
    node(page, 'cutoff').click()
    page.click('text=Add link')
    # The devices' screens and lights are targets: a light takes a color, a screen a text
    page.select_option('#link-0-target', label = 'Button_1 light')
    assert page.input_value('#link-0-option') == 'option:light'
    page.select_option('#link-0-target', label = 'Screen (text)')
    assert page.input_value('#link-0-option') == 'option:text'
    shot(page, 'device-targets')
    # Starts as the widget's name and value
    assert saved_layout(page)['links'][0]['value'] == 'cutoff\n{round(value * 100)}%'
    page.fill('#link-0-constant', 'Cutoff\n{value}')
    page.locator('#link-0-constant').blur()
    links = saved_layout(page)['links']
    assert links == [{'widget': 'cutoff', 'on': 'Changed', 'target': {'device': 0, 'control': 'Screen'}, 'option': 'text', 'value': 'Cutoff\n{value}'}]
    parser.load(saved_layout(page), devices = False)
    page.click('.tabs button[data-tab="connections"]')
    assert 'Screen · 1. MiniLab 3' in page.inner_text('#connections')
    # Removing the device removes the links to its screen
    page.click('#devices li:has-text("MiniLab 3") .label')
    page.click('#properties button.danger:has-text("Remove device")')
    assert 'links' not in saved_layout(page)


def put_layout(page, layout):
    page.evaluate("async (layout) => { await fetch('/api/layout', {method: 'PUT', body: JSON.stringify(layout)}); }", layout)
    page.reload()


def test_links_that_skip_and_send_changed(page):
    put_layout(page, {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 8, 'height': 3},
                      'widgets': [{'type': 'ButtonGroup', 'name': 'pads', 'x': 0, 'y': 0, 'width': 4, 'height': 1, 'options': {'mode': 'Button'}},
                                  {'type': 'Stepper', 'name': 'mode', 'x': 0, 'y': 1, 'width': 8, 'height': 1},
                                  {'type': 'Fader', 'name': 'level', 'x': 0, 'y': 2, 'width': 8, 'height': 1, 'options': {'direction': 'Horizontal'}}]})
    node(page, 'pads').click()
    page.click('text=Add link')
    page.select_option('#link-0-target', 'mode')
    page.select_option('#link-0-option', 'option:value')
    # Setting a value: the widget can send Changed, so its own links follow
    page.check('#link-0-emit')
    assert saved_layout(page)['links'][0]['emit'] is True
    page.select_option('#link-0-value', label = 'condition…')
    page.select_option('#link-0-if', 'x')
    page.check('#link-0-else-skip')
    link = saved_layout(page)['links'][0]
    assert link['value']['else'] == {'skip': True} and page.is_hidden('#link-0-else')
    parser.load(saved_layout(page), devices = False)
    page.click('.tabs button[data-tab="connections"]')
    assert ': skip' in page.inner_text('#connections')
    page.uncheck('#link-0-else-skip')
    assert saved_layout(page)['links'][0]['value']['else'] == 0.0
    # Another option: emit goes
    page.select_option('#link-0-option', 'option:visible')
    assert 'emit' not in saved_layout(page)['links'][0] and page.locator('#link-0-emit').count() == 0


def test_channel_lists_and_screen_texts_too_long(page):
    put_layout(page, {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 8, 'height': 2},
                      'devices': [{'type': 'arturia.MiniLab3', 'x': 0, 'y': 0}],
                      'outputs': [{'name': 'synths', 'type': 'midi_port.MidiPort', 'virtual': 'Synths'}],
                      'widgets': [{'type': 'Fader', 'name': 'space', 'x': 0, 'y': 0, 'width': 1, 'height': 2}],
                      'mappings': [{'widget': 'space', 'on': 'Changed', 'output': 'synths', 'message': {'type': 'ControlChange', 'control': 91}}],
                      'links': [{'widget': 'space', 'on': 'Changed', 'target': {'device': 0, 'control': 'Screen'}, 'option': 'text',
                                 'value': 'Space reverb\n{round(value * 100)}%'}]})
    page.click('.tabs button[data-tab="problems"]')
    assert '"Space reverb" is longer than line 1 of Screen · 1. MiniLab 3 (10 characters)' in page.inner_text('#problem-list')
    node(page, 'space').click()
    page.click('#properties .rule-summary li:has-text("synths")')
    page.fill('#mapping-0-channel-list', '1, 3-4, 10')
    page.press('#mapping-0-channel-list', 'Enter')
    assert saved_layout(page)['mappings'][0]['message']['channel'] == [1, 3, 4, 10]
    # Something that isn't channels is taken back
    page.fill('#mapping-0-channel-list', '0, 17')
    page.press('#mapping-0-channel-list', 'Enter')
    assert page.input_value('#mapping-0-channel-list') == '1, 3, 4, 10'
    page.fill('#mapping-0-channel-list', '2')
    page.press('#mapping-0-channel-list', 'Enter')
    assert saved_layout(page)['mappings'][0]['message']['channel'] == 2


def test_the_shared_key(page):
    put_layout(page, {'format': 'pyxelwidgets.layout', 'version': parser.VERSION, 'surface': {'width': 8, 'height': 5},
                      'widgets': [{'type': 'ButtonGroup', 'name': 'pads', 'x': 0, 'y': 0, 'width': 4, 'height': 1, 'options': {'mode': 'Button'}},
                                  {'type': 'ChordPads', 'name': 'chords', 'x': 0, 'y': 1, 'width': 8, 'height': 2},
                                  {'type': 'Keyboard', 'name': 'keys', 'x': 0, 'y': 3, 'width': 8, 'height': 2}]})
    page.click('#stage', position = {'x': 5, 'y': 5})
    page.select_option('#key-root', 'D')
    page.select_option('#key-scale', 'Dorian')
    assert page.inner_text('#key-follow') == 'Make 2 widgets follow it'
    page.click('#key-follow')
    layout = saved_layout(page)
    assert layout['key'] == {'root': 'D', 'scale': 'Dorian'}
    assert all(widget['options'].get('root') == '{key.root}' and widget['options'].get('scale') == '{key.scale}' for widget in layout['widgets'][1:])
    assert page.locator('#key-follow').count() == 0
    page.wait_for_function("() => true")
    assert page.designer.preview.ui['keys'].scale.name == 'Dorian'
    # A link changes it like an option
    node(page, 'pads').click()
    page.click('text=Add link')
    page.select_option('#link-0-target', 'key')
    assert page.input_value('#link-0-option') == 'option:scale'
    link = saved_layout(page)['links'][0]
    assert (link['target'], link['option'], link['change']) == ('key', 'scale', 'Toggle')
    close_rules(page)
    page.click('#mode-try')
    pad(page, 0, 0).click()
    page.wait_for_function("() => true")
    import time
    time.sleep(0.3)
    assert page.designer.preview.ui['chords'].scale.name != 'Dorian'
